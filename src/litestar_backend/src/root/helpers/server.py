import os
import signal
import subprocess
import sys
from typing import Any

import uvicorn

from root.config import RootConfig
from root.helpers.process import ensure_runtime_dirs, find_pid_on_port
from shared.adapters.metrics import bootstrap_multiproc
from shared.config import MetricsConfig


def _ensure_runtime_dirs_or_exit(config: RootConfig) -> None:
    try:
        ensure_runtime_dirs(config)
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)


def _exit_if_port_busy(config: RootConfig) -> None:
    existing = find_pid_on_port(config.app_port)
    if existing:
        print(f"Port {config.app_port} is already in use, PID: {existing}")
        sys.exit(1)


def start_nohup(config: RootConfig) -> None:
    _exit_if_port_busy(config)
    _ensure_runtime_dirs_or_exit(config)

    with config.console_log.open("a") as log_file:
        proc = subprocess.Popen(
            [sys.executable, "-m", "root.entrypoints.cli"],
            cwd=str(config.project_root),
            env={**os.environ, "PYTHONPATH": str(config.src_dir)},
            stderr=log_file,
            stdout=log_file,
            start_new_session=True,
        )

    config.pidfile.write_text(str(proc.pid))
    print(f"{config.app_name} started, PID: {proc.pid}")
    print(f"Log: {config.console_log}")
    print("Stop: start_litestar --stop")
    print()

    try:
        subprocess.run(["tail", "-f", str(config.console_log)], check=False)
    except KeyboardInterrupt:
        print(f"\nLog tail stopped. Server still running, PID: {proc.pid}.")


def _bootstrap_prometheus_multiproc() -> None:
    # MetricsConfig resolves multiproc_dir from PROMETHEUS_MULTIPROC_DIR when set
    # (e.g. the compose tmpfs mount), else volume_path/prometheus. bootstrap_multiproc
    # materializes that dir, wipes stale per-process shards, and reaffirms the env so
    # a non-compose run (local `start_litestar`) also exports it for prometheus_client.
    bootstrap_multiproc(MetricsConfig())


def start_foreground(config: RootConfig) -> None:
    _exit_if_port_busy(config)
    _ensure_runtime_dirs_or_exit(config)
    _bootstrap_prometheus_multiproc()

    # On SIGTERM uvicorn waits up to `timeout_graceful_shutdown` for inflight
    # requests, THEN runs Litestar's lifespan stop (drains workers, flushes
    # event bus). Together they must finish before the orchestrator's hard
    # timeout (K8s default `terminationGracePeriodSeconds=30s`).
    extra: dict[str, Any] = {}
    if config.should_reload:
        extra["reload_excludes"] = ["*.json", "*storage*", "storage/*"]
    else:
        extra["workers"] = config.app_workers

    uvicorn.run(
        "root.entrypoints.api:create_app",
        app_dir=str(config.src_dir),
        factory=True,
        host=config.app_host,
        port=config.app_port,
        reload=config.should_reload,
        timeout_graceful_shutdown=config.shutdown_timeout_s,
        **extra,
    )


def stop(config: RootConfig) -> None:
    if config.pidfile.exists():
        try:
            pid = int(config.pidfile.read_text().strip())
        except ValueError:
            print(f"Invalid PID file: {config.pidfile}")
            config.pidfile.unlink(missing_ok=True)
            sys.exit(1)

        should_remove_pidfile = False
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"Sent SIGTERM to {config.app_name}, PID: {pid}")
            should_remove_pidfile = True
        except ProcessLookupError:
            print(f"Process {pid} is not running")
            should_remove_pidfile = True
        except PermissionError:
            print(f"Permission denied sending SIGTERM to PID: {pid}")
            sys.exit(1)
        finally:
            if should_remove_pidfile:
                config.pidfile.unlink(missing_ok=True)
        return

    existing = find_pid_on_port(config.app_port)
    if existing:
        print(f"No PID file, but port {config.app_port} is held by PID: {existing}")
        print(f"Run: kill {existing}")
        return

    print(f"Nothing running on port {config.app_port}")

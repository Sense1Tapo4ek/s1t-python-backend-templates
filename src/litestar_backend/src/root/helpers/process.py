import re
import subprocess

from root.config import RootConfig


def parse_pid_from_ss_output(output: str, port: int) -> int | None:
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue

        local_address = parts[3]
        if not local_address.endswith(f":{port}"):
            continue

        if match := re.search(r"pid=(\d+)", line):
            return int(match.group(1))

    return None


def find_pid_on_port(port: int) -> int | None:
    try:
        result = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    return parse_pid_from_ss_output(result.stdout, port)


def ensure_runtime_dirs(config: RootConfig) -> None:
    # runtime_path is Optional in the type but always set by the model
    # validator post-init; assert turns the invariant into a clear error.
    assert config.runtime_path is not None
    try:
        config.log_dir.mkdir(parents=True, exist_ok=True)
        config.runtime_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Cannot create runtime directories: {exc}") from exc

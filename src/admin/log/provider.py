import asyncio

from dishka import Provider, Scope, provide
from litestar.channels import ChannelsPlugin

from shared.adapters.driven.db import SQLiteConnection

from .adapters.driven.workers import LogCleanupWorker, LogSinkWorker
from .adapters.lifespan import LogLifespanManager
from .app.interfaces import ILogBroadcaster, ILogPurger, ILogReader, ILogSink
from .app.use_cases import (
    ClearLogsUc,
    ExportLogsUc,
    LoadOlderLogsUc,
    RenderLogPageUc,
    StreamLogTailUc,
)
from .config import AdminLogConfig
from .ports.driven.dispatchers import ChannelsLogBroadcaster
from .ports.driven.gateways import AsyncioQueueLogSink
from .ports.driven.repos import SQLiteLogRepo
from .ports.driving.facades import LogsFacade


class AdminLogPortBindings(Provider):
    """Interface-to-implementation bindings for the admin_log context."""

    scope = Scope.APP

    @provide
    def sqlite_log_repo(
        self,
        connection: SQLiteConnection,
        config: AdminLogConfig,
    ) -> SQLiteLogRepo:
        return SQLiteLogRepo(
            _connection=connection,
            _stream_poll_interval_s=config.log_stream_poll_interval_s,
            _max_limit=config.log_max_limit,
        )

    @provide
    def log_reader(self, repo: SQLiteLogRepo) -> ILogReader:
        return repo

    @provide
    def log_purger(self, repo: SQLiteLogRepo) -> ILogPurger:
        return repo

    log_sink = provide(AsyncioQueueLogSink, provides=ILogSink)


class AdminLogProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> AdminLogConfig:
        return AdminLogConfig()

    @provide
    def log_queue(self) -> asyncio.Queue[str]:
        return asyncio.Queue(maxsize=10000)

    @provide
    def sqlite_connection(self, config: AdminLogConfig) -> SQLiteConnection:
        return SQLiteConnection(
            _db_path=config.log_db_path,
            _reader_count=config.log_db_reader_count,
        )

    @provide(provides=ILogBroadcaster)
    def log_broadcaster(self, channels: ChannelsPlugin) -> ChannelsLogBroadcaster:
        # Backlog/backpressure for SSE consumers is configured on the
        # ChannelsPlugin itself (subscriber_max_backlog) — see SharedProvider.
        return ChannelsLogBroadcaster(_channels=channels)

    @provide
    def render_log_page_uc(
        self,
        reader: ILogReader,
        config: AdminLogConfig,
    ) -> RenderLogPageUc:
        return RenderLogPageUc(_reader=reader, _tail_size=config.log_tail_size)

    @provide
    def load_older_logs_uc(
        self,
        reader: ILogReader,
        config: AdminLogConfig,
    ) -> LoadOlderLogsUc:
        return LoadOlderLogsUc(
            _reader=reader,
            _chunk_size=config.log_history_chunk,
        )

    stream_log_tail_uc = provide(StreamLogTailUc)
    export_logs_uc = provide(ExportLogsUc)
    clear_logs_uc = provide(ClearLogsUc)
    logs_facade = provide(LogsFacade)

    @provide
    def sink_worker(
        self,
        queue: asyncio.Queue[str],
        connection: SQLiteConnection,
        config: AdminLogConfig,
        broadcaster: ILogBroadcaster,
    ) -> LogSinkWorker:
        return LogSinkWorker(
            _queue=queue,
            _connection=connection,
            _batch_size=config.log_batch_size,
            _batch_timeout_ms=config.log_batch_timeout_ms,
            _broadcaster=broadcaster,
        )

    @provide
    def cleanup_worker(
        self,
        connection: SQLiteConnection,
        config: AdminLogConfig,
    ) -> LogCleanupWorker:
        return LogCleanupWorker(
            _connection=connection,
            _retention_days=config.log_retention_days,
            _interval_hours=config.log_cleanup_interval_hours,
        )

    @provide
    def lifespan_manager(
        self,
        connection: SQLiteConnection,
        sink_worker: LogSinkWorker,
        cleanup_worker: LogCleanupWorker,
        config: AdminLogConfig,
    ) -> LogLifespanManager:
        return LogLifespanManager(
            _connection=connection,
            _sink_worker=sink_worker,
            _cleanup_worker=cleanup_worker,
            _db_path=config.log_db_path,
            _migrations_path=config.log_migrations_path,
        )

"""DI providers for the admin/log context.

Two top-level providers:

- `AdminLogWebProvider` — used by the API entrypoint (`create_app`). Wires
  the read-side (repo, use cases, facade), the in-process producer
  pipeline (`RedisStreamPublisher`), and the SSE subscriber.
- `AdminLogSinkProvider` — used by `start_log_sink`. Wires the writer
  (LogSinkWorker), the retention worker, and the pub/sub publisher used
  to fan persisted batches out to web subscribers.

Both pick up the same `AdminLogConfig`/`BaseAppConfig` envs, so the
SQLite path and Valkey URL stay in sync without manual wiring.
"""

from dishka import Provider, Scope, provide
from litestar.channels import ChannelsPlugin
from redis.asyncio import Redis

from admin.metrics.adapters.driven.samplers import RedisStreamQueueDepthProvider
from admin.metrics.app.interfaces import IMetricsModulePlugin, IQueueDepthProvider
from shared.adapters.driven.db import SQLiteConnection
from shared.config import BaseAppConfig

from .adapters.driven.workers import LogCleanupWorker, LogSinkWorker
from .adapters.lifespan import LogLifespanManager, LogSinkLifespan
from .app.interfaces import ILogPublisher, ILogPurger, ILogReader, ILogSubscriber
from .app.use_cases import (
    ClearLogsUc,
    ExportLogsUc,
    LoadOlderLogsUc,
    RenderLogPageUc,
    StreamLogTailUc,
)
from .config import AdminLogConfig
from .ports.driven.dispatchers import ChannelsLogSubscriber, RedisPubSubLogPublisher
from .ports.driven.gateways import RedisStreamPublisher
from .ports.driven.plugins import LogsMetricsPlugin
from .ports.driven.repos import SQLiteLogRepo
from .ports.driving.facades import LogsFacade


def _build_redis_client(base: BaseAppConfig) -> Redis:
    # `decode_responses=False` keeps payloads as bytes, which matches what
    # Litestar's RedisChannelsBackend and our XREADGROUP path both expect.
    return Redis.from_url(base.valkey_url, decode_responses=False)


# ─── Web-side ────────────────────────────────────────────────────────────────


class AdminLogPortBindings(Provider):
    """Interface-to-implementation bindings shared across web entrypoint."""

    scope = Scope.APP

    @provide
    def sqlite_log_repo(self, connection: SQLiteConnection) -> SQLiteLogRepo:
        return SQLiteLogRepo(_connection=connection)

    @provide
    def log_reader(self, repo: SQLiteLogRepo) -> ILogReader:
        return repo

    @provide
    def log_purger(self, repo: SQLiteLogRepo) -> ILogPurger:
        return repo


class AdminLogWebProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> AdminLogConfig:
        return AdminLogConfig()

    @provide
    def redis_client(self, base: BaseAppConfig) -> Redis:
        return _build_redis_client(base)

    @provide
    def sqlite_connection(self, config: AdminLogConfig) -> SQLiteConnection:
        return SQLiteConnection(
            _db_path=config.log_db_path,
            _reader_count=config.log_db_reader_count,
        )

    @provide
    def stream_publisher(
        self,
        redis: Redis,
        config: AdminLogConfig,
        base: BaseAppConfig,
    ) -> RedisStreamPublisher:
        return RedisStreamPublisher(
            _redis=redis,
            _stream_key=config.log_stream_key,
            _stream_maxlen=config.log_stream_maxlen,
            _batch_size=config.log_batch_size,
            _app_name=base.app_name,
        )

    @provide(provides=ILogSubscriber)
    def log_subscriber(
        self,
        channels: ChannelsPlugin,
        config: AdminLogConfig,
    ) -> ChannelsLogSubscriber:
        return ChannelsLogSubscriber(
            _channels=channels,
            _channel_name=config.log_events_channel,
        )

    @provide
    def render_log_page_uc(
        self,
        reader: ILogReader,
        config: AdminLogConfig,
    ) -> RenderLogPageUc:
        return RenderLogPageUc(_reader=reader, _tail_size=config.log_page_size)

    @provide
    def load_older_logs_uc(
        self,
        reader: ILogReader,
        config: AdminLogConfig,
    ) -> LoadOlderLogsUc:
        return LoadOlderLogsUc(_reader=reader, _chunk_size=config.log_page_size)

    stream_log_tail_uc = provide(StreamLogTailUc)
    export_logs_uc = provide(ExportLogsUc)
    clear_logs_uc = provide(ClearLogsUc)
    logs_facade = provide(LogsFacade)

    @provide(provides=IQueueDepthProvider)
    def queue_depth_provider(
        self,
        publisher: RedisStreamPublisher,
    ) -> RedisStreamQueueDepthProvider:
        return RedisStreamQueueDepthProvider(_publisher=publisher)

    @provide(provides=IMetricsModulePlugin)
    def logs_metrics_plugin(
        self,
        redis: Redis,
        publisher: RedisStreamPublisher,
        config: AdminLogConfig,
    ) -> LogsMetricsPlugin:
        return LogsMetricsPlugin(
            _redis=redis,
            _publisher=publisher,
            _stream_key=config.log_stream_key,
            _consumer_group=config.log_consumer_group,
            _stream_maxlen=config.log_stream_maxlen,
            _batch_size=config.log_batch_size,
        )

    @provide
    def lifespan_manager(
        self,
        connection: SQLiteConnection,
        publisher: RedisStreamPublisher,
        config: AdminLogConfig,
    ) -> LogLifespanManager:
        return LogLifespanManager(
            _connection=connection,
            _publisher=publisher,
            _db_path=config.log_db_path,
            _migrations_path=config.log_migrations_path,
        )


# ─── Sink-side ───────────────────────────────────────────────────────────────


class AdminLogSinkProvider(Provider):
    """DI graph for the standalone `start_log_sink` entrypoint.

    Intentionally omits the web-only pieces (facade, use cases, SSE
    subscriber): the sink process has no HTTP surface.
    """

    scope = Scope.APP

    @provide
    def config(self) -> AdminLogConfig:
        return AdminLogConfig()

    @provide
    def base_config(self) -> BaseAppConfig:
        return BaseAppConfig()

    @provide
    def redis_client(self, base: BaseAppConfig) -> Redis:
        return _build_redis_client(base)

    @provide
    def sqlite_connection(self, config: AdminLogConfig) -> SQLiteConnection:
        return SQLiteConnection(
            _db_path=config.log_db_path,
            _reader_count=config.log_db_reader_count,
        )

    @provide(provides=ILogPublisher)
    def log_publisher(
        self,
        redis: Redis,
        config: AdminLogConfig,
    ) -> RedisPubSubLogPublisher:
        return RedisPubSubLogPublisher(
            _redis=redis,
            _channel=config.log_events_channel,
        )

    @provide
    def stream_publisher(
        self,
        redis: Redis,
        config: AdminLogConfig,
        base: BaseAppConfig,
    ) -> RedisStreamPublisher:
        # The sink emits its own structlog records through the same Valkey
        # Stream every other producer uses; the sink then reads them back
        # like any other entry. Keeps the observability path uniform.
        return RedisStreamPublisher(
            _redis=redis,
            _stream_key=config.log_stream_key,
            _stream_maxlen=config.log_stream_maxlen,
            _batch_size=config.log_batch_size,
            _app_name=base.app_name,
        )

    @provide
    def sink_worker(
        self,
        redis: Redis,
        connection: SQLiteConnection,
        publisher: ILogPublisher,
        config: AdminLogConfig,
    ) -> LogSinkWorker:
        return LogSinkWorker(
            _redis=redis,
            _connection=connection,
            _publisher=publisher,
            _stream_key=config.log_stream_key,
            _group=config.log_consumer_group,
            _consumer_name=config.log_consumer_name,
            _batch_size=config.log_batch_size,
            _claim_min_idle_ms=config.log_claim_min_idle_ms,
            _claim_interval_s=config.log_claim_interval_s,
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
    def sink_lifespan(
        self,
        connection: SQLiteConnection,
        sink_worker: LogSinkWorker,
        cleanup_worker: LogCleanupWorker,
        config: AdminLogConfig,
    ) -> LogSinkLifespan:
        return LogSinkLifespan(
            _connection=connection,
            _sink_worker=sink_worker,
            _cleanup_worker=cleanup_worker,
            _db_path=config.log_db_path,
            _migrations_path=config.log_migrations_path,
        )

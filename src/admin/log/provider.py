from dishka import Provider, Scope, provide

from .adapters.driven.files import LogFileSource
from .app.interfaces import ILogFollower, ILogReader
from .app.use_cases import (
    ExportLogsUc,
    LoadOlderLogsUc,
    RenderLogPageUc,
    StreamLogTailUc,
)
from .config import AdminLogConfig
from .ports.driven.repos import FileLogReader
from .ports.driving import LogsFacade


class AdminLogWebProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> AdminLogConfig:
        return AdminLogConfig()

    @provide
    def log_file_source(self, config: AdminLogConfig) -> LogFileSource:
        if config.file_path is None:
            raise RuntimeError("LOG_FILE_PATH could not be resolved")
        return LogFileSource(path=config.file_path)

    @provide
    def file_log_reader(self, source: LogFileSource) -> FileLogReader:
        return FileLogReader(_source=source)

    @provide
    def log_reader(self, reader: FileLogReader) -> ILogReader:
        return reader

    @provide
    def log_follower(self, reader: FileLogReader) -> ILogFollower:
        return reader

    @provide
    def render_log_page_uc(self, reader: ILogReader) -> RenderLogPageUc:
        return RenderLogPageUc(_reader=reader)

    @provide
    def load_older_logs_uc(self, reader: ILogReader) -> LoadOlderLogsUc:
        return LoadOlderLogsUc(_reader=reader)

    @provide
    def stream_log_tail_uc(self, follower: ILogFollower) -> StreamLogTailUc:
        return StreamLogTailUc(_follower=follower)

    @provide
    def export_logs_uc(self, reader: ILogReader) -> ExportLogsUc:
        return ExportLogsUc(_reader=reader)

    logs_facade = provide(LogsFacade)

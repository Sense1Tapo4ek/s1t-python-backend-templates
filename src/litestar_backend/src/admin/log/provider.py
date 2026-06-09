from dishka import Provider, Scope, provide

from .adapters.driven.log_file_source import LogFileSource
from .app import ExportLogsUc, ILogFollower, ILogReader, LogQueries
from .config import AdminLogConfig
from .ports.driven import FileLogReader
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

    log_queries = provide(LogQueries)
    export_logs_uc = provide(ExportLogsUc)
    logs_facade = provide(LogsFacade)

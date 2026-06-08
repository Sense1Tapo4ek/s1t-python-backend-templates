from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from shared.config import PostgresConfig

from .adapters.driven.engine import build_engine, build_sessionmaker
from .adapters.lifespan_manager import DbExampleLitestarLifespanManager
from .config import DbExampleLitestarConfig
from .ports.driven.services.author_service import AuthorService
from .ports.driven.services.book_service import BookService
from .ports.driving import AuthorFacade, BookFacade


class DbExampleLitestarProvider(Provider):
    scope = Scope.APP

    config = provide(DbExampleLitestarConfig)

    @provide
    def lifespan(
        self, engine: AsyncEngine, config: DbExampleLitestarConfig
    ) -> DbExampleLitestarLifespanManager:
        return DbExampleLitestarLifespanManager(engine=engine, schema_name=config.schema_name)

    @provide
    def engine(self, pg: PostgresConfig, config: DbExampleLitestarConfig) -> AsyncEngine:
        return build_engine(pg.alchemy_url, config.schema_name)

    @provide
    def sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return build_sessionmaker(engine)

    @provide(scope=Scope.REQUEST)
    async def session(self, sm: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
        async with sm() as s:
            yield s

    @provide(scope=Scope.REQUEST)
    def author_service(self, session: AsyncSession) -> AuthorService:
        return AuthorService(session=session)

    @provide(scope=Scope.REQUEST)
    def book_service(self, session: AsyncSession) -> BookService:
        return BookService(session=session)

    @provide(scope=Scope.REQUEST)
    def author_facade(self, author_service: AuthorService) -> AuthorFacade:
        return AuthorFacade(_service=author_service)

    @provide(scope=Scope.REQUEST)
    def book_facade(self, book_service: BookService) -> BookFacade:
        return BookFacade(_service=book_service)

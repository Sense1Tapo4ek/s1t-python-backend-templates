from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .adapters.driven.db.engine import build_engine, build_sessionmaker
from .adapters.driven.lifespan import DbExampleLitestarLifespanManager
from .config import DbExampleLitestarConfig
from .ports.driven.services.author_service import AuthorService
from .ports.driven.services.book_service import BookService
from .ports.driving import AuthorFacade, BookFacade


class DbExampleLitestarProvider(Provider):
    scope = Scope.APP

    config = provide(DbExampleLitestarConfig)
    lifespan = provide(DbExampleLitestarLifespanManager)

    @provide
    def engine(self, config: DbExampleLitestarConfig) -> AsyncEngine:
        if config.db_path is None:
            raise RuntimeError("DB_EXAMPLE_LITESTAR_DB_PATH could not be resolved")
        return build_engine(config.db_path)

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

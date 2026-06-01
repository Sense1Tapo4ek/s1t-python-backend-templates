from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .adapters.db_example_alchemy_lifespan_manager import DbExampleAlchemyLifespanManager
from .adapters.driven.db.engine import build_engine, build_sessionmaker
from .config import DbExampleAlchemyConfig
from .ports.driven.services.author_service import AuthorService
from .ports.driven.services.book_service import BookService


class DbExampleAlchemyProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> DbExampleAlchemyConfig:
        return DbExampleAlchemyConfig()

    @provide
    def engine(self, config: DbExampleAlchemyConfig) -> AsyncEngine:
        assert config.db_path is not None
        return build_engine(config.db_path)

    @provide
    def sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return build_sessionmaker(engine)

    @provide
    def lifespan(self, engine: AsyncEngine) -> DbExampleAlchemyLifespanManager:
        return DbExampleAlchemyLifespanManager(engine=engine)

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

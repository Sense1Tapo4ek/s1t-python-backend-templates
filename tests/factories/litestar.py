from polyfactory.factories.sqlalchemy_factory import SQLAlchemyFactory

from db_example_litestar.ports.orm_models import AuthorModel, BookModel


class AuthorModelFactory(SQLAlchemyFactory[AuthorModel]):
    __set_relationships__ = False


class BookModelFactory(SQLAlchemyFactory[BookModel]):
    __set_relationships__ = False

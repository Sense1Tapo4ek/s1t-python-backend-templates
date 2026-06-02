# Re-export the domain entities so driving adapters (controllers) can reference
# them without reaching past their allowed layer -- adapters/driving may import
# only ports/driving, yet SQLAlchemyDTO generics need the ORM model type.
from ...domain import AuthorModel, BookModel
from .author_dto import AuthorPatchDTO, AuthorReadDTO, AuthorWriteDTO
from .author_facade import AuthorFacade
from .book_dto import BookReadDTO, BookWriteDTO
from .book_facade import BookFacade

__all__ = [
    "AuthorFacade",
    "AuthorModel",
    "AuthorPatchDTO",
    "AuthorReadDTO",
    "AuthorWriteDTO",
    "BookFacade",
    "BookModel",
    "BookReadDTO",
    "BookWriteDTO",
]

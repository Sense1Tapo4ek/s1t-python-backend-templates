# Re-export the persistence model so driving adapters (controllers) can
# reference it without reaching past their allowed layer -- adapters/driving may
# import only ports/driving, yet SQLAlchemyDTO generics need the ORM model type.
# The model itself lives at the ports/ root (used by both branches).
from ..orm_models import AuthorModel, BookModel
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

from datetime import date
from uuid import UUID

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship


class AuthorModel(UUIDAuditBase):
    __tablename__ = "author"
    name: Mapped[str]
    dob: Mapped[date | None] = mapped_column(default=None)
    books: Mapped[list["BookModel"]] = relationship(
        back_populates="author", lazy="noload", cascade="all, delete-orphan"
    )


class BookModel(UUIDAuditBase):
    __tablename__ = "book"
    title: Mapped[str]
    author_id: Mapped[UUID] = mapped_column(ForeignKey("author.id"))
    author: Mapped[AuthorModel] = relationship(back_populates="books", lazy="noload")

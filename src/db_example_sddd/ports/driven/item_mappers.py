import asyncpg

from ...domain import Item


def to_domain(row: asyncpg.Record) -> Item:
    return Item(
        id=row["id"],                  # native uuid.UUID
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],  # native tz-aware datetime (TIMESTAMPTZ)
    )

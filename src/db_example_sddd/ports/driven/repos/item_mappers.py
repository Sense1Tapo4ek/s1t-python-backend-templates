from uuid import UUID

import aiosqlite

from ....domain import Item


def to_domain(row: aiosqlite.Row) -> Item:
    from datetime import datetime

    return Item(
        id=UUID(row["id"]),
        name=row["name"],
        description=row["description"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )

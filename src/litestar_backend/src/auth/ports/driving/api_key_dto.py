from datetime import datetime
from typing import Annotated
from uuid import UUID

import msgspec

from ...domain import ApiKeyRecord


class CreateApiKeyRequest(msgspec.Struct, kw_only=True):
    name: Annotated[str, msgspec.Meta(min_length=1, max_length=100)]


class CreatedApiKeyResponse(msgspec.Struct, kw_only=True):
    id: UUID
    name: str
    api_key: str  # plaintext, shown once
    role: str


class ApiKeyResponse(msgspec.Struct, kw_only=True):
    id: UUID
    name: str
    role: str
    created_at: datetime

    @classmethod
    def of(cls, record: ApiKeyRecord) -> "ApiKeyResponse":
        return cls(
            id=record.id,
            name=record.name,
            role=record.role.value,
            created_at=record.created_at,
        )

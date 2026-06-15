import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from shared.domain.auth import Role

API_KEY_PREFIX = "ak_"


@dataclass(frozen=True, slots=True, kw_only=True)
class ApiKeyRecord:
    id: UUID
    name: str
    role: Role
    created_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class GeneratedApiKey:
    plaintext: str  # returned to the caller ONCE; never stored
    key_hash: str


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> GeneratedApiKey:
    # 256 bits of entropy -> a plain SHA-256 of the key is a safe at-rest
    # representation (no salt/KDF needed: the keyspace is not brute-forceable,
    # unlike a human password). The prefix lets the resolver shape-gate cheaply.
    secret = API_KEY_PREFIX + secrets.token_urlsafe(32)
    return GeneratedApiKey(plaintext=secret, key_hash=hash_api_key(secret))

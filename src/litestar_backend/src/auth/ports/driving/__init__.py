from shared.generics.pagination import Page, decode_cursor, encode_cursor

from ...config import ADMIN_COOKIE_NAME, MAX_TOKEN_LEN
from .api_key_dto import ApiKeyResponse, CreateApiKeyRequest, CreatedApiKeyResponse
from .auth_facade import AuthFacade
from .guards import require_role
from .openapi import ADMIN_SECURITY, SECURITY_COMPONENTS
from .token_dto import RefreshRequest, RevokeRequest, TokenPairResponse
from .user_dto import LoginRequest, MeResponse, RegisterRequest, UserResponse

__all__ = [
    "ADMIN_COOKIE_NAME",
    "ADMIN_SECURITY",
    "MAX_TOKEN_LEN",
    "SECURITY_COMPONENTS",
    "ApiKeyResponse",
    "AuthFacade",
    "CreateApiKeyRequest",
    "CreatedApiKeyResponse",
    "LoginRequest",
    "MeResponse",
    "Page",
    "RefreshRequest",
    "RegisterRequest",
    "RevokeRequest",
    "TokenPairResponse",
    "UserResponse",
    "decode_cursor",
    "encode_cursor",
    "require_role",
]

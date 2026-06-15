from uuid import UUID

from shared.generics.errors import AppError, NotFoundError


class JwtDisabledError(AppError):
    def __init__(self) -> None:
        super().__init__("JWT issuance is not configured")


class ApiKeyNotFound(NotFoundError):
    def __init__(self, api_key_id: UUID) -> None:
        self.api_key_id = api_key_id
        super().__init__(f"API key {api_key_id} not found")

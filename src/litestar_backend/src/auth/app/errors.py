from shared.generics.errors import AppError


class JwtDisabledError(AppError):
    def __init__(self) -> None:
        super().__init__("JWT issuance is not configured")

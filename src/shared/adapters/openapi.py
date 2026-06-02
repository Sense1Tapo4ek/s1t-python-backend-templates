import msgspec
from litestar.openapi.datastructures import ResponseSpec


class ErrorDetail(msgspec.Struct, frozen=True):
    """Uniform error envelope returned by the global exception handlers.

    Every 4xx/5xx in this app serializes to ``{"detail": "<message>"}``;
    validation failures (400/422) additionally carry an ``extra`` list.
    """

    detail: str


# Matches src/shared/adapters/error_handlers.py + auth middleware status codes.
_ERROR_DESCRIPTIONS: dict[int, str] = {
    400: "Validation error - malformed or invalid request body/params.",
    401: "Missing or invalid admin bearer token / cookie.",
    403: "Authenticated but lacking the required role.",
    404: "Resource not found.",
    409: "Domain rule violation (conflict).",
    422: "Request well-formed but semantically unprocessable.",
    503: "Downstream/infrastructure dependency unavailable.",
}


def error_responses(*codes: int) -> dict[int, ResponseSpec]:
    """`responses=` map documenting the shared `{"detail": str}` envelope."""
    return {
        code: ResponseSpec(data_container=ErrorDetail, description=_ERROR_DESCRIPTIONS[code])
        for code in codes
    }

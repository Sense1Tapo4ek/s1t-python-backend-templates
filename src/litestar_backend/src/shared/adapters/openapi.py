from typing import Annotated

import msgspec
from litestar.openapi.datastructures import ResponseSpec

_PROBLEM_DETAILS_MEDIA_TYPE = "application/problem+json"


class ProblemDetail(msgspec.Struct, frozen=True):
    """RFC 9457 problem-details envelope served as application/problem+json.

    Every 4xx/5xx is rendered by the problem-details plugin. ``detail`` is a
    human-readable explanation (generic for 5xx -- no internals leaked);
    validation failures surface field info in ``title``. ``instance`` is the
    request path when present.
    """

    type: Annotated[
        str,
        msgspec.Meta(
            description="URI reference identifying the problem type.",
            examples=["urn:litestar-base:error:order-already-paid"],
        ),
    ]
    title: Annotated[
        str,
        msgspec.Meta(
            description="Short, human-readable summary of the problem type.",
            examples=["Conflict"],
        ),
    ]
    status: Annotated[
        int,
        msgspec.Meta(
            description="HTTP status code for this occurrence.",
            examples=[409],
        ),
    ]
    detail: Annotated[
        str | None,
        msgspec.Meta(
            description="Human-readable explanation of this occurrence.",
            examples=["Order 3fa85f64 is already paid."],
        ),
    ] = None
    instance: Annotated[
        str | None,
        msgspec.Meta(
            description="URI reference identifying this occurrence (request path).",
            examples=["/items/3fa85f64-5717-4562-b3fc-2c963f66afa6"],
        ),
    ] = None


# Matches src/shared/adapters/problem_details.py + auth middleware status codes.
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
    """`responses=` map documenting the RFC 9457 application/problem+json envelope."""
    return {
        code: ResponseSpec(
            data_container=ProblemDetail,
            description=_ERROR_DESCRIPTIONS[code],
            media_type=_PROBLEM_DETAILS_MEDIA_TYPE,
        )
        for code in codes
    }

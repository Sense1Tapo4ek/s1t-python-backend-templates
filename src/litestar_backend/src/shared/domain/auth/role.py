from enum import StrEnum


class Role(StrEnum):
    """All known roles, defined centrally so contexts can require role guards.

    `UNKNOWN` is the default for unauthenticated requests -- every request gets
    a `Principal`, anonymous ones just get `Role.UNKNOWN`. This eliminates the
    "no Principal at all" branch in downstream code (logging, guards, business
    logic).
    """

    UNKNOWN = "unknown"
    ADMIN = "admin"

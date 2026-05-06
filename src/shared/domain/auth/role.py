from enum import StrEnum


class Role(StrEnum):
    """All known roles, defined centrally so contexts can require role guards.

    `UNKNOWN` is the default for unauthenticated requests — every request gets
    a `Principal`, anonymous ones just get `Role.UNKNOWN`. This eliminates the
    "no Principal at all" branch in downstream code (logging, guards, business
    logic) and lets public endpoints (/health, /ping, /admin/login) coexist
    with protected ones via guards rather than middleware exclude lists.
    """

    UNKNOWN = "unknown"
    ADMIN = "admin"

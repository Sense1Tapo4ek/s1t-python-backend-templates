import structlog
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get
from litestar.exceptions import ValidationException
from litestar.response import Stream
from litestar.status_codes import HTTP_200_OK

from auth.ports.driving import ADMIN_SECURITY, require_role
from shared.adapters.openapi import error_responses
from shared.domain.auth import Role

from ....ports.driving import LogsFacade

_log = structlog.get_logger(__name__)

_VALID_FORMATS = frozenset({"ndjson", "csv"})


class ExportController(Controller):
    path = "/api/v1/admin/logs/export"
    guards = [require_role(Role.ADMIN)]  # noqa: RUF012
    security = ADMIN_SECURITY
    tags = ["Admin Logs"]  # noqa: RUF012

    @get("/", status_code=HTTP_200_OK,
         summary="Export logs", responses=error_responses(400, 401, 403))
    @inject
    async def export(
        self,
        facade: FromDishka[LogsFacade],
        format: str = "ndjson",
    ) -> Stream:
        """Stream the log file as a download in ``ndjson`` (default) or ``csv``."""
        if format not in _VALID_FORMATS:
            raise ValidationException(
                f"unknown format {format!r}; expected one of: "
                f"{', '.join(sorted(_VALID_FORMATS))}",
            )
        _log.info("export started", format=format)

        content, media_type, filename = (
            (facade.export_csv(), "text/csv", "logs.csv")
            if format == "csv"
            else (facade.export_ndjson(), "application/x-ndjson", "logs.ndjson")
        )
        return Stream(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

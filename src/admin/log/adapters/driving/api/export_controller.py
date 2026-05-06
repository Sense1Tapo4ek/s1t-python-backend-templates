import structlog
from dishka import FromDishka
from dishka.integrations.litestar import inject
from litestar import Controller, get
from litestar.exceptions import ValidationException
from litestar.response import Stream
from litestar.status_codes import HTTP_200_OK

from auth.ports.driving import require_role
from shared.domain.auth import Role

from ....ports.driving.facades import LogsFacade
from ....ports.driving.schemas import LogFilterSchema

_log = structlog.get_logger(__name__)

_VALID_FORMATS = frozenset({"ndjson", "csv"})


class ExportController(Controller):
    path = "/api/v1/admin/logs/export"
    guards = [require_role(Role.ADMIN)]  # noqa: RUF012

    @get("/", status_code=HTTP_200_OK)
    @inject
    async def export(
        self,
        facade: FromDishka[LogsFacade],
        format: str = "ndjson",
        level: str | None = None,
        levels: list[str] | None = None,
        q: str | None = None,
    ) -> Stream:
        if format not in _VALID_FORMATS:
            raise ValidationException(
                f"unknown format {format!r}; expected one of: "
                f"{', '.join(sorted(_VALID_FORMATS))}",
            )

        schema = LogFilterSchema(min_level=level, levels=levels, q=q)
        facade.parse_filter(schema)
        _log.info("export started", format=format, q=q, min_level=level, levels=levels)

        if format == "csv":
            return Stream(
                content=facade.export_csv(schema),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=logs.csv"},
            )

        return Stream(
            content=facade.export_ndjson(schema),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=logs.ndjson"},
        )

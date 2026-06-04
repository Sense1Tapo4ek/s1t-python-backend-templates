from pydantic import BaseModel, ConfigDict, Field


class LogEntrySchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: str = Field(
        description="ISO-8601 UTC timestamp of the log record.",
        examples=["2026-06-02T13:00:00.123456Z"],
    )
    level: str = Field(
        description="Log level name.",
        examples=["info", "warning", "error"],
    )
    logger: str = Field(
        description="Dotted logger name (module path).",
        examples=["orders.app.place_order_uc"],
    )
    event: str = Field(
        description="Stable structured event key (not interpolated).",
        examples=["item created"],
    )
    pathname: str | None = Field(default=None)
    lineno: int | None = Field(default=None)
    func_name: str | None = Field(default=None)
    trace_id: str | None = Field(default=None)
    span_id: str | None = Field(default=None)
    # JSON-encoded structured kwargs WITHOUT the promoted fields above.
    # Empty object "{}" if the record carried no extra context. Clients
    # merge {...entry, ...JSON.parse(context_json)} for drilldown.
    context_json: str = Field(
        default="{}",
        description="JSON-encoded structured kwargs excluding the promoted fields above.",
        examples=['{"item_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}'],
    )


class LogPageResponseSchema(BaseModel):
    """Wire response for a page of log lines.

    `cursor` is an opaque base64("inode:offset") token marking the byte
    offset of the OLDEST line in this page; pass it to `/older?cursor=`
    to read further back. `cursor=None` means no older history is
    available (start of file or rotation boundary).
    """

    model_config = ConfigDict(frozen=True)

    entries: list[LogEntrySchema] = Field(
        description="Log lines in the page, newest-first within the slice."
    )
    cursor: str | None = Field(
        default=None,
        description=(
            "Opaque base64('inode:offset') token marking the byte offset of "
            "the oldest line in this page; null when no older history exists."
        ),
        examples=["MTIzNDU2Nzg6NDA5Ng=="],
    )

from pydantic import BaseModel, ConfigDict, Field


class LogEntrySchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    timestamp: str
    level: str
    logger: str
    event: str
    pathname: str | None = Field(default=None)
    lineno: int | None = Field(default=None)
    func_name: str | None = Field(default=None)
    trace_id: str | None = Field(default=None)
    span_id: str | None = Field(default=None)
    # JSON-encoded structured kwargs WITHOUT the promoted fields above.
    # Empty object "{}" if the record carried no extra context. Clients
    # merge {...entry, ...JSON.parse(context_json)} for drilldown.
    context_json: str = Field(default="{}")


class LogPageResponseSchema(BaseModel):
    """Wire response for a page of log lines.

    `cursor` is an opaque base64("inode:offset") token marking the byte
    offset of the OLDEST line in this page; pass it to `/older?cursor=`
    to read further back. `cursor=None` means no older history is
    available (start of file or rotation boundary).
    """

    model_config = ConfigDict(frozen=True)

    entries: list[LogEntrySchema]
    cursor: str | None = Field(default=None)

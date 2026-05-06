from pydantic import BaseModel, ConfigDict, Field


class LogFilterSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    # 2 KiB is wildly more than any sane DSL query needs (typical: < 200 bytes).
    # The limit exists to keep `shlex.shlex` from CPU-burning on adversarial input.
    q: str | None = Field(
        default=None,
        description="Free-form DSL query",
        max_length=2048,
    )
    min_level: str | None = Field(default=None)
    levels: list[str] | None = Field(
        default=None,
        description="Explicit set of levels to include. Mutually exclusive with min_level.",
    )
    live_mode: bool = Field(default=False)


class LogEntrySchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    timestamp: str
    level: str
    logger: str
    event: str
    pathname: str
    lineno: int
    func_name: str
    trace_id: str | None = Field(default=None)
    span_id: str | None = Field(default=None)
    # JSON-encoded structured kwargs WITHOUT the reserved fields above.
    # Halves the SSE/snapshot payload vs shipping raw_json (which embeds
    # all top-level fields a second time). Clients reconstruct the full
    # record by merging: {...entry, ...JSON.parse(context_json)}.
    # Empty object "{}" if the record carried no extra context.
    context_json: str = Field(default="{}")


class LogPageResponseSchema(BaseModel):
    """Wire response for paginated log reads.

    `cursor` is the id of the OLDEST entry in this page; pass it back as
    `before` to fetch the previous page. `has_more=False` signals the
    caller to stop paginating.
    """

    model_config = ConfigDict(frozen=True)

    entries: list[LogEntrySchema]
    cursor: int | None = Field(default=None)
    has_more: bool = Field(default=False)


class ClearLogsResponseSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    deleted: int

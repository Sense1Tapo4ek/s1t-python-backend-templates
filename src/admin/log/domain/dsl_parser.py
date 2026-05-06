import re
import shlex
from collections.abc import Iterator
from datetime import datetime

from .dsl_constants import KV_KEY_PATTERN as _KV_KEY_PATTERN
from .dsl_constants import VALID_LEVELS as _VALID_LEVELS
from .errors import DslSyntaxError
from .log_filter_vo import LogFilterVo

_TRACE_ID_RE = re.compile(r"^[0-9a-f]{16}$")
_KV_PREFIX = "kv."


class DslParser:
    """Parse a free-form admin logs query string into a LogFilterVo.

    Supported tokens:
      level:WARN+              -> min_level
      level:ERROR              -> levels (multi-token accumulates)
      logger:ordering.*        -> loggers (glob handled in SQL builder)
      logger:auth              -> loggers
      trace:hex16              -> trace_id
      from:ISO8601             -> time_from
      to:ISO8601               -> time_to
      kv.<key>=<value>         -> kv_filters
      kv.<key>="quoted value"  -> kv_filters
      <bare>                   -> fts_phrase (joined with spaces)
    """

    @staticmethod
    def parse(raw: str) -> LogFilterVo:
        if not raw or not raw.strip():
            return LogFilterVo.empty()

        try:
            tokens = list(_tokenize(raw))
        except ValueError as exc:
            raise DslSyntaxError(position=0, reason=f"tokenization failed: {exc}") from exc

        min_level: str | None = None
        levels: list[str] = []
        loggers: list[str] = []
        trace_id: str | None = None
        kv: list[tuple[str, str]] = []
        time_from: datetime | None = None
        time_to: datetime | None = None
        text_parts: list[str] = []

        for position, token in tokens:
            if token.startswith(_KV_PREFIX):
                key, value = _parse_kv(token, position)
                kv.append((key, value))
                continue

            if ":" in token:
                head, _, tail = token.partition(":")
                match head:
                    case "level":
                        if tail.endswith("+"):
                            if min_level is not None or levels:
                                raise DslSyntaxError(
                                    position=position,
                                    reason="cannot mix level:X+ with other level filters",
                                )
                            min_level = _validate_level(tail[:-1], position)
                        else:
                            if min_level is not None:
                                raise DslSyntaxError(
                                    position=position,
                                    reason="cannot mix level:X with level:X+",
                                )
                            levels.append(_validate_level(tail, position))
                        continue
                    case "logger":
                        if not tail:
                            raise DslSyntaxError(position=position, reason="logger value is empty")
                        loggers.append(tail)
                        continue
                    case "trace":
                        if not tail:
                            raise DslSyntaxError(position=position, reason="trace value is empty")
                        if not _TRACE_ID_RE.fullmatch(tail):
                            raise DslSyntaxError(
                                position=position,
                                reason="trace_id must be 16 lowercase hex characters",
                            )
                        trace_id = tail
                        continue
                    case "from":
                        time_from = _parse_iso(tail, position, field="from")
                        continue
                    case "to":
                        time_to = _parse_iso(tail, position, field="to")
                        continue

            text_parts.append(token)

        return LogFilterVo(
            min_level=min_level,
            levels=tuple(levels) if levels else None,
            loggers=tuple(loggers) if loggers else None,
            trace_id=trace_id,
            kv_filters=tuple(kv) if kv else None,
            time_from=time_from,
            time_to=time_to,
            fts_phrase=" ".join(text_parts) if text_parts else None,
        )


def _tokenize(raw: str) -> Iterator[tuple[int, str]]:
    """Yield (position, token) pairs preserving quoted values intact.

    Position is approximate: shlex strips surrounding quotes from values, so
    when a token contained quoted whitespace (e.g. `kv.x="a b"`), the recovered
    position falls back to the running cursor and may be off by a few chars.
    Adequate for `DslSyntaxError.position` messages; not yet suitable for
    rendering a precise caret in a UI.
    """
    lexer = shlex.shlex(raw, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    lexer.quotes = '"'
    pos = 0
    cursor = 0
    for token in lexer:
        idx = raw.find(token, cursor)
        pos = idx if idx >= 0 else cursor
        cursor = pos + len(token)
        yield pos, token


def _parse_kv(token: str, position: int) -> tuple[str, str]:
    body = token[len(_KV_PREFIX):]
    if "=" not in body:
        raise DslSyntaxError(
            position=position,
            reason="kv token must use the form kv.<key>=<value>",
        )
    key, _, value = body.partition("=")
    if not key:
        raise DslSyntaxError(position=position, reason="kv key is empty")
    if not _KV_KEY_PATTERN.fullmatch(key):
        raise DslSyntaxError(
            position=position,
            reason=f"kv key {key!r} contains invalid characters",
        )
    return key, value


def _validate_level(value: str, position: int) -> str:
    upper = value.upper()
    if upper not in _VALID_LEVELS:
        raise DslSyntaxError(
            position=position,
            reason=f"unknown log level {value!r}",
        )
    return upper


def _parse_iso(value: str, position: int, field: str) -> datetime:
    if not value:
        raise DslSyntaxError(position=position, reason=f"{field} value is empty")
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise DslSyntaxError(
            position=position,
            reason=f"{field} is not valid ISO 8601: {exc}",
        ) from exc

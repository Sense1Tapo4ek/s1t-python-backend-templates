from enum import StrEnum


class Severity(StrEnum):
    OK = "ok"
    WARN = "warn"
    BAD = "bad"
    NEUTRAL = "neutral"


def classify(
    value: float,
    *,
    warn: float | None,
    bad: float | None,
) -> Severity:
    """Map a numeric value to a Severity using two upper thresholds.

    - `warn=None` means "no warn band" — anything below `bad` is OK.
    - `bad=None` means "no alarm" — always OK.
    - Inversion (warn > bad) is a programming error and raises.
    """
    if warn is not None and bad is not None and warn > bad:
        raise ValueError(f"warn ({warn}) must be <= bad ({bad})")
    if bad is not None and value >= bad:
        return Severity.BAD
    if warn is not None and value >= warn:
        return Severity.WARN
    return Severity.OK

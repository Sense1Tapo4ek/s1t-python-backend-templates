from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True, kw_only=True)
class DetailSectionVo:
    title: str
    payload: dict[str, Any]

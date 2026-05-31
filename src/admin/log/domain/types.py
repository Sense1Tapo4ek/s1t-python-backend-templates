from dataclasses import dataclass
from typing import NewType

LogId = NewType("LogId", int)


@dataclass(frozen=True, slots=True, kw_only=True)
class Cursor:
    inode: int
    offset: int

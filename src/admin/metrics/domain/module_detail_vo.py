from dataclasses import dataclass

from .detail_section_vo import DetailSectionVo


@dataclass(frozen=True, slots=True, kw_only=True)
class ModuleDetailVo:
    slug: str
    name: str
    sections: tuple[DetailSectionVo, ...]

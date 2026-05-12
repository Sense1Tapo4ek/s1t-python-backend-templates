"""Resident memory of this process.

`ru_maxrss` is reported in **kibibytes** on Linux and in **bytes** on
macOS/BSD. We normalise to bytes by detecting the platform. No external
deps.
"""

import resource
import sys
from dataclasses import dataclass


@dataclass(slots=True, kw_only=True)
class ProcessRssSampler:
    def current_rss_bytes(self) -> int:
        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # Linux/glibc reports KiB; Darwin reports bytes.
        if sys.platform == "darwin":
            return int(raw)
        return int(raw) * 1024

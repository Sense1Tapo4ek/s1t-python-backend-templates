# Re-export surface for the driving adapters (saq_jobs, uploaded_consumer):
# they may import only ports/driving (structure.md 4), and framework coupling
# is allowed here (ports.md 1.5). Counters stay module-level in
# adapters/driven/metrics (registration-once invariant); this module only
# re-exports them.
from ...adapters.driven.executors import plagiarism_blocking, transcode_cpu
from ...adapters.driven.metrics import EVENTS_RECEIVED, JOB_DURATION, JOBS_PROCESSED
from ...domain import JobKind

__all__ = [
    "EVENTS_RECEIVED",
    "JOBS_PROCESSED",
    "JOB_DURATION",
    "JobKind",
    "plagiarism_blocking",
    "transcode_cpu",
]

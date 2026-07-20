# 0027 - Map the three SAQ jobs to distinct execution models
Status: accepted
Date: 2026-06-08

## Context
The worker showcase must teach how to run heterogeneous work from a single async
SAQ worker without blocking its event loop. Three representative workloads:
external-API wait, a blocking/GIL-releasing call, and a CPU-bound loop.

## Decision
Map one job to each model: `stt` = async (`await`, no executor); `plagiarism` =
thread pool (`run_in_executor` of a blocking call); `transcode` = process pool
(`run_in_executor` of a CPU loop, true parallelism past the GIL). Pools are
built once in the SAQ `startup` hook and owned for the worker's lifetime;
process-pool work functions are module-level so they pickle.

## Consequences
- + One worker covers I/O-bound, blocking, and CPU-bound work without stalling
    the loop; the three models are visible side-by-side.
- - Two pools add startup/shutdown surface and a process-pool pickling
    constraint (work functions must stay module-level).

## Alternatives considered
- All jobs async - cannot run CPU-bound transcode without blocking the loop; rejected.
- A separate worker per model - more deploy units than the showcase needs; rejected.

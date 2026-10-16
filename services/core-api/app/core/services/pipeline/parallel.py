"""Parallel stage execution; waiting deadlines start at submission."""
import time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Callable
from app.core.services.pipeline.runtime import ServiceResult, _safe_run


@dataclass(frozen=True)
class StageSpec:
    name: str
    function: Callable
    fallback: Any
    timeout: float


def run_parallel(specs):
    if not specs:
        return []
    def execute(spec):
        result = _safe_run(spec.name, spec.function, spec.fallback)
        return result, time.monotonic()
    with ThreadPoolExecutor(max_workers=min(4, len(specs))) as pool:
        submitted = [(spec, time.monotonic(), pool.submit(execute, spec))
                     for spec in specs]
        results = []
        for spec, start, future in submitted:
            try:
                result, finished = future.result(timeout=max(0, spec.timeout - (time.monotonic() - start)))
                if finished - start > spec.timeout:
                    raise TimeoutError()
                results.append(result)
            except TimeoutError:
                # This stops waiting, not the running thread. Celery's process
                # hard limit remains the outer execution boundary.
                future.cancel()
                results.append(ServiceResult(spec.name, spec.fallback, False, fallback_used=True,
                                             error=f"timeout ({spec.timeout}s)", duration_s=time.monotonic() - start))
        return results

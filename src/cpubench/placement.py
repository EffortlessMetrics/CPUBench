from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import psutil


class PlacementError(RuntimeError):
    pass


@contextmanager
def placement_scope(selector: str) -> Iterator[dict[str, Any]]:
    process = psutil.Process()
    if selector == "scheduler_open":
        yield {"selector": selector, "requested": False, "verified": False}
        return
    if not selector.startswith("cpu:"):
        raise PlacementError(f"unsupported placement selector: {selector}")
    if not hasattr(process, "cpu_affinity"):
        raise PlacementError("process affinity is unavailable")
    cpu = int(selector.split(":", 1)[1])
    original = process.cpu_affinity()
    try:
        process.cpu_affinity([cpu])
        observed = process.cpu_affinity()
        if observed != [cpu]:
            raise PlacementError(f"affinity readback mismatch: requested {cpu}, observed {observed}")
        yield {"selector": selector, "requested": True, "verified": True, "observed": observed}
    finally:
        process.cpu_affinity(original)

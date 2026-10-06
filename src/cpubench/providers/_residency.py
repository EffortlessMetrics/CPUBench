from __future__ import annotations

from collections.abc import Callable
from typing import cast

import psutil


def current_cpu() -> int | None:
    process = psutil.Process()
    getter = getattr(process, "cpu_num", None)
    if not callable(getter):
        return None
    try:
        value = cast(Callable[[], int], getter)()
    except (AttributeError, OSError, NotImplementedError, psutil.Error):
        return None
    if value < 0:
        return None
    return value


def residency_metadata(start_cpu: int | None, end_cpu: int | None) -> dict[str, int | str]:
    metadata: dict[str, int | str] = {"record_type": "metadata"}
    if start_cpu is not None:
        metadata["placement_start_cpu"] = start_cpu
    if end_cpu is not None:
        metadata["placement_end_cpu"] = end_cpu
    return metadata

from __future__ import annotations

import psutil


def current_cpu() -> int | None:
    try:
        value = psutil.Process().cpu_num()
    except (AttributeError, OSError, NotImplementedError, psutil.Error):
        return None
    if value is None or int(value) < 0:
        return None
    return int(value)


def residency_metadata(start_cpu: int | None, end_cpu: int | None) -> dict[str, int | str]:
    metadata: dict[str, int | str] = {"record_type": "metadata"}
    if start_cpu is not None:
        metadata["placement_start_cpu"] = start_cpu
    if end_cpu is not None:
        metadata["placement_end_cpu"] = end_cpu
    return metadata

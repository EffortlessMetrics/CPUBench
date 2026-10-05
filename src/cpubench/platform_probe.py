from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import psutil

from .models import CapabilityEvidence, CapabilityState, MachineReceipt, RunEnvironmentReceipt


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _linux_cpuinfo() -> dict[str, Any]:
    text = _read_text(Path("/proc/cpuinfo")) or ""
    result: dict[str, Any] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if key in {"vendor_id", "model name", "cpu family", "model", "stepping", "microcode", "Hardware"}:
            result.setdefault(key, value)
    return result


def _linux_topology() -> dict[str, Any]:
    cpus: list[dict[str, Any]] = []
    for cpu_dir in sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*"), key=lambda p: int(p.name[3:])):
        cpu_id = int(cpu_dir.name[3:])
        topology = cpu_dir / "topology"
        entry = {
            "logical_cpu": cpu_id,
            "core_id": _read_text(topology / "core_id"),
            "package_id": _read_text(topology / "physical_package_id"),
            "thread_siblings": _read_text(topology / "thread_siblings_list"),
            "core_siblings": _read_text(topology / "core_siblings_list"),
            "online": _read_text(cpu_dir / "online") or "1",
        }
        cpus.append(entry)
    return {"logical_cpus": cpus}


def _cache_summary() -> list[dict[str, Any]]:
    caches: dict[tuple[str, str, str], dict[str, Any]] = {}
    for index in Path("/sys/devices/system/cpu/cpu0/cache").glob("index*"):
        level = _read_text(index / "level") or "unknown"
        cache_type = _read_text(index / "type") or "unknown"
        size = _read_text(index / "size") or "unknown"
        shared = _read_text(index / "shared_cpu_list") or "unknown"
        key = (level, cache_type, shared)
        caches[key] = {"level": level, "type": cache_type, "size": size, "shared_cpu_list": shared}
    return list(caches.values())


def _timer_capability() -> CapabilityEvidence:
    info = time.get_clock_info("monotonic")
    if not info.monotonic:
        state = CapabilityState.FAILED
        detail = "The host Python monotonic clock reports that it is not monotonic."
    else:
        state = CapabilityState.AVAILABLE_UNQUALIFIED
        detail = (
            "A monotonic interval clock is exposed by the host Python runtime. "
            "Campaign controls must still measure read overhead and effective resolution."
        )
    return CapabilityEvidence(
        state=state,
        authority="python.time.monotonic_ns",
        detail=detail,
        evidence={
            "implementation": info.implementation,
            "nominal_resolution_seconds": info.resolution,
            "monotonic": info.monotonic,
            "adjustable": info.adjustable,
        },
    )


def _native_timer_capability() -> CapabilityEvidence:
    system = platform.system()
    if system == "Windows":
        authority = "QueryPerformanceCounter"
    elif system in {"Linux", "Darwin"}:
        authority = "CLOCK_MONOTONIC_RAW_or_CLOCK_MONOTONIC"
    else:
        return CapabilityEvidence(
            state=CapabilityState.UNKNOWN,
            authority="platform-policy",
            detail="The bundled native provider timer has not been qualified on this platform.",
        )
    return CapabilityEvidence(
        state=CapabilityState.AVAILABLE_UNQUALIFIED,
        authority=authority,
        detail=(
            "A platform monotonic interval timer is available to the bundled native provider. "
            "Campaign controls must measure read overhead, effective resolution, and monotonicity "
            "before performance samples enter portable_elapsed views."
        ),
    )


def _hostname_hash() -> str:
    value = platform.node().encode("utf-8", errors="replace")
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _affinity_capability() -> CapabilityEvidence:
    system = platform.system().lower()
    process = psutil.Process()
    if system == "darwin":
        return CapabilityEvidence(
            state=CapabilityState.UNSUPPORTED,
            authority="platform-policy",
            detail="CPUBench does not claim hard processor affinity on macOS.",
        )
    if not hasattr(process, "cpu_affinity"):
        return CapabilityEvidence(
            state=CapabilityState.UNSUPPORTED,
            authority="psutil",
            detail="Process affinity API is unavailable.",
        )
    try:
        current = process.cpu_affinity()
    except (psutil.Error, OSError) as exc:
        return CapabilityEvidence(
            state=CapabilityState.FAILED,
            authority="psutil.Process.cpu_affinity",
            detail=str(exc),
        )
    return CapabilityEvidence(
        state=CapabilityState.AVAILABLE_UNQUALIFIED,
        authority="psutil.Process.cpu_affinity",
        detail="Affinity can be requested and read back; per-attempt residency still requires separate evidence.",
        evidence={"current_affinity": current},
    )


def _pmu_capability() -> CapabilityEvidence:
    system = platform.system().lower()
    if system != "linux":
        return CapabilityEvidence(
            state=CapabilityState.UNKNOWN,
            authority="platform-policy",
            detail="PMU support is not yet qualified on this platform.",
        )
    paranoid = _read_text(Path("/proc/sys/kernel/perf_event_paranoid"))
    if paranoid is None:
        return CapabilityEvidence(
            state=CapabilityState.UNSUPPORTED,
            authority="linux.procfs",
            detail="perf_event_paranoid was not available.",
        )
    return CapabilityEvidence(
        state=CapabilityState.AVAILABLE_UNQUALIFIED,
        authority="linux.perf_event",
        detail="Linux perf policy was observed, but no event set was qualified by this probe.",
        evidence={"perf_event_paranoid": paranoid},
    )


def _sensor_capability(kind: str) -> CapabilityEvidence:
    try:
        if kind == "thermal":
            data = psutil.sensors_temperatures(fahrenheit=False)
        else:
            data = psutil.sensors_battery()
    except (AttributeError, OSError, NotImplementedError) as exc:
        return CapabilityEvidence(state=CapabilityState.UNSUPPORTED, authority="psutil", detail=str(exc))
    if not data:
        return CapabilityEvidence(state=CapabilityState.UNSUPPORTED, authority="psutil", detail=f"no {kind} data")
    return CapabilityEvidence(
        state=CapabilityState.AVAILABLE_UNQUALIFIED,
        authority="psutil",
        evidence={"available": True},
    )


def _serializable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=lambda obj: getattr(obj, "_asdict", lambda: str(obj))()))


def _sensor_snapshot(kind: str) -> dict[str, Any]:
    try:
        if kind == "thermal":
            data = psutil.sensors_temperatures(fahrenheit=False)
        else:
            data = psutil.sensors_battery()
    except (AttributeError, OSError, NotImplementedError) as exc:
        return {"available": False, "error": str(exc)}
    if not data:
        return {"available": False}
    return {"available": True, "data": _serializable(data)}


def collect_machine_receipt() -> MachineReceipt:
    system_name = platform.system()
    cpuinfo = _linux_cpuinfo() if system_name == "Linux" else {}
    topology = _linux_topology() if system_name == "Linux" else {"logical_cpus": psutil.cpu_count(logical=True)}
    if system_name == "Linux":
        topology["caches"] = _cache_summary()

    frequency = None
    try:
        freq = psutil.cpu_freq()
        if freq:
            frequency = {"min": freq.min, "max": freq.max}
    except (AttributeError, OSError, NotImplementedError):
        pass

    vm = psutil.virtual_memory()
    known_unknowns: list[str] = []
    if system_name == "Darwin":
        known_unknowns.append("hard CPU affinity is not claimed")
    if not topology.get("logical_cpus"):
        known_unknowns.append("detailed CPU topology unavailable")

    receipt = MachineReceipt(
        system={
            "os": system_name,
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
            "hostname_hash": _hostname_hash(),
            "boot_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(psutil.boot_time())),
            "container_hints": {
                "dockerenv": Path("/.dockerenv").exists(),
                "cgroup": _read_text(Path("/proc/1/cgroup")) if system_name == "Linux" else None,
            },
        },
        cpu={
            "processor": platform.processor(),
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_processors": psutil.cpu_count(logical=True),
            "frequency": frequency,
            "linux_cpuinfo": cpuinfo,
        },
        topology=topology,
        memory={
            "total_bytes": vm.total,
            "page_size": os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else None,
        },
        runtime={
            "python": sys.version,
            "python_implementation": platform.python_implementation(),
        },
        capabilities={
            "timer.python_monotonic_ns": _timer_capability(),
            "timer.native_interval": _native_timer_capability(),
            "placement.process_affinity": _affinity_capability(),
            "counters.pmu": _pmu_capability(),
            "sensors.thermal": _sensor_capability("thermal"),
            "sensors.battery": _sensor_capability("battery"),
        },
        known_unknowns=known_unknowns,
    )
    return receipt.with_semantic_id()


def collect_run_environment_receipt(campaign_id: str, machine: MachineReceipt) -> RunEnvironmentReceipt:
    process = psutil.Process()
    affinity: list[int] | None = None
    if hasattr(process, "cpu_affinity"):
        try:
            affinity = process.cpu_affinity()
        except (psutil.Error, OSError):
            affinity = None

    current_frequency: dict[str, Any] = {"available": False}
    try:
        freq = psutil.cpu_freq()
        if freq:
            current_frequency = {"available": True, "current_mhz": freq.current, "min_mhz": freq.min, "max_mhz": freq.max}
    except (AttributeError, OSError, NotImplementedError):
        pass

    try:
        load_average: list[float] = list(os.getloadavg())
    except (AttributeError, OSError):
        load_average = []

    vm = psutil.virtual_memory()
    known_unknowns: list[str] = []
    if affinity is None:
        known_unknowns.append("process affinity snapshot unavailable")
    if not load_average:
        known_unknowns.append("load average unavailable")

    receipt = RunEnvironmentReceipt(
        campaign_id=campaign_id,
        machine_receipt_id=machine.semantic_id or "",
        process={
            "process_id": os.getpid(),
            "current_cpu": process.cpu_num() if hasattr(process, "cpu_num") else None,
            "affinity": affinity,
        },
        load={
            "load_average": load_average,
            "cpu_percent_snapshot": psutil.cpu_percent(interval=None, percpu=True),
        },
        memory={
            "available_bytes": vm.available,
            "used_bytes": vm.used,
            "percent": vm.percent,
        },
        power={
            "cpu_frequency": current_frequency,
            "battery": _sensor_snapshot("battery"),
        },
        thermal=_sensor_snapshot("thermal"),
        known_unknowns=known_unknowns,
        parent_ids=[machine.semantic_id or ""],
    )
    return receipt.with_semantic_id()

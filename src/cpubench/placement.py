from __future__ import annotations

import platform
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import psutil

from .models import AttemptState, CapabilityState, PlacementReceipt


class PlacementError(RuntimeError):
    def __init__(
        self,
        reason_code: str,
        detail: str,
        receipt: PlacementReceipt,
        *,
        attempt_state: AttemptState,
        abort_campaign: bool = False,
    ) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail
        self.receipt = receipt
        self.attempt_state = attempt_state
        self.abort_campaign = abort_campaign


def _replace(receipt: PlacementReceipt, **updates: Any) -> PlacementReceipt:
    data = receipt.model_dump(mode="python")
    data.update(updates)
    return PlacementReceipt.model_validate(data)


def _cpu_from_metadata(metadata: dict[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{key} must be a CPU identifier, not a boolean")
    try:
        cpu = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} is not an integer CPU identifier: {value!r}") from exc
    if cpu < 0:
        raise ValueError(f"{key} must be non-negative: {cpu}")
    return cpu


def _affinity(process: Any) -> list[int]:
    values = process.cpu_affinity()
    return sorted({int(value) for value in values})


def _platform_authority(system: str) -> str:
    if system == "linux":
        return "psutil.Process.cpu_affinity+provider.sched_getcpu"
    if system == "windows":
        return "psutil.Process.cpu_affinity+provider.GetCurrentProcessorNumber"
    return "psutil.Process.cpu_affinity+provider_residency"


def _restore_affinity(process: Any, original: list[int]) -> tuple[bool, str | None]:
    try:
        process.cpu_affinity(original)
        restored = _affinity(process)
    except (psutil.Error, OSError, ValueError) as exc:
        return False, str(exc)
    if restored != original:
        return False, f"restoration readback mismatch: expected {original}, observed {restored}"
    return True, None


@dataclass
class PlacementSession:
    receipt: PlacementReceipt

    def complete(self, metadata: dict[str, Any]) -> PlacementReceipt:
        try:
            start_cpu = _cpu_from_metadata(metadata, "placement_start_cpu")
            end_cpu = _cpu_from_metadata(metadata, "placement_end_cpu")
        except ValueError as exc:
            self.receipt = _replace(
                self.receipt,
                state=CapabilityState.FAILED,
                observed_start_cpu=None,
                observed_end_cpu=None,
                residency_verified=False,
                hard_affinity_verified=False,
                reason_code="residency_evidence_invalid",
                detail=str(exc),
            )
            return self.receipt

        common = {
            "observed_start_cpu": start_cpu,
            "observed_end_cpu": end_cpu,
        }
        if self.receipt.selector == "scheduler_open":
            self.receipt = _replace(
                self.receipt,
                **common,
                state=CapabilityState.AVAILABLE_UNQUALIFIED,
                residency_verified=None,
                hard_affinity_verified=False,
                reason_code="scheduler_open_by_design",
                detail="The operating-system scheduler selected execution CPUs; no hard-affinity claim is made.",
            )
            return self.receipt

        if start_cpu is None or end_cpu is None:
            self.receipt = _replace(
                self.receipt,
                **common,
                state=CapabilityState.AVAILABLE_UNQUALIFIED,
                residency_verified=None,
                hard_affinity_verified=False,
                reason_code="residency_evidence_incomplete",
                detail="Provider start/end CPU residency was not fully observed.",
            )
            return self.receipt

        accepted = set(self.receipt.accepted_cpus)
        if start_cpu != end_cpu:
            self.receipt = _replace(
                self.receipt,
                **common,
                state=CapabilityState.FAILED,
                residency_verified=False,
                hard_affinity_verified=False,
                reason_code="residency_migrated",
                detail=f"Provider migrated from CPU {start_cpu} to CPU {end_cpu}.",
            )
            return self.receipt
        if start_cpu not in accepted or end_cpu not in accepted:
            self.receipt = _replace(
                self.receipt,
                **common,
                state=CapabilityState.FAILED,
                residency_verified=False,
                hard_affinity_verified=False,
                reason_code="residency_outside_accepted_affinity",
                detail=(
                    f"Provider executed on CPU {start_cpu}; accepted affinity set was "
                    f"{sorted(accepted)}."
                ),
            )
            return self.receipt

        if self.receipt.platform == "linux":
            self.receipt = _replace(
                self.receipt,
                **common,
                state=CapabilityState.QUALIFIED,
                residency_verified=True,
                hard_affinity_verified=True,
                reason_code="hard_affinity_qualified",
                detail="Affinity request, readback, and provider start/end residency agree.",
            )
            return self.receipt

        if self.receipt.platform == "windows":
            self.receipt = _replace(
                self.receipt,
                **common,
                state=CapabilityState.AVAILABLE_UNQUALIFIED,
                residency_verified=True,
                hard_affinity_verified=False,
                reason_code="windows_process_affinity_limited",
                detail=(
                    "Process affinity and provider residency agree within the visible processor group, "
                    "but processor-group and CPU Set authority are not yet qualified."
                ),
            )
            return self.receipt

        self.receipt = _replace(
            self.receipt,
            **common,
            state=CapabilityState.AVAILABLE_UNQUALIFIED,
            residency_verified=True,
            hard_affinity_verified=False,
            reason_code="platform_placement_authority_unqualified",
            detail="Affinity and residency agree, but this platform backend is not qualified.",
        )
        return self.receipt

    def record_restore_failure(self, detail: str) -> None:
        self.receipt = _replace(
            self.receipt,
            state=CapabilityState.FAILED,
            hard_affinity_verified=False,
            reason_code="affinity_restore_failed",
            detail=detail,
            restored=False,
        )


def _error_receipt(
    selector: str,
    system: str,
    state: CapabilityState,
    reason_code: str,
    detail: str,
    *,
    requested_cpus: list[int] | None = None,
    original_cpus: list[int] | None = None,
) -> PlacementReceipt:
    return PlacementReceipt(
        selector=selector,
        platform=system,
        state=state,
        authority=_platform_authority(system),
        requested=selector != "scheduler_open",
        request_verified=False,
        requested_cpus=requested_cpus or [],
        original_cpus=original_cpus or [],
        reason_code=reason_code,
        detail=detail,
    )


def _parse_cpu_selector(selector: str, system: str) -> int:
    if not selector.startswith("cpu:"):
        receipt = _error_receipt(
            selector,
            system,
            CapabilityState.FAILED,
            "placement_selector_unsupported",
            f"Unsupported placement selector: {selector}",
        )
        raise PlacementError(
            receipt.reason_code,
            receipt.detail or receipt.reason_code,
            receipt,
            attempt_state=AttemptState.INCOMPATIBLE,
        )
    value = selector.split(":", 1)[1]
    try:
        cpu = int(value)
    except ValueError as exc:
        receipt = _error_receipt(
            selector,
            system,
            CapabilityState.FAILED,
            "placement_cpu_invalid",
            f"Invalid logical CPU identifier: {value!r}",
        )
        raise PlacementError(
            receipt.reason_code,
            receipt.detail or receipt.reason_code,
            receipt,
            attempt_state=AttemptState.INCOMPATIBLE,
        ) from exc
    if cpu < 0:
        receipt = _error_receipt(
            selector,
            system,
            CapabilityState.FAILED,
            "placement_cpu_invalid",
            f"Logical CPU identifier must be non-negative: {cpu}",
        )
        raise PlacementError(
            receipt.reason_code,
            receipt.detail or receipt.reason_code,
            receipt,
            attempt_state=AttemptState.INCOMPATIBLE,
        )
    return cpu


@contextmanager
def placement_scope(selector: str) -> Iterator[PlacementSession]:
    process = psutil.Process()
    system = platform.system().lower()

    if selector == "scheduler_open":
        original: list[int] = []
        if hasattr(process, "cpu_affinity"):
            try:
                original = _affinity(process)
            except (psutil.Error, OSError, ValueError):
                original = []
        session = PlacementSession(
            PlacementReceipt(
                selector=selector,
                platform=system,
                state=CapabilityState.AVAILABLE_UNQUALIFIED,
                authority="operating_system_scheduler",
                original_cpus=original,
                reason_code="scheduler_open_by_design",
                detail="No hard-affinity request was made.",
            )
        )
        yield session
        return

    cpu = _parse_cpu_selector(selector, system)
    if system == "darwin":
        receipt = _error_receipt(
            selector,
            system,
            CapabilityState.UNSUPPORTED,
            "hard_affinity_unsupported_macos",
            "CPUBench does not claim hard processor affinity on macOS.",
            requested_cpus=[cpu],
        )
        raise PlacementError(
            receipt.reason_code,
            receipt.detail or receipt.reason_code,
            receipt,
            attempt_state=AttemptState.UNSUPPORTED,
        )
    if not hasattr(process, "cpu_affinity"):
        receipt = _error_receipt(
            selector,
            system,
            CapabilityState.UNSUPPORTED,
            "hard_affinity_api_unavailable",
            "Process affinity API is unavailable.",
            requested_cpus=[cpu],
        )
        raise PlacementError(
            receipt.reason_code,
            receipt.detail or receipt.reason_code,
            receipt,
            attempt_state=AttemptState.UNSUPPORTED,
        )

    try:
        original = _affinity(process)
    except (psutil.Error, OSError, ValueError) as exc:
        receipt = _error_receipt(
            selector,
            system,
            CapabilityState.FAILED,
            "affinity_read_failed",
            str(exc),
            requested_cpus=[cpu],
        )
        raise PlacementError(
            receipt.reason_code,
            receipt.detail or receipt.reason_code,
            receipt,
            attempt_state=AttemptState.INSTRUMENT_FAILED,
        ) from exc

    if cpu not in original:
        receipt = _error_receipt(
            selector,
            system,
            CapabilityState.FAILED,
            "requested_cpu_unavailable",
            f"Requested CPU {cpu} is not in the process affinity set {original}.",
            requested_cpus=[cpu],
            original_cpus=original,
        )
        raise PlacementError(
            receipt.reason_code,
            receipt.detail or receipt.reason_code,
            receipt,
            attempt_state=AttemptState.INCOMPATIBLE,
        )

    try:
        process.cpu_affinity([cpu])
        accepted = _affinity(process)
    except (psutil.Error, OSError, ValueError) as exc:
        restored, restore_detail = _restore_affinity(process, original)
        reason_code = "affinity_request_or_readback_failed"
        detail = str(exc)
        abort_campaign = not restored
        if abort_campaign:
            reason_code = "affinity_restore_failed_after_request"
            detail = f"{detail}; restoration failed: {restore_detail}"
        receipt = PlacementReceipt(
            selector=selector,
            platform=system,
            state=CapabilityState.FAILED,
            authority=_platform_authority(system),
            requested=True,
            request_verified=False,
            requested_cpus=[cpu],
            original_cpus=original,
            restored=restored,
            reason_code=reason_code,
            detail=detail,
        )
        raise PlacementError(
            receipt.reason_code,
            receipt.detail or receipt.reason_code,
            receipt,
            attempt_state=AttemptState.INSTRUMENT_FAILED,
            abort_campaign=abort_campaign,
        ) from exc

    if accepted != [cpu]:
        restored, restore_detail = _restore_affinity(process, original)
        reason_code = "affinity_readback_mismatch"
        detail = f"Requested CPU {cpu}; affinity readback was {accepted}."
        abort_campaign = not restored
        if abort_campaign:
            reason_code = "affinity_restore_failed_after_readback_mismatch"
            detail = f"{detail} Restoration failed: {restore_detail}"
        receipt = PlacementReceipt(
            selector=selector,
            platform=system,
            state=CapabilityState.FAILED,
            authority=_platform_authority(system),
            requested=True,
            request_verified=False,
            requested_cpus=[cpu],
            accepted_cpus=accepted,
            original_cpus=original,
            restored=restored,
            reason_code=reason_code,
            detail=detail,
        )
        raise PlacementError(
            receipt.reason_code,
            receipt.detail or receipt.reason_code,
            receipt,
            attempt_state=AttemptState.INSTRUMENT_FAILED,
            abort_campaign=abort_campaign,
        )

    session = PlacementSession(
        PlacementReceipt(
            selector=selector,
            platform=system,
            state=CapabilityState.AVAILABLE_UNQUALIFIED,
            authority=_platform_authority(system),
            requested=True,
            request_verified=True,
            requested_cpus=[cpu],
            accepted_cpus=accepted,
            original_cpus=original,
            reason_code="residency_pending",
            detail="Affinity request and readback agree; provider residency evidence is pending.",
        )
    )
    try:
        yield session
    finally:
        restored, restore_detail = _restore_affinity(process, original)
        if restored:
            session.receipt = _replace(session.receipt, restored=True)
        else:
            detail = restore_detail or "affinity restoration could not be verified"
            session.record_restore_failure(detail)
            raise PlacementError(
                session.receipt.reason_code,
                session.receipt.detail or session.receipt.reason_code,
                session.receipt,
                attempt_state=AttemptState.INSTRUMENT_FAILED,
                abort_campaign=True,
            )

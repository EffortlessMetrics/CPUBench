from __future__ import annotations

from typing import Any

import pytest

from cpubench.models import (
    AttemptRecord,
    AttemptState,
    CapabilityState,
    ImplementationPolicy,
    MachineReceipt,
    OperatingMode,
    PlacementReceipt,
    RunPlanItem,
    ValidityOutcome,
)
from cpubench.placement import PlacementError, placement_scope
from cpubench.validation import _evaluate_obligation


class FakeProcess:
    def __init__(self, affinity: list[int], *, readback: list[int] | None = None, restore_fails: bool = False) -> None:
        self.affinity = list(affinity)
        self.readback = readback
        self.restore_fails = restore_fails
        self.original = list(affinity)
        self.set_calls: list[list[int]] = []

    def cpu_affinity(self, value: list[int] | None = None) -> list[int]:
        if value is None:
            if self.readback is not None and self.set_calls and self.affinity != self.original:
                return list(self.readback)
            return list(self.affinity)
        if self.restore_fails and value == self.original and self.set_calls:
            raise OSError("restore failed")
        self.affinity = list(value)
        self.set_calls.append(list(value))
        return list(self.affinity)


def _patch_process(monkeypatch: pytest.MonkeyPatch, process: FakeProcess, system: str) -> None:
    monkeypatch.setattr("cpubench.placement.psutil.Process", lambda: process)
    monkeypatch.setattr("cpubench.placement.platform.system", lambda: system)


def _item(selector: str = "cpu:1") -> RunPlanItem:
    return RunPlanItem(
        attempt_id="placement-attempt",
        sequence_index=0,
        instrument_release_id="sha256:instrument",
        pack_release_id="sha256:pack",
        pack_id="memory-access",
        family_id="memory.dependent_load_latency",
        family_version="0.1.0",
        point_id="ws-32k",
        form_id="random_pointer_chase",
        provider_id="native-c11",
        parameters={"completed_units": 100},
        attempt_index=0,
        samples_per_attempt=1,
        warmup_samples=0,
        timeout_seconds=10.0,
        operating_mode=OperatingMode.CHARACTERIZATION,
        implementation_policy=ImplementationPolicy.NATIVE,
        placement=selector,
    )


def _machine() -> MachineReceipt:
    return MachineReceipt(
        system={"platform": "test"},
        cpu={"logical_processors": 2},
        topology={},
        memory={},
        runtime={},
        capabilities={},
    ).with_semantic_id()


def _attempt(receipt: PlacementReceipt) -> AttemptRecord:
    return AttemptRecord(
        attempt_id="placement-attempt",
        state=AttemptState.COMPLETED,
        family_id="memory.dependent_load_latency",
        point_id="ws-32k",
        provider_id="native-c11",
        requested_parameters={"completed_units": 100},
        placement=receipt,
    ).with_semantic_id()


def test_scheduler_open_never_claims_hard_affinity(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess([0, 1])
    _patch_process(monkeypatch, process, "Linux")

    with placement_scope("scheduler_open") as session:
        receipt = session.complete({"placement_start_cpu": 0, "placement_end_cpu": 1})

    assert receipt.selector == "scheduler_open"
    assert receipt.requested is False
    assert receipt.hard_affinity_verified is False
    assert receipt.state == CapabilityState.AVAILABLE_UNQUALIFIED
    assert receipt.observed_cpus == [0, 1]
    assert receipt.migrated is True
    assert process.set_calls == []


def test_linux_exact_cpu_requires_request_readback_and_residency(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess([0, 1])
    _patch_process(monkeypatch, process, "Linux")

    with placement_scope("cpu:1") as session:
        receipt = session.complete({"placement_start_cpu": 1, "placement_end_cpu": 1})

    assert receipt.state == CapabilityState.QUALIFIED
    assert receipt.request_verified is True
    assert receipt.residency_verified is True
    assert receipt.hard_affinity_verified is True
    assert receipt.accepted_cpus == [1]
    assert session.receipt.restored is True
    assert process.affinity == [0, 1]


def test_missing_residency_is_inconclusive_not_qualified(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess([0, 1])
    _patch_process(monkeypatch, process, "Linux")

    with placement_scope("cpu:1") as session:
        receipt = session.complete({})

    assert receipt.state == CapabilityState.AVAILABLE_UNQUALIFIED
    assert receipt.request_verified is True
    assert receipt.residency_verified is None
    assert receipt.hard_affinity_verified is False
    assert receipt.reason_code == "residency_evidence_incomplete"


def test_migrated_residency_fails_hard_affinity(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess([0, 1])
    _patch_process(monkeypatch, process, "Linux")

    with placement_scope("cpu:1") as session:
        receipt = session.complete({"placement_start_cpu": 1, "placement_end_cpu": 0})

    assert receipt.state == CapabilityState.FAILED
    assert receipt.migrated is True
    assert receipt.hard_affinity_verified is False
    assert receipt.reason_code == "residency_migrated"


def test_windows_process_affinity_remains_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess([0, 1])
    _patch_process(monkeypatch, process, "Windows")

    with placement_scope("cpu:1") as session:
        receipt = session.complete({"placement_start_cpu": 1, "placement_end_cpu": 1})

    assert receipt.request_verified is True
    assert receipt.residency_verified is True
    assert receipt.state == CapabilityState.AVAILABLE_UNQUALIFIED
    assert receipt.hard_affinity_verified is False
    assert receipt.reason_code == "windows_process_affinity_limited"


def test_readback_mismatch_is_instrument_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess([0, 1], readback=[0, 1])
    _patch_process(monkeypatch, process, "Linux")

    with pytest.raises(PlacementError) as raised:
        with placement_scope("cpu:1"):
            pass

    assert raised.value.reason_code == "affinity_readback_mismatch"
    assert raised.value.attempt_state == AttemptState.INSTRUMENT_FAILED
    assert raised.value.receipt.state == CapabilityState.FAILED


def test_unavailable_cpu_is_incompatible(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess([0, 1])
    _patch_process(monkeypatch, process, "Linux")

    with pytest.raises(PlacementError) as raised:
        with placement_scope("cpu:9"):
            pass

    assert raised.value.reason_code == "requested_cpu_unavailable"
    assert raised.value.attempt_state == AttemptState.INCOMPATIBLE


def test_negative_cpu_selector_is_incompatible(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess([0, 1])
    _patch_process(monkeypatch, process, "Linux")

    with pytest.raises(PlacementError) as raised:
        with placement_scope("cpu:-1"):
            pass

    assert raised.value.reason_code == "placement_cpu_invalid"
    assert raised.value.attempt_state == AttemptState.INCOMPATIBLE


def test_macos_exact_cpu_is_unsupported(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess([0, 1])
    _patch_process(monkeypatch, process, "Darwin")

    with pytest.raises(PlacementError) as raised:
        with placement_scope("cpu:1"):
            pass

    assert raised.value.reason_code == "hard_affinity_unsupported_macos"
    assert raised.value.attempt_state == AttemptState.UNSUPPORTED


def test_restore_failure_invalidates_placement(monkeypatch: pytest.MonkeyPatch) -> None:
    process = FakeProcess([0, 1], restore_fails=True)
    _patch_process(monkeypatch, process, "Linux")

    with placement_scope("cpu:1") as session:
        session.complete({"placement_start_cpu": 1, "placement_end_cpu": 1})

    assert session.receipt.state == CapabilityState.FAILED
    assert session.receipt.hard_affinity_verified is False
    assert session.receipt.restored is False
    assert session.receipt.reason_code == "affinity_restore_failed"


def test_hard_affinity_obligation_uses_typed_receipt() -> None:
    qualified = PlacementReceipt(
        selector="cpu:1",
        platform="linux",
        state=CapabilityState.QUALIFIED,
        authority="test",
        requested=True,
        request_verified=True,
        requested_cpus=[1],
        accepted_cpus=[1],
        observed_start_cpu=1,
        observed_end_cpu=1,
        residency_verified=True,
        hard_affinity_verified=True,
        reason_code="hard_affinity_qualified",
    )
    result = _evaluate_obligation(
        "placement.hard_affinity",
        _attempt(qualified),
        _item(),
        _machine(),
        {},
    )
    assert result.outcome == ValidityOutcome.PASS

    incomplete = qualified.model_copy(
        update={
            "state": CapabilityState.AVAILABLE_UNQUALIFIED,
            "residency_verified": None,
            "hard_affinity_verified": False,
            "reason_code": "residency_evidence_incomplete",
        }
    )
    result = _evaluate_obligation(
        "placement.hard_affinity",
        _attempt(PlacementReceipt.model_validate(incomplete.model_dump())),
        _item(),
        _machine(),
        {},
    )
    assert result.outcome == ValidityOutcome.INCONCLUSIVE


def test_legacy_untyped_receipt_is_not_promoted_to_qualified() -> None:
    receipt = PlacementReceipt.model_validate(
        {"selector": "cpu:1", "requested": True, "verified": True, "observed": [1]}
    )
    assert receipt.request_verified is True
    assert receipt.hard_affinity_verified is False
    assert receipt.state == CapabilityState.AVAILABLE_UNQUALIFIED
    assert receipt.reason_code == "legacy_residency_not_receipted"

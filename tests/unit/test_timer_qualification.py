from cpubench.models import (
    AttemptRecord,
    AttemptState,
    CapabilityEvidence,
    CapabilityState,
    ImplementationPolicy,
    MachineReceipt,
    OperatingMode,
    ProfileSpec,
    RunPlan,
    RunPlanItem,
    SampleRecord,
    ValidityOutcome,
)
from cpubench.validation import _derive_timer_qualifications, _timer_outcome


def _machine() -> MachineReceipt:
    return MachineReceipt(
        system={"platform": "test"},
        cpu={"logical_processors": 1},
        topology={},
        memory={},
        runtime={},
        capabilities={
            "timer.python_monotonic_ns": CapabilityEvidence(
                state=CapabilityState.AVAILABLE_UNQUALIFIED,
                authority="test",
            ),
            "timer.native_interval": CapabilityEvidence(
                state=CapabilityState.AVAILABLE_UNQUALIFIED,
                authority="test",
            ),
        },
    ).with_semantic_id()


def _profile(*, ratio: float = 100.0) -> ProfileSpec:
    return ProfileSpec(
        profile_id="timer-test",
        title="Timer test",
        attempts_per_point=1,
        samples_per_attempt=1,
        warmup_samples=0,
        unit_scale=1.0,
        timeout_seconds=10.0,
        minimum_timer_overhead_ratio=ratio,
    ).with_semantic_id()


def _item(attempt_id: str, family_id: str, point_id: str = "timer-control") -> RunPlanItem:
    return RunPlanItem(
        attempt_id=attempt_id,
        sequence_index=0,
        instrument_release_id="sha256:instrument",
        pack_release_id="sha256:pack",
        pack_id="controls",
        family_id=family_id,
        family_version="0.1.0",
        point_id=point_id,
        form_id="baseline",
        provider_id="python-control",
        parameters={"completed_units": 100},
        attempt_index=0,
        samples_per_attempt=1,
        warmup_samples=0,
        timeout_seconds=10.0,
        operating_mode=OperatingMode.CHARACTERIZATION,
        implementation_policy=ImplementationPolicy.NATIVE,
        placement="scheduler_open",
    )


def _plan(item: RunPlanItem) -> RunPlan:
    return RunPlan(
        campaign_id="timer-test",
        campaign_spec_id="sha256:campaign",
        instrument_release_id="sha256:instrument",
        pack_release_ids={"controls": "sha256:pack"},
        profile_id="sha256:profile",
        machine_receipt_id="sha256:machine",
        run_environment_receipt_id="sha256:environment",
        schedule_seed=1,
        items=[item],
    ).with_semantic_id()


def _attempt(
    attempt_id: str,
    *,
    timer: str = "python.time.monotonic_ns",
    elapsed_ns: int = 5_000,
    completed_units: int = 100,
    resolution_ns: int = 10,
    non_monotonic: int = 0,
    family_id: str = "controls.timer_overhead",
) -> AttemptRecord:
    return AttemptRecord(
        attempt_id=attempt_id,
        state=AttemptState.COMPLETED,
        family_id=family_id,
        point_id="timer-control",
        provider_id="python-control",
        samples=[
            SampleRecord(
                sample_index=0,
                elapsed_ns=elapsed_ns,
                completed_units=completed_units,
                checksum="timer-control",
                timer=timer,
                metrics={
                    "min_positive_delta_ns": resolution_ns,
                    "non_monotonic_count": non_monotonic,
                    "zero_delta_count": 0,
                },
            )
        ],
    ).with_semantic_id()


def test_timer_control_qualifies_and_derives_minimum_duration() -> None:
    item = _item("control", "controls.timer_overhead")
    qualifications = _derive_timer_qualifications(
        _plan(item),
        {"control": _attempt("control")},
        _profile(ratio=100.0),
        _machine(),
    )

    qualification = qualifications["python.time.monotonic_ns"]
    assert qualification.state == CapabilityState.QUALIFIED
    assert qualification.read_overhead_ns == 50.0
    assert qualification.effective_resolution_ns == 10
    assert qualification.minimum_sample_duration_ns == 5_000
    assert qualification.control_attempt_ids == ["control"]


def test_non_monotonic_timer_control_is_rejected() -> None:
    item = _item("control", "controls.timer_overhead")
    qualifications = _derive_timer_qualifications(
        _plan(item),
        {"control": _attempt("control", non_monotonic=1)},
        _profile(),
        _machine(),
    )

    qualification = qualifications["python.time.monotonic_ns"]
    assert qualification.state == CapabilityState.FAILED
    assert qualification.reason_code == "timer_non_monotonic_observation"


def test_sample_below_qualified_minimum_is_instrument_invalid() -> None:
    item = _item("control", "controls.timer_overhead")
    qualifications = _derive_timer_qualifications(
        _plan(item),
        {"control": _attempt("control", elapsed_ns=10_000)},
        _profile(ratio=100.0),
        _machine(),
    )
    target = _attempt(
        "target",
        elapsed_ns=1_000,
        completed_units=1,
        family_id="memory.dependent_load_latency",
    )

    outcome = _timer_outcome(target, _machine(), qualifications)

    assert outcome.outcome == ValidityOutcome.FAIL
    assert outcome.reason_code == "sample_below_minimum_timer_duration"


def test_timer_control_without_positive_delta_remains_unqualified() -> None:
    item = _item("control", "controls.timer_overhead")
    qualifications = _derive_timer_qualifications(
        _plan(item),
        {"control": _attempt("control", resolution_ns=0)},
        _profile(),
        _machine(),
    )

    qualification = qualifications["python.time.monotonic_ns"]
    assert qualification.state == CapabilityState.AVAILABLE_UNQUALIFIED
    assert qualification.reason_code == "timer_positive_resolution_not_observed"


def test_failed_timer_control_blocks_qualification() -> None:
    valid_item = _item("control-valid", "controls.timer_overhead").model_copy(update={"sequence_index": 0})
    failed_item = _item("control-failed", "controls.timer_overhead").model_copy(update={"sequence_index": 1})
    plan = RunPlan(
        campaign_id="timer-test",
        campaign_spec_id="sha256:campaign",
        instrument_release_id="sha256:instrument",
        pack_release_ids={"controls": "sha256:pack"},
        profile_id="sha256:profile",
        machine_receipt_id="sha256:machine",
        run_environment_receipt_id="sha256:environment",
        schedule_seed=1,
        items=[valid_item, failed_item],
    ).with_semantic_id()
    failed = AttemptRecord(
        attempt_id="control-failed",
        state=AttemptState.EXECUTION_FAILED,
        family_id="controls.timer_overhead",
        point_id="timer-control",
        provider_id="python-control",
        provider_stdout='{"record_type":"metadata","timer":"python.time.monotonic_ns"}\n',
        reason_code="provider_nonzero_exit",
    ).with_semantic_id()

    qualifications = _derive_timer_qualifications(
        plan,
        {
            "control-valid": _attempt("control-valid"),
            "control-failed": failed,
        },
        _profile(),
        _machine(),
    )

    qualification = qualifications["python.time.monotonic_ns"]
    assert qualification.state == CapabilityState.FAILED
    assert qualification.reason_code == "timer_control_attempt_failed"
    assert qualification.failed_control_attempt_ids == ["control-failed"]
    assert qualification.control_attempt_ids == ["control-failed", "control-valid"]


def test_invalid_timer_control_work_does_not_set_threshold() -> None:
    item = _item("control", "controls.timer_overhead")
    qualifications = _derive_timer_qualifications(
        _plan(item),
        {"control": _attempt("control", completed_units=10_000)},
        _profile(),
        _machine(),
    )

    qualification = qualifications["python.time.monotonic_ns"]
    assert qualification.state == CapabilityState.FAILED
    assert qualification.reason_code == "timer_control_work_invalid"
    assert qualification.invalid_control_attempt_ids == ["control"]
    assert qualification.read_overhead_ns is None
    assert qualification.minimum_sample_duration_ns is None


def test_profile_rejects_unbounded_timer_ratio() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _profile(ratio=float("inf"))
    with pytest.raises(ValidationError):
        _profile(ratio=1_000_001.0)


def test_python_timer_control_detects_reversal_between_pairs(monkeypatch: object, capsys: object) -> None:
    import json

    from cpubench.providers import control

    readings = iter([100, 110, 120, 90, 100, 130])
    monkeypatch.setattr(control.time, "monotonic_ns", lambda: next(readings))  # type: ignore[attr-defined]

    assert control.run_timer_overhead(samples=1, warmups=0, completed_units=2) == 0
    output = capsys.readouterr().out.splitlines()  # type: ignore[attr-defined]
    sample = json.loads(output[-1])
    assert sample["non_monotonic_count"] == 1


def test_python_timer_control_rejects_reversed_outer_interval(monkeypatch: object, capsys: object) -> None:
    from cpubench.providers import control

    readings = iter([100, 110, 120, 90])
    monkeypatch.setattr(control.time, "monotonic_ns", lambda: next(readings))  # type: ignore[attr-defined]

    assert control.run_timer_overhead(samples=1, warmups=0, completed_units=1) == 3
    assert "outer interval reversed" in capsys.readouterr().err  # type: ignore[attr-defined]


def test_python_timer_control_carries_warmup_reversal(monkeypatch: object, capsys: object) -> None:
    import json

    from cpubench.providers import control

    readings = iter([
        100, 110, 90, 120,  # warmup: reversal within the pair
        130, 140, 150, 160,  # retained sample: monotonic
    ])
    monkeypatch.setattr(control.time, "monotonic_ns", lambda: next(readings))  # type: ignore[attr-defined]

    assert control.run_timer_overhead(samples=1, warmups=1, completed_units=1) == 0
    output = capsys.readouterr().out.splitlines()  # type: ignore[attr-defined]
    sample = json.loads(output[-1])
    assert sample["non_monotonic_count"] == 1


def test_timer_failure_precedes_unmapped_timer_regardless_of_iteration_order() -> None:
    control_item = _item("control", "controls.timer_overhead")
    qualifications = _derive_timer_qualifications(
        _plan(control_item),
        {"control": _attempt("control", elapsed_ns=10_000)},
        _profile(ratio=100.0),
        _machine(),
    )
    target = _attempt(
        "target",
        timer="unmapped.timer",
        elapsed_ns=10_000,
        completed_units=1,
        family_id="memory.dependent_load_latency",
    )
    target = target.model_copy(
        update={
            "samples": [
                target.samples[0],
                target.samples[0].model_copy(
                    update={
                        "sample_index": 1,
                        "timer": "python.time.monotonic_ns",
                        "elapsed_ns": 1_000,
                    }
                ),
            ],
            "semantic_id": None,
        }
    ).with_semantic_id()

    outcome = _timer_outcome(target, _machine(), qualifications)

    assert outcome.outcome == ValidityOutcome.FAIL
    assert outcome.reason_code == "sample_below_minimum_timer_duration"

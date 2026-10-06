from pathlib import Path

import pytest
import yaml

from cpubench.analysis import analyze_campaign
from cpubench.campaign import execute_campaign, finalize_campaign, persist_runtime, prepare_runtime
from cpubench.evidence import CampaignStore
from cpubench.models import (
    AttemptRecord,
    CapabilityState,
    InstrumentRelease,
    PackRelease,
    PlacementReceipt,
    ProfileSpec,
    RunPlan,
)
from cpubench.report import generate_report
from cpubench.validation import validate_campaign


def test_control_only_campaign_end_to_end(tmp_path: Path) -> None:
    campaign_file = tmp_path / "campaign.yaml"
    campaign_file.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "artifact_kind": "campaign_spec",
                "campaign_id": "e2e",
                "title": "E2E",
                "description": "Control-only end-to-end test.",
                "profile": "profiles/smoke.yaml",
                "packs": [{"pack": "packs/controls/pack.yaml"}],
                "operating_mode": "characterization",
                "implementation_policy": "native",
                "placement": "scheduler_open",
                "output_root": str(tmp_path / "runs"),
                "schedule_seed": 1,
                "public_claims_enabled": False,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    runtime = prepare_runtime(campaign_file, resume=True)
    persist_runtime(runtime)
    instrument = InstrumentRelease.model_validate_json(
        (runtime.store.root / "instrument-release.json").read_text(encoding="utf-8")
    )
    plan = RunPlan.model_validate_json((runtime.store.root / "run-plan.json").read_text(encoding="utf-8"))
    pack_release = PackRelease.model_validate_json(
        (runtime.store.root / "pack-releases" / "controls" / "release.json").read_text(encoding="utf-8")
    )
    assert plan.instrument_release_id == instrument.semantic_id
    assert plan.pack_release_ids["controls"] == pack_release.semantic_id
    counts = execute_campaign(runtime)
    assert counts["completed"] == len(runtime.plan.items)
    resumed = prepare_runtime(campaign_file, resume=True)
    persist_runtime(resumed)
    resumed_counts = execute_campaign(resumed, resume=True)
    assert resumed_counts["completed"] == len(runtime.plan.items)
    validation = validate_campaign(runtime.store.root)
    assert validation.coverage["completed"] == len(runtime.plan.items)
    assert "python.time.monotonic_ns" in validation.timer_qualifications
    assert any(
        timer in validation.timer_qualifications
        for timer in {"CLOCK_MONOTONIC_RAW", "CLOCK_MONOTONIC", "QueryPerformanceCounter"}
    )
    for qualification in validation.timer_qualifications.values():
        assert qualification.control_attempt_ids
        if qualification.state == CapabilityState.QUALIFIED:
            assert qualification.read_overhead_ns is not None
            assert qualification.effective_resolution_ns is not None
            assert qualification.minimum_sample_duration_ns is not None
        elif qualification.state == CapabilityState.AVAILABLE_UNQUALIFIED:
            assert qualification.reason_code in {
                "timer_positive_resolution_not_observed",
                "timer_read_overhead_not_observed",
            }
        elif qualification.state == CapabilityState.FAILED:
            assert (
                qualification.non_monotonic_observations > 0
                or qualification.failed_control_attempt_ids
                or qualification.invalid_control_attempt_ids
            )
        else:
            pytest.fail(f"unexpected timer qualification state: {qualification.state}")
    analysis = analyze_campaign(runtime.store.root)
    assert analysis.points
    report = generate_report(runtime.store.root)
    assert report.exists()
    assert "Timer qualification" in report.read_text(encoding="utf-8")
    attempt_path = next((runtime.store.root / "attempts").glob("*/attempt.json"))
    stored_attempt = AttemptRecord.model_validate_json(attempt_path.read_text(encoding="utf-8"))
    recomputed = stored_attempt.model_copy(update={"semantic_id": None}).with_semantic_id()
    assert stored_attempt.semantic_id == recomputed.semantic_id
    assert stored_attempt.placement.selector == "scheduler_open"
    assert stored_attempt.run_environment_receipt_id
    environment_digest = stored_attempt.run_environment_receipt_id.split(":", 1)[-1]
    assert (runtime.store.root / "run-environments" / f"{environment_digest}.json").exists()
    finalize_campaign(runtime.store.root)
    assert CampaignStore(runtime.store.root).verify().valid


def test_work_correct_view_is_usable_without_measurement_requirements(tmp_path: Path) -> None:
    campaign_file = tmp_path / "campaign.yaml"
    campaign_file.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "artifact_kind": "campaign_spec",
                "campaign_id": "work-view",
                "title": "Work view",
                "description": "Validate the work-only projection.",
                "profile": "profiles/smoke.yaml",
                "packs": [{"pack": "packs/controls/pack.yaml"}],
                "operating_mode": "characterization",
                "implementation_policy": "native",
                "placement": "scheduler_open",
                "output_root": str(tmp_path / "work-runs"),
                "schedule_seed": 2,
                "public_claims_enabled": False,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    runtime = prepare_runtime(campaign_file, resume=True)
    persist_runtime(runtime)
    execute_campaign(runtime)
    validation = validate_campaign(runtime.store.root, validity_view="work_correct")
    assert all(item.comparability.value == "pass" for item in validation.attempts)


def test_campaign_finalization_rejects_incomplete_bundle(tmp_path: Path) -> None:
    campaign_file = tmp_path / "incomplete.yaml"
    campaign_file.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "artifact_kind": "campaign_spec",
                "campaign_id": "incomplete",
                "title": "Incomplete",
                "description": "Finalization must fail before execution and derived evidence.",
                "profile": "profiles/smoke.yaml",
                "packs": [{"pack": "packs/controls/pack.yaml"}],
                "operating_mode": "characterization",
                "implementation_policy": "native",
                "placement": "scheduler_open",
                "output_root": str(tmp_path / "incomplete-runs"),
                "schedule_seed": 3,
                "public_claims_enabled": False,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    runtime = prepare_runtime(campaign_file, resume=True)
    persist_runtime(runtime)
    try:
        finalize_campaign(runtime.store.root)
    except RuntimeError as exc:
        assert "required artifacts are missing" in str(exc)
    else:
        raise AssertionError("incomplete campaign unexpectedly finalized")


def test_resume_rejects_changed_machine_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    campaign_file = tmp_path / "machine-change.yaml"
    campaign_file.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "artifact_kind": "campaign_spec",
                "campaign_id": "machine-change",
                "title": "Machine change",
                "description": "Resume must not cross machine identity.",
                "profile": "profiles/smoke.yaml",
                "packs": [{"pack": "packs/controls/pack.yaml"}],
                "operating_mode": "characterization",
                "implementation_policy": "native",
                "placement": "scheduler_open",
                "output_root": str(tmp_path / "machine-change-runs"),
                "schedule_seed": 4,
                "public_claims_enabled": False,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    runtime = prepare_runtime(campaign_file, resume=True)
    persist_runtime(runtime)
    original = runtime.machine
    changed = original.model_copy(
        update={
            "cpu": {**original.cpu, "processor": "different-test-processor"},
            "semantic_id": None,
        }
    ).with_semantic_id()
    monkeypatch.setattr("cpubench.campaign.collect_machine_receipt", lambda: changed)
    with pytest.raises(RuntimeError, match="current machine identity differs"):
        prepare_runtime(campaign_file, resume=True)


def test_finalization_rejects_attempt_that_differs_from_plan(tmp_path: Path) -> None:
    campaign_file = tmp_path / "tampered.yaml"
    campaign_file.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "artifact_kind": "campaign_spec",
                "campaign_id": "tampered",
                "title": "Tampered",
                "description": "Attempt records must remain joined to the frozen plan.",
                "profile": "profiles/smoke.yaml",
                "packs": [{"pack": "packs/controls/pack.yaml"}],
                "operating_mode": "characterization",
                "implementation_policy": "native",
                "placement": "scheduler_open",
                "output_root": str(tmp_path / "tampered-runs"),
                "schedule_seed": 5,
                "public_claims_enabled": False,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    runtime = prepare_runtime(campaign_file, resume=True)
    persist_runtime(runtime)
    execute_campaign(runtime)
    validate_campaign(runtime.store.root)
    analyze_campaign(runtime.store.root)
    generate_report(runtime.store.root)

    attempt_path = next((runtime.store.root / "attempts").glob("*/attempt.json"))
    attempt = AttemptRecord.model_validate_json(attempt_path.read_text(encoding="utf-8"))
    tampered = attempt.model_copy(
        update={
            "requested_parameters": {**attempt.requested_parameters, "tampered": True},
            "semantic_id": None,
        }
    ).with_semantic_id()
    attempt_path.write_text(tampered.model_dump_json(indent=2), encoding="utf-8")

    with pytest.raises(RuntimeError, match="attempt record differs from frozen plan"):
        finalize_campaign(runtime.store.root)


def _write_profile_policy_campaign(tmp_path: Path, campaign_id: str) -> Path:
    campaign_file = tmp_path / f"{campaign_id}.yaml"
    campaign_file.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "artifact_kind": "campaign_spec",
                "campaign_id": campaign_id,
                "title": "Profile policy binding",
                "description": "Reject changed validation policy.",
                "profile": "profiles/smoke.yaml",
                "packs": [{"pack": "packs/controls/pack.yaml"}],
                "operating_mode": "characterization",
                "implementation_policy": "native",
                "placement": "scheduler_open",
                "output_root": str(tmp_path / "runs"),
                "schedule_seed": 1,
                "public_claims_enabled": False,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return campaign_file


def test_validation_rejects_profile_that_differs_from_frozen_plan(tmp_path: Path) -> None:
    runtime = prepare_runtime(_write_profile_policy_campaign(tmp_path, "profile-binding"), resume=True)
    persist_runtime(runtime)
    profile_path = runtime.store.root / "profile.json"
    profile = ProfileSpec.model_validate_json(profile_path.read_text(encoding="utf-8"))
    changed = profile.model_copy(
        update={
            "minimum_timer_overhead_ratio": profile.minimum_timer_overhead_ratio + 10.0,
            "semantic_id": None,
        }
    ).with_semantic_id()
    profile_path.write_text(changed.model_dump_json(exclude_none=True, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="profile does not match the frozen run plan"):
        validate_campaign(runtime.store.root)


def test_validation_rejects_profile_with_stale_semantic_identity(tmp_path: Path) -> None:
    runtime = prepare_runtime(_write_profile_policy_campaign(tmp_path, "profile-tamper"), resume=True)
    persist_runtime(runtime)
    profile_path = runtime.store.root / "profile.json"
    profile = ProfileSpec.model_validate_json(profile_path.read_text(encoding="utf-8"))
    stale = profile.model_copy(
        update={"minimum_timer_overhead_ratio": profile.minimum_timer_overhead_ratio + 10.0}
    )
    profile_path.write_text(stale.model_dump_json(exclude_none=True, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="profile semantic identity"):
        validate_campaign(runtime.store.root)


def test_finalization_rejects_tampered_placement_receipt(tmp_path: Path) -> None:
    runtime = prepare_runtime(_write_profile_policy_campaign(tmp_path, "placement-tamper"), resume=True)
    persist_runtime(runtime)
    execute_campaign(runtime)
    validate_campaign(runtime.store.root)
    analyze_campaign(runtime.store.root)
    generate_report(runtime.store.root)

    placement_path = next((runtime.store.root / "attempts").glob("*/placement.json"))
    placement = PlacementReceipt.model_validate_json(placement_path.read_text(encoding="utf-8"))
    tampered = placement.model_copy(update={"detail": "tampered placement receipt"})
    placement_path.write_text(tampered.model_dump_json(exclude_none=True, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="attempt placement receipt mismatch"):
        finalize_campaign(runtime.store.root)

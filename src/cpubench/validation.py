from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
import math
from pathlib import Path
from statistics import median

from .evidence import CampaignStore
from .models import (
    AttemptRecord,
    AttemptState,
    AttemptValidation,
    CapabilityState,
    FamilySpec,
    MachineReceipt,
    ObligationResult,
    ProfileSpec,
    RunPlan,
    RunPlanItem,
    TimerQualification,
    ValidationBundle,
    ValidityOutcome,
)

VALIDITY_VIEWS = {
    "work_correct",
    "portable_elapsed",
    "pinned_characterization",
    "mechanism_diagnostic",
    "product_native",
}


def _load_families(campaign_dir: Path) -> dict[str, FamilySpec]:
    families: dict[str, FamilySpec] = {}
    for path in (campaign_dir / "pack-releases").glob("*/families/*.json"):
        family = FamilySpec.model_validate_json(path.read_text(encoding="utf-8"))
        families[family.family_id] = family
    return families


def _load_attempts(campaign_dir: Path) -> dict[str, AttemptRecord]:
    attempts: dict[str, AttemptRecord] = {}
    for path in (campaign_dir / "attempts").glob("*/attempt.json"):
        attempt = AttemptRecord.model_validate_json(path.read_text(encoding="utf-8"))
        attempts[attempt.attempt_id] = attempt
    return attempts


def _result(obligation_id: str, outcome: ValidityOutcome, reason: str, detail: str | None = None) -> ObligationResult:
    return ObligationResult(obligation_id=obligation_id, outcome=outcome, reason_code=reason, detail=detail)


def _machine_timer_capability(timer: str, machine: MachineReceipt) -> CapabilityState | None:
    if timer == "python.time.monotonic_ns":
        capability = machine.capabilities.get("timer.python_monotonic_ns")
    elif timer in {"CLOCK_MONOTONIC_RAW", "CLOCK_MONOTONIC", "QueryPerformanceCounter"}:
        capability = machine.capabilities.get("timer.native_interval")
    else:
        return None
    return capability.state if capability is not None else None


@dataclass
class _TimerObservations:
    attempt_ids: list[str] = field(default_factory=list)
    read_overheads: list[float] = field(default_factory=list)
    resolutions: list[int] = field(default_factory=list)
    observations: int = 0
    non_monotonic: int = 0
    zero_delta: int = 0


def _derive_timer_qualifications(
    plan: RunPlan,
    attempts: dict[str, AttemptRecord],
    profile: ProfileSpec,
    machine: MachineReceipt,
) -> dict[str, TimerQualification]:
    controls: dict[str, _TimerObservations] = defaultdict(_TimerObservations)
    control_families = {"controls.timer_overhead", "controls.native_timer_overhead"}
    for item in plan.items:
        if item.family_id not in control_families:
            continue
        attempt = attempts.get(item.attempt_id)
        if attempt is None or attempt.state != AttemptState.COMPLETED:
            continue
        timers = {sample.timer for sample in attempt.samples if sample.timer and sample.timer != "unknown"}
        for timer in timers:
            bucket = controls[timer]
            bucket.attempt_ids.append(attempt.attempt_id)
            for sample in attempt.samples:
                if sample.timer != timer:
                    continue
                bucket.read_overheads.append(sample.elapsed_ns / sample.completed_units)
                resolution = int(sample.metrics.get("min_positive_delta_ns", 0))
                if resolution > 0:
                    bucket.resolutions.append(resolution)
                bucket.observations += sample.completed_units
                bucket.non_monotonic += int(sample.metrics.get("non_monotonic_count", 0))
                bucket.zero_delta += int(sample.metrics.get("zero_delta_count", 0))

    result: dict[str, TimerQualification] = {}
    for timer, bucket in controls.items():
        read_overheads = bucket.read_overheads
        resolutions = bucket.resolutions
        non_monotonic = bucket.non_monotonic
        machine_state = _machine_timer_capability(timer, machine)
        read_overhead = median(read_overheads) if read_overheads else None
        effective_resolution = min(resolutions) if resolutions else None
        minimum_duration = None
        if read_overhead is not None and effective_resolution is not None:
            minimum_duration = max(
                1,
                math.ceil(max(read_overhead, float(effective_resolution)) * profile.minimum_timer_overhead_ratio),
            )

        if machine_state in {CapabilityState.FAILED, CapabilityState.UNSUPPORTED}:
            state = machine_state
            reason_code = "machine_timer_capability_rejected"
        elif non_monotonic > 0:
            state = CapabilityState.FAILED
            reason_code = "timer_non_monotonic_observation"
        elif effective_resolution is None:
            state = CapabilityState.AVAILABLE_UNQUALIFIED
            reason_code = "timer_positive_resolution_not_observed"
        elif read_overhead is None:
            state = CapabilityState.AVAILABLE_UNQUALIFIED
            reason_code = "timer_read_overhead_not_observed"
        else:
            state = CapabilityState.QUALIFIED
            reason_code = "timer_control_qualified"

        result[timer] = TimerQualification(
            timer=timer,
            state=state,
            control_attempt_ids=sorted(set(bucket.attempt_ids)),
            observations=bucket.observations,
            non_monotonic_observations=non_monotonic,
            zero_delta_observations=bucket.zero_delta,
            read_overhead_ns=read_overhead,
            effective_resolution_ns=effective_resolution,
            minimum_sample_duration_ns=minimum_duration,
            overhead_ratio=profile.minimum_timer_overhead_ratio,
            reason_code=reason_code,
            detail=(
                f"read_overhead_ns={read_overhead}; effective_resolution_ns={effective_resolution}; "
                f"minimum_sample_duration_ns={minimum_duration}"
            ),
        )
    return result


def _timer_outcome(
    attempt: AttemptRecord,
    machine: MachineReceipt,
    qualifications: dict[str, TimerQualification],
) -> ObligationResult:
    obligation_id = "instrument.timer_qualified"
    timers = {sample.timer for sample in attempt.samples}
    if not timers or "unknown" in timers:
        return _result(obligation_id, ValidityOutcome.FAIL, "sample_timer_unknown")

    for timer in timers:
        qualification = qualifications.get(timer)
        if qualification is None:
            state = _machine_timer_capability(timer, machine)
            if state is None:
                return _result(obligation_id, ValidityOutcome.INCONCLUSIVE, "sample_timer_not_mapped", f"timer={timer}")
            if state == CapabilityState.FAILED:
                return _result(obligation_id, ValidityOutcome.FAIL, "timer_capability_failed", f"timer={timer}")
            if state in {CapabilityState.UNSUPPORTED, CapabilityState.UNKNOWN}:
                return _result(obligation_id, ValidityOutcome.UNSUPPORTED, "timer_capability_unsupported", f"timer={timer}")
            return _result(
                obligation_id,
                ValidityOutcome.INCONCLUSIVE,
                "timer_control_missing",
                f"timer={timer}; run the matching timer-overhead control in the same campaign",
            )
        if qualification.state == CapabilityState.FAILED:
            return _result(obligation_id, ValidityOutcome.FAIL, qualification.reason_code, qualification.detail)
        if qualification.state in {CapabilityState.UNSUPPORTED, CapabilityState.UNKNOWN}:
            return _result(obligation_id, ValidityOutcome.UNSUPPORTED, qualification.reason_code, qualification.detail)
        if qualification.state == CapabilityState.AVAILABLE_UNQUALIFIED:
            return _result(obligation_id, ValidityOutcome.INCONCLUSIVE, qualification.reason_code, qualification.detail)
        if attempt.family_id in {"controls.timer_overhead", "controls.native_timer_overhead"}:
            # Calibration controls measure the threshold; applying that threshold
            # back to the controls would make the qualification self-referential.
            continue
        minimum = qualification.minimum_sample_duration_ns
        if minimum is None:
            return _result(obligation_id, ValidityOutcome.INCONCLUSIVE, "timer_minimum_duration_missing")
        too_short = [sample.elapsed_ns for sample in attempt.samples if sample.timer == timer and sample.elapsed_ns < minimum]
        if too_short:
            return _result(
                obligation_id,
                ValidityOutcome.FAIL,
                "sample_below_minimum_timer_duration",
                f"timer={timer}; minimum_ns={minimum}; observed_ns={too_short}",
            )
    return _result(obligation_id, ValidityOutcome.PASS, "timer_control_qualified")


def _evaluate_obligation(
    obligation_id: str,
    attempt: AttemptRecord,
    item: RunPlanItem,
    machine: MachineReceipt,
    timer_qualifications: dict[str, TimerQualification],
) -> ObligationResult:
    if obligation_id == "work.completed_units":
        if not attempt.samples:
            return _result(obligation_id, ValidityOutcome.FAIL, "completed_units_missing")
        expected = item.parameters.get("completed_units")
        values = [sample.completed_units for sample in attempt.samples]
        if any(value <= 0 for value in values):
            return _result(obligation_id, ValidityOutcome.FAIL, "completed_units_zero")
        if expected is not None and any(value != int(expected) for value in values):
            return _result(
                obligation_id,
                ValidityOutcome.FAIL,
                "completed_units_mismatch",
                f"expected={expected}; observed={values}",
            )
        return _result(obligation_id, ValidityOutcome.PASS, "completed_units_match")

    if obligation_id == "work.output_checksum":
        checksums = [sample.checksum for sample in attempt.samples]
        if checksums and all(checksum and checksum.lower() not in {"invalid", "none"} for checksum in checksums):
            return _result(obligation_id, ValidityOutcome.PASS, "checksum_present")
        return _result(obligation_id, ValidityOutcome.FAIL, "checksum_missing")

    if obligation_id == "work.valid_cycle":
        value = attempt.effective_parameters.get("cycle_validated")
        if value is True:
            return _result(obligation_id, ValidityOutcome.PASS, "provider_cycle_validated")
        return _result(obligation_id, ValidityOutcome.INCONCLUSIVE, "cycle_validation_not_receipted")

    if obligation_id == "work.disjoint_chains":
        value = attempt.effective_parameters.get("disjoint_chains")
        if value is True:
            return _result(obligation_id, ValidityOutcome.PASS, "provider_disjoint_chains_validated")
        return _result(obligation_id, ValidityOutcome.INCONCLUSIVE, "disjoint_chain_validation_not_receipted")

    if obligation_id == "work.database_validated":
        value = attempt.effective_parameters.get("database_validated")
        if value is True:
            return _result(obligation_id, ValidityOutcome.PASS, "provider_database_population_validated")
        return _result(obligation_id, ValidityOutcome.INCONCLUSIVE, "database_validation_not_receipted")

    if obligation_id == "timing.setup_excluded":
        value = attempt.effective_parameters.get("setup_excluded")
        if value is True:
            return _result(obligation_id, ValidityOutcome.PASS, "provider_setup_boundary_receipted")
        return _result(obligation_id, ValidityOutcome.INCONCLUSIVE, "setup_boundary_not_receipted")

    if obligation_id == "instrument.timer_qualified":
        return _timer_outcome(attempt, machine, timer_qualifications)

    if obligation_id == "placement.hard_affinity":
        if attempt.placement.get("verified") is True:
            return _result(obligation_id, ValidityOutcome.PASS, "affinity_mask_verified")
        if attempt.placement.get("selector") == "scheduler_open":
            return _result(obligation_id, ValidityOutcome.UNSUPPORTED, "scheduler_open_by_design")
        return _result(obligation_id, ValidityOutcome.FAIL, "placement_not_verified")

    return _result(obligation_id, ValidityOutcome.INCONCLUSIVE, "validator_not_implemented")


def _aggregate_outcome(outcomes: Iterable[ValidityOutcome]) -> ValidityOutcome:
    values = list(outcomes)
    if any(value == ValidityOutcome.FAIL for value in values):
        return ValidityOutcome.FAIL
    if any(value == ValidityOutcome.INCONCLUSIVE for value in values):
        return ValidityOutcome.INCONCLUSIVE
    if any(value == ValidityOutcome.UNSUPPORTED for value in values):
        return ValidityOutcome.UNSUPPORTED
    if values and all(value == ValidityOutcome.PASS for value in values):
        return ValidityOutcome.PASS
    return ValidityOutcome.NOT_EVALUATED


def _view_measurement_ids(family: FamilySpec, validity_view: str) -> set[str]:
    if validity_view == "work_correct":
        return set()
    ids = {key for key in family.obligations if key.startswith(("timing.", "instrument."))}
    if validity_view in {"pinned_characterization", "mechanism_diagnostic"}:
        ids.update(key for key in family.obligations if key.startswith("placement."))
    if validity_view == "mechanism_diagnostic":
        ids.update(key for key in family.obligations if key.startswith("diagnostic."))
    return ids


def _comparability(
    validity_view: str,
    work_outcome: ValidityOutcome,
    measurement_outcome: ValidityOutcome,
) -> ValidityOutcome:
    if validity_view == "work_correct":
        return work_outcome
    if work_outcome == ValidityOutcome.PASS and measurement_outcome == ValidityOutcome.PASS:
        return ValidityOutcome.PASS
    if ValidityOutcome.FAIL in {work_outcome, measurement_outcome}:
        return ValidityOutcome.FAIL
    if ValidityOutcome.INCONCLUSIVE in {work_outcome, measurement_outcome}:
        return ValidityOutcome.INCONCLUSIVE
    if ValidityOutcome.UNSUPPORTED in {work_outcome, measurement_outcome}:
        return ValidityOutcome.UNSUPPORTED
    return ValidityOutcome.NOT_EVALUATED


def validate_campaign(campaign_dir: Path, *, validity_view: str = "portable_elapsed") -> ValidationBundle:
    if validity_view not in VALIDITY_VIEWS:
        raise ValueError(f"unknown validity view: {validity_view}; choose from {sorted(VALIDITY_VIEWS)}")

    campaign_dir = campaign_dir.resolve()
    plan = RunPlan.model_validate_json((campaign_dir / "run-plan.json").read_text(encoding="utf-8"))
    machine = MachineReceipt.model_validate_json((campaign_dir / "machine-receipt.json").read_text(encoding="utf-8"))
    profile = ProfileSpec.model_validate_json((campaign_dir / "profile.json").read_text(encoding="utf-8"))
    families = _load_families(campaign_dir)
    attempts = _load_attempts(campaign_dir)
    timer_qualifications = _derive_timer_qualifications(plan, attempts, profile, machine)

    validations: list[AttemptValidation] = []
    coverage: dict[str, int] = {}

    for item in plan.items:
        attempt = attempts.get(item.attempt_id)
        if attempt is None:
            validations.append(
                AttemptValidation(
                    attempt_id=item.attempt_id,
                    work_validity=ValidityOutcome.NOT_EVALUATED,
                    measurement_validity=ValidityOutcome.NOT_EVALUATED,
                    comparability=ValidityOutcome.NOT_EVALUATED,
                    obligations=[],
                )
            )
            coverage["missing_attempt"] = coverage.get("missing_attempt", 0) + 1
            continue

        coverage[attempt.state.value] = coverage.get(attempt.state.value, 0) + 1
        if attempt.state != AttemptState.COMPLETED:
            outcome = (
                ValidityOutcome.UNSUPPORTED
                if attempt.state in {AttemptState.UNSUPPORTED, AttemptState.INCOMPATIBLE}
                else ValidityOutcome.NOT_EVALUATED
            )
            validations.append(
                AttemptValidation(
                    attempt_id=item.attempt_id,
                    work_validity=outcome,
                    measurement_validity=outcome,
                    comparability=outcome,
                    obligations=[],
                )
            )
            continue

        family = families[item.family_id]
        obligation_results = [
            _evaluate_obligation(obligation_id, attempt, item, machine, timer_qualifications)
            for obligation_id in family.obligations
        ]

        work_ids = {key for key in family.obligations if key.startswith("work.")}
        measurement_ids = _view_measurement_ids(family, validity_view)

        work_outcome = _aggregate_outcome(
            result.outcome for result in obligation_results if result.obligation_id in work_ids
        )
        measurement_outcome = (
            ValidityOutcome.NOT_EVALUATED
            if not measurement_ids
            else _aggregate_outcome(
                result.outcome for result in obligation_results if result.obligation_id in measurement_ids
            )
        )

        validations.append(
            AttemptValidation(
                attempt_id=item.attempt_id,
                work_validity=work_outcome,
                measurement_validity=measurement_outcome,
                comparability=_comparability(validity_view, work_outcome, measurement_outcome),
                obligations=obligation_results,
            )
        )

    bundle = ValidationBundle(
        campaign_id=plan.campaign_id,
        run_plan_id=plan.semantic_id or "",
        validity_view=validity_view,
        attempts=validations,
        coverage=coverage,
        timer_qualifications=timer_qualifications,
    ).with_semantic_id()
    CampaignStore(campaign_dir).write_json(
        "validation/validation-bundle.json",
        bundle.model_dump(mode="json", exclude_none=True),
    )
    return bundle

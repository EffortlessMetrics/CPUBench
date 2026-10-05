from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .evidence import CampaignStore
from .models import (
    AttemptRecord,
    AttemptState,
    AttemptValidation,
    CapabilityState,
    FamilySpec,
    MachineReceipt,
    ObligationResult,
    RunPlan,
    RunPlanItem,
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


def _timer_outcome(attempt: AttemptRecord, machine: MachineReceipt) -> ObligationResult:
    obligation_id = "instrument.timer_qualified"
    timers = {sample.timer for sample in attempt.samples}
    if not timers or "unknown" in timers:
        return _result(obligation_id, ValidityOutcome.FAIL, "sample_timer_unknown")

    python_capability = machine.capabilities.get("timer.python_monotonic_ns")
    native_capability = machine.capabilities.get("timer.native_interval")
    for timer in timers:
        if timer == "python.time.monotonic_ns":
            capability = python_capability
        elif timer in {"CLOCK_MONOTONIC_RAW", "CLOCK_MONOTONIC", "QueryPerformanceCounter"}:
            capability = native_capability
        else:
            return _result(
                obligation_id,
                ValidityOutcome.INCONCLUSIVE,
                "sample_timer_not_mapped",
                f"timer={timer}",
            )
        if capability is None:
            return _result(obligation_id, ValidityOutcome.FAIL, "timer_capability_missing", f"timer={timer}")
        if capability.state == CapabilityState.FAILED:
            return _result(obligation_id, ValidityOutcome.FAIL, "timer_capability_failed", capability.detail)
        if capability.state in {CapabilityState.UNSUPPORTED, CapabilityState.UNKNOWN}:
            return _result(obligation_id, ValidityOutcome.UNSUPPORTED, "timer_capability_unsupported", capability.detail)
        if capability.state == CapabilityState.AVAILABLE_UNQUALIFIED:
            return _result(
                obligation_id,
                ValidityOutcome.INCONCLUSIVE,
                "timer_available_unqualified",
                f"timer={timer}; {capability.detail or ''}",
            )
    return _result(obligation_id, ValidityOutcome.PASS, "timer_qualified")


def _evaluate_obligation(
    obligation_id: str,
    attempt: AttemptRecord,
    item: RunPlanItem,
    machine: MachineReceipt,
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
        return _timer_outcome(attempt, machine)

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
    families = _load_families(campaign_dir)
    attempts = _load_attempts(campaign_dir)

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
            _evaluate_obligation(obligation_id, attempt, item, machine)
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
    ).with_semantic_id()
    CampaignStore(campaign_dir).write_json(
        "validation/validation-bundle.json",
        bundle.model_dump(mode="json", exclude_none=True),
    )
    return bundle

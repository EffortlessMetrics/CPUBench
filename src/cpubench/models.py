from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .canonical import semantic_id


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ArtifactModel(StrictModel):
    schema_version: int = 1
    artifact_kind: str
    semantic_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    parent_ids: list[str] = Field(default_factory=list)

    def semantic_payload(self) -> dict[str, Any]:
        return self.model_dump(
            mode="python",
            exclude={"semantic_id", "created_at"},
            exclude_none=True,
        )

    def with_semantic_id(self) -> Self:
        data = self.model_dump(mode="python")
        data["semantic_id"] = semantic_id(self.artifact_kind, self.schema_version, self.semantic_payload())
        return self.__class__.model_validate(data)


class CapabilityState(StrEnum):
    QUALIFIED = "qualified"
    AVAILABLE_UNQUALIFIED = "available_unqualified"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    UNKNOWN = "unknown"


class AttemptState(StrEnum):
    PLANNED = "planned"
    COMPLETED = "completed"
    UNSUPPORTED = "unsupported"
    INCOMPATIBLE = "incompatible"
    INVALID_WORK = "invalid_work"
    INSTRUMENT_FAILED = "instrument_failed"
    EXECUTION_FAILED = "execution_failed"
    TIMED_OUT = "timed_out"
    ABORTED = "aborted"
    INCOMPLETE = "incomplete"


class PackRole(StrEnum):
    CALIBRATION = "calibration"
    PUBLIC_REFERENCE = "public_reference"
    CHALLENGE = "challenge"
    APPLICATION = "application"
    DIAGNOSTIC = "diagnostic"
    REGRESSION = "regression"
    BRIDGE = "bridge"


class DisclosureState(StrEnum):
    DEVELOPMENT_PUBLIC = "development_public"
    FROZEN_PUBLIC = "frozen_public"
    CHALLENGE_PRIVATE = "challenge_private"
    VENDOR_SHARED = "vendor_shared"
    REMEDIATION_HOLDOUT = "remediation_holdout"
    RETIRED_PUBLIC = "retired_public"
    RESTRICTED_LICENSED = "restricted_licensed"


class OperatingMode(StrEnum):
    PRODUCT = "product"
    CHARACTERIZATION = "characterization"
    MECHANISM = "mechanism"


class ImplementationPolicy(StrEnum):
    EXACT = "exact"
    PORTABLE = "portable"
    NATIVE = "native"
    TUNED = "tuned"
    PRODUCT = "product"


class ValidityOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"
    UNSUPPORTED = "unsupported"
    INCONCLUSIVE = "inconclusive"


class CapabilityEvidence(StrictModel):
    state: CapabilityState
    authority: str
    detail: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class MachineReceipt(ArtifactModel):
    artifact_kind: Literal["machine_receipt"] = "machine_receipt"
    system: dict[str, Any]
    cpu: dict[str, Any]
    topology: dict[str, Any]
    memory: dict[str, Any]
    runtime: dict[str, Any]
    capabilities: dict[str, CapabilityEvidence]
    known_unknowns: list[str] = Field(default_factory=list)


class RunEnvironmentReceipt(ArtifactModel):
    artifact_kind: Literal["run_environment_receipt"] = "run_environment_receipt"
    campaign_id: str
    machine_receipt_id: str
    process: dict[str, Any]
    load: dict[str, Any]
    memory: dict[str, Any]
    power: dict[str, Any]
    thermal: dict[str, Any]
    known_unknowns: list[str] = Field(default_factory=list)


class InstrumentRelease(ArtifactModel):
    artifact_kind: Literal["instrument_release"] = "instrument_release"
    instrument_id: str
    instrument_version: str
    provider_protocol_version: int
    evidence_format_version: int
    control_plane_digest: str
    components: dict[str, str]
    known_limits: list[str] = Field(default_factory=list)


class WorkContract(StrictModel):
    useful_unit: str
    input_population: str
    required_output: str
    quality_or_tolerance: str


class ResourceBudget(StrictModel):
    expected_wall_seconds_per_attempt: float = Field(gt=0)
    maximum_wall_seconds_per_attempt: float = Field(gt=0)
    peak_memory_bytes: int = Field(ge=0)
    output_bytes_per_attempt: int = Field(ge=0)
    privilege: Literal["none", "optional", "required"] = "none"

    @model_validator(mode="after")
    def maximum_covers_expected(self) -> Self:
        if self.maximum_wall_seconds_per_attempt < self.expected_wall_seconds_per_attempt:
            raise ValueError("maximum wall time must cover expected wall time")
        return self


class PointSpec(StrictModel):
    point_id: str
    parameters: dict[str, int | float | str | bool]
    profiles: list[str] = Field(default_factory=lambda: ["smoke", "qualify", "review", "characterize"])
    tags: list[str] = Field(default_factory=list)


class ObligationSpec(StrictModel):
    severity: Literal["blocking", "required_for_view", "diagnostic"] = "blocking"
    description: str
    views: list[str] = Field(default_factory=list)


class MutantSpec(StrictModel):
    mutant_id: str
    description: str
    expected_failures: list[str]


class FamilySpec(ArtifactModel):
    artifact_kind: Literal["family_spec"] = "family_spec"
    family_id: str
    family_version: str
    title: str
    surface: str
    question: str
    evaluated_object: str
    provider_id: str
    work_contract: WorkContract
    resource_budget: ResourceBudget | None = None
    demand_geometry: dict[str, Any]
    intervention_axes: list[str]
    invariants: list[str]
    forms: list[str]
    points: list[PointSpec]
    timing_authority: Literal["provider_elapsed", "provider_cycles", "runner_elapsed"]
    supported_modes: list[OperatingMode]
    primary_metrics: list[str]
    diagnostic_metrics: list[str] = Field(default_factory=list)
    obligations: dict[str, ObligationSpec]
    mutants: list[MutantSpec] = Field(default_factory=list)
    claim_boundary: list[str]

    @model_validator(mode="after")
    def unique_points(self) -> Self:
        point_ids = [point.point_id for point in self.points]
        if len(point_ids) != len(set(point_ids)):
            raise ValueError(f"duplicate point_id in {self.family_id}")
        return self


class PackFamilyRef(StrictModel):
    family: str


class PackSpec(ArtifactModel):
    artifact_kind: Literal["pack_spec"] = "pack_spec"
    pack_id: str
    pack_version: str
    title: str
    role: PackRole
    disclosure: DisclosureState
    families: list[PackFamilyRef]


class PackRelease(ArtifactModel):
    artifact_kind: Literal["pack_release"] = "pack_release"
    pack_id: str
    pack_version: str
    title: str
    role: PackRole
    disclosure: DisclosureState
    pack_spec_id: str
    family_spec_ids: dict[str, str]
    family_versions: dict[str, str]


class VariantMember(StrictModel):
    label: str
    role: Literal["baseline", "challenge", "control"]
    family_id: str
    point_id: str
    form_id: str | None = None
    implementation_id: str | None = None
    transformation: str
    preserves: list[str]
    expected_variation: list[str] = Field(default_factory=list)


class VariantSetSpec(ArtifactModel):
    artifact_kind: Literal["variant_set_spec"] = "variant_set_spec"
    variant_set_id: str
    variant_set_version: str
    title: str
    question: str
    baseline_label: str
    members: list[VariantMember]
    comparison_metric: str
    threshold: float = Field(gt=0)
    claim_boundary: list[str]

    @model_validator(mode="after")
    def labels_are_valid(self) -> Self:
        labels = [member.label for member in self.members]
        if len(labels) != len(set(labels)):
            raise ValueError("variant member labels must be unique")
        if self.baseline_label not in labels:
            raise ValueError("variant baseline_label must identify one member")
        if sum(member.role == "baseline" for member in self.members) != 1:
            raise ValueError("variant set must contain exactly one baseline member")
        return self


class ProfileSpec(ArtifactModel):
    artifact_kind: Literal["profile_spec"] = "profile_spec"
    profile_id: str
    title: str
    attempts_per_point: int = Field(ge=1)
    samples_per_attempt: int = Field(ge=1)
    warmup_samples: int = Field(ge=0)
    unit_scale: float = Field(gt=0)
    timeout_seconds: float = Field(gt=0)
    minimum_timer_overhead_ratio: float = Field(
        default=100.0, ge=10.0, le=1_000_000.0, allow_inf_nan=False
    )
    randomized_interleaving: bool = True
    include_tags: list[str] = Field(default_factory=list)


class CampaignPackRef(StrictModel):
    pack: str


class CampaignSpec(ArtifactModel):
    artifact_kind: Literal["campaign_spec"] = "campaign_spec"
    campaign_id: str
    title: str
    description: str
    profile: str
    packs: list[CampaignPackRef]
    operating_mode: OperatingMode = OperatingMode.CHARACTERIZATION
    implementation_policy: ImplementationPolicy = ImplementationPolicy.NATIVE
    placement: str = "scheduler_open"
    output_root: str = ".cpubench/runs"
    schedule_seed: int = 1
    public_claims_enabled: bool = False


class FamilyDescriptor(StrictModel):
    family_id: str
    implementation_id: str
    supported_os: list[str]
    supported_arch: list[str]
    timing_authority: str
    capabilities: list[str] = Field(default_factory=list)


class ProviderDescriptor(ArtifactModel):
    artifact_kind: Literal["provider_descriptor"] = "provider_descriptor"
    provider_id: str
    provider_version: str
    protocol_version: int = 1
    families: list[FamilyDescriptor]


class BuildReceipt(ArtifactModel):
    artifact_kind: Literal["build_receipt"] = "build_receipt"
    provider_id: str
    implementation_id: str
    source_digest: str
    compiler: str
    commands: list[list[str]]
    binary_path: str
    binary_digest: str
    build_policy: ImplementationPolicy
    logs: list[str] = Field(default_factory=list)

    def semantic_payload(self) -> dict[str, Any]:
        payload = super().semantic_payload()
        # These remain captured evidence, but their absolute local values do not
        # change the produced executable or its declared build meaning.
        payload.pop("binary_path", None)
        payload.pop("commands", None)
        payload.pop("logs", None)
        return payload


class RunPlanItem(StrictModel):
    attempt_id: str
    sequence_index: int
    instrument_release_id: str
    pack_release_id: str
    pack_id: str
    family_id: str
    family_version: str
    point_id: str
    form_id: str
    provider_id: str
    parameters: dict[str, int | float | str | bool]
    attempt_index: int
    samples_per_attempt: int
    warmup_samples: int
    timeout_seconds: float
    operating_mode: OperatingMode
    implementation_policy: ImplementationPolicy
    placement: str


class RunPlan(ArtifactModel):
    artifact_kind: Literal["run_plan"] = "run_plan"
    campaign_id: str
    campaign_spec_id: str
    instrument_release_id: str
    pack_release_ids: dict[str, str]
    profile_id: str
    machine_receipt_id: str
    run_environment_receipt_id: str
    schedule_seed: int
    items: list[RunPlanItem]


class SampleRecord(StrictModel):
    sample_index: int
    elapsed_ns: int = Field(gt=0)
    completed_units: int = Field(gt=0)
    checksum: str
    timer: str
    metrics: dict[str, int | float | str | bool] = Field(default_factory=dict)


class AttemptRecord(ArtifactModel):
    artifact_kind: Literal["attempt_record"] = "attempt_record"
    attempt_id: str
    state: AttemptState
    family_id: str
    point_id: str
    provider_id: str
    run_environment_receipt_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    requested_parameters: dict[str, Any] = Field(default_factory=dict)
    effective_parameters: dict[str, Any] = Field(default_factory=dict)
    samples: list[SampleRecord] = Field(default_factory=list)
    work_output: dict[str, Any] = Field(default_factory=dict)
    placement: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    provider_stdout: str = ""
    provider_stderr: str = ""
    reason_code: str | None = None
    detail: str | None = None

    def semantic_payload(self) -> dict[str, Any]:
        payload = super().semantic_payload()
        # Raw channels are retained as separately hashed evidence files. Keeping
        # them out of the structured attempt identity makes attempt.json
        # independently self-verifiable.
        payload.pop("provider_stdout", None)
        payload.pop("provider_stderr", None)
        return payload


class ObligationResult(StrictModel):
    obligation_id: str
    outcome: ValidityOutcome
    reason_code: str
    detail: str | None = None


class AttemptValidation(StrictModel):
    attempt_id: str
    work_validity: ValidityOutcome
    measurement_validity: ValidityOutcome
    comparability: ValidityOutcome
    obligations: list[ObligationResult]


class TimerQualification(StrictModel):
    timer: str
    state: CapabilityState
    control_attempt_ids: list[str]
    failed_control_attempt_ids: list[str] = Field(default_factory=list)
    invalid_control_attempt_ids: list[str] = Field(default_factory=list)
    observations: int = Field(ge=0)
    non_monotonic_observations: int = Field(ge=0)
    zero_delta_observations: int = Field(ge=0)
    read_overhead_ns: float | None = Field(default=None, gt=0)
    effective_resolution_ns: int | None = Field(default=None, gt=0)
    minimum_sample_duration_ns: int | None = Field(default=None, gt=0)
    overhead_ratio: float = Field(ge=10.0, le=1_000_000.0, allow_inf_nan=False)
    reason_code: str
    detail: str | None = None


class ValidationBundle(ArtifactModel):
    artifact_kind: Literal["validation_bundle"] = "validation_bundle"
    campaign_id: str
    run_plan_id: str
    validity_view: str
    attempts: list[AttemptValidation]
    coverage: dict[str, int]
    timer_qualifications: dict[str, TimerQualification] = Field(default_factory=dict)


class PointEstimate(StrictModel):
    family_id: str
    point_id: str
    form_id: str
    parameters: dict[str, Any]
    eligible_attempts: int
    median_ns_per_unit: float
    ci95_low_ns_per_unit: float
    ci95_high_ns_per_unit: float
    mad_ns_per_unit: float
    min_ns_per_unit: float
    max_ns_per_unit: float
    median_units_per_second: float
    bootstrap_resamples: int = Field(ge=0)


class AnalysisBundle(ArtifactModel):
    artifact_kind: Literal["analysis_bundle"] = "analysis_bundle"
    campaign_id: str
    validation_bundle_id: str
    analysis_policy: str
    points: list[PointEstimate]
    notes: list[str] = Field(default_factory=list)


class IntegrityContrast(StrictModel):
    variant_set_id: str
    baseline_label: str
    challenge_label: str
    baseline_median_ns: float
    challenge_median_ns: float
    ratio: float
    threshold: float
    finding: Literal["no_material_divergence", "identity_sensitive_divergence"]


class FindingBundle(ArtifactModel):
    artifact_kind: Literal["finding_bundle"] = "finding_bundle"
    finding_type: str
    observation: str
    effect: dict[str, Any]
    intent_status: Literal["unknown", "not_assessed", "supported", "not_supported"] = "not_assessed"
    claim_boundary: list[str] = Field(default_factory=list)


class StudyCampaignRef(StrictModel):
    path: str
    label: str | None = None


class StudySpec(ArtifactModel):
    artifact_kind: Literal["study_spec"] = "study_spec"
    study_id: str
    title: str
    description: str
    campaigns: list[StudyCampaignRef]
    baseline_campaign_id: str
    validity_view: str
    analysis_policy: str
    missingness_policy: Literal["omit_unmatched"] = "omit_unmatched"
    output_root: str = ".cpubench/studies"

    @model_validator(mode="after")
    def campaign_paths_are_unique(self) -> Self:
        paths = [campaign.path for campaign in self.campaigns]
        if len(paths) != len(set(paths)):
            raise ValueError("study campaign paths must be unique")
        return self


class StudyPointResult(StrictModel):
    family_id: str
    family_version: str
    point_id: str
    form_id: str
    parameters: dict[str, Any]
    values_ns_per_unit: dict[str, float]
    intervals_ns_per_unit: dict[str, list[float]]
    relative_speed_to_baseline: dict[str, float]
    relative_speed_interval_to_baseline: dict[str, list[float]]


class StudyBundle(ArtifactModel):
    artifact_kind: Literal["study_bundle"] = "study_bundle"
    study_id: str
    baseline_campaign_id: str
    campaign_labels: dict[str, str]
    campaign_machine_ids: dict[str, str]
    validation_views: dict[str, str]
    analysis_policy: str
    missingness_policy: str
    points: list[StudyPointResult]
    omissions: list[dict[str, Any]] = Field(default_factory=list)


class VerificationResult(StrictModel):
    valid: bool
    checked_files: int
    mismatches: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    unexpected: list[str] = Field(default_factory=list)


class ResolvedPaths(StrictModel):
    repo_root: Path
    campaign_file: Path
    campaign_dir: Path

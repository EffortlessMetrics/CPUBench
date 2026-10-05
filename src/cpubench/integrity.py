from __future__ import annotations

import statistics
import sys
from pathlib import Path
from typing import Any, Literal

from .evidence import atomic_write_json
from .models import (
    AnalysisBundle,
    FindingBundle,
    ImplementationPolicy,
    IntegrityContrast,
    OperatingMode,
    PointEstimate,
    RunPlanItem,
    VariantMember,
    VariantSetSpec,
)
from .provider import ProviderCommand, SubprocessProvider
from .serde import load_model


def _provider(behavior: str) -> SubprocessProvider:
    return SubprocessProvider(
        ProviderCommand(
            provider_id=f"fake-{behavior}",
            argv=[sys.executable, "-m", "cpubench.providers.fake"],
            env={
                "CPUBENCH_FAKE_PROVIDER_ID": f"fake-{behavior}",
                "CPUBENCH_FAKE_BEHAVIOR": behavior,
            },
        )
    )


def _item(label: str, index: int) -> RunPlanItem:
    return RunPlanItem(
        attempt_id=f"integrity-{label}-{index}",
        sequence_index=index,
        instrument_release_id="sha256:integrity-demo-instrument",
        pack_release_id="sha256:integrity-demo-pack",
        pack_id="integrity-demo",
        family_id="integrity.identity_probe",
        family_version="0.1.0",
        point_id=label,
        form_id="matched_identity",
        provider_id="fake",
        parameters={"variant_label": label, "completed_units": 1},
        attempt_index=index,
        samples_per_attempt=3,
        warmup_samples=1,
        timeout_seconds=30,
        operating_mode=OperatingMode.CHARACTERIZATION,
        implementation_policy=ImplementationPolicy.EXACT,
        placement="scheduler_open",
    )


def _median_elapsed(provider: SubprocessProvider, label: str) -> float:
    attempt = provider.run_attempt(_item(label, 0))
    if not attempt.samples:
        raise RuntimeError(f"integrity demo produced no samples for {label}")
    return statistics.median(sample.elapsed_ns for sample in attempt.samples)


def run_integrity_demo(output_dir: Path, threshold: float = 1.25) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Any]] = {}
    for behavior in ("honest", "gamed"):
        provider = _provider(behavior)
        public = _median_elapsed(provider, "public")
        alias = _median_elapsed(provider, "alias")
        ratio = max(public, alias) / min(public, alias)
        finding_kind: Literal["no_material_divergence", "identity_sensitive_divergence"] = (
            "identity_sensitive_divergence" if ratio >= threshold else "no_material_divergence"
        )
        contrast = IntegrityContrast(
            variant_set_id=f"integrity-demo-{behavior}",
            baseline_label="public",
            challenge_label="alias",
            baseline_median_ns=public,
            challenge_median_ns=alias,
            ratio=ratio,
            threshold=threshold,
            finding=finding_kind,
        )
        results[behavior] = contrast.model_dump(mode="json")

    finding = FindingBundle(
        finding_type="integrity_demo",
        observation="The known-gamed provider diverges across matched identities while the honest provider remains within threshold.",
        effect=results,
        intent_status="not_assessed",
        claim_boundary=[
            "This is a detector self-test, not evidence about a hardware vendor.",
            "Observed identity sensitivity does not by itself establish motive.",
        ],
    ).with_semantic_id()
    payload = {
        "schema_version": 1,
        "results": results,
        "finding": finding.model_dump(mode="json", exclude_none=True),
    }
    atomic_write_json(output_dir / "integrity-demo.json", payload)
    return payload


def analyze_variant_set(campaign_dir: Path, variant_path: Path, output_dir: Path) -> FindingBundle:
    campaign_dir = campaign_dir.resolve()
    variant_path = variant_path.resolve()
    variant = load_model(variant_path, VariantSetSpec).with_semantic_id()
    if variant.comparison_metric != "median_ns_per_unit":
        raise ValueError(
            f"unsupported integrity comparison metric: {variant.comparison_metric}; "
            "the alpha supports median_ns_per_unit"
        )
    analysis = AnalysisBundle.model_validate_json(
        (campaign_dir / "analysis" / "analysis-bundle.json").read_text(encoding="utf-8")
    )
    points = {
        (point.family_id, point.point_id, point.form_id): point
        for point in analysis.points
    }

    baseline_member = next(member for member in variant.members if member.role == "baseline")

    def resolve(member: VariantMember) -> PointEstimate:
        matches = [
            point
            for (family_id, point_id, form_id), point in points.items()
            if family_id == member.family_id
            and point_id == member.point_id
            and (member.form_id is None or form_id == member.form_id)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"variant member {member.label!r} resolved to {len(matches)} points; "
                f"family={member.family_id} point={member.point_id} form={member.form_id}"
            )
        return matches[0]

    baseline = resolve(baseline_member)
    contrasts: list[dict[str, Any]] = []
    divergent = False
    control_failed = False
    for member in variant.members:
        if member.role == "baseline":
            continue
        challenge = resolve(member)
        low = min(baseline.median_ns_per_unit, challenge.median_ns_per_unit)
        high = max(baseline.median_ns_per_unit, challenge.median_ns_per_unit)
        ratio = high / low
        finding_kind: Literal["no_material_divergence", "identity_sensitive_divergence"] = (
            "identity_sensitive_divergence" if ratio >= variant.threshold else "no_material_divergence"
        )
        if finding_kind == "identity_sensitive_divergence":
            if member.role == "challenge":
                divergent = True
            elif member.role == "control":
                control_failed = True
        contrast_payload = IntegrityContrast(
            variant_set_id=variant.variant_set_id,
            baseline_label=baseline_member.label,
            challenge_label=member.label,
            baseline_median_ns=baseline.median_ns_per_unit,
            challenge_median_ns=challenge.median_ns_per_unit,
            ratio=ratio,
            threshold=variant.threshold,
            finding=finding_kind,
        ).model_dump(mode="json")
        contrast_payload["member_role"] = member.role
        contrasts.append(contrast_payload)

    if control_failed:
        finding_type = "integrity_control_failure"
        observation = "At least one construct-preserving control exceeded the declared divergence threshold."
    elif divergent:
        finding_type = "identity_sensitive_performance_policy"
        observation = "At least one matched challenge variant exceeded the declared divergence threshold."
    else:
        finding_type = "no_material_identity_sensitive_divergence"
        observation = "No matched challenge variant exceeded the declared divergence threshold."

    bundle = FindingBundle(
        finding_type=finding_type,
        observation=observation,
        effect={
            "campaign_analysis_id": analysis.semantic_id,
            "variant_set_id": variant.semantic_id,
            "comparison_metric": variant.comparison_metric,
            "contrasts": contrasts,
        },
        intent_status="not_assessed",
        claim_boundary=[
            *variant.claim_boundary,
            "Observed identity sensitivity does not by itself establish motive.",
            "The finding is valid only to the extent that the declared preserved properties are actually matched.",
        ],
        parent_ids=[analysis.semantic_id or "", variant.semantic_id or ""],
    ).with_semantic_id()
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "variant-set.json", variant.model_dump(mode="json", exclude_none=True))
    atomic_write_json(output_dir / "finding-bundle.json", bundle.model_dump(mode="json", exclude_none=True))
    return bundle

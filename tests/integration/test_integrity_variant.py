from pathlib import Path

import yaml

from cpubench.evidence import atomic_write_json
from cpubench.integrity import analyze_variant_set
from cpubench.models import AnalysisBundle, PointEstimate


def test_variant_set_analysis_detects_divergence(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    analysis_dir = campaign_dir / "analysis"
    analysis_dir.mkdir(parents=True)
    points = [
        PointEstimate(
            family_id="integrity.identity_probe",
            point_id="public",
            form_id="matched_identity",
            parameters={"variant": "public"},
            eligible_attempts=3,
            median_ns_per_unit=2.0,
            ci95_low_ns_per_unit=1.9,
            ci95_high_ns_per_unit=2.1,
            mad_ns_per_unit=0.1,
            min_ns_per_unit=1.9,
            max_ns_per_unit=2.1,
            median_units_per_second=500_000_000.0,
            bootstrap_resamples=2000,
        ),
        PointEstimate(
            family_id="integrity.identity_probe",
            point_id="alias",
            form_id="matched_identity",
            parameters={"variant": "alias"},
            eligible_attempts=3,
            median_ns_per_unit=4.0,
            ci95_low_ns_per_unit=3.9,
            ci95_high_ns_per_unit=4.1,
            mad_ns_per_unit=0.1,
            min_ns_per_unit=3.9,
            max_ns_per_unit=4.1,
            median_units_per_second=250_000_000.0,
            bootstrap_resamples=2000,
        ),
    ]
    analysis = AnalysisBundle(
        campaign_id="integrity-test",
        validation_bundle_id="sha256:validation",
        analysis_policy="median_of_attempt_medians_bootstrap_v1",
        points=points,
    ).with_semantic_id()
    atomic_write_json(analysis_dir / "analysis-bundle.json", analysis.model_dump(mode="json"))

    variant_path = tmp_path / "variant.yaml"
    variant_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "artifact_kind": "variant_set_spec",
                "variant_set_id": "identity-alias",
                "variant_set_version": "0.1.0",
                "title": "Public versus alias",
                "question": "Does evaluation identity change performance?",
                "baseline_label": "public",
                "comparison_metric": "median_ns_per_unit",
                "threshold": 1.25,
                "members": [
                    {
                        "label": "public",
                        "role": "baseline",
                        "family_id": "integrity.identity_probe",
                        "point_id": "public",
                        "form_id": "matched_identity",
                        "transformation": "published identity",
                        "preserves": ["work"],
                    },
                    {
                        "label": "alias",
                        "role": "challenge",
                        "family_id": "integrity.identity_probe",
                        "point_id": "alias",
                        "form_id": "matched_identity",
                        "transformation": "neutral alias",
                        "preserves": ["work"],
                    },
                ],
                "claim_boundary": ["does not establish intent"],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    finding = analyze_variant_set(campaign_dir, variant_path, tmp_path / "finding")
    assert finding.finding_type == "identity_sensitive_performance_policy"
    assert finding.effect["contrasts"][0]["ratio"] == 2.0
    assert (tmp_path / "finding" / "finding-bundle.json").exists()

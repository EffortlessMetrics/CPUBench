from pathlib import Path

import yaml

from cpubench.analysis import analyze_campaign
from cpubench.campaign import execute_campaign, finalize_campaign, persist_runtime, prepare_runtime
from cpubench.report import generate_report
from cpubench.study import compare_study, report_study
from cpubench.validation import validate_campaign


def _completed_campaign(tmp_path: Path, campaign_id: str) -> Path:
    campaign_file = tmp_path / f"{campaign_id}.yaml"
    campaign_file.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "artifact_kind": "campaign_spec",
                "campaign_id": campaign_id,
                "title": campaign_id,
                "description": "Study fixture.",
                "profile": "profiles/smoke.yaml",
                "packs": [{"pack": "packs/controls/pack.yaml"}],
                "operating_mode": "characterization",
                "implementation_policy": "native",
                "placement": "scheduler_open",
                "output_root": str(tmp_path / "runs"),
                "schedule_seed": 7,
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
    finalize_campaign(runtime.store.root)
    return runtime.store.root


def test_study_compares_finalized_campaigns(tmp_path: Path) -> None:
    baseline = _completed_campaign(tmp_path, "baseline")
    candidate = _completed_campaign(tmp_path, "candidate")
    study_file = tmp_path / "study.yaml"
    study_file.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "artifact_kind": "study_spec",
                "study_id": "comparison",
                "title": "Comparison",
                "description": "Compare two finalized fixtures.",
                "campaigns": [
                    {"path": str(baseline), "label": "Baseline"},
                    {"path": str(candidate), "label": "Candidate"},
                ],
                "baseline_campaign_id": "baseline",
                "validity_view": "portable_elapsed",
                "analysis_policy": "median_of_attempt_medians_bootstrap_v1",
                "missingness_policy": "omit_unmatched",
                "output_root": str(tmp_path / "studies"),
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    bundle, output_dir = compare_study(study_file)
    assert bundle.points
    assert not bundle.omissions
    assert (output_dir / "study-bundle.json").exists()
    report = report_study(study_file)
    assert report.exists()

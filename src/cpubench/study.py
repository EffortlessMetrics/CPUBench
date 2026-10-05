from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evidence import CampaignStore, atomic_write_json, atomic_write_text
from .models import (
    AnalysisBundle,
    CampaignSpec,
    MachineReceipt,
    RunPlan,
    StudyBundle,
    StudyPointResult,
    StudySpec,
    ValidationBundle,
)
from .serde import load_model


@dataclass(frozen=True)
class CampaignComparisonInput:
    root: Path
    campaign: CampaignSpec
    machine: MachineReceipt
    plan: RunPlan
    validation: ValidationBundle
    analysis: AnalysisBundle
    label: str


def load_study(path: Path) -> StudySpec:
    return load_model(path, StudySpec).with_semantic_id()


def _resolve_campaign_path(study_path: Path, path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = (study_path.parent / path).resolve()
    return path


def _load_campaign(root: Path, label: str | None) -> CampaignComparisonInput:
    verification = CampaignStore(root).verify()
    if not verification.valid:
        raise ValueError(
            f"campaign is not finalized and verifiable: {root}; "
            f"missing={verification.missing} mismatches={verification.mismatches} unexpected={verification.unexpected}"
        )
    campaign = CampaignSpec.model_validate_json((root / "campaign-spec.json").read_text(encoding="utf-8"))
    machine = MachineReceipt.model_validate_json((root / "machine-receipt.json").read_text(encoding="utf-8"))
    plan = RunPlan.model_validate_json((root / "run-plan.json").read_text(encoding="utf-8"))
    validation = ValidationBundle.model_validate_json(
        (root / "validation" / "validation-bundle.json").read_text(encoding="utf-8")
    )
    analysis = AnalysisBundle.model_validate_json(
        (root / "analysis" / "analysis-bundle.json").read_text(encoding="utf-8")
    )
    return CampaignComparisonInput(
        root=root,
        campaign=campaign,
        machine=machine,
        plan=plan,
        validation=validation,
        analysis=analysis,
        label=label or campaign.title,
    )


def _family_versions(plan: RunPlan) -> dict[tuple[str, str, str], str]:
    versions: dict[tuple[str, str, str], str] = {}
    for item in plan.items:
        versions[(item.family_id, item.point_id, item.form_id)] = item.family_version
    return versions


def compare_study(path: Path) -> tuple[StudyBundle, Path]:
    path = path.resolve()
    study = load_study(path)
    campaigns = [
        _load_campaign(_resolve_campaign_path(path, ref.path), ref.label)
        for ref in study.campaigns
    ]
    by_id = {campaign.campaign.campaign_id: campaign for campaign in campaigns}
    if len(by_id) != len(campaigns):
        raise ValueError("campaign IDs must be unique within a study")
    if study.baseline_campaign_id not in by_id:
        raise ValueError(f"baseline campaign not present: {study.baseline_campaign_id}")

    baseline = by_id[study.baseline_campaign_id]
    labels = {campaign.campaign.campaign_id: campaign.label for campaign in campaigns}
    machine_ids = {campaign.campaign.campaign_id: campaign.machine.semantic_id or "" for campaign in campaigns}
    views = {campaign.campaign.campaign_id: campaign.validation.validity_view for campaign in campaigns}
    if len(set(views.values())) != 1:
        raise ValueError(f"study campaigns use different validity views: {views}")
    if set(views.values()) != {study.validity_view}:
        raise ValueError(f"study validity view does not match campaign evidence: declared={study.validity_view} observed={views}")
    policies = {campaign.analysis.analysis_policy for campaign in campaigns}
    if len(policies) != 1:
        raise ValueError(f"study campaigns use different analysis policies: {sorted(policies)}")
    if policies != {study.analysis_policy}:
        raise ValueError(
            f"study analysis policy does not match campaign evidence: declared={study.analysis_policy} observed={sorted(policies)}"
        )

    point_maps = {
        campaign.campaign.campaign_id: {
            (point.family_id, point.point_id, point.form_id): point
            for point in campaign.analysis.points
        }
        for campaign in campaigns
    }
    version_maps = {campaign.campaign.campaign_id: _family_versions(campaign.plan) for campaign in campaigns}
    all_keys = sorted(set().union(*(set(points) for points in point_maps.values())))

    results: list[StudyPointResult] = []
    omissions: list[dict[str, Any]] = []
    campaign_ids = [campaign.campaign.campaign_id for campaign in campaigns]
    for key in all_keys:
        missing = [campaign_id for campaign_id in campaign_ids if key not in point_maps[campaign_id]]
        if missing:
            omissions.append(
                {
                    "family_id": key[0],
                    "point_id": key[1],
                    "form_id": key[2],
                    "reason_code": "point_missing_from_campaign",
                    "campaign_ids": missing,
                }
            )
            continue
        versions = {version_maps[campaign_id].get(key, "unknown") for campaign_id in campaign_ids}
        if len(versions) != 1:
            omissions.append(
                {
                    "family_id": key[0],
                    "point_id": key[1],
                    "form_id": key[2],
                    "reason_code": "family_version_mismatch",
                    "versions": {
                        campaign_id: version_maps[campaign_id].get(key, "unknown")
                        for campaign_id in campaign_ids
                    },
                }
            )
            continue
        parameter_payloads = {
            json.dumps(point_maps[campaign_id][key].parameters, sort_keys=True, separators=(",", ":"))
            for campaign_id in campaign_ids
        }
        if len(parameter_payloads) != 1:
            omissions.append(
                {
                    "family_id": key[0],
                    "point_id": key[1],
                    "form_id": key[2],
                    "reason_code": "point_parameter_mismatch",
                }
            )
            continue
        values = {
            campaign_id: point_maps[campaign_id][key].median_ns_per_unit
            for campaign_id in campaign_ids
        }
        intervals = {
            campaign_id: [
                point_maps[campaign_id][key].ci95_low_ns_per_unit,
                point_maps[campaign_id][key].ci95_high_ns_per_unit,
            ]
            for campaign_id in campaign_ids
        }
        baseline_value = values[study.baseline_campaign_id]
        relative = {
            campaign_id: baseline_value / value
            for campaign_id, value in values.items()
        }
        baseline_interval = intervals[study.baseline_campaign_id]
        relative_intervals: dict[str, list[float]] = {}
        for campaign_id in campaign_ids:
            if campaign_id == study.baseline_campaign_id:
                relative_intervals[campaign_id] = [1.0, 1.0]
                continue
            candidate_interval = intervals[campaign_id]
            relative_intervals[campaign_id] = [
                baseline_interval[0] / candidate_interval[1],
                baseline_interval[1] / candidate_interval[0],
            ]
        base_point = point_maps[baseline.campaign.campaign_id][key]
        results.append(
            StudyPointResult(
                family_id=key[0],
                family_version=next(iter(versions)),
                point_id=key[1],
                form_id=key[2],
                parameters=base_point.parameters,
                values_ns_per_unit=values,
                intervals_ns_per_unit=intervals,
                relative_speed_to_baseline=relative,
                relative_speed_interval_to_baseline=relative_intervals,
            )
        )

    bundle = StudyBundle(
        study_id=study.study_id,
        baseline_campaign_id=study.baseline_campaign_id,
        campaign_labels=labels,
        campaign_machine_ids=machine_ids,
        validation_views=views,
        analysis_policy=study.analysis_policy,
        missingness_policy=study.missingness_policy,
        points=results,
        omissions=omissions,
        parent_ids=[
            *(campaign.analysis.semantic_id or "" for campaign in campaigns),
            study.semantic_id or "",
        ],
    ).with_semantic_id()

    output_root = Path(study.output_root)
    if not output_root.is_absolute():
        output_root = (path.parent / output_root).resolve()
    output_dir = output_root / study.study_id
    output_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_dir / "study-spec.json", study.model_dump(mode="json", exclude_none=True))
    atomic_write_json(output_dir / "study-bundle.json", bundle.model_dump(mode="json", exclude_none=True))
    return bundle, output_dir


def report_study(path: Path) -> Path:
    bundle, output_dir = compare_study(path)
    campaign_ids = list(bundle.campaign_labels)
    header = "".join(f"<th>{html.escape(bundle.campaign_labels[campaign_id])}</th>" for campaign_id in campaign_ids)
    rows: list[str] = []
    for point in bundle.points:
        values = "".join(
            f"<td>{point.values_ns_per_unit[campaign_id]:.4f}<br>"
            f"<small>{point.intervals_ns_per_unit[campaign_id][0]:.4f}–{point.intervals_ns_per_unit[campaign_id][1]:.4f} ns/unit</small><br>"
            f"<small>{point.relative_speed_to_baseline[campaign_id]:.3f}× baseline speed "
            f"({point.relative_speed_interval_to_baseline[campaign_id][0]:.3f}–"
            f"{point.relative_speed_interval_to_baseline[campaign_id][1]:.3f})</small></td>"
            for campaign_id in campaign_ids
        )
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(point.family_id)}</code></td>"
            f"<td>{html.escape(point.point_id)}</td>"
            f"<td>{html.escape(point.family_version)}</td>"
            f"{values}</tr>"
        )
    omissions = html.escape(json.dumps(bundle.omissions, indent=2, sort_keys=True))
    text = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(bundle.study_id)} · CPUBench study</title>
<style>
body{{margin:0;background:#f5f1e8;color:#1a1816;font:16px/1.5 system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:32px 20px 72px}}
h1{{border-left:6px solid #156b76;padding-left:16px}}section{{background:#fafaf7;border:1px solid #d8d1c5;border-radius:12px;padding:18px;margin:18px 0;overflow:auto}}
table{{border-collapse:collapse;width:100%;font-size:.9rem}}th,td{{padding:9px;border-bottom:1px solid #ddd5c8;text-align:left;vertical-align:top}}th{{color:#156b76}}code{{font-family:ui-monospace,monospace}}small{{color:#5f5953}}
</style></head><body><main>
<h1>{html.escape(bundle.study_id)}</h1>
<p>Direct comparisons include only points with matching family version, form, parameters, validity view, and analysis policy. A speed ratio above 1.0 means faster than the baseline on the lower-is-better ns/unit metric.</p>
<section><h2>Comparable points</h2><table><thead><tr><th>Family</th><th>Point</th><th>Version</th>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></section>
<section><h2>Omissions</h2><pre>{omissions}</pre></section>
<footer>Study bundle: <code>{html.escape(bundle.semantic_id or '')}</code></footer>
</main></body></html>"""
    report_dir = output_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(report_dir / "index.html", text)
    atomic_write_json(
        report_dir / "summary.json",
        bundle.model_dump(mode="json", exclude_none=True),
    )
    return report_dir / "index.html"

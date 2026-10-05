from __future__ import annotations

import hashlib
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .evidence import CampaignStore
from .models import (
    AnalysisBundle,
    AttemptRecord,
    RunPlan,
    PointEstimate,
    ValidationBundle,
    ValidityOutcome,
)


def _mad(values: list[float]) -> float:
    if not values:
        return 0.0
    center = statistics.median(values)
    return statistics.median(abs(value - center) for value in values)


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        raise ValueError("percentile requires at least one value")
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = fraction * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = position - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def _bootstrap_median_interval(values: list[float], key: tuple[str, str, str], resamples: int = 2_000) -> tuple[float, float, int]:
    if len(values) == 1:
        return values[0], values[0], 0
    seed_material = "\0".join(key).encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big")
    rng = random.Random(seed)
    medians = [statistics.median(rng.choices(values, k=len(values))) for _ in range(resamples)]
    medians.sort()
    return _percentile(medians, 0.025), _percentile(medians, 0.975), resamples


def analyze_campaign(campaign_dir: Path) -> AnalysisBundle:
    campaign_dir = campaign_dir.resolve()
    plan = RunPlan.model_validate_json((campaign_dir / "run-plan.json").read_text(encoding="utf-8"))
    validation = ValidationBundle.model_validate_json(
        (campaign_dir / "validation" / "validation-bundle.json").read_text(encoding="utf-8")
    )
    validation_by_id = {item.attempt_id: item for item in validation.attempts}
    item_by_id = {item.attempt_id: item for item in plan.items}

    grouped: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    parameters: dict[tuple[str, str, str], dict[str, Any]] = {}

    for attempt_path in (campaign_dir / "attempts").glob("*/attempt.json"):
        attempt = AttemptRecord.model_validate_json(attempt_path.read_text(encoding="utf-8"))
        valid = validation_by_id.get(attempt.attempt_id)
        if valid is None or valid.comparability != ValidityOutcome.PASS:
            continue
        item = item_by_id[attempt.attempt_id]
        sample_values = [sample.elapsed_ns / sample.completed_units for sample in attempt.samples]
        if not sample_values:
            continue
        key = (item.family_id, item.point_id, item.form_id)
        grouped[key].append(statistics.median(sample_values))
        parameters[key] = item.parameters

    points: list[PointEstimate] = []
    for key in sorted(grouped):
        values = grouped[key]
        family_id, point_id, form_id = key
        low, high, resamples = _bootstrap_median_interval(values, key)
        median = statistics.median(values)
        points.append(
            PointEstimate(
                family_id=family_id,
                point_id=point_id,
                form_id=form_id,
                parameters=parameters[key],
                eligible_attempts=len(values),
                median_ns_per_unit=median,
                ci95_low_ns_per_unit=low,
                ci95_high_ns_per_unit=high,
                mad_ns_per_unit=_mad(values),
                min_ns_per_unit=min(values),
                max_ns_per_unit=max(values),
                median_units_per_second=(1_000_000_000.0 / median),
                bootstrap_resamples=resamples,
            )
        )

    bundle = AnalysisBundle(
        campaign_id=plan.campaign_id,
        validation_bundle_id=validation.semantic_id or "",
        analysis_policy="median_of_attempt_medians_bootstrap_v1",
        points=points,
        notes=[
            "Each point estimate is the median of independent attempt medians.",
            "MAD is computed across eligible attempt estimates.",
            "The 95% interval is a deterministic percentile bootstrap over independent attempt medians; one-attempt points have a degenerate interval.",
            "No raw sample is deleted; instrument-invalid attempts remain in the campaign bundle.",
        ],
    ).with_semantic_id()
    CampaignStore(campaign_dir).write_json("analysis/analysis-bundle.json", bundle.model_dump(mode="json", exclude_none=True))
    return bundle

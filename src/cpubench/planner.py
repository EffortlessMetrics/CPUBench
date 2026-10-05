from __future__ import annotations

import hashlib
import random
from typing import Any

from .canonical import canonical_json_bytes
from .models import (
    CampaignSpec,
    FamilySpec,
    InstrumentRelease,
    MachineReceipt,
    PackRelease,
    PackSpec,
    ProfileSpec,
    RunEnvironmentReceipt,
    RunPlan,
    RunPlanItem,
)


def _attempt_id(payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()[:24]
    return f"attempt-{digest}"


def compile_run_plan(
    campaign: CampaignSpec,
    profile: ProfileSpec,
    machine: MachineReceipt,
    environment: RunEnvironmentReceipt,
    instrument: InstrumentRelease,
    packs: list[tuple[PackSpec, list[FamilySpec]]],
    pack_releases: list[PackRelease],
) -> RunPlan:
    items: list[RunPlanItem] = []
    release_by_pack = {release.pack_id: release for release in pack_releases}
    for pack, families in packs:
        pack_release = release_by_pack[pack.pack_id]
        for family in families:
            if campaign.operating_mode not in family.supported_modes:
                continue
            for point in family.points:
                if profile.profile_id not in point.profiles:
                    continue
                parameters = dict(point.parameters)
                if "completed_units" in parameters:
                    parameters["completed_units"] = max(
                        1_000,
                        int(int(parameters["completed_units"]) * profile.unit_scale),
                    )
                for attempt_index in range(profile.attempts_per_point):
                    identity_payload = {
                        "campaign_id": campaign.campaign_id,
                        "instrument_release_id": instrument.semantic_id,
                        "pack_release_id": pack_release.semantic_id,
                        "run_environment_receipt_id": environment.semantic_id,
                        "pack_id": pack.pack_id,
                        "family_id": family.family_id,
                        "family_version": family.family_version,
                        "point_id": point.point_id,
                        "form_id": family.forms[0],
                        "parameters": parameters,
                        "attempt_index": attempt_index,
                        "profile_id": profile.semantic_id,
                        "machine_receipt_id": machine.semantic_id,
                        "schedule_seed": campaign.schedule_seed,
                    }
                    items.append(
                        RunPlanItem(
                            attempt_id=_attempt_id(identity_payload),
                            sequence_index=0,
                            instrument_release_id=instrument.semantic_id or "",
                            pack_release_id=pack_release.semantic_id or "",
                            pack_id=pack.pack_id,
                            family_id=family.family_id,
                            family_version=family.family_version,
                            point_id=point.point_id,
                            form_id=family.forms[0],
                            provider_id=family.provider_id,
                            parameters=parameters,
                            attempt_index=attempt_index,
                            samples_per_attempt=profile.samples_per_attempt,
                            warmup_samples=profile.warmup_samples,
                            timeout_seconds=profile.timeout_seconds,
                            operating_mode=campaign.operating_mode,
                            implementation_policy=campaign.implementation_policy,
                            placement=campaign.placement,
                        )
                    )

    if profile.randomized_interleaving:
        random.Random(campaign.schedule_seed).shuffle(items)
    for index, item in enumerate(items):
        items[index] = item.model_copy(update={"sequence_index": index})

    return RunPlan(
        campaign_id=campaign.campaign_id,
        campaign_spec_id=campaign.semantic_id or "",
        instrument_release_id=instrument.semantic_id or "",
        pack_release_ids={release.pack_id: release.semantic_id or "" for release in pack_releases},
        profile_id=profile.semantic_id or "",
        machine_receipt_id=machine.semantic_id or "",
        run_environment_receipt_id=environment.semantic_id or "",
        schedule_seed=campaign.schedule_seed,
        items=items,
    ).with_semantic_id()

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import sha256_file
from .evidence import CampaignStore, atomic_write_json, atomic_write_text
from .instrument import compile_pack_release, current_instrument_release
from .models import (
    ArtifactModel,
    AttemptRecord,
    AttemptState,
    AnalysisBundle,
    BuildReceipt,
    CampaignSpec,
    FamilySpec,
    ImplementationPolicy,
    InstrumentRelease,
    MachineReceipt,
    PackRelease,
    PackSpec,
    PlacementReceipt,
    ProfileSpec,
    RunEnvironmentReceipt,
    RunPlan,
    RunPlanItem,
    ValidationBundle,
    utc_now,
)
from .native import ensure_native_provider
from .placement import PlacementError, placement_scope
from .planner import compile_run_plan
from .platform_probe import collect_machine_receipt, collect_run_environment_receipt
from .provider import SubprocessProvider, python_provider
from .specs import load_campaign, load_pack, load_profile


@dataclass
class LoadedCampaign:
    source_path: Path
    spec: CampaignSpec
    profile: ProfileSpec
    packs: list[tuple[PackSpec, list[FamilySpec]]]
    pack_releases: list[PackRelease]

    @property
    def families(self) -> dict[str, FamilySpec]:
        return {family.family_id: family for _pack, families in self.packs for family in families}


@dataclass
class CampaignRuntime:
    loaded: LoadedCampaign
    instrument: InstrumentRelease
    machine: MachineReceipt
    environment: RunEnvironmentReceipt
    plan: RunPlan
    providers: dict[str, SubprocessProvider]
    build_receipts: list[BuildReceipt]
    store: CampaignStore


def load_campaign_bundle(path: Path, profile_override: str | None = None) -> LoadedCampaign:
    path = path.resolve()
    spec = load_campaign(path)
    profile_ref = profile_override or spec.profile
    profile = load_profile(profile_ref, base_dir=path.parent)
    packs: list[tuple[PackSpec, list[FamilySpec]]] = []
    for ref in spec.packs:
        packs.append(load_pack(ref.pack, base_dir=path.parent))
    pack_releases = [compile_pack_release(pack, families) for pack, families in packs]
    return LoadedCampaign(
        source_path=path,
        spec=spec,
        profile=profile,
        packs=packs,
        pack_releases=pack_releases,
    )


def campaign_output_dir(loaded: LoadedCampaign) -> Path:
    root = Path(loaded.spec.output_root)
    if not root.is_absolute():
        root = (loaded.source_path.parent / root).resolve()
    return root / loaded.spec.campaign_id


def _python_build_receipt(provider_id: str, module_path: Path, policy: ImplementationPolicy) -> BuildReceipt:
    return BuildReceipt(
        provider_id=provider_id,
        implementation_id=f"{provider_id}-v0",
        source_digest=sha256_file(module_path),
        compiler="python-runtime",
        commands=[],
        binary_path=str(module_path),
        binary_digest=sha256_file(module_path),
        build_policy=policy,
        logs=["Python module provider; no native build step."],
    ).with_semantic_id()


def prepare_runtime(
    path: Path,
    *,
    profile_override: str | None = None,
    resume: bool = False,
) -> CampaignRuntime:
    loaded = load_campaign_bundle(path, profile_override)
    output_dir = campaign_output_dir(loaded)
    if output_dir.exists() and not resume:
        if any(output_dir.iterdir()):
            raise RuntimeError(f"campaign output already exists: {output_dir}; use --resume or change campaign_id")
    store = CampaignStore(output_dir)
    if store.finalized:
        raise RuntimeError(f"campaign is finalized: {output_dir}")

    instrument = current_instrument_release()
    instrument_path = output_dir / "instrument-release.json"
    if resume and instrument_path.exists():
        persisted_instrument = InstrumentRelease.model_validate_json(instrument_path.read_text(encoding="utf-8"))
        if persisted_instrument.semantic_id != instrument.semantic_id:
            raise RuntimeError(
                "instrument release changed since this campaign was prepared; start a new campaign instead of resuming"
            )
        instrument = persisted_instrument

    if resume:
        campaign_path = output_dir / "campaign-spec.json"
        if campaign_path.exists():
            persisted_campaign = CampaignSpec.model_validate_json(campaign_path.read_text(encoding="utf-8"))
            if persisted_campaign.semantic_id != loaded.spec.semantic_id:
                raise RuntimeError("campaign specification changed; start a new campaign instead of resuming")
        profile_path = output_dir / "profile.json"
        if profile_path.exists():
            persisted_profile = ProfileSpec.model_validate_json(profile_path.read_text(encoding="utf-8"))
            if not persisted_profile.semantic_identity_is_valid():
                raise RuntimeError("persisted profile semantic identity does not match its content")
            if persisted_profile.semantic_id != loaded.profile.semantic_id:
                raise RuntimeError("profile changed; start a new campaign instead of resuming")
        for release in loaded.pack_releases:
            release_path = output_dir / "pack-releases" / release.pack_id / "release.json"
            if release_path.exists():
                persisted_release = PackRelease.model_validate_json(release_path.read_text(encoding="utf-8"))
                if persisted_release.semantic_id != release.semantic_id:
                    raise RuntimeError(
                        f"pack release changed for {release.pack_id}; start a new campaign instead of resuming"
                    )
    machine_path = output_dir / "machine-receipt.json"
    if resume and machine_path.exists():
        persisted_machine = MachineReceipt.model_validate_json(machine_path.read_text(encoding="utf-8"))
        current_machine = collect_machine_receipt()
        if persisted_machine.semantic_id != current_machine.semantic_id:
            raise RuntimeError(
                "current machine identity differs from the persisted campaign machine receipt; "
                "start a new campaign rather than resuming on a different machine or boot"
            )
        machine = persisted_machine
    else:
        machine = collect_machine_receipt()

    environment_path = output_dir / "run-environment-receipt.json"
    if resume and environment_path.exists():
        environment = RunEnvironmentReceipt.model_validate_json(environment_path.read_text(encoding="utf-8"))
        if environment.machine_receipt_id != machine.semantic_id:
            raise RuntimeError("run environment references a different machine receipt")
    else:
        environment = collect_run_environment_receipt(loaded.spec.campaign_id, machine)

    providers: dict[str, SubprocessProvider] = {}
    build_receipts: list[BuildReceipt] = []
    provider_ids = {family.provider_id for family in loaded.families.values()}
    if "python-control" in provider_ids:
        provider = python_provider("cpubench.providers.control", "python-control")
        providers["python-control"] = provider
        from .providers import control

        build_receipts.append(_python_build_receipt("python-control", Path(control.__file__).resolve(), loaded.spec.implementation_policy))
    if "python-sqlite" in provider_ids:
        provider = python_provider("cpubench.providers.sqlite_anchor", "python-sqlite")
        providers["python-sqlite"] = provider
        from .providers import sqlite_anchor

        build_receipts.append(
            _python_build_receipt(
                "python-sqlite",
                Path(sqlite_anchor.__file__).resolve(),
                loaded.spec.implementation_policy,
            )
        )
    if "native-c11" in provider_ids:
        provider, receipt = ensure_native_provider(output_dir / "build" / "native", loaded.spec.implementation_policy)
        providers["native-c11"] = provider
        build_receipts.append(receipt)

    missing = provider_ids - providers.keys()
    if missing:
        raise RuntimeError(f"no provider adapter for: {sorted(missing)}")

    for provider_id, provider in providers.items():
        descriptor = provider.describe()
        if descriptor.provider_id != provider_id:
            raise RuntimeError(f"provider ID mismatch: expected {provider_id}, got {descriptor.provider_id}")
        self_test = provider.self_test()
        if not self_test.get("ok"):
            raise RuntimeError(f"provider self-test failed for {provider_id}: {self_test}")

    plan_path = output_dir / "run-plan.json"
    if resume and plan_path.exists():
        plan = RunPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
        if plan.instrument_release_id != instrument.semantic_id:
            raise RuntimeError("stored run plan references a different instrument release")
        expected_pack_ids = {release.pack_id: release.semantic_id or "" for release in loaded.pack_releases}
        if plan.pack_release_ids != expected_pack_ids:
            raise RuntimeError("stored run plan references different pack releases")
        if plan.run_environment_receipt_id != environment.semantic_id:
            raise RuntimeError("stored run plan references a different run environment receipt")
    else:
        plan = compile_run_plan(
            loaded.spec,
            loaded.profile,
            machine,
            environment,
            instrument,
            loaded.packs,
            loaded.pack_releases,
        )

    return CampaignRuntime(
        loaded=loaded,
        instrument=instrument,
        machine=machine,
        environment=environment,
        plan=plan,
        providers=providers,
        build_receipts=build_receipts,
        store=store,
    )


def persist_runtime(runtime: CampaignRuntime) -> None:
    store = runtime.store
    loaded = runtime.loaded
    _write_artifact_once(store, "campaign-spec.json", loaded.spec)
    _write_artifact_once(store, "instrument-release.json", runtime.instrument)
    _write_artifact_once(store, "profile.json", loaded.profile)
    _write_artifact_once(store, "machine-receipt.json", runtime.machine)
    _write_artifact_once(store, "run-environment-receipt.json", runtime.environment)
    _write_artifact_once(store, "run-plan.json", runtime.plan)
    pack_release_by_id = {release.pack_id: release for release in loaded.pack_releases}
    for pack, families in loaded.packs:
        _write_artifact_once(store, f"pack-releases/{pack.pack_id}/pack.json", pack)
        _write_artifact_once(store, f"pack-releases/{pack.pack_id}/release.json", pack_release_by_id[pack.pack_id])
        for family in families:
            _write_artifact_once(store, f"pack-releases/{pack.pack_id}/families/{family.family_id}.json", family)
    for receipt in runtime.build_receipts:
        _write_artifact_once(store, f"build-receipts/{receipt.provider_id}.json", receipt)
    store.append_event(
        {
            "event": "campaign_prepared",
            "at": utc_now().isoformat(),
            "campaign_id": loaded.spec.campaign_id,
            "run_plan_id": runtime.plan.semantic_id,
            "planned_attempts": len(runtime.plan.items),
        }
    )


def _write_artifact_once(store: CampaignStore, relative: str, artifact: ArtifactModel) -> None:
    path = store.root / relative
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("semantic_id") != artifact.semantic_id:
            raise RuntimeError(f"refusing to replace artifact with a different semantic identity: {relative}")
        return
    store.write_json(relative, artifact.model_dump(mode="json", exclude_none=True))


def _attempt_path(store: CampaignStore, attempt_id: str) -> Path:
    return store.root / "attempts" / attempt_id / "attempt.json"


def _environment_receipt_relative(receipt_id: str) -> str:
    digest = receipt_id.split(":", 1)[-1]
    return f"run-environments/{digest}.json"


def _assert_attempt_matches_plan(
    store: CampaignStore,
    item: RunPlanItem,
    attempt: AttemptRecord,
) -> None:
    request_path = store.root / "attempts" / item.attempt_id / "request.json"
    if not request_path.exists():
        raise RuntimeError(f"attempt request is missing: {item.attempt_id}")
    request = RunPlanItem.model_validate_json(request_path.read_text(encoding="utf-8"))
    if request.model_dump(mode="json") != item.model_dump(mode="json"):
        raise RuntimeError(f"attempt request differs from frozen plan: {item.attempt_id}")
    expected = {
        "attempt_id": item.attempt_id,
        "family_id": item.family_id,
        "point_id": item.point_id,
        "provider_id": item.provider_id,
        "requested_parameters": item.parameters,
    }
    observed = {
        "attempt_id": attempt.attempt_id,
        "family_id": attempt.family_id,
        "point_id": attempt.point_id,
        "provider_id": attempt.provider_id,
        "requested_parameters": attempt.requested_parameters,
    }
    if observed != expected:
        raise RuntimeError(f"attempt record differs from frozen plan: {item.attempt_id}")
    if attempt.placement.selector != item.placement:
        raise RuntimeError(f"attempt placement differs from frozen plan: {item.attempt_id}")


def _write_attempt(
    store: CampaignStore,
    item: RunPlanItem,
    attempt: AttemptRecord,
    placement: PlacementReceipt,
    run_environment_receipt_id: str,
) -> AttemptRecord:
    attempt_dir = store.attempt_dir(item.attempt_id)
    atomic_write_json(attempt_dir / "request.json", item.model_dump(mode="json"))
    attempt = attempt.model_copy(
        update={
            "placement": placement,
            "run_environment_receipt_id": run_environment_receipt_id,
            "semantic_id": None,
        }
    ).with_semantic_id()
    attempt_data = attempt.model_dump(
        mode="json",
        exclude_none=True,
        exclude={"provider_stdout", "provider_stderr"},
    )
    atomic_write_json(attempt_dir / "attempt.json", attempt_data)
    sample_lines = "".join(
        json.dumps(sample.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n"
        for sample in attempt.samples
    )
    atomic_write_text(attempt_dir / "samples.ndjson", sample_lines)
    atomic_write_json(attempt_dir / "output.json", attempt.work_output)
    atomic_write_json(attempt_dir / "placement.json", placement.model_dump(mode="json", exclude_none=True))
    if attempt.provider_stdout:
        atomic_write_text(attempt_dir / "provider.stdout.ndjson", attempt.provider_stdout)
    if attempt.provider_stderr:
        atomic_write_text(attempt_dir / "provider.stderr.log", attempt.provider_stderr)
    elif attempt.warnings:
        atomic_write_text(attempt_dir / "provider.stderr.log", "\n".join(attempt.warnings) + "\n")
    return attempt


def execute_campaign(runtime: CampaignRuntime, *, resume: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}
    store = runtime.store
    current_machine = collect_machine_receipt()
    if current_machine.semantic_id != runtime.machine.semantic_id:
        raise RuntimeError(
            "current machine identity differs from the frozen run plan; "
            "start a new campaign rather than executing on another machine or boot"
        )
    session_environment = collect_run_environment_receipt(runtime.loaded.spec.campaign_id, runtime.machine)
    if session_environment.semantic_id is None:
        raise RuntimeError("run environment receipt is missing a semantic identity")
    _write_artifact_once(
        store,
        _environment_receipt_relative(session_environment.semantic_id),
        session_environment,
    )
    store.append_event(
        {
            "event": "execution_session_started",
            "at": utc_now().isoformat(),
            "run_environment_receipt_id": session_environment.semantic_id,
        }
    )
    for item in runtime.plan.items:
        existing = _attempt_path(store, item.attempt_id)
        if resume and existing.exists():
            previous = AttemptRecord.model_validate_json(existing.read_text(encoding="utf-8"))
            _assert_attempt_matches_plan(store, item, previous)
            counts[previous.state.value] = counts.get(previous.state.value, 0) + 1
            continue
        store.append_event(
            {
                "event": "attempt_started",
                "at": utc_now().isoformat(),
                "attempt_id": item.attempt_id,
                "sequence_index": item.sequence_index,
            }
        )
        try:
            with placement_scope(item.placement) as placement_session:
                attempt = runtime.providers[item.provider_id].run_attempt(item)
                placement_session.complete(attempt.effective_parameters)
            placement = placement_session.receipt
        except PlacementError as exc:
            placement = exc.receipt
            attempt = AttemptRecord(
                attempt_id=item.attempt_id,
                state=exc.attempt_state,
                family_id=item.family_id,
                point_id=item.point_id,
                provider_id=item.provider_id,
                requested_parameters=item.parameters,
                started_at=utc_now(),
                finished_at=utc_now(),
                reason_code=exc.reason_code,
                detail=exc.detail,
            ).with_semantic_id()
        attempt = _write_attempt(
            store,
            item,
            attempt,
            placement,
            session_environment.semantic_id,
        )
        counts[attempt.state.value] = counts.get(attempt.state.value, 0) + 1
        store.append_event(
            {
                "event": "attempt_terminal",
                "at": utc_now().isoformat(),
                "attempt_id": item.attempt_id,
                "state": attempt.state.value,
                "reason_code": attempt.reason_code,
            }
        )
    store.append_event(
        {
            "event": "campaign_execution_complete",
            "at": utc_now().isoformat(),
            "counts": counts,
        }
    )
    return counts


def finalize_campaign(campaign_dir: Path) -> dict[str, Any]:
    root = campaign_dir.resolve()
    store = CampaignStore(root)
    required = [
        "campaign-spec.json",
        "instrument-release.json",
        "profile.json",
        "machine-receipt.json",
        "run-environment-receipt.json",
        "run-plan.json",
        "validation/validation-bundle.json",
        "analysis/analysis-bundle.json",
        "report/index.html",
        "report/summary.json",
    ]
    missing_required = [relative for relative in required if not (root / relative).exists()]
    if missing_required:
        raise RuntimeError(f"campaign cannot be finalized; required artifacts are missing: {missing_required}")

    plan = RunPlan.model_validate_json((root / "run-plan.json").read_text(encoding="utf-8"))
    profile = ProfileSpec.model_validate_json((root / "profile.json").read_text(encoding="utf-8"))
    if not profile.semantic_identity_is_valid():
        raise RuntimeError("profile semantic identity does not match its persisted content")
    if profile.semantic_id != plan.profile_id:
        raise RuntimeError("profile does not match the frozen run plan")
    expected_ids = {item.attempt_id for item in plan.items}
    attempt_paths = list((root / "attempts").glob("*/attempt.json"))
    attempts = [AttemptRecord.model_validate_json(path.read_text(encoding="utf-8")) for path in attempt_paths]
    observed_ids = {attempt.attempt_id for attempt in attempts}
    missing_attempts = sorted(expected_ids - observed_ids)
    unexpected_attempts = sorted(observed_ids - expected_ids)
    if missing_attempts or unexpected_attempts:
        raise RuntimeError(
            "campaign attempt population does not match the frozen plan; "
            f"missing={missing_attempts} unexpected={unexpected_attempts}"
        )
    incomplete = sorted(
        attempt.attempt_id
        for attempt in attempts
        if attempt.state in {AttemptState.PLANNED, AttemptState.INCOMPLETE}
    )
    if incomplete:
        raise RuntimeError(f"campaign contains non-terminal attempts: {incomplete}")
    items_by_id = {item.attempt_id: item for item in plan.items}
    for attempt in attempts:
        item = items_by_id[attempt.attempt_id]
        _assert_attempt_matches_plan(store, item, attempt)
        if not attempt.run_environment_receipt_id:
            raise RuntimeError(f"attempt lacks an execution environment receipt: {attempt.attempt_id}")
        environment_path = root / _environment_receipt_relative(attempt.run_environment_receipt_id)
        if not environment_path.exists():
            raise RuntimeError(f"attempt environment receipt is missing: {attempt.attempt_id}")
        execution_environment = RunEnvironmentReceipt.model_validate_json(
            environment_path.read_text(encoding="utf-8")
        )
        if execution_environment.semantic_id != attempt.run_environment_receipt_id:
            raise RuntimeError(f"attempt environment identity mismatch: {attempt.attempt_id}")
        if execution_environment.machine_receipt_id != plan.machine_receipt_id:
            raise RuntimeError(f"attempt environment references another machine: {attempt.attempt_id}")
        placement_path = root / "attempts" / attempt.attempt_id / "placement.json"
        if not placement_path.exists():
            raise RuntimeError(f"attempt placement receipt is missing: {attempt.attempt_id}")
        placement = PlacementReceipt.model_validate_json(placement_path.read_text(encoding="utf-8"))
        if placement != attempt.placement:
            raise RuntimeError(f"attempt placement receipt mismatch: {attempt.attempt_id}")
        recomputed = attempt.model_copy(update={"semantic_id": None}).with_semantic_id()
        if recomputed.semantic_id != attempt.semantic_id:
            raise RuntimeError(f"attempt semantic identity mismatch: {attempt.attempt_id}")

    validation = ValidationBundle.model_validate_json(
        (root / "validation" / "validation-bundle.json").read_text(encoding="utf-8")
    )
    if validation.run_plan_id != plan.semantic_id:
        raise RuntimeError("validation bundle references a different run plan")
    if {item.attempt_id for item in validation.attempts} != expected_ids:
        raise RuntimeError("validation bundle does not cover the frozen attempt population")
    recomputed_validation = validation.model_copy(update={"semantic_id": None}).with_semantic_id()
    if recomputed_validation.semantic_id != validation.semantic_id:
        raise RuntimeError("validation bundle semantic identity mismatch")

    analysis = AnalysisBundle.model_validate_json(
        (root / "analysis" / "analysis-bundle.json").read_text(encoding="utf-8")
    )
    if analysis.validation_bundle_id != validation.semantic_id:
        raise RuntimeError("analysis bundle references a different validation bundle")
    recomputed_analysis = analysis.model_copy(update={"semantic_id": None}).with_semantic_id()
    if recomputed_analysis.semantic_id != analysis.semantic_id:
        raise RuntimeError("analysis bundle semantic identity mismatch")

    return store.finalize()


def preflight_summary(path: Path, profile_override: str | None = None) -> dict[str, Any]:
    loaded = load_campaign_bundle(path, profile_override)
    machine = collect_machine_receipt()
    environment = collect_run_environment_receipt(loaded.spec.campaign_id, machine)
    instrument = current_instrument_release()
    plan = compile_run_plan(
        loaded.spec,
        loaded.profile,
        machine,
        environment,
        instrument,
        loaded.packs,
        loaded.pack_releases,
    )
    provider_ids = sorted({item.provider_id for item in plan.items})
    return {
        "campaign_id": loaded.spec.campaign_id,
        "profile": loaded.profile.profile_id,
        "operating_mode": loaded.spec.operating_mode.value,
        "instrument_release": instrument.semantic_id,
        "run_environment_receipt": environment.semantic_id,
        "pack_releases": {release.pack_id: release.semantic_id for release in loaded.pack_releases},
        "providers": provider_ids,
        "families": sorted(loaded.families),
        "planned_attempts": len(plan.items),
        "samples": sum(item.samples_per_attempt for item in plan.items),
        "estimated_peak_working_set_bytes": max(
            (int(item.parameters.get("working_set_bytes", 0)) for item in plan.items),
            default=0,
        ),
        "output_dir": str(campaign_output_dir(loaded)),
        "capability_limits": machine.known_unknowns,
    }


def initialize_campaign(path: Path, *, campaign_id: str = "example-review") -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    content = f"""schema_version: 1
artifact_kind: campaign_spec
campaign_id: {campaign_id}
title: Example CPU review campaign
description: >-
  A runnable public campaign using calibration controls and the first memory-access pack.
profile: profiles/smoke.yaml
packs:
  - pack: packs/controls/pack.yaml
  - pack: packs/memory-access/pack.yaml
operating_mode: characterization
implementation_policy: native
placement: scheduler_open
output_root: .cpubench/runs
schedule_seed: 20261004
public_claims_enabled: false
"""
    path.write_text(content, encoding="utf-8")
    return path

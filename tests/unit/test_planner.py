from pathlib import Path

from cpubench.campaign import load_campaign_bundle
from cpubench.instrument import current_instrument_release
from cpubench.planner import compile_run_plan
from cpubench.platform_probe import collect_machine_receipt
from cpubench.platform_probe import collect_run_environment_receipt


def test_smoke_plan_is_deterministic() -> None:
    loaded = load_campaign_bundle(Path("examples/quickstart.yaml"))
    machine = collect_machine_receipt()
    environment = collect_run_environment_receipt(loaded.spec.campaign_id, machine)
    instrument = current_instrument_release()
    first = compile_run_plan(
        loaded.spec,
        loaded.profile,
        machine,
        environment,
        instrument,
        loaded.packs,
        loaded.pack_releases,
    )
    second = compile_run_plan(
        loaded.spec,
        loaded.profile,
        machine,
        environment,
        instrument,
        loaded.packs,
        loaded.pack_releases,
    )
    assert [item.attempt_id for item in first.items] == [item.attempt_id for item in second.items]
    assert first.profile_id == loaded.profile.semantic_id
    assert len(first.items) >= 4

from cpubench.models import ImplementationPolicy, OperatingMode, RunPlanItem
from cpubench.provider import python_provider


def test_control_provider_contract() -> None:
    provider = python_provider("cpubench.providers.control", "python-control")
    descriptor = provider.describe()
    assert descriptor.provider_id == "python-control"
    assert provider.self_test()["ok"] is True
    item = RunPlanItem(
        attempt_id="test-control",
        sequence_index=0,
        instrument_release_id="sha256:test-instrument",
        pack_release_id="sha256:test-pack",
        pack_id="controls",
        family_id="controls.timer_overhead",
        family_version="0.1.0",
        point_id="timer-1k",
        form_id="baseline",
        provider_id="python-control",
        parameters={"completed_units": 100},
        attempt_index=0,
        samples_per_attempt=2,
        warmup_samples=1,
        timeout_seconds=10,
        operating_mode=OperatingMode.CHARACTERIZATION,
        implementation_policy=ImplementationPolicy.NATIVE,
        placement="scheduler_open",
    )
    attempt = provider.run_attempt(item)
    assert attempt.state.value == "completed"
    assert len(attempt.samples) == 2
    assert attempt.provider_stdout
    assert attempt.provider_stderr == ""

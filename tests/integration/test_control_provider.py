from cpubench.models import ImplementationPolicy, OperatingMode, RunPlanItem
from cpubench.provider import python_provider


def test_control_provider_contract() -> None:
    provider = python_provider("cpubench.providers.control", "python-control")
    descriptor = provider.describe()
    assert descriptor.provider_id == "python-control"
    assert descriptor.provider_version == "0.2.0"
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
    assert ("placement_start_cpu" in attempt.effective_parameters) == (
        "placement_end_cpu" in attempt.effective_parameters
    )
    assert len(attempt.samples) == 2
    assert attempt.effective_parameters["timer_control"] is True
    assert attempt.provider_stdout
    assert attempt.provider_stderr == ""

    for sample in attempt.samples:
        metrics = sample.metrics
        assert metrics["non_monotonic_count"] == 0
        assert metrics["zero_delta_count"] >= 0
        assert metrics["min_positive_delta_ns"] >= 0
        assert metrics["max_delta_ns"] >= metrics["min_positive_delta_ns"]
        assert metrics["sum_pair_delta_ns"] >= metrics["max_delta_ns"]
        if metrics["min_positive_delta_ns"] == 0:
            assert metrics["zero_delta_count"] == sample.completed_units

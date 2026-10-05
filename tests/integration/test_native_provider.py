from pathlib import Path

import pytest

from cpubench.models import ImplementationPolicy, OperatingMode, RunPlanItem
from cpubench.native import ensure_native_provider


@pytest.mark.native
def test_native_provider_builds_and_runs(tmp_path: Path) -> None:
    provider, receipt = ensure_native_provider(tmp_path / "build")
    assert receipt.binary_digest.startswith("sha256:")
    assert provider.self_test()["ok"] is True
    item = RunPlanItem(
        attempt_id="test-native",
        sequence_index=0,
        instrument_release_id="sha256:test-instrument",
        pack_release_id="sha256:test-pack",
        pack_id="memory-access",
        family_id="memory.dependent_load_latency",
        family_version="0.1.0",
        point_id="ws-32k",
        form_id="random_pointer_chase",
        provider_id="native-c11",
        parameters={"working_set_bytes": 32768, "chains": 1, "completed_units": 20000, "seed": 1},
        attempt_index=0,
        samples_per_attempt=2,
        warmup_samples=1,
        timeout_seconds=60,
        operating_mode=OperatingMode.CHARACTERIZATION,
        implementation_policy=ImplementationPolicy.NATIVE,
        placement="scheduler_open",
    )
    attempt = provider.run_attempt(item)
    assert attempt.state.value == "completed"
    assert attempt.effective_parameters["cycle_validated"] is True
    assert len(attempt.samples) == 2

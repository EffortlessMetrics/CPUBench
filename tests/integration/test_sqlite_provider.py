from cpubench.provider import python_provider
from cpubench.models import RunPlanItem


def test_sqlite_provider_self_test_and_run() -> None:
    provider = python_provider("cpubench.providers.sqlite_anchor", "python-sqlite")
    descriptor = provider.describe()
    assert descriptor.provider_id == "python-sqlite"
    assert provider.self_test()["ok"] is True
    attempt = provider.run_attempt(
        RunPlanItem(
            attempt_id="sqlite-attempt",
            sequence_index=0,
            instrument_release_id="sha256:test-instrument",
            pack_release_id="sha256:test-pack",
            pack_id="application-sqlite",
            family_id="application.sqlite_index_lookup",
            family_version="0.1.0",
            point_id="rows-1k",
            form_id="warm_indexed_lookup",
            provider_id="python-sqlite",
            parameters={"rows": 1000, "payload_bytes": 16, "completed_units": 200, "seed": 1},
            attempt_index=0,
            samples_per_attempt=2,
            warmup_samples=1,
            timeout_seconds=30,
            operating_mode="characterization",
            implementation_policy="native",
            placement="scheduler_open",
        )
    )
    assert attempt.state.value == "completed"
    assert len(attempt.samples) == 2
    assert attempt.effective_parameters["database_validated"] is True
    assert all(sample.completed_units == 200 for sample in attempt.samples)

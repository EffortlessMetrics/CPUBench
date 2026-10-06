from cpubench.canonical import semantic_id
from cpubench.models import (
    AttemptRecord,
    AttemptState,
    BuildReceipt,
    CapabilityState,
    ImplementationPolicy,
    PlacementReceipt,
)


def test_build_receipt_identity_ignores_local_path_and_logs() -> None:
    left = BuildReceipt(
        provider_id="native-c11",
        implementation_id="native-c11-v0",
        source_digest="sha256:source",
        compiler="cc 1.0",
        commands=[["cc", "-O3", "provider.c"]],
        binary_path="/tmp/a/cpubench-native",
        binary_digest="sha256:binary",
        build_policy=ImplementationPolicy.NATIVE,
        logs=["built under /tmp/a"],
    ).with_semantic_id()
    right = BuildReceipt(
        provider_id="native-c11",
        implementation_id="native-c11-v0",
        source_digest="sha256:source",
        compiler="cc 1.0",
        commands=[],
        binary_path="C:/different/cpubench-native.exe",
        binary_digest="sha256:binary",
        build_policy=ImplementationPolicy.NATIVE,
        logs=["built somewhere else"],
    ).with_semantic_id()
    assert left.semantic_id == right.semantic_id


def test_attempt_identity_is_recomputable_without_raw_channels() -> None:
    attempt = AttemptRecord(
        attempt_id="attempt-1",
        state=AttemptState.COMPLETED,
        family_id="controls.timer_overhead",
        point_id="timer-1k",
        provider_id="python-control",
        placement={"selector": "cpu:1", "verified": True},
        provider_stdout='{"record_type":"sample"}\n',
        provider_stderr="diagnostic\n",
    ).with_semantic_id()
    reconstructed = AttemptRecord.model_validate_json(
        attempt.model_dump_json(exclude={"provider_stdout", "provider_stderr"})
    )
    recomputed = reconstructed.model_copy(update={"semantic_id": None}).with_semantic_id()
    assert recomputed.semantic_id == attempt.semantic_id


def test_legacy_placement_payload_preserves_attempt_identity() -> None:
    typed = AttemptRecord(
        attempt_id="legacy-attempt",
        state=AttemptState.COMPLETED,
        family_id="memory.dependent_load_latency",
        point_id="ws-32k",
        provider_id="native-c11",
        placement=PlacementReceipt(
            selector="cpu:1",
            platform="linux",
            state=CapabilityState.AVAILABLE_UNQUALIFIED,
            authority="test",
            requested=True,
            request_verified=True,
            requested_cpus=[1],
            accepted_cpus=[1],
            observed_cpus=[1],
            reason_code="test",
        ),
    )
    legacy_placement = {
        "selector": "cpu:1",
        "requested": True,
        "verified": True,
        "observed": [1],
    }
    payload = typed.semantic_payload()
    payload["placement"] = legacy_placement
    raw = typed.model_dump(mode="python")
    raw["placement"] = legacy_placement
    raw["semantic_id"] = semantic_id("attempt_record", typed.schema_version, payload)

    restored = AttemptRecord.model_validate(raw)

    assert restored.placement.authority == "legacy_untyped_placement"
    assert restored.semantic_identity_is_valid()

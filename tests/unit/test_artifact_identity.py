from cpubench.models import AttemptRecord, AttemptState, BuildReceipt, ImplementationPolicy


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

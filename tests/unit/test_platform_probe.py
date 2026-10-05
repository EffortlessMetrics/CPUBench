from cpubench.models import CapabilityState
from cpubench.platform_probe import collect_machine_receipt


def test_doctor_emits_machine_receipt() -> None:
    receipt = collect_machine_receipt()
    assert receipt.semantic_id
    assert receipt.cpu["logical_processors"] >= 1
    assert "hostname_hash" in receipt.system
    assert "hostname" not in receipt.system
    assert receipt.capabilities["timer.python_monotonic_ns"].state in {
        CapabilityState.QUALIFIED,
        CapabilityState.AVAILABLE_UNQUALIFIED,
    }
    assert receipt.capabilities["timer.native_interval"].state in {
        CapabilityState.QUALIFIED,
        CapabilityState.AVAILABLE_UNQUALIFIED,
        CapabilityState.UNKNOWN,
    }

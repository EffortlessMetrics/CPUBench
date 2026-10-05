from pathlib import Path

from cpubench.integrity import run_integrity_demo


def test_integrity_demo_separates_gamed_provider(tmp_path: Path) -> None:
    result = run_integrity_demo(tmp_path)
    assert result["results"]["honest"]["finding"] == "no_material_divergence"
    assert result["results"]["gamed"]["finding"] == "identity_sensitive_divergence"

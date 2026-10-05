import json
from pathlib import Path

from cpubench.evidence import CampaignStore


def test_campaign_store_finalize_and_verify(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "run")
    store.write_json("a.json", {"value": 1})
    store.append_event({"event": "test"})
    manifest = store.finalize()
    assert "a.json" in manifest["files"]
    assert store.verify().valid


def test_campaign_store_detects_tampering(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "run")
    store.write_json("a.json", {"value": 1})
    store.finalize()
    (store.root / "a.json").write_text(json.dumps({"value": 2}), encoding="utf-8")
    result = store.verify()
    assert not result.valid
    assert result.mismatches == ["a.json"]


def test_campaign_store_detects_unexpected_files(tmp_path: Path) -> None:
    store = CampaignStore(tmp_path / "run")
    store.write_json("a.json", {"value": 1})
    store.finalize()
    (store.root / "injected.txt").write_text("unexpected", encoding="utf-8")
    result = store.verify()
    assert not result.valid
    assert result.unexpected == ["injected.txt"]

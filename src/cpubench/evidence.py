from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .canonical import canonical_json_text, sha256_file
from .models import VerificationResult


EXCLUDED_FROM_MANIFEST = {"manifest.json", "verification.json"}


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, canonical_json_text(value, pretty=True))


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = canonical_json_text(event, pretty=False) + "\n"
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


class CampaignStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def finalized(self) -> bool:
        return (self.root / "manifest.json").exists()

    def assert_mutable(self) -> None:
        if self.finalized:
            raise RuntimeError(f"campaign is finalized and immutable: {self.root}")

    def write_json(self, relative: str, value: Any) -> Path:
        self.assert_mutable()
        path = self.root / relative
        atomic_write_json(path, value)
        return path

    def append_event(self, event: dict[str, Any]) -> None:
        self.assert_mutable()
        append_event(self.root / "events.ndjson", event)

    def attempt_dir(self, attempt_id: str) -> Path:
        path = self.root / "attempts" / attempt_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def finalize(self) -> dict[str, Any]:
        self.assert_mutable()
        files: dict[str, str] = {}
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(self.root).as_posix()
            if relative in EXCLUDED_FROM_MANIFEST:
                continue
            files[relative] = sha256_file(path)
        manifest = {
            "schema_version": 1,
            "artifact_kind": "campaign_manifest",
            "files": files,
        }
        atomic_write_json(self.root / "manifest.json", manifest)
        return manifest

    def verify(self) -> VerificationResult:
        manifest_path = self.root / "manifest.json"
        if not manifest_path.exists():
            return VerificationResult(valid=False, checked_files=0, missing=["manifest.json"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        mismatches: list[str] = []
        missing: list[str] = []
        expected_files = set(manifest.get("files", {}))
        actual_files = {
            path.relative_to(self.root).as_posix()
            for path in self.root.rglob("*")
            if path.is_file() and path.relative_to(self.root).as_posix() not in EXCLUDED_FROM_MANIFEST
        }
        unexpected = sorted(actual_files - expected_files)
        checked = 0
        for relative, expected in manifest.get("files", {}).items():
            path = self.root / relative
            if not path.exists():
                missing.append(relative)
                continue
            checked += 1
            actual = sha256_file(path)
            if actual != expected:
                mismatches.append(relative)
        valid = not mismatches and not missing and not unexpected
        result = VerificationResult(
            valid=valid,
            checked_files=checked,
            mismatches=mismatches,
            missing=missing,
            unexpected=unexpected,
        )
        atomic_write_json(self.root / "verification.json", result.model_dump(mode="json"))
        return result

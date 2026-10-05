from __future__ import annotations

import hashlib
from pathlib import Path

from . import __version__
from .models import FamilySpec, InstrumentRelease, PackRelease, PackSpec


def _package_digest() -> str:
    """Hash the installed Python control plane and bundled public resources."""
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def current_instrument_release() -> InstrumentRelease:
    control_plane_digest = _package_digest()
    return InstrumentRelease(
        instrument_id="cpubench-python",
        instrument_version=__version__,
        provider_protocol_version=1,
        evidence_format_version=1,
        control_plane_digest=control_plane_digest,
        components={
            "control_plane": control_plane_digest,
            "provider_protocol": "1",
            "evidence_format": "1",
            "schema_generation": "pydantic-v2",
        },
        known_limits=[
            "platform measurement authority is capability-scoped",
            "the alpha has not completed publication-grade multi-machine qualification",
            "active challenge-pack execution against real products is not yet included",
        ],
    ).with_semantic_id()


def compile_pack_release(pack: PackSpec, families: list[FamilySpec]) -> PackRelease:
    return PackRelease(
        pack_id=pack.pack_id,
        pack_version=pack.pack_version,
        title=pack.title,
        role=pack.role,
        disclosure=pack.disclosure,
        pack_spec_id=pack.semantic_id or "",
        family_spec_ids={family.family_id: family.semantic_id or "" for family in families},
        family_versions={family.family_id: family.family_version for family in families},
        parent_ids=[pack.semantic_id or "", *(family.semantic_id or "" for family in families)],
    ).with_semantic_id()

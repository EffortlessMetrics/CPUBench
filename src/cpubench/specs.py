from __future__ import annotations

from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path
from typing import Iterator, TypeVar

from pydantic import BaseModel

from .models import CampaignSpec, FamilySpec, PackSpec, ProfileSpec
from .serde import load_model

T = TypeVar("T", bound=BaseModel)


@contextmanager
def resolved_spec(path_text: str, *, base_dir: Path | None = None) -> Iterator[Path]:
    candidate = Path(path_text)
    if not candidate.is_absolute() and base_dir is not None:
        local = (base_dir / candidate).resolve()
        if local.exists():
            yield local
            return
    if candidate.exists():
        yield candidate.resolve()
        return
    resource = files("cpubench.resources").joinpath(path_text)
    if not resource.is_file():
        raise FileNotFoundError(f"spec not found: {path_text}")
    with as_file(resource) as materialized:
        yield Path(materialized)


def load_campaign(path: Path) -> CampaignSpec:
    return load_model(path, CampaignSpec).with_semantic_id()


def load_profile(path_text: str, *, base_dir: Path | None = None) -> ProfileSpec:
    with resolved_spec(path_text, base_dir=base_dir) as path:
        return load_model(path, ProfileSpec).with_semantic_id()


def load_pack(path_text: str, *, base_dir: Path | None = None) -> tuple[PackSpec, list[FamilySpec]]:
    with resolved_spec(path_text, base_dir=base_dir) as path:
        pack = load_model(path, PackSpec).with_semantic_id()
        family_base = path.parent
        families: list[FamilySpec] = []
        for ref in pack.families:
            with resolved_spec(ref.family, base_dir=family_base) as family_path:
                families.append(load_model(family_path, FamilySpec).with_semantic_id())
        return pack, families

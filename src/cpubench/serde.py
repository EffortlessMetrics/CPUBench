from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel

from .canonical import canonical_json_text

T = TypeVar("T", bound=BaseModel)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected mapping in {path}")
    return value


def load_model(path: Path, model: type[T]) -> T:
    if path.suffix.lower() in {".yaml", ".yml"}:
        raw = load_yaml(path)
    else:
        raw = json.loads(path.read_text(encoding="utf-8"))
    return model.model_validate(raw)


def dump_model(path: Path, value: BaseModel, *, pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        canonical_json_text(value.model_dump(mode="json", exclude_none=True), pretty=pretty),
        encoding="utf-8",
    )

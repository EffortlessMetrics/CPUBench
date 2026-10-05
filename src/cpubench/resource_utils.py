from __future__ import annotations

from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path
from typing import Iterator


@contextmanager
def resource_path(relative: str) -> Iterator[Path]:
    """Materialize one packaged resource path for the duration of the context."""
    target = files("cpubench.resources").joinpath(relative)
    with as_file(target) as materialized:
        yield Path(materialized)

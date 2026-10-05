from __future__ import annotations

import sys
from pathlib import Path

import yaml


EXCLUDED_PARTS = {".git", ".venv", "build", "dist", ".cpubench", "runs"}


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    checked = 0
    for path in sorted([*root.rglob("*.yaml"), *root.rglob("*.yml")]):
        if any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts):
            continue
        checked += 1
        try:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, yaml.YAMLError) as exc:
            failures.append(f"{path.relative_to(root)}: {exc}")
            continue
        if value is None:
            failures.append(f"{path.relative_to(root)}: empty YAML document")
    if failures:
        print("YAML validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"YAML documents are valid: {checked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

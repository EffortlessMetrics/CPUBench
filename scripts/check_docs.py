from __future__ import annotations

import re
import sys
from pathlib import Path

LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    files = [repository / "README.md", *sorted((repository / "docs").glob("*.md"))]
    broken: list[str] = []
    for source in files:
        for target in LINK.findall(source.read_text(encoding="utf-8")):
            plain = target.split("#", 1)[0]
            if not plain or "://" in plain or plain.startswith("mailto:"):
                continue
            resolved = (source.parent / plain).resolve()
            if not resolved.exists():
                broken.append(f"{source.relative_to(repository)} -> {target}")
    if broken:
        print("broken documentation links:", file=sys.stderr)
        for item in broken:
            print(f"  {item}", file=sys.stderr)
        return 1
    print("documentation links are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

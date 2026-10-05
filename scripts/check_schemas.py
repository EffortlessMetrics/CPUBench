from __future__ import annotations

import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    committed = repository / "contracts" / "schemas"
    with tempfile.TemporaryDirectory(prefix="cpubench-schemas-") as temp:
        generated = Path(temp)
        result = subprocess.run(
            [sys.executable, "-m", "cpubench", "schema", "export", str(generated)],
            cwd=repository,
            check=False,
        )
        if result.returncode != 0:
            return result.returncode
        left = {path.name for path in committed.glob("*.json")}
        right = {path.name for path in generated.glob("*.json")}
        if left != right:
            print(f"schema file set differs: committed={sorted(left)} generated={sorted(right)}", file=sys.stderr)
            return 1
        changed = [name for name in sorted(left) if not filecmp.cmp(committed / name, generated / name, shallow=False)]
        if changed:
            print(f"generated schemas are stale: {changed}", file=sys.stderr)
            return 1
    print("schemas are current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

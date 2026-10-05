from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .canonical import sha256_file
from .models import BuildReceipt, ImplementationPolicy
from .provider import ProviderCommand, SubprocessProvider
from .resource_utils import resource_path


class NativeBuildError(RuntimeError):
    pass


def _source_digest(source_dir: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        digest.update(path.relative_to(source_dir).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _compiler_identity(build_dir: Path) -> str:
    cache = build_dir / "CMakeCache.txt"
    compiler_path: str | None = None
    if cache.exists():
        for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("CMAKE_C_COMPILER:FILEPATH="):
                compiler_path = line.split("=", 1)[1]
                break
    if not compiler_path:
        compiler_path = os.environ.get("CC") or shutil.which("cc") or "unknown-c-compiler"
    try:
        result = subprocess.run(
            [compiler_path, "--version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        first_line = (result.stdout or result.stderr).splitlines()[0].strip()
        if first_line:
            return f"{compiler_path}: {first_line}"
    except (OSError, subprocess.SubprocessError, IndexError):
        pass
    return compiler_path


def _find_binary(build_dir: Path) -> Path:
    names = {"cpubench-native", "cpubench-native.exe"}
    candidates = [path for path in build_dir.rglob("*") if path.is_file() and path.name in names]
    if not candidates:
        raise NativeBuildError(f"could not find cpubench-native in {build_dir}")
    candidates.sort(key=lambda p: ("Release" not in p.parts, len(p.parts)))
    return candidates[0]


def ensure_native_provider(build_root: Path, policy: ImplementationPolicy = ImplementationPolicy.NATIVE) -> tuple[SubprocessProvider, BuildReceipt]:
    cmake = shutil.which("cmake")
    if not cmake:
        raise NativeBuildError("CMake is required to build the bundled native provider")

    with resource_path("native") as source_dir:
        source_dir = Path(source_dir)
        source_digest = _source_digest(source_dir)
        short = source_digest.split(":", 1)[1][:16]
        build_dir = build_root / short
        binary_marker = build_dir / "binary.path"
        commands: list[list[str]] = []
        logs: list[str] = []

        if binary_marker.exists():
            binary = Path(binary_marker.read_text(encoding="utf-8").strip())
            if binary.exists():
                receipt = BuildReceipt(
                    provider_id="native-c11",
                    implementation_id="native-c11-v0",
                    source_digest=source_digest,
                    compiler=_compiler_identity(build_dir),
                    commands=[],
                    binary_path=str(binary),
                    binary_digest=sha256_file(binary),
                    build_policy=policy,
                    logs=["reused cached native provider"],
                ).with_semantic_id()
                return SubprocessProvider(ProviderCommand("native-c11", [str(binary)])), receipt

        build_dir.mkdir(parents=True, exist_ok=True)
        configure = [
            cmake,
            "-S",
            str(source_dir),
            "-B",
            str(build_dir),
            "-DCMAKE_BUILD_TYPE=Release",
        ]
        if shutil.which("ninja"):
            configure.extend(["-G", "Ninja"])
        build = [cmake, "--build", str(build_dir), "--config", "Release", "--parallel"]

        for command in (configure, build):
            commands.append(command)
            result = subprocess.run(command, text=True, capture_output=True, check=False)
            logs.append(result.stdout)
            logs.append(result.stderr)
            if result.returncode != 0:
                raise NativeBuildError(
                    f"native provider build failed ({result.returncode})\n"
                    f"command: {' '.join(command)}\n{result.stdout}\n{result.stderr}"
                )

        binary = _find_binary(build_dir).resolve()
        binary_marker.write_text(str(binary), encoding="utf-8")
        compiler = _compiler_identity(build_dir)
        receipt = BuildReceipt(
            provider_id="native-c11",
            implementation_id="native-c11-v0",
            source_digest=source_digest,
            compiler=compiler,
            commands=commands,
            binary_path=str(binary),
            binary_digest=sha256_file(binary),
            build_policy=policy,
            logs=[line for line in logs if line.strip()],
        ).with_semantic_id()
        return SubprocessProvider(ProviderCommand("native-c11", [str(binary)])), receipt

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sqlite3
import sys
import time
from typing import Any

from cpubench.models import FamilyDescriptor, ProviderDescriptor


PROVIDER_ID = "python-sqlite"
VERSION = "0.1.0"
FAMILY_ID = "application.sqlite_index_lookup"


def descriptor() -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=PROVIDER_ID,
        provider_version=VERSION,
        families=[
            FamilyDescriptor(
                family_id=FAMILY_ID,
                implementation_id="python-stdlib-sqlite-v0",
                supported_os=["linux", "windows", "darwin"],
                supported_arch=["x86_64", "aarch64", "arm64", "amd64"],
                timing_authority="provider_elapsed",
            )
        ],
    ).with_semantic_id()


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _payload(row_id: int, payload_bytes: int) -> bytes:
    digest = hashlib.sha256(f"cpubench-sqlite:{row_id}".encode("utf-8")).digest()
    repeats = (payload_bytes + len(digest) - 1) // len(digest)
    return (digest * repeats)[:payload_bytes]


def _build_database(rows: int, payload_bytes: int) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA journal_mode=OFF")
    connection.execute("PRAGMA synchronous=OFF")
    connection.execute("PRAGMA temp_store=MEMORY")
    connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, payload BLOB NOT NULL)")
    connection.executemany(
        "INSERT INTO items(id, payload) VALUES (?, ?)",
        ((row_id, _payload(row_id, payload_bytes)) for row_id in range(rows)),
    )
    connection.commit()
    observed = connection.execute("SELECT COUNT(*), SUM(LENGTH(payload)) FROM items").fetchone()
    if observed != (rows, rows * payload_bytes):
        raise RuntimeError(f"database validation failed: expected {(rows, rows * payload_bytes)}, observed {observed}")
    return connection


def _query_keys(rows: int, completed_units: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    return [rng.randrange(rows) for _ in range(completed_units)]


def _run_batch(cursor: sqlite3.Cursor, keys: list[int]) -> int:
    checksum = 0
    for key in keys:
        row = cursor.execute("SELECT payload FROM items WHERE id = ?", (key,)).fetchone()
        if row is None:
            raise RuntimeError(f"missing row: {key}")
        payload = row[0]
        checksum = ((checksum * 1_099_511_628_211) ^ payload[0] ^ payload[-1] ^ key) & 0xFFFFFFFFFFFFFFFF
    return checksum


def run_lookup(
    samples: int,
    warmups: int,
    rows: int,
    completed_units: int,
    seed: int,
    payload_bytes: int,
) -> int:
    if rows <= 0 or completed_units <= 0 or payload_bytes <= 0:
        raise ValueError("rows, completed_units, and payload_bytes must be positive")

    connection = _build_database(rows, payload_bytes)
    cursor = connection.cursor()
    key_sets = [_query_keys(rows, completed_units, seed + index) for index in range(warmups + samples)]

    emit(
        {
            "record_type": "metadata",
            "family_id": FAMILY_ID,
            "timer": "python.time.monotonic_ns",
            "setup_excluded": True,
            "database_validated": True,
            "database_location": "sqlite-memory",
            "rows": rows,
            "payload_bytes": payload_bytes,
            "sqlite_version": sqlite3.sqlite_version,
            "python_version": sys.version.split()[0],
            "warm_state": True,
        }
    )

    for sample_index, keys in enumerate(key_sets):
        start = time.monotonic_ns()
        checksum = _run_batch(cursor, keys)
        end = time.monotonic_ns()
        if sample_index < warmups:
            continue
        emit(
            {
                "record_type": "sample",
                "sample_index": sample_index - warmups,
                "elapsed_ns": max(1, end - start),
                "completed_units": completed_units,
                "checksum": f"sqlite:{checksum:016x}",
                "timer": "python.time.monotonic_ns",
                "rows": rows,
                "payload_bytes": payload_bytes,
            }
        )

    cursor.close()
    connection.close()
    return 0


def self_test() -> dict[str, Any]:
    connection = _build_database(128, 16)
    cursor = connection.cursor()
    keys = [0, 1, 127, 64, 5]
    first = _run_batch(cursor, keys)
    second = _run_batch(cursor, keys)
    cursor.close()
    connection.close()
    return {
        "ok": first == second and first != 0,
        "sqlite_version": sqlite3.sqlite_version,
        "checksum": f"{first:016x}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="cpubench-sqlite-provider")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("describe")
    sub.add_parser("self-test")
    run = sub.add_parser("run")
    run.add_argument("--family", required=True)
    run.add_argument("--samples", type=int, required=True)
    run.add_argument("--warmup-samples", type=int, default=0)
    run.add_argument("--rows", type=int, default=10_000)
    run.add_argument("--completed-units", type=int, default=5_000)
    run.add_argument("--seed", type=int, default=401)
    run.add_argument("--payload-bytes", type=int, default=32)
    args, _unknown = parser.parse_known_args()

    if args.command == "describe":
        print(descriptor().model_dump_json(exclude_none=True))
        return 0
    if args.command == "self-test":
        print(json.dumps(self_test(), sort_keys=True))
        return 0
    if args.family != FAMILY_ID:
        return 64

    try:
        return run_lookup(
            args.samples,
            args.warmup_samples,
            args.rows,
            args.completed_units,
            args.seed,
            args.payload_bytes,
        )
    except (ValueError, RuntimeError, sqlite3.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())

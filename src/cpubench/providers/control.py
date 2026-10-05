from __future__ import annotations

import argparse
import json
import time
from typing import Any

from cpubench.models import FamilyDescriptor, ProviderDescriptor


PROVIDER_ID = "python-control"
VERSION = "0.2.0"


def descriptor() -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=PROVIDER_ID,
        provider_version=VERSION,
        families=[
            FamilyDescriptor(
                family_id="controls.timer_overhead",
                implementation_id="python-monotonic-ns-v0",
                supported_os=["linux", "windows", "darwin"],
                supported_arch=["x86_64", "aarch64", "arm64", "amd64"],
                timing_authority="provider_elapsed",
            ),
            FamilyDescriptor(
                family_id="controls.sleep_interval",
                implementation_id="python-sleep-v0",
                supported_os=["linux", "windows", "darwin"],
                supported_arch=["x86_64", "aarch64", "arm64", "amd64"],
                timing_authority="provider_elapsed",
            ),
        ],
    ).with_semantic_id()


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def run_timer_overhead(samples: int, warmups: int, completed_units: int) -> int:
    timer = "python.time.monotonic_ns"
    emit({"record_type": "metadata", "setup_excluded": True, "timer": timer, "timer_control": True})
    for sample_index in range(warmups + samples):
        start = time.monotonic_ns()
        checksum = 0
        non_monotonic_count = 0
        zero_delta_count = 0
        min_positive_delta_ns: int | None = None
        max_delta_ns = 0
        sum_pair_delta_ns = 0
        for _ in range(completed_units):
            a = time.monotonic_ns()
            b = time.monotonic_ns()
            if b < a:
                non_monotonic_count += 1
                delta = 0
            else:
                delta = b - a
            if delta == 0:
                zero_delta_count += 1
            else:
                min_positive_delta_ns = (
                    delta if min_positive_delta_ns is None else min(min_positive_delta_ns, delta)
                )
                max_delta_ns = max(max_delta_ns, delta)
            sum_pair_delta_ns += delta
            checksum ^= delta
        end = time.monotonic_ns()
        if sample_index < warmups:
            continue
        emit(
            {
                "record_type": "sample",
                "sample_index": sample_index - warmups,
                "elapsed_ns": max(1, end - start),
                "completed_units": completed_units,
                "checksum": f"timer:{checksum}:{non_monotonic_count}:{zero_delta_count}",
                "timer": timer,
                "non_monotonic_count": non_monotonic_count,
                "zero_delta_count": zero_delta_count,
                "min_positive_delta_ns": min_positive_delta_ns or 0,
                "max_delta_ns": max_delta_ns,
                "sum_pair_delta_ns": sum_pair_delta_ns,
            }
        )
    return 0


def run_sleep_interval(samples: int, warmups: int, sleep_ns: int) -> int:
    emit({"record_type": "metadata", "setup_excluded": True, "timer": "python.time.monotonic_ns"})
    for sample_index in range(warmups + samples):
        start = time.monotonic_ns()
        time.sleep(sleep_ns / 1_000_000_000)
        end = time.monotonic_ns()
        if sample_index < warmups:
            continue
        emit(
            {
                "record_type": "sample",
                "sample_index": sample_index - warmups,
                "elapsed_ns": max(1, end - start),
                "completed_units": 1,
                "checksum": f"sleep:{sleep_ns}",
                "timer": "python.time.monotonic_ns",
                "requested_sleep_ns": sleep_ns,
            }
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="cpubench-control-provider")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("describe")
    sub.add_parser("self-test")
    run = sub.add_parser("run")
    run.add_argument("--family", required=True)
    run.add_argument("--samples", type=int, required=True)
    run.add_argument("--warmup-samples", type=int, default=0)
    run.add_argument("--completed-units", type=int, default=1_000)
    run.add_argument("--sleep-ns", type=int, default=5_000_000)
    args, _unknown = parser.parse_known_args()

    if args.command == "describe":
        print(descriptor().model_dump_json(exclude_none=True))
        return 0
    if args.command == "self-test":
        start = time.monotonic_ns()
        end = time.monotonic_ns()
        print(json.dumps({"ok": end >= start, "timer": "python.time.monotonic_ns"}, sort_keys=True))
        return 0
    if args.family == "controls.timer_overhead":
        return run_timer_overhead(args.samples, args.warmup_samples, args.completed_units)
    if args.family == "controls.sleep_interval":
        return run_sleep_interval(args.samples, args.warmup_samples, args.sleep_ns)
    print(json.dumps({"error": "unsupported family", "family": args.family}), flush=True)
    return 64


if __name__ == "__main__":
    raise SystemExit(main())

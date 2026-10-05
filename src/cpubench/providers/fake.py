from __future__ import annotations

import argparse
import json
import os
import time

from cpubench.models import FamilyDescriptor, ProviderDescriptor


PROVIDER_ID = os.environ.get("CPUBENCH_FAKE_PROVIDER_ID", "fake-honest")
BEHAVIOR = os.environ.get("CPUBENCH_FAKE_BEHAVIOR", "honest")


def descriptor() -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=PROVIDER_ID,
        provider_version="0.1.0",
        families=[
            FamilyDescriptor(
                family_id="integrity.identity_probe",
                implementation_id=f"{PROVIDER_ID}-v0",
                supported_os=["linux", "windows", "darwin"],
                supported_arch=["any"],
                timing_authority="provider_elapsed",
            )
        ],
    ).with_semantic_id()


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("describe")
    sub.add_parser("self-test")
    run = sub.add_parser("run")
    run.add_argument("--family", required=True)
    run.add_argument("--samples", type=int, required=True)
    run.add_argument("--warmup-samples", type=int, default=0)
    run.add_argument("--variant-label", default="baseline")
    run.add_argument("--completed-units", type=int, default=1)
    args, _unknown = parser.parse_known_args()

    if args.command == "describe":
        print(descriptor().model_dump_json(exclude_none=True))
        return 0
    if args.command == "self-test":
        print(json.dumps({"ok": True, "behavior": BEHAVIOR}, sort_keys=True))
        return 0
    if args.family != "integrity.identity_probe":
        return 64

    baseline_ns = 4_000_000
    if BEHAVIOR == "gamed" and args.variant_label == "public":
        baseline_ns = 2_000_000
    if BEHAVIOR == "failing":
        return 3

    for idx in range(args.warmup_samples + args.samples):
        start = time.monotonic_ns()
        target = start + baseline_ns
        while time.monotonic_ns() < target:
            pass
        end = time.monotonic_ns()
        if idx < args.warmup_samples:
            continue
        print(
            json.dumps(
                {
                    "record_type": "sample",
                    "sample_index": idx - args.warmup_samples,
                    "elapsed_ns": max(1, end - start),
                    "completed_units": args.completed_units,
                    "checksum": "integrity:valid",
                    "timer": "python.time.monotonic_ns",
                    "variant_label": args.variant_label,
                    "behavior": BEHAVIOR,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

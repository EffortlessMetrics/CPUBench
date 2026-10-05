# CPUBench

> **Provisional name.** The repository is called **CPUBench** while the product boundary is being proven. The name is expected to change before a stable public release.

CPUBench is an evidence-producing system for CPU review campaigns. It turns a machine, a frozen workload plan, and a declared measurement policy into an inspectable bundle of raw samples, validity decisions, family-level analyses, and article-ready reports.

It is not an overall-score generator. The current alpha proves a smaller chain:

```text
machine receipt
→ planning and per-execution run-environment receipts
→ installed InstrumentRelease and compiled PackRelease identities
→ frozen campaign plan
→ receipted provider build
→ raw attempts and samples
→ obligation-level validation
→ family-level analysis
→ static report
→ immutable manifest and offline verification
```

The Python control plane owns authoring, planning, orchestration, evidence, validation, analysis, and reporting. Timed native work runs in a separate C11 provider, so Python is not inside the measured memory-access loop.

## Current status

`0.2.0a0` is a runnable instrument-development alpha.

Implemented:

- Linux, Windows, and macOS machine/capability receipts;
- immutable campaign plans and filesystem evidence bundles;
- explicit installed-instrument and compiled-pack release identities;
- subprocess provider protocol (`describe`, `self-test`, `run`);
- campaign-qualified Python and native interval timers with measured overhead, effective resolution, and minimum sample duration;
- calibration controls for known-duration intervals;
- native dependent-load-latency and memory-level-parallelism families;
- a scoped warm in-memory SQLite indexed-lookup application anchor;
- obligation-level work and measurement validation;
- median-of-attempt-medians analysis, deterministic bootstrap intervals, and retained raw samples;
- static HTML, Markdown, JSON, and SVG reporting;
- direct comparison of finalized compatible campaigns through `StudySpec`;
- bundle finalization and offline hash verification;
- a known-honest versus known-gamed integrity-detector self-test.

Not yet earned:

- publication-grade validation across the target hardware matrix;
- public/private challenge-pack execution against real systems;
- topology/coherence families;
- validated mechanism-to-application studies beyond the initial SQLite anchor;
- the private official-tool SPEC adapter;
- any universal or named composite CPU score.

See [Current status](docs/CURRENT_STATUS.md) and [Roadmap](docs/ROADMAP.md).

## Quick start

Requirements:

- Python 3.11 or newer;
- CMake 3.20 or newer;
- a C11 compiler for the bundled native provider.

```bash
git clone https://github.com/EffortlessMetrics/CPUBench.git
cd CPUBench

python -m venv .venv
# Linux/macOS
. .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -e .
```

Inspect the machine without changing it:

```bash
cpubench doctor --output machine-receipt.json
```

Run the bundled smoke campaign:

```bash
cpubench campaign preflight examples/quickstart.yaml
cpubench campaign all examples/quickstart.yaml --fresh
```

The completed bundle is written under:

```text
examples/.cpubench/runs/quickstart/
```

Open `report/index.html`, then verify the retained evidence independently:

```bash
cpubench campaign verify examples/.cpubench/runs/quickstart
```

Run the first scoped application anchor alongside the controlled memory pack:

```bash
cpubench campaign all examples/application-anchor.yaml --fresh
```

The SQLite result intentionally measures the configured Python/SQLite stack over
a warm in-memory indexed-lookup population. It is not relabelled as isolated
CPU-core performance.

Compare two finalized campaigns:

```bash
cpubench study init comparisons/two-machines.yaml \
  --baseline /path/to/baseline-campaign \
  --campaign /path/to/candidate-campaign
cpubench study report comparisons/two-machines.yaml
```

Only points with matching family version, form, parameters, validity view, and analysis policy enter the direct comparison.

Run the benchmark-integrity detector self-test:

```bash
cpubench integrity demo --output .cpubench/integrity-demo
```

The honest mock provider should remain within the declared threshold. The gamed mock provider deliberately recognizes the public variant and should be detected. This proves the detector path; it is not a finding about any hardware vendor.

Analyze authored matched variants from retained campaign evidence:

```bash
cpubench integrity analyze /path/to/campaign variants/public-vs-alias.yaml \
  --output findings/public-vs-alias
```

## The user-facing object is a campaign

A review campaign declares:

```yaml
schema_version: 1
artifact_kind: campaign_spec
campaign_id: quickstart
title: CPUBench quick start
description: Calibration controls and the first memory-access families.
profile: profiles/smoke.yaml
packs:
  - pack: packs/controls/pack.yaml
  - pack: packs/memory-access/pack.yaml
operating_mode: characterization
implementation_policy: native
placement: scheduler_open
output_root: .cpubench/runs
schedule_seed: 20261004
public_claims_enabled: false
```

Create a new campaign:

```bash
cpubench campaign init reviews/new-machine.yaml --campaign-id new-machine
cpubench campaign preflight reviews/new-machine.yaml
cpubench campaign all reviews/new-machine.yaml
```

For investigation and recovery, every stage remains available separately:

```text
campaign plan
campaign run
campaign status
campaign validate
campaign analyze
campaign report
campaign finalize
campaign verify
```

Finalized campaigns can then be joined without rewriting them:

```text
study init
study compare
study report
```

## What one run preserves

```text
campaign-spec.json
instrument-release.json
profile.json
machine-receipt.json
run-environment-receipt.json        # planning-time snapshot
run-environments/<digest>.json   # execution-session snapshots
run-plan.json
build-receipts/
pack-releases/
events.ndjson
attempts/<attempt-id>/
validation/
analysis/
report/
manifest.json
verification.json
```

A report is a projection. The run bundle remains the authority.

## Benchmark hierarchy

```text
Pack
└── Family
    └── Form
        └── Point
            └── Attempt
                └── Sample
```

- A **pack** groups implementation and release material by evidentiary role.
- A **family** asks one bounded measurement question.
- A **form** is a controlled condition.
- A **point** is one coordinate on a curve or matrix.
- An **attempt** is an independent execution, normally a fresh process.
- A **sample** is one retained timing observation inside an attempt.

Generated points do not become independent workloads merely because they produce separate rows.

## Design laws

1. **Measure the configured stack.** CPU model, firmware, memory, compiler, runtime, operating mode, placement, provider, and instrument release travel with the result.
2. **Preserve evidence before interpretation.** Raw execution, validation, analysis, and report views are separate artifacts.
3. **Validate the benchmark as aggressively as the system under test.** Known-good controls and known-bad mutants qualify the instrument.
4. **Use curves, matrices, and service boundaries.** One point can conceal cache knees, saturation, topology transitions, and thermal collapse.
5. **Keep controlled principles and realistic work separate but connected.** Microbenchmarks explain; application anchors establish relevance.
6. **Treat integrity as its own plane.** Matched public and challenge variants test whether evaluation identity changes behaviour.
7. **Do not infer motive from effect alone.** The instrument reports conduct, contrasts, mechanisms, impact, and uncertainty. Intent remains an editorial conclusion requiring additional evidence.
8. **No silent fallback.** Unsupported capability, failed placement, unavailable counters, and invalid work remain explicit outcomes.
9. **No universal validity bit.** A run may be valid for scheduler-open product performance while ineligible for pinned-topology analysis.
10. **No universal CPU score.** Named views may be added only with an explicit target population, weighting policy, quality gates, and missingness rules.

## Repository map

```text
src/cpubench/                 Python control plane
src/cpubench/resources/       Bundled profiles, packs, and native provider
contracts/schemas/            Exported artifact schemas
docs/                         Construct, protocol, trust, and operating guides
examples/                     Runnable campaign definitions
tests/                        Unit, integration, native, and end-to-end proof
SOURCE_LEDGER.yaml             Source provenance
RIGHTS_LEDGER.yaml             Redistribution and disclosure boundaries
WORKLOAD_LEDGER.yaml           Workload purpose, status, and disposition
```

## Development

```bash
python -m pip install -e '.[dev]'
pytest
ruff check .
mypy src/cpubench
cpubench schema export contracts/schemas
```

Native proof only:

```bash
pytest -m native
```

Build and verify the smoke campaign before merging changes that affect execution, validation, analysis, or evidence:

```bash
cpubench campaign all examples/quickstart.yaml --fresh
```

## Documentation

- [Construct](docs/CONSTRUCT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Protocol](docs/PROTOCOL.md)
- [Campaigns](docs/CAMPAIGNS.md)
- [Family authoring](docs/AUTHORING.md)
- [Evidence](docs/EVIDENCE.md)
- [Integrity and challenge packs](docs/INTEGRITY.md)
- [Platform authority](docs/PLATFORMS.md)
- [Statistics](docs/STATISTICS.md)
- [Timer qualification](docs/TIMERS.md)
- [SPEC boundary](docs/SPEC.md)
- [Trust and security](docs/TRUST.md)
- [Release model](docs/RELEASES.md)
- [Current status](docs/CURRENT_STATUS.md)
- [Issue plan](docs/ISSUE_PLAN.md)
- [Issue-ready backlog](docs/BACKLOG.md)
- [Naming](docs/NAMING.md)
- [Roadmap](docs/ROADMAP.md)

## License

CPUBench is available under either of:

- Apache License 2.0; or
- MIT License.

Restricted third-party benchmark assets are not included and are not covered by this repository's license.

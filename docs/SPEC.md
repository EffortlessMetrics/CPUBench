# SPEC integration boundary

## Decision

SPEC workloads remain behind their licensed installation and official tooling.

CPUBench will integrate them through a private, version-specific adapter. It will not vendor, extract, or redistribute restricted source, inputs, validators, or tools.

## Adapter responsibilities

A future adapter will:

```text
locate the licensed installation
verify product and update level
record a local installation digest
materialize permitted configuration
invoke official run tooling
retain config, logs, rawfile, and disclosure evidence
import safe metrics and status
classify reportable / estimate / research execution
prevent restricted payloads from entering public bundles
```

## Authority

The official SPEC raw result and tooling remain authoritative for SPEC result meaning and compliance.

CPUBench may:

- schedule the run inside a larger campaign;
- retain the safe receipts;
- connect SPEC outcomes to other application and diagnostic evidence;
- project approved metrics into a review report.

CPUBench must not relabel a hand-extracted or modified workload as an official SPEC result.

## Local configuration

Restricted assets should be referenced through an ignored local catalog:

```yaml
assets:
  spec_cpu:
    path_env: SPEC_CPU_HOME
    expected_product: unresolved
    expected_release: unresolved
    installation_digest: sha256:...
    disclosure: restricted_licensed
```

The public repository contains adapter code and safe schemas only.

## Current status

No SPEC adapter or SPEC asset is included in `0.1.0a0`.

The exact licensed product/version, local source, and publication rules must be inventoried before implementation. See `SOURCE_LEDGER.yaml` and `RIGHTS_LEDGER.yaml`.

# Provider and evidence protocol

## Provider commands

A provider executable implements three commands.

### `describe`

Print one JSON `ProviderDescriptor` to stdout and exit zero.

```json
{
  "artifact_kind": "provider_descriptor",
  "schema_version": 1,
  "provider_id": "native-c11",
  "provider_version": "0.1.0",
  "protocol_version": 1,
  "families": [
    {
      "family_id": "memory.dependent_load_latency",
      "implementation_id": "native-c11-v0",
      "supported_os": ["linux", "windows", "darwin"],
      "supported_arch": ["x86_64", "aarch64"],
      "timing_authority": "provider_elapsed",
      "capabilities": []
    }
  ]
}
```

### `self-test`

Run deterministic functional checks without producing a publishable performance result.

```json
{
  "ok": true,
  "timer": "CLOCK_MONOTONIC_RAW",
  "completed_units": 10000,
  "checksum": "..."
}
```

Self-test should cover, where applicable:

- input generation;
- small known output;
- work accounting;
- allocation and alignment;
- thread/barrier correctness;
- timer access;
- code-path selection.

### `run`

The control plane invokes one family point and one independent attempt per process.

Common arguments:

```text
run
--family <family-id>
--samples <n>
--warmup-samples <n>
--<family-parameter> <value>
```

The provider writes newline-delimited JSON records to stdout. Human diagnostics go to stderr.

Metadata record:

```json
{
  "record_type": "metadata",
  "family_id": "memory.dependent_load_latency",
  "timer": "CLOCK_MONOTONIC_RAW",
  "setup_excluded": true,
  "cycle_validated": true
}
```

Sample record:

```json
{
  "record_type": "sample",
  "sample_index": 0,
  "elapsed_ns": 1284142,
  "completed_units": 100000,
  "checksum": "0012ab...",
  "timer": "CLOCK_MONOTONIC_RAW",
  "working_set_bytes": 2097152,
  "chains": 1
}
```

The provider emits raw quantities. `ns/unit`, throughput, ratios, and aggregate statistics are derived later.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Completed protocol operation |
| `2` | Invalid request or provider bug |
| `3` | Runtime or instrument failure |
| `64` | Family, parameter, or capability unsupported |

The control plane converts these into explicit terminal states. No missing or failed attempt becomes a performance value.

## Timed-region authority

A family chooses one timing authority:

```text
provider_elapsed
provider_cycles
runner_elapsed
```

- Native microbenchmarks normally use `provider_elapsed`.
- External applications may use `runner_elapsed` with optional phase evidence.
- Qualified cycle measurements are additional evidence, not a substitute for elapsed time.

## Output requirements

A valid sample reports:

- sample index;
- elapsed nanoseconds;
- completed useful units;
- checksum or output identity;
- timer identity;
- family diagnostics required by the contract.

The provider must not emit only a normalized score.

## No silent fallback

If a requested path is unavailable, the provider must:

1. return `64`; or
2. explicitly report the selected fallback where the family permits it.

A fallback never inherits the original implementation identity silently.

## Planning

The control plane expands:

```text
family
× form
× point
× implementation
× operating mode
× placement
× independent attempt
```

The resulting `RunPlan` is frozen before performance evidence exists.

The plan retains a planning-time environment receipt. Actual attempts additionally name the execution-session environment receipt captured immediately before that run session.

Each item records:

- opaque attempt ID;
- sequence index;
- family/version/point/form;
- requested parameters;
- sample and warm-up counts;
- timeout;
- operating mode;
- implementation policy;
- placement selector.

## Attempt lifecycle

```text
planned
→ started
→ evidence written
→ terminal
```

Terminal states:

```text
completed
unsupported
incompatible
invalid_work
instrument_failed
execution_failed
timed_out
aborted
incomplete
```

Every non-success state receives a stable reason code and retained evidence.

## Event journal

`events.ndjson` is append-only during a campaign. It records preparation, attempt starts, attempt terminal states, and campaign completion.

The journal is operational evidence. Canonical attempt JSON and samples remain the structured data authority.

## Validation

Validators evaluate named obligations, not a general impression.

Outcomes:

```text
pass
fail
not_evaluated
unsupported
inconclusive
```

Views then select which obligations are required for a particular comparison.

## Finalization

`campaign finalize` hashes every canonical file except the manifest and verification result, then writes `manifest.json`.

After finalization, CPUBench refuses further canonical writes to the campaign.

`campaign verify` recomputes hashes offline and writes the non-authoritative `verification.json` result.

# Evidence

## Evidence law

CPUBench keeps four layers distinct:

```text
execution evidence
→ validity interpretation
→ statistical analysis
→ report projection
```

A chart is not the raw result. A validity decision does not rewrite the attempt. A revised analysis policy does not require rerunning the machine when the raw evidence remains sufficient.

## Campaign directory

```text
runs/<campaign-id>/
├── campaign-spec.json
├── instrument-release.json
├── profile.json
├── machine-receipt.json
├── run-environment-receipt.json        # planning-time snapshot
├── run-environments/
│   └── <receipt-digest>.json             # execution-session snapshots
├── run-plan.json
├── build/
├── build-receipts/
├── pack-releases/
├── events.ndjson
├── attempts/
│   └── <attempt-id>/
│       ├── request.json
│       ├── attempt.json
│       ├── samples.ndjson
│       ├── output.json
│       ├── placement.json
│       ├── provider.stdout.ndjson
│       └── provider.stderr.log
├── validation/
│   └── validation-bundle.json
├── analysis/
│   └── analysis-bundle.json
├── report/
│   ├── index.html
│   ├── summary.md
│   └── summary.json
├── manifest.json
└── verification.json
```

## Atomic writes

Structured files are written through a temporary file, flushed, fsynced, and atomically renamed.

The event journal is append-only during execution.

The alpha assumes one writer per campaign directory. Process locking and remote execution are deferred.

## Resumability

The frozen plan gives every attempt an opaque deterministic ID.

On resume:

- the current machine receipt must match the frozen campaign machine;
- completed attempt files and their frozen requests are verified before reuse;
- missing/incomplete plan items are executed under a newly captured session environment receipt;
- every completed attempt records the session environment that produced it;
- finalized campaigns reject new canonical writes.

A future recovery record will distinguish a restarted infrastructure attempt from an independent performance repetition more explicitly. The current design never silently overwrites a completed attempt.

## Finalization

Finalization hashes every canonical file and writes `manifest.json`.

Before hashing, CPUBench requires:

- the exact planned attempt population to be present;
- every attempt to have a terminal state;
- attempt semantic identities to recompute and remain joined to their frozen plan item;
- every attempt to reference a retained execution-session environment receipt for the frozen machine;
- validation to cover the frozen plan;
- analysis to reference that validation bundle;
- the static report and summary to exist.

```bash
cpubench campaign finalize <campaign-dir>
```

Verification recomputes every retained hash:

```bash
cpubench campaign verify <campaign-dir>
```

`verification.json` is excluded from the canonical manifest because it is a local verification outcome, not source evidence.

## Raw quantities

Providers report:

```text
elapsed_ns
completed_units
checksum / output identity
```

Normalized metrics are derived later. This lets a denominator or aggregation defect be repaired without fabricating a rerun.

## Availability versus verdict

These are orthogonal:

```text
availability
work validity
measurement validity
comparability
```

Examples:

- unavailable PMU counters do not make elapsed time zero;
- failed build is not poor CPU performance;
- wrong output preserves diagnostic timing but is ineligible for valid performance analysis;
- scheduler-open execution may be valid for a product view and ineligible for pinned characterization.

## Privacy

Machine receipts may contain sensitive operational metadata. Public campaigns should review or redact:

- hostname;
- user paths;
- private asset locations;
- serial numbers;
- network identifiers;
- embargoed firmware or device details.

The public alpha will move toward hashed host identity and explicit publication projections. Do not publish a raw private campaign directory without review.

## Publication projection

A future publication command will copy only approved evidence into a rights-safe public bundle. Execution, local retention, vendor sharing, Git commit, and public release are separate permissions.

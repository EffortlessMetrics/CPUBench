# Current status

**Status date:** 2026-10-05
**Release:** `0.2.0a0`
**Publication posture:** instrument-development alpha; no public CPU ranking claim

## Working end-to-end

The repository currently executes this chain:

```text
CampaignSpec
→ InstrumentRelease + PackRelease identities
→ machine receipt
→ planning and execution-session environment receipts
→ provider build and self-test
→ deterministic RunPlan
→ resumable attempts
→ raw sample evidence
→ obligation-level validation
→ family-level analysis
→ static report
→ immutable manifest
→ offline verification
```

## Implemented commands

```text
cpubench version
cpubench doctor

cpubench campaign init
cpubench campaign preflight
cpubench campaign plan
cpubench campaign run
cpubench campaign status
cpubench campaign validate
cpubench campaign analyze
cpubench campaign report
cpubench campaign finalize
cpubench campaign verify
cpubench campaign all

cpubench family lint
cpubench integrity demo
cpubench schema export

cpubench study init
cpubench study compare
cpubench study report
```

## Implemented providers

### Python control provider

- monotonic Python timer read-pair overhead with delta statistics;
- known-duration sleep interval.

### Native C11 provider

- native monotonic timer read-pair overhead and effective-resolution control;
- dependent randomized pointer chase;
- one/two/four/eight/sixteen disjoint chain memory-level-parallelism sweep;
- deterministic input generation;
- cycle/disjointness self-validation;
- setup outside timed region;
- exact completed-unit and checksum evidence.

The C11 provider currently uses `CLOCK_MONOTONIC_RAW`/`CLOCK_MONOTONIC` on POSIX and `QueryPerformanceCounter` on Windows.

### Python/SQLite application provider

- deterministic in-memory database population;
- warm primary-key lookup population;
- setup and key generation outside the timed region;
- exact lookup-count, database-population, and checksum receipts;
- explicit configured Python/SQLite-stack claim boundary.

## Implemented platform receipt

- operating-system/runtime identity;
- CPU and memory summary;
- Linux core/package/sibling topology;
- Linux cache summary;
- nominal timer availability, with qualification deferred to campaign controls;
- process-affinity and provider execution-residency capability;
- Linux PMU policy observation;
- thermal/battery data where psutil exposes it;
- explicit macOS hard-affinity limitation;
- typed per-attempt placement receipts covering request, readback, provider start/end residency, migration, and affinity restoration.

## Implemented evidence

- canonical JSON semantic identities;
- explicit installed-instrument and compiled-pack release identities;
- atomic structured writes;
- append-only event journal;
- deterministic attempt IDs;
- raw NDJSON samples;
- explicit terminal attempt states;
- resumable plan execution with frozen-machine checks and per-session environment receipts;
- final manifest and offline hash verification.

## Implemented analysis

- named validity view input;
- campaign-derived timer qualification and minimum sample duration;
- separate work, measurement, and comparability outcomes;
- median of valid attempt medians;
- deterministic 95% percentile-bootstrap intervals over independent attempt medians;
- MAD, min, and max across attempts;
- family SVG curves;
- static HTML/Markdown/JSON reports;
- no universal score.

## Integrity proof

The detector self-test includes:

- known-honest mock provider;
- known-gamed mock provider;
- matched public/alias variant comparison;
- bounded identity-sensitive finding;
- explicit statement that intent is not assessed.

The alpha also exports `VariantSetSpec` and can derive a separate
`FindingBundle` from matched points already present in a campaign analysis.

It does not yet compile blinded production challenge variants against real
hardware/software stacks.

## Known limits

- No instrument release has completed multi-machine qualification.
- Machine receipts still need stronger privacy projection before public sharing.
- Provider raw stdout is parsed into evidence; exact byte-for-byte channel retention is scheduled next.
- Platform placement is limited to scheduler-open or a logical CPU ID; Linux can qualify exact-CPU attempts when request, readback, and provider residency agree.
- Windows processor-group and CPU Set authority is incomplete.
- macOS remains scheduler-open.
- PMU, cycles, energy, NUMA placement, and sustained thermal traces are not yet qualified.
- Timer overhead ratios and minimum-duration policy have not yet been calibrated against a publication-grade hardware campaign.
- The SQLite anchor is implemented but has not yet completed cross-hardware external-validity study.
- No topology/coherence pack is implemented.
- No private challenge-pack vault exists.
- No SPEC adapter exists.
- Study comparison is intentionally strict and does not yet model nested device/build variance or bridge releases.
- No composite profile is published.

## Next development gate

**Instrument Validation 0.1** should prove together:

1. calibration controls reject known instrument defects;
2. dependent-load curves show stable, interpretable storage transitions;
3. MLP forms preserve total work and expose overlap;
4. known-honest and known-gamed challenge controls separate correctly;
5. platform limits remain explicit on Linux, Windows, and macOS;
6. reports regenerate from retained evidence;
7. finalized bundles verify offline;
8. at least one irregular-memory application anchor responds coherently;
9. run time and operator burden fit a review workflow.

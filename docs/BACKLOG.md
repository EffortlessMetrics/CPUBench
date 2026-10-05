# Issue-ready backlog

This document contains the initial GitHub issue bodies. The repository can be created and the issues published without reconstructing the programme from conversation history.

Each issue is an implementation transaction. Programme completion remains governed by the release issues.

---

## 1. Intake: freeze the unresolved source corpus

**Role:** contract authority / intake  
**Priority:** P0  
**Blocks:** corpus migration, SPEC adapter, public provenance review

### Goal

Replace every unresolved source placeholder with an exact, rights-classified artifact while preserving the untouched originals.

### Inputs

- Ian's agent-generated repository;
- the exact two GitHub repositories supplied to the agent;
- Ian's untouched 2022 benchmark suite;
- the exact SPEC product, release/update, and local installation;
- the original agent session, source list, or build plan where available.

### Outputs

- exact URL, commit, archive digest, or restricted local locator;
- license and redistribution classification;
- immutable source snapshot or digest;
- workload-ledger rows for every inherited benchmark;
- historical intent/selection notes where available.

### Invariants

- originals are preserved before repair or normalization;
- unknown rights remain non-public;
- a generated implementation does not become canonical merely because it exists;
- SPEC payloads remain outside the public repository.

### Acceptance

- no `unresolved` source needed for corpus migration remains in `SOURCE_LEDGER.yaml`;
- every inherited benchmark has a provisional disposition;
- the ledgers pass schema/lint checks;
- public and restricted assets are cleanly separated.

### Non-goals

- repairing benchmarks;
- choosing final suite membership;
- publishing restricted material.

---

## 2. Evidence: fault-injected recovery and immutable query index

**Role:** implementation slice  
**Priority:** P0  
**Depends on:** existing filesystem evidence store

### Goal

Prove that interrupted campaigns remain inspectable and resumable at every state transition, then add a disposable query index over canonical bundles.

### Outputs

- crash-injection test points before/after request, start, sample, output, terminal event, and finalization;
- explicit recovery records distinguishing infrastructure retries from independent performance attempts;
- lock discipline for one writer per campaign;
- rebuildable SQLite index for campaign/family/point/machine/view queries.

### Acceptance

- every injected crash leaves a verifiable partial bundle;
- resume never overwrites a completed attempt;
- replacement infrastructure attempts receive new identities;
- deleting the index and rebuilding it produces equivalent query results;
- the index is never required to verify canonical evidence.

### Non-goals

- remote execution;
- hosted result service;
- database as canonical authority.

---

## 3. Publication: compile rights-safe public campaign bundles

**Role:** implementation slice / publication boundary  
**Priority:** P0

### Goal

Create a deterministic projection from a private finalized campaign to a public bundle containing only approved evidence.

### Outputs

- publication policy schema;
- allow/deny classification by artifact and field;
- machine-receipt redaction/projection;
- restricted-path and secret scanner;
- public manifest and verification command;
- dry-run diff showing included, excluded, and transformed material.

### Acceptance

- raw private bundle remains unchanged;
- hostname, user paths, restricted locators, serials, credentials, and embargoed fields are excluded or transformed;
- SPEC payloads cannot cross the publication boundary;
- projected bundle verifies independently;
- the report links only to evidence present in the projection.

### Mutants

- injected token/credential;
- private absolute path;
- restricted source file;
- serial number in machine metadata;
- report link to excluded evidence.

---

## 4. Instrument: qualify timer overhead and sample-duration policy

**Role:** benchmark family / instrument qualification  
**Priority:** P0

### Goal

Replace nominal timer availability with measured qualification of resolution, overhead, monotonicity, arithmetic, and minimum usable sample duration.

### Outputs

- timer read-overhead distribution;
- effective resolution probe;
- monotonicity and cross-second arithmetic tests;
- calibration receipt;
- profile-level minimum duration/overhead ratio;
- explicit qualified/limited/failed capability result.

### Acceptance

- known broken timer arithmetic mutant fails;
- too-short samples become instrument-invalid rather than noisy performance values;
- calibration evidence is retained;
- cold-start forms cannot be warmed by calibration;
- Linux, Windows, and macOS report scoped authority rather than one universal pass.

### Non-goals

- universal cycle counter;
- disabling boost by default;
- PMU qualification.

---

## 5. Instrument: prove placement and residency

**Role:** platform implementation slice  
**Priority:** P0

### Goal

Distinguish requested placement, accepted affinity state, and observed execution residency.

### Outputs

- semantic placement selectors;
- request/readback receipts;
- start/end CPU observations where available;
- migration detection policy;
- explicit scheduler-open mode;
- reason codes for unsupported, failed, and limited placement.

### Acceptance

- failed placement never inherits a pinned result label;
- scheduler-open results remain eligible only for compatible views;
- Linux affinity is requested and read back;
- Windows support is processor-group/CPU-Set aware;
- macOS does not claim hard pinning without platform authority;
- placement mutants fail the pinned-characterization view.

---

## 6. Platform: complete Windows topology and CPU Set authority

**Role:** platform implementation slice  
**Priority:** P0

### Goal

Represent Windows systems correctly beyond a single 64-bit process affinity mask.

### Outputs

- processor groups, logical processors, cores, packages, NUMA nodes, efficiency classes, and CPU Sets;
- thread placement using appropriate APIs;
- readback and limitation reporting;
- tests with synthetic >64-logical-CPU fixtures.

### Acceptance

- no shift/bitmask overflow path remains;
- systems spanning processor groups are not truncated;
- heterogeneous classes remain distinguishable;
- unsupported rights/API failures are explicit;
- Windows CI validates normalization and contract behaviour.

---

## 7. Platform: enrich macOS topology without false affinity claims

**Role:** platform implementation slice  
**Priority:** P0

### Goal

Capture useful Apple Silicon topology and operating evidence while preserving the scheduler-open authority boundary.

### Outputs

- performance/efficiency core counts where exposed;
- cache and frequency/power data where public APIs permit;
- scheduler-open product and characterization receipts;
- explicit affinity-tag versus hard-affinity distinction;
- platform limitations in reports.

### Acceptance

- no result claims a hard-pinned core without proof;
- work semantics and elapsed timing can remain comparable where earned;
- topology-specific views exclude unsupported runs;
- macOS CI covers the collector and public projection.

---

## 8. Validation: implement native locality/MLP mutants

**Role:** benchmark family / instrument validation  
**Priority:** P0

### Goal

Make the measurement system reject intentionally broken implementations of the first native families.

### Required mutants

- traversal result unused;
- sequential chain labelled random;
- input generation inside the timed region;
- wrong completed-load denominator;
- multiple chains sharing one dependency;
- chain count increasing total work;
- failed placement accepted;
- stale binary/receipt mismatch;
- checksum corruption.

### Acceptance

- every mutant fails its declared obligation;
- valid sentinels exercise every blocking obligation;
- validator failure is distinguishable from workload failure;
- the mutant matrix runs in CI without being interpreted as performance evidence.

---

## 9. Integrity: execute blinded challenge variants

**Role:** benchmark family / integrity plane  
**Priority:** P0

### Goal

Move from the honest/gamed detector self-test to campaign-integrated challenge execution in which subject-visible requests do not reveal variant roles.

### Outputs

- `VariantSetSpec` loader and compiler;
- exact-binary alias variant;
- held-out-input variant;
- separate hidden evaluation authority;
- challenge-pack local vault and disclosure states;
- integrity contrast analysis and `FindingBundle` generation.

### Acceptance

- provider request contains no `challenge`, `hidden`, or expected-verdict metadata;
- the same frozen challenge population is used across the compared cohort;
- honest and gamed controlled systems remain separable;
- generally applicable optimization control is not misclassified;
- effect, mechanism evidence, user impact, intent status, and claim boundary remain separate.

### Non-goals

- declaring vendor intent automatically;
- claiming permanent cheating resistance;
- publishing active challenge payloads.

---

## 10. Release: Instrument Validation 0.1

**Role:** release transaction  
**Priority:** P0  
**Depends on:** issues 1–9 as applicable

### Goal

Freeze and evaluate the first instrument release before publishing CPU rankings.

### Validation dimensions

- sanity;
- specificity/invariance;
- sensitivity;
- reproducibility;
- cross-tool triangulation;
- honest/gamed separability;
- platform-limit handling;
- operator burden and run budget.

### Hardware surface

Use materially different systems where available: modern AMD chiplet/cache, older AMD, heterogeneous Intel mobile, Apple Silicon, and older Intel mobile.

### Acceptance

- exact instrument/pack/profile/analysis policies are frozen before interpretation;
- known-bad mutants are rejected;
- locality and MLP curves are interpretable;
- reports regenerate from retained evidence;
- bundles verify offline;
- limitations narrow the eligible views;
- one release decision is issued:
  - `validated_for_internal_review`;
  - `validated_with_limits`;
  - `not_validated`;
  - `instrument_failure`.

---

## 11. Application: irregular-memory anchor

**Role:** benchmark family / application anchor  
**Priority:** P1

### Goal

Connect the locality and MLP families to one deterministic, recognizable irregular-memory task.

### Candidate ladder

```text
dependent locality + MLP
→ hash/graph kernel
→ SQLite indexed lookup or graph traversal application
```

### Outputs

- input population and rights;
- useful-work/output contract;
- phase timings where possible;
- cold/warm and latency/throughput semantics;
- `StudySpec` testing coherence across multiple architectures.

### Acceptance

- application correctness is independently validated;
- the anchor is not relabelled as a pure CPU-core benchmark;
- controlled-family agreement and divergence are both reported;
- one implementation/input does not become an exhaustive oracle.

---

## 12. Workflow: common review spine and diagnostic branches

**Role:** programme / reviewer workflow  
**Priority:** P1

### Goal

Compile a review campaign graph with one common comparison denominator and conditional anomaly investigations.

### Outputs

- common-spine declaration;
- predeclared diagnostic triggers;
- branch provenance;
- run-budget/resource estimate;
- explicit supplemental-versus-composite treatment;
- resume and inspection UI in the CLI.

### Acceptance

- all directly compared machines receive the same compatible common spine;
- diagnostic branches never silently enter a composite;
- branch trigger and evidence remain inspectable;
- campaign preflight reports expected duration, memory, disk, privilege, and unsupported families.

---

## 13. Topology: atomic handoff latency

**Role:** benchmark family  
**Priority:** P1

### Goal

Measure defined atomic token transfer across topology relationships without timing thread creation or unverified placement.

### Forms

- release/acquire store-load ping-pong;
- relaxed atomic RMW/CAS;
- sequentially consistent control;
- round-trip primary and labelled derived one-way estimate.

### Acceptance

- workers are created and placed before timing;
- exact completed round trips are receipted;
- one pair at a time forms the canonical matrix;
- concurrent-pair execution has a separate interference identity;
- core-pair relationships are topology-labelled;
- the existing CnC and Rust donors are retained as source specimens/cross-checks.

---

## 14. Coherence: false-sharing matched family

**Role:** benchmark family  
**Priority:** P1

### Goal

Measure the penalty from logically independent updates sharing a cache line.

### Forms

- same-line updates;
- separate-line matched control;
- read-shared control;
- topology placements;
- contention/task-granularity sweep.

### Acceptance

- useful update work and count remain matched;
- line placement is proven;
- output correctness is exact;
- the same-line/separate-line relation survives held-out layout variants;
- results remain family curves/matrices rather than one global coherence score.

---

## 15. SPEC: restricted official-tool adapter

**Role:** private adapter  
**Priority:** P1

### Goal

Integrate the exact licensed SPEC installation without copying restricted material or bypassing official execution authority.

### Outputs

- local restricted-asset catalog;
- installation/release verification;
- config materialization;
- official-tool invocation;
- rawfile/config/log retention;
- safe metric import;
- reportable/estimate/research classification;
- publication-boundary tests.

### Acceptance

- public repository contains no SPEC payload;
- official rawfile remains source evidence;
- modified/research runs cannot be described as official results;
- applicable disclosure/run rules travel with imported evidence;
- missing licensed assets produce an explicit unsupported result.

---

## 16. Migration: classify Ian's 2022 and generated suites

**Role:** corpus migration programme  
**Priority:** P1  
**Depends on:** source intake, instrument validation

### Goal

Convert historical code and analyst judgment into reviewed family/application/regression roles without wholesale porting.

### Dossier per workload

- source/revision/rights;
- original purpose and reader decision;
- actual timed region;
- work/output contract;
- compiler/platform assumptions;
- race/UB/timer/fallback risks;
- historical anomalies and usefulness;
- proposed role and disposition.

### Acceptance

- every workload receives `wrap`, `repair`, `reimplement`, `reference`, `anchor`, `replace`, `retire`, or `defer`;
- original code and rationale remain preserved;
- no workload enters a frozen release without controls, mutants, and claim boundary;
- duplication and coverage are reviewed at family level.

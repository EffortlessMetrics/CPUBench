# Architecture

## Decision

CPUBench begins as one Python control-plane repository with language-neutral subprocess providers and immutable filesystem evidence bundles.

This keeps the research loop fast without placing Python inside native timed kernels.

## System shape

```text
Human-authored YAML
        |
        v
Authoring compiler and Pydantic validation
        |
        v
CampaignSpec + PackSpec + FamilySpec + ProfileSpec
        |
        +-----------------------+
        |                       |
        v                       v
Platform doctor             Build adapter
        |                       |
        v                       v
MachineReceipt             BuildReceipt
        |                       |
        +-----------+-----------+
                    |
                    v
                 Planner
                    |
                    v
                 RunPlan
                    |
                    v
                 Executor
                    |
          +---------+----------+
          |                    |
          v                    v
 Python controls       Native / external providers
          |                    |
          +---------+----------+
                    |
                    v
              Attempt evidence
                    |
                    v
             ValidationBundle
                    |
                    v
              AnalysisBundle
                    |
                    v
              Static reports
                    |
                    v
             Manifest + verify
```

## Hexagonal boundaries

### Domain

`src/cpubench/models.py` and `canonical.py` define the durable vocabulary and identities. Domain code does not execute benchmarks or inspect the operating system.

### Application services

`campaign.py`, `planner.py`, `validation.py`, `analysis.py`, and `report.py` coordinate the workflow.

### Ports

The stable conceptual ports are:

- benchmark provider;
- build adapter;
- topology/placement adapter;
- timer/counter/telemetry adapter;
- evidence store.

The alpha keeps these lightweight rather than creating a package per interface.

### Adapters

- Python control provider;
- bundled C11 memory provider;
- psutil/sysfs platform discovery;
- process-affinity adapter;
- filesystem store.

Future adapters may wrap official SPEC tooling, application-native drivers, Phoronix profiles, Google Benchmark executables, or reference instruments.

## Why subprocess providers

One-shot subprocesses provide:

- implementation-language independence;
- fresh-process attempt boundaries;
- crash and timeout containment;
- exact executable identity;
- separate stdout/stderr capture;
- straightforward wrapping of existing tools;
- an enforceable privilege and sandbox boundary;
- no unstable in-process plug-in ABI.

A provider supports:

```text
describe
self-test
run
```

See [Protocol](PROTOCOL.md).

## Why filesystem bundles

The canonical authority is a portable directory rather than a live database.

Benefits:

- direct inspection;
- offline verification;
- content hashing;
- simple archival and publication;
- repairable/rebuildable indexes;
- no service dependency during hardware review;
- clear private/public boundaries.

A SQLite search index is planned as a derived cache. It will never become the only surviving authority.

## Control plane versus data plane

### Control plane

Python owns:

- spec loading and validation;
- semantic identities;
- machine discovery;
- provider build and discovery;
- deterministic run planning;
- process execution;
- raw evidence retention;
- obligation-level validation;
- analysis and reports;
- finalization and verification.

### Data plane

Providers own:

- input materialization local to the workload;
- precise setup/timed/teardown boundaries;
- measured useful work;
- raw timing;
- completed-unit accounting;
- output/checksum evidence;
- effective implementation metadata.

A provider does not choose report weights, decide public claims, or silently downgrade requirements.

## Dependency rule

```text
domain
  ← application services
      ← adapters and CLI
```

Provider executables know the provider protocol, not the report model.

## Durable artifacts

The alpha implements:

```text
CampaignSpec
InstrumentRelease
PackSpec
PackRelease
FamilySpec
VariantSetSpec schema
ProfileSpec
MachineReceipt
RunEnvironmentReceipt
BuildReceipt
RunPlan
AttemptRecord / SampleRecord
ValidationBundle
AnalysisBundle
FindingBundle
Manifest / VerificationResult
```

Planned additional publication objects:

```text
PublicationView
```

`VariantSetSpec` is implemented as a strict authored contract and exported
schema; production challenge-pack compilation remains a later gate.

## Identity

Each semantic artifact ID is:

```text
sha256(
  canonical_json({
    artifact_kind,
    schema_version,
    semantic_payload
  })
)
```

Canonicalization:

- UTF-8;
- sorted object keys;
- no NaN or infinity;
- explicit parent IDs;
- no timestamp in semantic payload.

Captured attempt identities intentionally include their concrete execution evidence.

## Repository layout

```text
src/cpubench/
  domain and application modules
src/cpubench/providers/
  Python protocol providers
src/cpubench/resources/
  bundled profiles, packs, native provider
contracts/schemas/
  exported JSON Schemas
docs/
  normative and operating documentation
fixtures/
  future known-good and known-bad specimens
tests/
  unit, integration, native, end-to-end proof
```

## Evolution boundary

Python is the correct starting control plane because the unresolved work is mostly construct discovery, protocol design, adapters, analysis, and report iteration.

A later compiled control plane is justified only when measurements show a real operational limit. The provider boundary already permits high-performance Rust, Go, C, C++, Swift, Kotlin, or application-native implementations without changing the evidence model.

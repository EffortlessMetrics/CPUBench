# Family authoring

## Start from the measurement question

A benchmark implementation is not a family definition.

Before code, write:

1. **Question** — what bounded property or regime is being observed?
2. **Useful unit** — what work completes once?
3. **Output/quality** — what proves the work is correct?
4. **Intervention** — which dimension changes across forms or points?
5. **Invariants** — what must remain stable?
6. **Execution regime** — latency, throughput, scaling, service, burst, sustained?
7. **Implementation policy** — fixed binary, fixed source, constrained task, product path?
8. **Primary evidence shape** — curve, matrix, frontier, or service boundary?
9. **Application link** — what real task might this explain?
10. **Claim boundary** — what does it not measure?

## Family schema

```yaml
schema_version: 1
artifact_kind: family_spec
family_id: memory.dependent_load_latency
family_version: 0.1.0
title: Dependent load latency
surface: controlled_principle
question: >-
  How does load-to-use latency change as a randomized dependent
  working set crosses effective storage regions?
evaluated_object: fixed_source_native_binary
provider_id: native-c11

work_contract:
  useful_unit: one validated indexed load
  input_population: deterministic randomized cycle
  required_output: final traversal checksum and completed-load count
  quality_or_tolerance: exact integer validation

demand_geometry:
  dependency: serial
  locality: randomized
  arithmetic_intensity: minimal

intervention_axes:
  - working_set_bytes

invariants:
  - index representation
  - completed load count
  - output validation
  - timed region

forms:
  - random_pointer_chase

points:
  - point_id: ws-2m
    parameters:
      working_set_bytes: 2097152
      chains: 1
      completed_units: 2000000
      seed: 103
    profiles: [smoke, qualify, review, characterize]

timing_authority: provider_elapsed
supported_modes: [characterization, mechanism]
primary_metrics: [ns_per_load]
diagnostic_metrics: [elapsed_ns, checksum]

obligations:
  work.completed_units:
    severity: blocking
    description: Exact useful-load count must be reported.
  work.output_checksum:
    severity: blocking
    description: A traversal-derived output must survive the timed loop.

mutants:
  - mutant_id: locality.result_unused
    description: Discard output and permit dead-code elimination.
    expected_failures: [work.output_checksum]

claim_boundary:
  - does_not_measure_streaming_bandwidth
  - does_not_establish_application_performance
```

## Obligation design

Obligations should be local and falsifiable.

Good:

```text
work.completed_units
work.output_checksum
work.valid_cycle
timing.setup_excluded
instrument.timer_qualified
placement.hard_affinity
```

Weak:

```text
benchmark_is_good
results_look_reasonable
system_was_stable
```

Every blocking obligation should eventually have:

- a known-good positive witness;
- a known-bad mutant;
- a validator capable of separating them;
- a stable reason code.

## Mutants

Question/form variants test the system under test. Mutants test the measurement system.

Typical mutants:

- output unused;
- wrong unit denominator;
- setup included in timing;
- changed algorithm;
- lowered precision;
- stale binary;
- silent fallback;
- affinity request ignored;
- several independent chains sharing one dependency;
- public identity special-cased.

A family is not ready because one reference implementation returns plausible values. It is ready when the instrument accepts legitimate alternatives and rejects the known-bad forms for the intended reason.

## Provider implementation

A provider must implement the [provider protocol](PROTOCOL.md).

The provider should:

- materialize setup outside the timed region;
- identify the exact timed boundary;
- report raw elapsed time and completed units;
- preserve an output derived from useful work;
- emit effective path metadata;
- return unsupported rather than silently falling back;
- avoid report or suite policy.

## Proof and measurement builds

Use two related build paths.

### Proof build

May enable:

- assertions;
- sanitizers;
- race detection;
- UB checks;
- exhaustive small inputs;
- property testing;
- differential checking.

### Measurement build

Uses:

- declared optimization policy;
- minimal observation;
- exact binary receipt;
- stable timing boundary.

The proof build is not timed. The measurement build does not escape the shared work contract.

## Family lint

```bash
cpubench family lint packs/memory-access/pack.yaml
```

The current linter validates Pydantic structure and uniqueness. Planned authoring checks will require all admission questions, unit definitions, obligation coverage, mutants, rights, and resource bounds.

## Versioning

Rotate the family version when any of these change materially:

- useful work;
- input population;
- algorithmic boundary;
- quality/tolerance;
- timed region;
- forms or point semantics;
- required obligations;
- primary metric meaning.

Implementation-only fixes may rotate the implementation identity without rotating the family when the work contract and result semantics remain unchanged. The release record must still identify the new binary.

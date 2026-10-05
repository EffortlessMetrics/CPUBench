# Construct

## Governing object

CPUBench measures **configured systems performing declared work under declared conditions**.

It does not treat “CPU performance” as one intrinsic scalar. A stored result belongs to:

```text
work contract
× input population
× implementation
× build receipt
× machine receipt
× operating mode
× placement policy
× measurement instrument
× run plan
```

A report may project that evidence as “CPU A versus CPU B,” but the retained bundle must preserve the complete stack.

## Product object: review campaign

A campaign is a bounded review or investigation transaction:

```text
question or decision
→ machine intake
→ common comparison spine
→ challenge variants
→ anomaly-triggered diagnostics
→ application verification
→ finding or bounded conclusion
→ publication / remediation / regression
```

The campaign, not an individual executable, owns:

- the directly compared cohort;
- the common workload population;
- operating and implementation modes;
- run budget;
- challenge-pack policy;
- validity view;
- analysis and publication boundary.

## Benchmark hierarchy

```text
Pack
└── Family
    └── Form
        └── Point
            └── Attempt
                └── Sample
```

### Pack

A packaging and release unit. Packs have evidentiary roles:

- calibration;
- public reference;
- challenge;
- application;
- diagnostic;
- regression;
- bridge.

A pack is not automatically a scoring unit.

### Family

One bounded measurement question. Examples:

- dependent load latency as working set changes;
- useful load throughput as independent chain count changes;
- atomic handoff latency across topology relations;
- sustained throughput under a power and duration regime.

A family must state:

1. useful work;
2. correct output or quality;
3. intervention;
4. invariants;
5. execution regime;
6. implementation freedom;
7. validity obligations;
8. primary curve, contrast, matrix, or boundary;
9. intended application or decision link;
10. claim boundary.

### Form

A controlled condition inside a family. A form may be a treatment, baseline, inverse, control, or diagnostic. Forms are authored; they are not inferred from benchmark names after execution.

### Point

One parameter coordinate, such as:

```text
working_set_bytes = 2 MiB
chains = 4
placement = scheduler_open
```

A family generally produces a curve or matrix. Many points improve the family evidence; they do not multiply the family's aggregate weight.

### Attempt

An independent execution under one frozen point. The default attempt boundary is a fresh provider process.

### Sample

A raw observation inside an attempt. Samples estimate one attempt's behaviour. They are not independent machines, builds, or process populations.

## Evaluated objects

A family must identify the evaluated object:

| Object | Includes |
|---|---|
| Exact instruction | Instruction sequence, processor, execution environment |
| Fixed binary | Binary, OS, firmware, hardware |
| Fixed source | Source, compiler, libraries, OS, hardware |
| Managed runtime | Program, runtime/JIT/GC, OS, hardware |
| Native application | Application stack, libraries, platform services, hardware |
| Service | Full serving stack under request policy |
| Platform-native path | Application plus permitted accelerator dispatch |

A fixed-source result includes compiler quality. A product result includes runtime and library decisions. A platform-native media result using a media engine is not a CPU-only codec result.

## Workload demand geometry

Families should author demand rather than permanent bottleneck labels.

### Code and control

```text
instruction footprint
branch density and entropy
history structure
indirect-target diversity
call/return geometry
instruction-page footprint
```

### Compute and dataflow

```text
dependency depth
available instruction-level parallelism
operation mix
precision
vector width
reduction geometry
arithmetic intensity
```

### Data and locality

```text
working-set size
reuse distance
stride
prefetchability
pointer dependence
independent miss streams
read/write mix
page footprint
NUMA placement
```

### Parallel and coordination

```text
task graph
task granularity
load balance
shared-state density
ownership transfer
contention
synchronization
topology crossings
```

### Runtime dynamism

```text
process startup
dynamic linking
allocation
JIT compilation
garbage collection
page faults
system calls
scheduler interaction
```

“Memory bound” and “front-end bound” are observed responses on one configured stack, not durable family identities.

## Execution regimes

A workload may support several distinct questions:

| Regime | Primary question |
|---|---|
| One-job latency | How long does one useful job take? |
| Cooperative scaling | How much faster does one shared job become? |
| Independent throughput | How many unrelated jobs complete per interval? |
| Service capacity | What load meets the declared latency/error contract? |
| Foreground under load | How much background work can coexist with acceptable foreground latency? |

These are not interchangeable “multicore” results.

## Temporal regimes

```text
cold start
first iteration
warm steady state
tail / worst case
short burst
sustained equilibrium
recovery after idle
```

A cooled burst result and a continuous sustained result may both be valid. They answer different questions.

## Operating modes

### Product

Ordinary user-visible behaviour:

- default power policy;
- scheduler-selected placement;
- normal boost and thermal policy;
- platform-native dispatch where permitted.

### Characterization

Controlled user-space measurement:

- declared placement;
- declared core class and NUMA policy where supported;
- quiet-system preflight;
- no hidden conversion into fixed-frequency mechanism testing.

### Mechanism

Narrow architectural diagnosis:

- exact code forms;
- architecture-specific counters;
- optional controlled frequency or privileged helper;
- correspondingly narrower claims.

## Implementation policies

```text
exact      fixed instruction or binary shape
portable   common optimized source and baseline ISA
native     broadly applicable local ISA/CPU tuning
tuned      declared LTO/PGO/workload-specific legal tuning
product    upstream application/runtime/library choices
```

The operating mode and implementation policy are independent axes.

## Result planes

The canonical result vector keeps separate:

- work correctness;
- execution availability;
- measurement authority;
- comparability;
- latency and throughput;
- scaling;
- energy;
- stability and tails;
- output quality;
- integrity challenge results;
- campaign operating cost.

No universal total is required.

## Validity views

CPUBench does not use one universal `valid` bit.

Initial views:

### `work_correct`

The declared work and output checks passed.

### `portable_elapsed`

Adds:

- qualified monotonic interval timing;
- sufficient work duration;
- no prohibited fallback.

Does not require PMUs or hard affinity.

### `pinned_characterization`

Adds verified placement and required topology authority.

### `mechanism_diagnostic`

Adds family-specific cycle, counter, code-shape, or frequency evidence.

### `product_native`

Allows normal scheduler and platform dispatch but requires the effective provider/offload path to be named.

## Controlled principles and application relevance

The intended explanatory ladder is:

```text
controlled mechanism
→ useful kernel
→ application phase
→ end-to-end application
→ reader decision
```

Co-movement strengthens an explanation but does not prove causality by itself. A stronger causal case combines:

1. controlled intervention;
2. expected mechanism signature;
3. application sensitivity;
4. replication on another stack or treatment.

Divergence is retained rather than forced into a preferred story.

## Integrity construct

A challenge family asks whether evaluation identity changes system behaviour while declared work remains matched:

```text
same relevant work
+ changed benchmark identity or held-out input
→ changed policy or performance?
```

The instrument reports observed conduct, matched contrast, mechanism evidence, user effect, alternatives, and uncertainty. It does not mechanically infer intent.

## Admission rule

A family may enter a frozen public pack only after:

- construct review;
- work-validity proof;
- timed-region review;
- known-good controls;
- known-bad mutants;
- instrument qualification;
- cross-platform claim review;
- rights review;
- bounded public claim.

Popularity, plausible numbers, a large vendor delta, historical use, or inexpensive agent generation are investigation signals—not admission authority.

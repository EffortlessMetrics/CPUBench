# Platform authority

## Principle

Portability means shared work semantics plus explicit capability—not identical control on every operating system.

Every capability reports:

```text
qualified
available_unqualified
unsupported
failed
unknown
```

Unsupported evidence remains unsupported. It does not silently downgrade under the same metric name.

## Machine receipt

`cpubench doctor` records:

- operating system and kernel;
- architecture;
- CPU identity and logical/physical count;
- Linux topology and cache data where available;
- memory size and page size;
- Python runtime;
- timer, affinity, PMU, thermal, and battery capability;
- known unknowns.

The alpha's receipt is an instrument-development record, not a complete hardware inventory. DIMM topology, firmware details, Windows processor groups, macOS core classes, and wall-power authority require further adapters.

## Run-environment receipt

Campaign preparation records dynamic state separately from machine identity:

- process ID, current CPU, and current affinity where available;
- load-average and per-CPU utilization snapshot;
- available/used memory;
- current CPU frequency snapshot;
- battery and thermal readings where exposed;
- dynamic known unknowns.

The receipt describes the starting environment. Per-attempt residency, sustained
telemetry, and end-state comparison remain separate future evidence surfaces.

## Linux

Current alpha:

- Python and native interval timers reported as available until campaign controls qualify overhead, resolution, and monotonicity;
- bundled provider uses `CLOCK_MONOTONIC_RAW` where exposed, otherwise `CLOCK_MONOTONIC`;
- process affinity request/readback through psutil;
- sysfs logical/core/package/sibling topology;
- basic cache metadata from sysfs;
- `/proc/cpuinfo` identity;
- `perf_event_paranoid` observation without claiming PMU event qualification;
- psutil thermal sensors where available.

Planned:

- direct `perf_event_open` adapter;
- event maps by CPU family;
- multiplexing and coverage receipts;
- NUMA memory placement;
- huge-page treatments;
- energy counter qualification;
- per-attempt residency evidence.

## Windows

Current alpha:

- campaign-qualified Python monotonic timing;
- native provider uses and campaign-qualifies `QueryPerformanceCounter`;
- psutil affinity where available;
- basic processor and memory inventory.

Required before strong topology claims:

- processor-group-aware topology;
- CPU Set and thread-group placement;
- readback across systems with more than 64 logical processors;
- explicit core classes and cache domains;
- ETW/PMU/power authority where qualified.

A single process affinity mask is not a complete Windows topology model.

## macOS

Current alpha:

- campaign-qualified Python monotonic timing;
- native provider uses and campaign-qualifies a monotonic POSIX clock;
- scheduler-open product/portable measurements;
- explicit statement that hard affinity is not claimed.

Planned:

- richer sysctl machine inventory;
- performance/efficiency core-class metadata;
- qualified power and thermal evidence where available;
- application-native product studies.

The system must not fabricate Linux-style pinning authority on Apple Silicon.

## Containers, VMs, WSL, and translation

These are configured-system treatments.

A campaign should record:

- container/VM indicators;
- guest and host information where available;
- translation layer;
- virtualized timers/counters;
- placement limits.

Shared CI may prove functional correctness. It should not supply canonical hardware performance evidence.

## Placement selectors

Implemented:

```text
scheduler_open
cpu:<logical-id>
```

Planned semantic selectors:

```text
one_representative_per_core
same_core_smt_pair
same_private_cache_domain
same_last_level_cache_domain
different_last_level_cache_domain
same_core_class
different_core_class
different_numa_node
```

The planner will resolve semantic selectors into platform IDs and preserve both the request and resolution.

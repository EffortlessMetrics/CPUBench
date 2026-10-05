# Timer qualification

A timer being present is not evidence that a benchmark sample is long enough to interpret.

CPUBench qualifies interval timers inside each campaign through matched calibration families. The machine receipt first states which timer sources the platform exposes. Campaign controls then measure the effective behavior of the exact timer/provider stack used by the workload.

## Qualification chain

```text
platform timer capability
→ paired-read control attempts
→ monotonicity and positive-delta checks
→ observed read-pair overhead and effective resolution
→ profile policy
→ minimum usable sample duration
→ attempt-level validity
```

The platform doctor reports timers as `available_unqualified` until campaign evidence establishes their observed behavior. A timer can be available yet remain ineligible for performance interpretation.

## Control families

The controls pack contains two timer families.

### `controls.timer_overhead`

Qualifies `python.time.monotonic_ns` for Python/runtime providers.

### `controls.native_timer_overhead`

Qualifies the bundled native provider's interval timer:

- `CLOCK_MONOTONIC_RAW` where available on POSIX;
- otherwise `CLOCK_MONOTONIC`;
- `QueryPerformanceCounter` on Windows.

Each useful unit performs a paired timer observation. The provider retains:

```text
outer elapsed time
completed read-pair count
minimum positive pair delta
maximum pair delta
zero-delta count
non-monotonic count
checksum derived from observations
```

## Derived qualification

For each timer, CPUBench derives:

```text
read-pair overhead
  median(outer elapsed / completed read pairs)

effective resolution
  minimum retained positive pair delta

minimum sample duration
  ceil(max(read-pair overhead, effective resolution)
       × profile.minimum_timer_overhead_ratio)
```

The current profile policies are:

| Profile | Minimum ratio |
|---|---:|
| `smoke` | 50× |
| `qualify` | 1000× |
| `review` | 1000× |
| `characterize` | 1000× |

These ratios are explicit policy, not universal physical constants. Instrument validation may revise them under a new profile or instrument release.

## Qualification states

| State | Meaning |
|---|---|
| `qualified` | Positive resolution and read overhead were observed, with no non-monotonic control observations. |
| `available_unqualified` | The source exists, but required calibration evidence is incomplete. |
| `failed` | The timer reversed, the platform capability failed, or another blocking defect was observed. |
| `unsupported` | The platform cannot provide the requested timer authority. |
| `unknown` | Available evidence does not establish the state. |

Zero-delta observations are retained because timer granularity can legitimately produce them. Qualification requires at least one positive delta. Any non-monotonic control observation fails the timer for the campaign.

## Sample validity

A workload attempt using a qualified timer is measurement-valid only when every retained sample meets the timer's campaign-derived minimum duration.

Too-short samples fail with:

```text
sample_below_minimum_timer_duration
```

They do not enter analysis as noisy but otherwise valid performance values.

If a workload uses a timer without a matching control in the same campaign, its timer obligation remains inconclusive:

```text
timer_control_missing
```

## Evidence and reporting

`ValidationBundle.timer_qualifications` retains, per timer:

```text
control attempt identities
observation count
non-monotonic and zero-delta counts
read-pair overhead
observed effective resolution
minimum sample duration
profile ratio
reason code and detail
```

HTML, Markdown, and JSON reports project this evidence without replacing the validation bundle.

## Claim boundary

The current controls qualify interval timing on the named configured stack. They do not establish:

- instruction latency of the timer read itself;
- cross-core synchronization of cycle counters;
- PMU accuracy;
- equivalence among operating-system timer implementations;
- suitability for one-way sub-resolution event timing;
- absence of virtualization or firmware effects.

Those require separate mechanism-specific qualification.

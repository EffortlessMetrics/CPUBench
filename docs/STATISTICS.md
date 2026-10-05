# Statistical policy

## Hierarchy

CPUBench preserves the level at which evidence was generated:

```text
physical device
└── machine state / boot / thermal cycle
    └── build
        └── independent attempt (normally fresh process)
            └── inner samples
                └── loop iterations / useful units
```

Large inner-loop counts do not create independent builds, processes, thermal states, or devices.

## Alpha analysis policy

For each valid attempt:

```text
attempt estimate = median(sample elapsed_ns / completed_units)
```

For each point:

```text
point estimate = median(eligible attempt estimates)
```

Dispersion:

```text
MAD across attempt estimates
minimum and maximum attempt estimate
deterministic 95% percentile-bootstrap interval over attempt estimates
```

Raw samples remain in the campaign bundle.

## Why attempt medians

The median provides a robust first alpha summary without deleting evidence or choosing a best run. It is not a universal answer to benchmark noise.

Instrument validation must still establish:

- sufficient sample duration;
- appropriate attempt boundary;
- stable work accounting;
- absence of systematic schedule/order bias;
- whether additional build, reboot, thermal, or device repetition is required.

## No silent outlier deletion

The alpha does not discard timing outliers.

A future analysis policy may exclude samples only when a retained instrument fact establishes invalid execution, such as:

- failed output validation;
- thread migration prohibited by the selected view;
- thermal/power policy violation;
- counter or timer failure;
- provider protocol defect.

The original evidence remains retained and exclusion reasons are versioned.

## Interleaving

Profiles may deterministically randomize point/attempt order using the campaign seed.

Interleaving reduces time drift; it does not make equal attempt indices statistically paired.

Blocking and matching must be declared in the campaign/study design.

## Uncertainty

The current report exposes attempt count, MAD, range, and a deterministic 95%
percentile-bootstrap interval over independent attempt medians. The resampling
seed is derived from the family/point/form identity so reanalysis is stable.
One-attempt smoke points receive a degenerate interval and are not evidence of
population uncertainty.

Before publication-grade comparison, add or validate:

- ratio/effect intervals;
- nested variance studies where build/process/device variation matters;
- device count;
- coverage and missingness sensitivity.

## Best-of-N

Best-of-N may become a named peak-potential view. It must not replace expected/default performance.

## Family weighting

The inferential hierarchy is:

```text
sample
→ attempt
→ point
→ form
→ family
→ application family
→ named profile
```

Many points improve a curve. They do not automatically give that family more influence in a composite.

A future composite must declare:

- target population;
- family weights;
- normalization reference;
- quality gates;
- missingness policy;
- energy policy;
- sensitivity to alternative weights.

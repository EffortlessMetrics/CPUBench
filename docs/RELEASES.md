# Release model

## Three version axes

### Control-plane release

The Python package and provider protocol version.

Example:

```text
cpubench 0.2.0a0
provider protocol 1
```

### Instrument release

The frozen measurement system:

```text
control plane
platform adapters
provider protocol
validation rules
reason codes
evidence format
analysis compatibility
```

Every campaign now retains an explicit `InstrumentRelease` containing the
installed control-plane version, provider/evidence protocol versions, a digest
of the installed Python package and bundled resources, component identities,
and known limits. `RunPlan` binds to that exact release.

### Pack release

The frozen workload population:

```text
families
forms
points / generation rules
inputs
implementations
known limits
disclosure role
```

Every loaded pack now compiles into an explicit `PackRelease` binding the pack
specification to the exact family semantic IDs and versions used by the plan.
The human-authored `PackSpec` and compiled `PackRelease` are both preserved.

## Candidate and frozen lanes

```text
candidate
  mutable research and development

frozen
  immutable comparison population

regression
  retained known failures and fixes

retired
  historical releases preserved for audit
```

## Comparability

Material changes rotate comparability identity:

- useful work;
- input population;
- output quality/tolerance;
- timed boundary;
- implementation policy;
- validation obligations;
- analysis formula.

A code fix that preserves family semantics still rotates the implementation/build identity.

## Bridge packs

Adjacent suite editions should share a long-lived bridge population.

```text
edition N
    ↕ direct bridge study
edition N+1
```

A bridge study establishes observed continuity and change. It does not create a universal score-conversion formula.

## Challenge release lifecycle

```text
development_private
→ frozen_private
→ vendor_shared_subset
→ remediation_holdout
→ retired_public / retired_private
```

Challenge packs rotate when exposed or contaminated.

## Public release gate

A public performance release requires:

- validated instrument release;
- frozen pack release;
- complete source/rights ledger;
- declared validity view;
- machine and build receipts;
- sufficient attempt/device evidence;
- rights-safe publication bundle;
- limitations and claim boundary;
- reproducible report.

`0.2.0a0` is an instrument-development alpha and does not satisfy this gate.

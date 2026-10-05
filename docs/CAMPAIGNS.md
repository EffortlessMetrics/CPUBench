# Campaigns

## Campaign purpose

A campaign is the smallest user-facing unit that can support a CPU review or investigation. It binds:

- the subject machine;
- the comparison question;
- the pack population;
- profile and run budget;
- operating mode;
- implementation policy;
- placement policy;
- analysis and publication boundary.

Each campaign executes one machine at a time. `StudySpec` joins several
finalized campaigns under one declared comparison policy without mutating them.

## Create a campaign

```bash
cpubench campaign init reviews/new-machine.yaml --campaign-id new-machine
```

Edit the generated YAML rather than editing Python orchestration.

```yaml
schema_version: 1
artifact_kind: campaign_spec
campaign_id: new-machine
title: New machine review
description: Calibration and memory-access characterization.
profile: profiles/review.yaml
packs:
  - pack: packs/controls/pack.yaml
  - pack: packs/memory-access/pack.yaml
operating_mode: characterization
implementation_policy: native
placement: scheduler_open
output_root: .cpubench/runs
schedule_seed: 20261004
public_claims_enabled: false
```

## Preflight

```bash
cpubench campaign preflight reviews/new-machine.yaml
```

Preflight reports:

- resolved packs and families;
- providers;
- planned attempt and sample count;
- peak declared working set;
- output location;
- known platform limits.

Preflight does not change the machine.

## Execute the complete chain

```bash
cpubench campaign all reviews/new-machine.yaml
```

This performs:

```text
machine receipt
→ run-environment receipt
→ instrument and pack release identities
→ provider build and self-test
→ run-plan freeze
→ attempt execution
→ validation
→ analysis
→ report
→ finalization
→ verification
```

Use `--fresh` only when intentionally deleting an unfinished run directory with the same campaign ID.

## Stage commands

For investigation, use the stages directly:

```bash
cpubench campaign plan reviews/new-machine.yaml
cpubench campaign run reviews/new-machine.yaml
cpubench campaign validate reviews/.cpubench/runs/new-machine
cpubench campaign analyze reviews/.cpubench/runs/new-machine
cpubench campaign report reviews/.cpubench/runs/new-machine
cpubench campaign finalize reviews/.cpubench/runs/new-machine
cpubench campaign verify reviews/.cpubench/runs/new-machine
```

An interrupted `campaign run` resumes completed attempts from the frozen plan. It does not overwrite finalized campaigns.

## Profiles

Profiles select execution breadth and budget; they do not redefine family meaning.

### `smoke`

- one attempt;
- two samples;
- small work scale;
- functional installation and evidence proof.

### `qualify`

- repeated attempts and samples;
- instrument controls and mutants;
- intended for new platform or family qualification.

### `review`

- practical editorial population;
- selected curve points;
- several independent attempts;
- intended to fit a hardware-review cycle.

### `characterize`

- full curves and larger work scales;
- ten attempts and samples by default;
- intended for deeper architectural investigation.

Profile defaults are bootstrap policy, not permanent scientific law. Instrument validation will determine whether repetition counts and work scales are sufficient.

## Placement

The alpha supports:

```text
scheduler_open
cpu:<logical-id>
```

Examples:

```yaml
placement: scheduler_open
```

```yaml
placement: cpu:4
```

Pinned placement is eligible only when the platform adapter can request and read back affinity. macOS currently remains scheduler-open by design.

Semantic selectors such as `same_llc_domain` and `different_core_class` are planned with the topology/coherence pack.

## Operating modes

### Product

Use ordinary scheduler, power, boost, and dispatch behaviour.

### Characterization

Use declared placement and quiet-system controls where supported.

### Mechanism

Use exact low-level forms and optional architecture-specific instrumentation.

Machine preparation will be a separate reversible operation. `doctor` and preflight remain read-only.

## Campaign output

See [Evidence](EVIDENCE.md) for the canonical directory structure.

## Publication flag

`public_claims_enabled` is false by default.

The current alpha does not turn this flag into automatic permission. It records operator intent and prevents internal instrument-development runs from being mistaken for publication-qualified evidence.

A future publication gate will require:

- validated instrument release;
- frozen public pack release;
- eligible validity view;
- rights-safe evidence;
- complete limitations and claim boundary.

## Comparing finalized campaigns

A study joins immutable campaigns without rewriting their evidence.

```bash
cpubench study init comparisons/two-machines.yaml \
  --baseline /evidence/baseline \
  --campaign /evidence/candidate

cpubench study compare comparisons/two-machines.yaml
cpubench study report comparisons/two-machines.yaml
```

The alpha comparison admits a point only when every campaign has:

- the same family ID and version;
- the same point and form;
- the same parameter payload;
- the same validity view;
- the same analysis policy;
- a finalized bundle that verifies offline.

`study init` freezes the baseline campaign's validity view and analysis policy
into the study definition. Comparison fails rather than silently switching to a
different policy. Unmatched points follow the declared `omit_unmatched`
missingness policy and remain visible as omissions.

The study reports `baseline_ns_per_unit / candidate_ns_per_unit` as relative
speed for the current lower-is-better elapsed metric. Values above `1.0` mean
faster than baseline. It also retains each campaign's 95% attempt-bootstrap
interval and reports a conservative ratio interval derived from the marginal
intervals.

Missing or incompatible points appear as omissions with reason codes; they are not imputed or converted to zero.

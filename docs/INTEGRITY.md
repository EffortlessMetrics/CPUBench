# Benchmark integrity and challenge packs

## Construct

The integrity plane asks:

> Does the configured system behave differently because it recognizes the evaluation identity, published input, or known implementation while the relevant work remains matched?

The governing contrast is:

```text
same declared useful work
+ changed identity or held-out fixture
→ changed performance or control policy?
```

This is distinct from ordinary work correctness. A system can complete valid work while granting a public benchmark a special frequency, scheduler, thermal, or implementation path.

## Why it is first-class

Public benchmarks are necessarily inspectable and may receive legitimate optimization. They remain useful comparison surfaces. They should not be the sole evidence that ordinary applications receive the same policy.

The review campaign therefore separates:

- public reference pack;
- private frozen challenge pack;
- diagnostic follow-up;
- remediation holdout;
- retired/declassified regression pack.

## Variant types

### Exact binary alias

Same executable bytes, inputs, and command; neutral filename/path/process identity changes.

This is the strongest probe for simple name recognition.

### Package or bundle alias

Same source/workload under changed package, bundle, signing, or manifest identity where the platform permits it.

Because packaging can change the binary, several neutral controls are required.

### Workload-preserving sibling

An independent conforming implementation performs the same declared work without the famous code shape.

This tests transfer beyond one implementation but introduces legitimate compiler/layout variation. It requires family-level analysis rather than byte-equality assumptions.

### Held-out input

An unseen input sampled from the same authored population tests whether optimization transfers beyond the published fixture.

## Blind execution

The provider and system under test should not receive:

```text
challenge=true
hidden_variant=true
expected_result=no_difference
```

The relationship among public and challenge variants belongs to evaluation authority outside the subject-visible request.

The alpha includes the detector self-test and an authored `VariantSetSpec`
analysis path over retained campaign points. It does not yet include a
production challenge-pack vault or blinded variant compilation.

## Detector self-test

```bash
cpubench integrity demo
```

The command runs:

- a known-honest provider that treats public and alias variants equally;
- a known-gamed provider that recognizes the public label and changes timing.

Expected outcome:

```text
honest → no material divergence
gamed  → identity-sensitive divergence
```

This qualifies the contrast path. It is not evidence about a real vendor.

## Analyze retained campaign variants

Once a campaign contains matched public/control/challenge points, author a
`VariantSetSpec` and analyze it without rewriting the campaign:

```bash
cpubench integrity analyze \
  /path/to/finalized-or-analyzed-campaign \
  variants/public-vs-alias.yaml \
  --output findings/public-vs-alias
```

The resulting `FindingBundle` retains the campaign analysis identity, variant
contract, symmetric divergence ratio, threshold, claim boundary, and explicit
`intent_status: not_assessed`.

This command trusts the authored preservation claim. Production challenge
qualification must separately prove that the matched variants really preserve
the declared work and differ only in the intended treatment.

## Do not infer motive automatically

A finding should preserve:

```text
observed behaviour
controlled contrast
mechanism evidence
user impact
alternative explanations
vendor explanation
remediation evidence
intent status
```

The instrument may report:

> The public identity was 18% faster than the matched alias and used a different frequency policy.

It should not automatically report:

> The vendor intentionally cheated.

Intent may be supported by direct evidence, admissions, explicit benchmark lists, recurrence after disclosure, or other investigation. Effects alone do not establish conscious design.

## Remediation workflow

```text
finding
→ vendor packet
→ response
→ candidate fix
→ shared reproducer retest
→ independent holdout retest
→ remediation ruling
→ retained regression
```

Retaining a separate holdout distinguishes repairing the underlying policy from special-casing the disclosed reproducer.

## Challenge-pack lifecycle

```text
development_private
→ frozen_private
→ vendor_shared_subset
→ remediation_holdout
→ retired_public or retired_private
```

Exact active challenge fixtures should be hashed and frozen before subject-specific results are inspected.

The methodology can be public while active instances remain private. No design should claim permanent contamination or gaming resistance.

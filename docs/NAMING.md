# Naming

## Current ruling

**CPUBench is a provisional repository name, not final branding.**

It is clear enough to build under and generic enough not to force a premature product story. It is also crowded, descriptive, and narrower than the actual object: the system governs review campaigns, integrity challenges, evidence, application anchors, diagnostics, and remediation—not only CPU benchmark kernels.

Do not spend implementation time renaming before the first instrument-validation release.

## Rename trigger

Revisit the name when these are true:

- the campaign workflow is proven on real machines;
- the integrity plane is operational;
- at least one mechanism-to-application ladder exists;
- the public/private pack boundary is stable;
- the likely institutional home is known.

## Naming criteria

The final name should:

- describe evidence-producing hardware review rather than one score;
- remain usable if the corpus grows beyond CPUs into platform paths;
- avoid confusion with existing benchmark suites and packages;
- work as a CLI and repository slug;
- be defensible as a public methodology/instrument name;
- not imply certification or authority the project has not earned.

## Migration design

The Python distribution and CLI are currently `cpubench`.

A later rename should preserve:

- artifact kind/version semantics;
- provider protocol;
- campaign bundle readability;
- import compatibility for at least one transition release;
- Git history and release provenance.

The durable artifact format should not depend on final branding.

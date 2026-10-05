# ADR 0001: Python control plane with subprocess providers

- **Status:** accepted for alpha
- **Date:** 2026-10-04

## Context

The unsettled work is specification, platform discovery, planning, evidence retention, validation, analysis, and report iteration. The timed workload still needs native execution and precise boundaries.

## Decision

Use Python for the control plane and one-shot subprocesses for benchmark providers.

## Consequences

Positive:

- fast protocol iteration;
- cross-platform orchestration;
- language-neutral provider boundary;
- fresh-process attempts;
- crash and timeout containment;
- native kernels remain outside Python timing overhead.

Costs:

- Python runtime is part of control-plane receipts;
- packaging and dependency acquisition require care;
- a later compiled controller may be useful for fleet operation.

A port is justified by measured operational constraints, not by discomfort with Python in a benchmark repository.

# ADR 0003: Preserve partial platform authority

- **Status:** accepted
- **Date:** 2026-10-04

## Context

Linux, Windows, and macOS expose different timing, placement, topology, PMU, energy, and thermal controls.

## Decision

Represent each capability as qualified, available-unqualified, unsupported, failed, or unknown. Allow portable work semantics without claiming identical measurement authority.

## Consequences

- scheduler-open macOS results can remain useful;
- pinned-topology views can exclude them honestly;
- missing counters do not become zero;
- reports need capability and validity coverage beside performance.

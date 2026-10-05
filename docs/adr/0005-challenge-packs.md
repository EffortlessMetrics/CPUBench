# ADR 0005: Challenge packs are separate from public reference packs

- **Status:** accepted in design; production implementation pending
- **Date:** 2026-10-04

## Context

Public benchmark exposure permits legitimate optimization and benchmark-specific treatment. Previous investigations demonstrated that changing evaluation identity while preserving relevant work can reveal policy differences.

## Decision

Maintain frozen private challenge packs with matched identities/inputs, separate disclosure roles, blind provider requests, remediation holdouts, and eventual declassification or retirement.

## Consequences

- public reference results remain reproducible;
- integrity evidence does not depend on one famous executable;
- challenge-pack secrecy and vendor-sharing permissions need explicit governance;
- observed divergence is reported separately from motive or intent.

# ADR 0004: Campaign is the primary user object

- **Status:** accepted
- **Date:** 2026-10-04

## Context

A real CPU review includes common benchmarks, integrity challenges, anomalies, diagnostics, application checks, vendor response, and publication. A flat suite does not own that work graph.

## Decision

Make `CampaignSpec` and the campaign directory the normal user-facing object. Packs and families remain methodology components inside the campaign.

## Consequences

- reviewers can run one inspectable transaction;
- diagnostic branches can be supplemental without changing the common comparison denominator;
- campaign-level cost and usability can be measured;
- cross-machine study support is required before a full editorial workflow is complete.

# ADR 0002: Filesystem bundles are canonical evidence

- **Status:** accepted for alpha
- **Date:** 2026-10-04

## Context

Hardware review must survive CI expiry, service failure, private/offline labs, vendor disclosure, and later reanalysis.

## Decision

Use immutable portable campaign directories as canonical evidence. A future SQLite index is derived and rebuildable.

## Consequences

- users can inspect and archive complete evidence;
- reports can be regenerated offline;
- hashes can detect tampering;
- remote query performance is not optimized initially;
- one-writer discipline is required until locking/remote execution arrives.

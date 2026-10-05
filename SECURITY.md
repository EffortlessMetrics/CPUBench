# Security policy

## Reporting

Please report security vulnerabilities privately to the repository maintainers through GitHub's private vulnerability reporting when enabled. Do not open a public issue for a vulnerability that could execute arbitrary code, expose private challenge packs, disclose licensed assets, or compromise review machines.

## Scope

Security-sensitive areas include:

- source acquisition and build scripts;
- provider subprocess execution;
- path handling in campaign bundles;
- archive extraction;
- future sandbox and privileged helpers;
- challenge-pack disclosure;
- restricted SPEC asset handling;
- publication projections;
- evidence tampering and verification.

## Current posture

`0.2.0a0` is intended for trusted first-party and pinned provider code.

It does not yet sandbox untrusted contributed providers. Do not run unknown benchmark packs on valuable hardware.

Ordinary execution does not require root. Future privileged measurement must use a narrow audited helper and must never execute arbitrary provider code in privileged context.

# Trust and security

## Threat model

Benchmarking executes third-party code, compilers, build scripts, generated binaries, and platform instrumentation on valuable hardware. CPUBench must preserve measurement authority without turning the review machine into an unbounded execution environment.

## Source trust classes

```text
first_party_reviewed
third_party_pinned
external_installed
private_restricted
untrusted_candidate
```

The alpha supports the first four operationally. Untrusted public contribution execution requires stronger sandboxing and governance.

## Acquisition requirements

External sources should record:

- URL;
- exact commit/version;
- digest;
- license;
- expected size;
- redistribution class;
- acquisition date.

No normal benchmark run may download undeclared code or data.

## Network

The target default is:

- network allowed during explicit acquisition/build stages where required;
- network disabled during benchmark execution;
- no workload-specific remote dependency at run time.

The alpha does not yet enforce network isolation automatically. Campaign operators should run trusted bundled packs only.

## Privilege

Normal review runs should remain unprivileged.

Privileged measurement, if added, must use a narrow audited helper that exposes named operations such as:

```text
open qualified counter set
read qualified sensor
request reversible power/frequency policy
request platform-specific placement
```

It must not execute arbitrary provider code in kernel or privileged context.

Community-supplied code never receives privileged helper access by default.

## Machine preparation

`doctor` and preflight are read-only.

A future `prepare` command will:

- show a dry-run plan;
- require explicit authorization;
- record original state;
- apply bounded reversible changes;
- record effective state;
- restore and verify restoration.

Preparation must never be hidden inside a benchmark command.

## Private and embargoed evidence

Keep separate permissions for:

```text
execution
local retention
vendor sharing
Git commit
public publication
```

Public bundles must exclude:

- credentials;
- private asset paths;
- restricted payloads;
- embargoed product identifiers where prohibited;
- raw host/user identifiers unless approved;
- proprietary vendor correspondence.

## Challenge packs

Active challenge packs should live outside the public repository in a content-addressed local vault.

The public methodology may describe transformation classes without exposing active filenames, hashes, package identities, or held-out inputs.

## Build and run separation

Builds may use a contained environment where the resulting binary identity remains receipted.

Performance execution should normally be host-native. Containers, VMs, WSL, emulation, and translation are explicit configured-system treatments.

## Evidence integrity

Campaign finalization hashes all canonical files. Verification detects missing or modified files.

The alpha does not yet provide cryptographic signatures or remote attestation. Those can be added without replacing the canonical bundle format.

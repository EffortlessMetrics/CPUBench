# Contributing

CPUBench is accepting design and implementation work while the first instrument release is being qualified. Performance claims and new benchmark families carry a higher burden than ordinary feature code.

## Start here

Read:

1. [Construct](docs/CONSTRUCT.md)
2. [Architecture](docs/ARCHITECTURE.md)
3. [Protocol](docs/PROTOCOL.md)
4. [Family authoring](docs/AUTHORING.md)
5. [Trust](docs/TRUST.md)
6. [Current status](docs/CURRENT_STATUS.md)

## Development setup

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'

pytest
ruff check .
mypy src/cpubench
```

Run the complete smoke proof:

```bash
cpubench campaign all examples/quickstart.yaml --fresh
```

## Contribution classes

### Control-plane changes

Must preserve:

- artifact identity rules;
- terminal attempt states;
- raw evidence;
- offline report regeneration;
- final bundle verification.

### Provider changes

Must include:

- protocol contract tests;
- deterministic self-test;
- work/output validation;
- exact completed-unit accounting;
- setup/timing boundary evidence;
- unsupported/failure paths.

### New family

Must include:

- `FamilySpec`;
- bounded question and claim boundary;
- positive witness;
- controls;
- known-bad mutants;
- proof build and measurement build plan;
- rights and source entry;
- resource budget;
- qualification evidence.

Do not submit a benchmark only because it is popular or produces an interesting vendor difference.

## Pull request expectations

A PR should state:

```text
Goal
Authority and dependencies
Transformation
Evidence produced
Invariants
Negative tests / mutants
Non-goals
Verification commands
```

Keep raw evidence and generated reports out of ordinary source PRs unless they are small governed fixtures.

## Performance evidence

Shared CI is functional evidence, not canonical performance authority.

Performance claims should name:

- machine receipt;
- build receipt;
- operating mode;
- pack/family version;
- validity view;
- attempt/device population;
- uncertainty;
- claim boundary.

## Code style

- Python 3.11+ typing;
- Pydantic models at external/durable boundaries;
- no hidden fallback;
- stable reason codes for failures;
- deterministic canonical output;
- native code with warnings enabled;
- comments explain benchmark mechanism, not obvious syntax.

## Licensing

Contributions are accepted under `MIT OR Apache-2.0` unless an explicitly approved vendored component carries a compatible separate license and notice.

Do not contribute restricted benchmark materials or data you cannot redistribute.

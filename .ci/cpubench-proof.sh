#!/usr/bin/env sh
set -eu

python -m compileall -q src tests
pytest
ruff check .
mypy src/cpubench
rm -rf .proof-run
mkdir -p .proof-run
cp examples/quickstart.yaml .proof-run/campaign.yaml
python -m cpubench campaign all .proof-run/campaign.yaml --fresh
python -m cpubench integrity demo --output .proof-run/integrity
python -m cpubench schema export contracts/schemas
python scripts/check_schemas.py
python scripts/check_docs.py
python scripts/check_yaml.py

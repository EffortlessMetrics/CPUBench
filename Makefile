PYTHON ?= python
CPUBENCH ?= $(PYTHON) -m cpubench

.PHONY: install format lint typecheck test schemas smoke integrity verify clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

format:
	$(PYTHON) -m ruff format .

lint:
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy src/cpubench

test:
	$(PYTHON) -m pytest

schemas:
	$(CPUBENCH) schema export contracts/schemas

smoke:
	rm -rf examples/.cpubench
	$(CPUBENCH) campaign all examples/quickstart.yaml --profile profiles/smoke.yaml --fresh

integrity:
	rm -rf .cpubench/integrity-demo
	$(CPUBENCH) integrity demo --output .cpubench/integrity-demo

verify: lint typecheck test schemas smoke integrity
	$(PYTHON) scripts/check_schemas.py
	$(PYTHON) scripts/check_docs.py
	$(PYTHON) scripts/check_yaml.py

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov dist build .cpubench examples/.cpubench
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

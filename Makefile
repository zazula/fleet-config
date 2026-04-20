PYTHON ?= python3

.PHONY: fmt lint test

fmt:
	$(PYTHON) -m ruff format src tests

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m mypy src tests

test:
	$(PYTHON) -m pytest tests/ -v

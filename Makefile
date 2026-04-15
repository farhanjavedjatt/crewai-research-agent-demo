.PHONY: install dev run cli history ui test lint typecheck fmt clean

PY := python3
VENV := .venv
BIN := $(VENV)/bin

install:
	$(PY) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -e ".[dev]"

run ui:
	$(BIN)/streamlit run streamlit_app.py

cli:
	$(BIN)/python -m research_crew run "$(Q)"

history:
	$(BIN)/python -m research_crew history

test:
	$(BIN)/pytest

lint:
	$(BIN)/ruff check src tests

fmt:
	$(BIN)/ruff format src tests
	$(BIN)/ruff check --fix src tests

typecheck:
	$(BIN)/mypy src

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info

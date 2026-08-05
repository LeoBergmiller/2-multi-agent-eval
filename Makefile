.PHONY: help install relock data demo record eval test lint fmt clean

VENV := .venv
PY   := $(VENV)/bin/python

# Gate 0 default task.
TASK    ?= evals/tasks/gate0_inpatient_encounters_2023.yaml

# `make demo` writes a SCRATCH run (gitignored). The committed demo run is
# written only by `make record` — a committed artifact that every invocation
# overwrote would not be an artifact.
RUN_ID  ?= local
MODE    ?= replay
DEMO_RUN_ID := demo-gate0

help:
	@echo "make install  - sync $(VENV) from uv.lock (exact, committed resolution)"
	@echo "make data     - build data/warehouse.duckdb from data/fixtures/"
	@echo "make demo     - replay the task into runs/$(RUN_ID)/ and print the eval line"
	@echo "                (no API key, no network, no warehouse required)"
	@echo "make record   - LIVE run: re-record cassettes + refresh runs/$(DEMO_RUN_ID)/"
	@echo "                (needs ANTHROPIC_API_KEY; costs money)"
	@echo "make eval     - re-score an existing run: make eval RUN_ID=<id>"
	@echo "make test     - pytest"
	@echo "make lint     - ruff check + mypy"
	@echo "make fmt      - ruff format + fix"

# --frozen: never re-resolve. The committed lock is the contract; if pyproject
# and uv.lock disagree this fails loudly rather than silently drifting.
install:
	uv sync --frozen

# Run after intentionally changing a dependency in pyproject.toml.
relock:
	uv lock
	uv sync --frozen

# Invoked by PATH, not as `-m data.load_fixtures`: `data/` is not a package and
# is not in pyproject's packages list, so module resolution would only succeed
# when CWD happens to put the repo root on sys.path. `make data` is in the
# clone-and-run path, so it must not depend on where it was invoked from.
# The script resolves its own paths from __file__, so by-path is fully portable.
data:
	$(PY) data/load_fixtures.py

# Replay by default: no API key, no network — and deliberately NO dependency on
# `data`, because a replayed run needs no warehouse at all. If this target ever
# starts needing one, the replay layer has sprung a leak.
demo:
	$(PY) -m analyst.runner --task $(TASK) --run-id $(RUN_ID) --mode $(MODE)
	$(PY) -m evals.runner  --run-id $(RUN_ID)
	$(PY) -m evals.report  --run-id $(RUN_ID)

# Live run that also writes cassettes, and the only thing that refreshes the
# committed demo run. Needs ANTHROPIC_API_KEY and the warehouse.
record: data
	$(PY) -m analyst.runner --task $(TASK) --run-id $(DEMO_RUN_ID) --mode record
	$(PY) -m evals.runner  --run-id $(DEMO_RUN_ID)
	$(PY) -m evals.report  --run-id $(DEMO_RUN_ID)

eval:
	$(PY) -m evals.runner --run-id $(RUN_ID)
	$(PY) -m evals.report --run-id $(RUN_ID)

test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check .
	$(VENV)/bin/ruff format --check .
	$(VENV)/bin/mypy

fmt:
	$(VENV)/bin/ruff format .
	$(VENV)/bin/ruff check --fix .

clean:
	rm -rf data/warehouse.duckdb .pytest_cache .ruff_cache .mypy_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

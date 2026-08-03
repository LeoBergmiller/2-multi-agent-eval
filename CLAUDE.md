# Project 2 — Multi-Agent Healthcare Ops Analyst

Full architecture: `docs/architecture.md`. Decisions and rationale: `docs/decisions.md`.
Read architecture.md before any non-trivial change.

## What this is
A multi-agent LangGraph system over Synthea healthcare operations data, whose
purpose is TRAJECTORY-FIRST EVALUATION. The eval harness is the product; the
agents are the subject under test.

## Priority when tradeoffs arise
1. Eval correctness and reproducibility  2. Span completeness
3. Typed contracts and recovery  4. Agent capability  5. UI polish (last)

## Hard rules
- Five graph nodes. Do not add a sixth.
- No dataframes through LLM context — `ResultRef` only.
- No untyped dicts across module boundaries.
- Validation failures are recorded events routed to replan, never unhandled exceptions.
- No LLM judge in the blocking CI gate.
- Reference trajectories are partial-order constraint sets, never single golden paths.
- Two cassette seams only: LLM client and MCP client.
- No absolute local paths in `pyproject.toml`.
- Cassette miss in REPLAY mode = hard failure. Never fall through to live.
- `reference_sql` and `ground_truth` are HUMAN-VERIFIED. Draft and execute them,
  but never mark them canonical without explicit human sign-off.
- Every capability ships with its span attributes and its metric in the same PR.
- Stop at the current gate boundary. Do not build ahead.

## Style
Python 3.12.3 (matches Project 1), ruff, full type hints, YAML→frozen dataclass/Pydantic configs, pytest.

## Current gate
Gate 0 — walking skeleton. See `docs/architecture.md` §10.

## Environment
Virtualenv at `.venv` (Python 3.12.3, matches Project 1).
Run `source .venv/bin/activate` before any python/pip/pytest command.
Never install into system Python.

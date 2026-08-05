# Multi-Agent Healthcare Ops Analyst

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
Gate 1 — MVP complete. See `docs/architecture.md` §10.
**Read `docs/gate-0.md` before planning** — retrospective, deferrals, and what bit last gate.

## Carried from Gate 0
- `ground_truth` returns to `status: draft` the moment Synthea replaces the fixture. The number
  changes and D17 applies again — a human re-signs before it counts.
- The replan edge is a one-line change of the router's target from terminal. Not a restructure;
  the ingress/egress boundary already records `ValidationEvent`s.
- `evals/trajectory.py` already emits the raw signals for `loop_rate` and
  `context_transfer_integrity` (repeated `(tool, args_hash)` pairs). Those land as scorers, not
  as new plumbing.

## Standing rule: one real `make record` per gate
The stubbed RECORD test proves our wiring, never the vendor's wire format. A schema or SDK
change would pass every test and only surface on a live call.

## Environment
Python 3.12.3 at `.venv` (matches Project 1), managed by **uv**.
Install with `uv sync --frozen`; run things with `uv run …` or `.venv/bin/…`.
**Never `pip install`.** It mutates the venv out of step with `uv.lock` and nothing fails —
which silently voids the frozen-resolution guarantee the reproducibility claim rests on, and a
drift that breaks replay presents as a cassette bug. To change a dependency: edit
`pyproject.toml`, then `make relock`.
Never install into system Python.

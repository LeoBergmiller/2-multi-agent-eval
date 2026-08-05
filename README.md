# Multi-Agent Healthcare Operations Analyst

An autonomous multi-agent healthcare operations analyst (LangGraph + MCP) evaluated at the
**trajectory level** — not just on whether the final answer was right, but on whether the path
to it was.

> **Gate 0 of 5 — walking skeleton.** Three of five nodes, one of five MCP tools, one of eight
> metrics, one task. The eval harness is the product; the agents are the subject under test.
> This README describes what runs today, not what is planned. See
> [`docs/architecture.md` §10](docs/architecture.md) for the gate plan.

## Current results

```
gate0_inpatient_encounters_2023  task_success=1.00  answer=37 (expected 37±0)
  steps=4  tools=1  cost=$0.0356  mode=replay  ground_truth=verified
  max handoff bundle: 602 tokens; repeated tool calls: 0

GATE 0: PASS
```

| | Gate 0 | Gate 1 target |
|---|---|---|
| Tasks | 1 | 25 |
| Metrics | 1 (`task_success`) | 8 |
| Graph nodes | 3 | 5 |
| MCP tools | 1 (`run_sql`) | 5 + 2 resources + 2 prompts |
| Single-agent baseline arm | — | ✅ |
| Cost / task | $0.0356 | measured across the set |

One task means `task_success` is necessarily 1.00 or 0.00. It becomes a rate at Gate 1.

## Run it

No API key. No network. No warehouse. No Project 1 install.

```bash
make install   # uv sync --frozen — the exact committed resolution
make demo      # replays the task from committed cassettes and prints the eval line
```

`make demo` is the definition of done for this gate ([§12](docs/architecture.md)). It exits
non-zero if the gate fails, so CI and a human get the same verdict.

```bash
make test      # 107 tests
make lint      # ruff + strict mypy
make record    # LIVE run: re-records cassettes and refreshes runs/demo-gate0/ (needs a key, costs money)
```

## How the evaluation works

**Ground truth is executed, not generated.** Every task's expected value comes from running
`reference_sql` against the warehouse. Both `reference_sql` and `ground_truth` are
**human-verified artifacts** — the coding agent may draft and execute them, but a human signs
off before a number becomes canonical, and the harness *refuses to count an unverified ground
truth as a pass*. If the same system wrote both the analyst and its reference answers, the
errors would be correlated and invisible.

**Reference trajectories are partial-order constraint sets, not golden paths.** A task declares
`required_tools`, `forbidden_tools`, `required_order` pairs, `min_steps` and `must_cite` — what
must be true, without dictating how. A single golden sequence punishes valid alternate orderings
and overfits the eval to one implementation.

**The gate is hermetic by construction.** CI has no `ANTHROPIC_API_KEY` secret configured. The
suite replays from committed cassettes, and a cassette miss in replay mode is a **hard failure**
that never falls through to a live call — verified by a test that leaves a working live client
attached and asserts it is never used. A green build that quietly made an API call would be
worse than a red one.

**No LLM judge in the blocking gate.** Judged metrics are nightly and sampled; the gate scores
deterministically.

## Architecture

```
TaskSpec
   ↓
[Planner] ──emits──> Plan (DAG of SubTasks)
   ↓  deterministic router (no model decides routing)
   └──> [SQL Analyst] ──MCP──> run_sql ──> ResultRef
   ↓
[Synthesizer] ──> FinalAnswer (with provenance)
```

Docs Analyst, Quant Analyst and the Validator node arrive at Gate 1. Five nodes is the ceiling.

Load-bearing choices, each with its reasoning in [`docs/decisions.md`](docs/decisions.md):

- **No dataframes through an LLM context.** Tools return a `ResultRef` plus schema, row count and
  five sample rows; full frames live in `runs/{run_id}/results/`. This bounds context and makes
  `context.bundle_tokens` a measurable per-step metric.
- **Bounded handoffs, no shared scratchpad.** A specialist receives its subtask and its input
  refs, nothing else. Passing full history to every agent is just a slower single agent.
- **Validation failures are recorded events, never escaping exceptions.** A boundary violation
  becomes a typed `ValidationEvent` on state and on the span, routed by the router.
- **Two cassette seams only** — the LLM client and the MCP client. `run_sql`, and later
  `run_python` and `search_metric_definitions`, are all MCP tools, so one interceptor covers
  them all.
- **Cost is measured, not estimated.** Prices live beside the model IDs in `config/models.yaml`
  with the date they were verified, and every run records a hash of that table — so editing a
  price later cannot silently re-cost an old run.

## Data, and what it is not

The warehouse is **synthetic** ([Synthea](https://github.com/synthetichealth/synthea)-shaped).
Its population is module-generated, so **epidemiological conclusions from it are meaningless**.
This project measures the *agent's* correctness, not clinical findings. The dataset's job is to
supply relational complexity and operational messiness.

**Scope boundary:** this is an operational-analytics system — admissions, encounters, length of
stay, readmissions, payer mix, throughput. It is **not clinical decision support** and does not
emit clinical guidance. That boundary is enforced in the Synthesizer prompt, not just stated
here.

At Gate 0 the warehouse is a small committed CSV fixture using Synthea's real column names, so
that Gate 1's ingest is a data swap rather than a rewrite. It is deliberately not clean: six
encounters have a `NULL` discharge timestamp (still-admitted patients). The Gate 0 task's answer
is 37; a query that drops those returns 31, and one that ignores `ENCOUNTERCLASS` returns 182.
The traps are in the SQL, not in the definition — which matters, because the metrics dictionary
that would disambiguate definitions is a Gate 1 deliverable.

## Not building (with triggers)

| Not building | What would change it |
|---|---|
| Cross-session agent memory | the analyst must recall prior sessions' derived definitions |
| Full A2A layer | more than one agent independently operated |
| Network topology | never here — traces become unattributable |
| A "Critic Agent" | the deterministic validator node suffices |
| OAuth 2.1 on MCP | multi-tenant or external consumers |
| E2B sandbox | multi-tenant untrusted execution I don't operate |
| MIMIC-IV / HCUP real data | when redistribution isn't required |

State durability uses the LangGraph checkpointer. That is **durable execution, not memory** —
the distinction is deliberate.

## Layout

```
src/analyst/     the system under test
evals/           the harness that measures it — deliberately a separate namespace
cassettes/       committed; powers CI, demo mode and the video identically
runs/demo-gate0/ committed run artifact: meta, plan, spans, results, final, eval
docs/            architecture brief and the decisions log
```

Python 3.12.3, `uv` with a committed lockfile, ruff, strict mypy.

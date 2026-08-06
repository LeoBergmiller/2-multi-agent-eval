# Gate 1a — Real Data and the Full Tool Surface

*Add to the repo as `docs/gate-1a.md`. Companion to `docs/architecture.md` (the spec) and `docs/gate-0.md` (the retrospective). Read all three before planning.*

Gate 1 is split into four sub-gates because its surface is roughly five times Gate 0's, and one plan for all of it will drift. Each sub-gate ends with the README true, a run committed, and CI green — same discipline as Gate 0, finer grain. **Fresh session per sub-gate.**

- **1a** (this document) — real data, full tool surface, Docs Analyst
- **1b** — Quant Analyst, Validator, replan edge, failure injection
- **1c** — remaining metrics, full task set, single-agent baseline, the comparison table
- **1d** — Streamlit demo, README, video. **Timeboxed to half a day.**

---

## 0. What 1a is

Replace the Gate 0 fixture with real Synthea data, build the four remaining MCP tools plus both resources and both prompts, integrate Project 1's retrieval as `search_metric_definitions`, author the metrics dictionary, add the Docs Analyst node, and author 7 seed tasks with human-verified ground truth.

**Exit criterion:** the system correctly answers a question that requires *both* a SQL query and a metrics-dictionary lookup, where skipping the lookup produces a plausible wrong number — and the trace shows both agents working.

**Node count at end of 1a: four.** Planner, SQL Analyst, Docs Analyst, Synthesizer. Quant Analyst and Validator are 1b. Five remains the ceiling.

---

## 1. Ordering constraint that dominates everything

**Synthea ingest lands before any task is authored.**

Ground truth is executed against the warehouse (D17). A task authored against the Gate 0 fixture would have to be human-verified twice — once now, once after the swap — and that verification is the human's time, not the agent's. Nothing that depends on a row count gets written until the real warehouse exists.

Corollary: **the Gate 0 ground truth of 37 dies with the fixture.** Per the carried rule in `CLAUDE.md`, `gate0_inpatient_encounters_2023.yaml` returns to `status: draft` the moment the fixture is deleted, and is re-verified against Synthea or retired.

---

## 2. Step order

### Step 1 — Project 1 spike (do this first, before anything else)

The only part of 1a with a dependency outside your control: a tagged package, a built index, a ~120s HF warmup. Prove it works before the corpus exists.

- Fix and tag Project 1 (see D24 — the extras split and the `local` ingest source are prerequisites, so the tag comes **last**, not first), add the git-pinned optional extra to `pyproject.toml`, `uv sync --extra rag`
- Build a throwaway 3-document index
- Implement `RetrievalBackend` protocol + `RagEvalRetriever` using the **in-process path only** (`load_config(explicit_path) → load_resources(cfg) → build_retriever(strategy, cfg, resources) → retriever.retrieve(query, k)`, which returns a `RetrievalResult` whose `.chunks` is the list). Never the FastAPI `/query` endpoint — it runs generation, which costs money and returns an answer when the agent wants passages.
- `chunk.parent_id → doc_id`; pass `chunk_id` and `score` through unchanged. `parent_id` is typed `str | None` — a `None` reaching `doc_id` must **raise at the adapter boundary**, never default. `must_cite` is keyed on `doc_id`, so a `"None"` string would be a silent-wrong citation.
- `warmup()` called once at MCP server startup, never per call. It must build the retriever too, not just load resources — `rerank` loads its cross-encoder at `build_retriever` time.
- **Register `search_metric_definitions` as an MCP tool here.** Pulled forward from step 5: recording through the MCP seam is impossible without the tool that crosses it. This is the one piece of step 5 that step 1 owns.
- Record one cassette through the MCP seam; prove replay works with the index deleted. **These cassettes are disposable by design** — `corpus_version` hashes the corpus into the retrieval cassette key (§6.2), so the real dictionary landing in step 4 invalidates every one of them. That is the mechanism working, not a defect. Re-record after step 4.

**Report the three Phase D numbers before proceeding:** cold `warmup()` (first run, model download), **warm `warmup()`**, and p50 `retrieve` latency. Warm warmup is the number that matters, because `StdioMCPClient` spawns a fresh server subprocess per run — warmup is paid once per *task*, not once per process. Whether a sweep reuses one server subprocess is an architecture decision to be made from that measurement and recorded in `decisions.md`; the server is stateless (read-only DuckDB, read-only index) and the cassettes sit at the client seam, so hermeticity does not constrain the answer.

**Stop and report if:** the P1 API differs from the above, or the extra can't install without the local path. Do not work around it silently — the whole Gate 1 shape depends on this tool being cheap and reliable.

### Step 2 — Synthea ingest

- Generate with a **fixed seed**, ~2000 patients. Tune down if generation is slow; the requirement is enough rows that joins are non-trivial, not scale.
- Commit the generation command + seed in the `Makefile`. **Gitignore the CSVs and the DuckDB file** — they're derived and too large.
- `make data` regenerates deterministically from the seed.
- **This does not break clone-and-run.** Proven at Gate 0: replay needs neither DuckDB nor the network. A stranger runs `make demo` from cassettes with no JDK, no warehouse, no key. Building the warehouse is only needed to run live or re-record. State this explicitly in the README.
- Tables to load: `patients`, `encounters`, `organizations`, `providers`, `payers`, `conditions`, `procedures`, `claims`, `payer_transitions`.
- **Declare column types explicitly.** The Gate 0 lesson: DuckDB's sniffer infers `STOP` as VARCHAR because of empty strings, making every date comparison a silent string comparison.
- Delete `data/fixtures/` and the TODO in `data/README.md`.

### Step 3 — `messify.py`

Deterministic, seeded, committed, runs after ingest. Inject:

- duplicate encounter rows (double-posted feed)
- null `STOP` for still-admitted patients
- payer names with inconsistent casing and trailing whitespace
- a small number of encounters with `STOP < START`
- one organization that changed its ID mid-year

Each pathology becomes both a metrics-dictionary rule and a candidate trap task. Emit a summary of what it injected — the counts are needed for reference SQL.

### Step 3.5 — Draft the 7 task intents (prose only)

One paragraph per task: the question, the trap, and which tools it should force. **No SQL, no numbers, no ground truth.**

This exists because step 4 says to author the dictionary task-intent-first while step 7 authors the tasks — you cannot derive a dictionary from intent that does not exist yet. Drafting intent here resolves that without violating §1, which governs *ground truth* (needs the warehouse) rather than intent (does not).

The intents are provisional. Step 7 may change a question once the real row counts are known; what step 4 needs is the *shape* of the ambiguity, not the final wording.

### Step 4 — Metrics dictionary

**Author it task-intent-first, not exhaustively.** Start from "what would a competent analyst plausibly get wrong here?" The ambiguity that makes the trap is the dictionary entry; the dictionary is a byproduct of task design, not an input to it.

Two categories:

**Load-bearing (~10).** Each one is the definition a seed task requires. Candidates: 30-day readmission (index assignment, exclusions for death/transfer/AMA/planned, discharge- vs admission-anchored window, same-facility vs any-facility); length of stay (midnights vs calendar days vs hours, same-day discharge, outlier truncation); "admission" (which `ENCOUNTERCLASS` values count — this is the highest-value trap, since counting wellness visits is wrong by an order of magnitude); payer mix denominator; attributed provider; plus one per `messify.py` pathology.

**Near-miss distractors (~15–20).** Written *after* the load-bearing set, and this is what makes retrieval a real problem rather than a lookup. With ten documents, retrieval is trivially perfect and RAGAS measures nothing. Distractors are plausible, retrievable, and *wrong for the specific question*: "readmission — 90-day all-cause," "readmission — same-facility only," "LOS — midnights," "LOS — calendar days." Retrieving one yields a subtly wrong answer rather than an obviously irrelevant one, which is exactly the failure the eval should catch.

Corpus is committed. `corpus_version` hashes its contents and is part of the retrieval cassette key.

### Step 5 — Remaining MCP tools, resources, prompts

Tools: `describe_schema`, `describe_table`, `search_metric_definitions`, `run_python`. Resources: `schema://warehouse`, `docs://metrics/{doc_id}`. Prompts: `analyst/plan`, `analyst/sql_style`.

`run_python` needs `LocalDockerSandbox` behind the `SandboxBackend` protocol: `--network none`, read-only rootfs + tmpfs scratch, memory and CPU caps, non-root user, wall-clock kill, artifacts mounted read-only. E2B is documented as a swap-in, **not implemented** — an adapter you never execute is dead code.

`describe_table` must return the real Synthea column set. Its output shape is what the SQL Analyst prompt is written against.

### Step 6 — Docs Analyst node

Thin: `SubTask` → `search_metric_definitions` → `AgentResult` with `artifact_refs` and `assumptions_made`. Bounded `context_bundle` — it receives its subtask and input refs, nothing else.

Planner must now emit plans with genuine fan-out: a `Plan` DAG where the docs lookup and the SQL work are separate `SubTask`s with a `required_order` dependency.

### Step 7 — Seed tasks (7, human-verified)

**Authored last in 1a, but they are the specification for 1b–1c, not a test of what 1a happens to do.** If a tool isn't required by any seed task, ask why it's in the design.

| # | Shape | Exercises |
|---|---|---|
| 1 | Multi-table join, no definitional ambiguity | `describe_schema`, `describe_table`, `run_sql` |
| 2 | Wrong without the definition lookup | `search_metric_definitions` → `run_sql`, `required_order`, `must_cite` |
| 3 | Requires computation over a result set | `run_sql` → `run_python`, `ResultRef` passing |
| 4 | Needs both docs and quant | full fan-out, bounded handoffs |
| 5 | Answerable in SQL alone | `forbidden_tools: [run_python]` — over-tooling trap |
| 6 | Turns on a `messify.py` pathology | data-quality reasoning |
| 7 | Two similar dictionary entries, one correct | distractor-sensitive retrieval, RAGAS |

**No failure-injection task in 1a** — the machinery is 1b. That task gets authored there.

**Retiring the Gate 0 task has blast radius — sequence it here, don't discover it at the checklist.** `gate0_inpatient_encounters_2023.yaml` is the `Makefile`'s default `TASK`, and `runs/demo-gate0/` plus its committed cassettes are keyed to it. Retiring or re-verifying it therefore means, in order: pick the new default `TASK` from the seed set, re-record its cassettes, commit the new run at `runs/demo-gate1a/`, and retire `runs/demo-gate0/`. **That re-record is this gate's one real `make record`** — it satisfies the standing rule rather than being an extra chore, so do not also schedule a separate live run.

**Ground-truth protocol (D17).** For each: draft `reference_sql`, execute it, and present the human with the number, the row count, and enough of the row set to check. `status: draft` until explicit sign-off. `require_verified_ground_truth: true` means the harness scores but refuses to pass on an unverified number. Record `by`, `on`, and `method` in the task YAML.

**Design the eventual set by metric coverage, not by count.** "25 tasks" is arbitrary. The requirement is that no metric is degenerate — `recovery_rate` over three tasks is noise. Target: every metric has ≥5 tasks exercising it non-trivially. The count falls out (likely 22–28) and is defensible in a way a round number isn't. The other ~17 get authored in 1c as variations, once the system runs.

---

## 3. Carried from Gate 0 — do not relearn these

- **Silent-failure shape.** Every Gate 0 defect and near-miss was a wrong thing that couldn't fail loudly: DuckDB's case-insensitivity, Pydantic's silent extra-drop, OTel's warn-and-continue, a dump/load asymmetry never exercised in one process. When adding a component, ask what its silent-wrong mode is and write the test that would catch it.
- **Replay covers the cassetted result, not the artifact behind the ref.** A replayed run's `results/` is empty by design: the recorded artifact is the `ResultRef`, not the frame it points at, and recording the frame would be a third seam. So any new path that *resolves* a ref to its file is invisible to the hermetic gate — it passes CI and fails only live. **Every new ref-consuming path needs a RECORD-mode test.** First one due with seed task 3 (`run_sql → run_python`), which is the first consumer of the frame behind a ref.
- **No global state.** The tracer is threaded through `RunContext`. Nothing new sets a process-global.
- **`extra="forbid"` on every contract.** It caught a partial `TaskFile` model at Gate 0.
- **One real `make record` per gate.** The stubbed RECORD path can't detect a vendor wire-format change.
- **Cassette hygiene.** New tests that call `run_task` must monkeypatch `cassettes_root`, or they overwrite the committed cassettes CI depends on.
- **`uv sync --frozen` / `uv run`. Never `pip install`** — it mutates the venv out of step with `uv.lock`, nothing fails, and it later presents as a cassette bug. Need a dependency? Edit `pyproject.toml`, then `make relock`.

---

## 4. Explicitly not in 1a

Quant Analyst · Validator node · replan edge · failure injection · the seven remaining metrics · the single-agent baseline · the Streamlit app · LangSmith export · A2A · the full task set.

**LangSmith sampled export is the first thing cut if 1c runs long.** `spans.jsonl` is the source of truth and the demo app renders it; LangSmith is a viewing convenience with nothing downstream depending on it. Cut it to Gate 2 and record why.

---

## 5. Exit checklist

- [ ] P1 tagged with the extras split + `local` source (D24); `uv sync --extra rag` resolves; CI still green *without* the extra
- [ ] P1 retrieval works in-process; the three Phase D numbers measured and the subprocess-reuse decision recorded
- [ ] Retrieval cassette **re-recorded after step 4** — the step-1 cassettes died with the throwaway corpus (`corpus_version`); replay works with the index deleted
- [ ] `make data` regenerates the Synthea warehouse deterministically from a committed seed
- [ ] `messify.py` deterministic, its injected counts reported
- [ ] `data/fixtures/` deleted; Gate 0 task re-verified against Synthea or retired, with the `Makefile` default `TASK` repointed and `runs/demo-gate0/` retired
- [ ] 7 task intents drafted in prose (step 3.5) before the dictionary was authored
- [ ] Metrics dictionary committed: ~10 load-bearing + ~15–20 distractors, `corpus_version` in the cassette key
- [ ] All 5 tools, 2 resources, 2 prompts live; `LocalDockerSandbox` hardened as specified
- [ ] Docs Analyst node; Planner emits genuine fan-out
- [ ] 7 seed tasks, all `status: verified` with recorded method
- [ ] **Exit criterion met:** a question requiring both SQL and a docs lookup answers correctly, and skipping the lookup demonstrably produces a wrong number
- [ ] `make lint` green, tests green, `make demo` runs keyless from cassettes
- [ ] One committed run at `runs/demo-gate1a/`, produced by this gate's one real `make record`
- [ ] A RECORD-mode test covering `ResultRef` resolution (seed task 3)
- [ ] `docs/gate-1a.md` retrospective; `CLAUDE.md` gate line updated to 1b

**Stop at the checklist. No 1b work.**

---

## 6. Guardrails

- Four nodes at the end of 1a. Five is the ceiling.
- No dataframes through LLM context — `ResultRef` only.
- No untyped dicts across module boundaries.
- Validation failures are recorded events, never unhandled exceptions.
- Reference trajectories are partial-order constraint sets, never single golden paths.
- Two cassette seams only.
- `reference_sql` and `ground_truth` are human-verified. Draft and execute them; never mark canonical without explicit sign-off.
- Every capability ships with its span attributes and its metric in the same commit.
- Commit plans only — the human runs all git commands.

# Project 2 — Architecture Decisions Log

*Interview cheat-sheet. Every entry answers "why did you choose X over Y?" Format: Options · Choice · Rationale · the pushback you'd get and how you answer it.*

*Status: all decisions resolved as of pre-build. Companion to `docs/architecture.md` (the build spec).*

---

## Framing and orchestration

### D1 — Project framing
- **Options:** simple tool-using agent · multi-agent system with trajectory evaluation
- **Choice:** multi-agent system centered on trajectory-first evaluation and the standard protocol stack
- **Rationale:** agentic is the biggest skills gap; agent evaluation (distinct from LLM eval) is the most sophisticated signal; both extend published multi-agent research
- **Pushback:** *"Isn't this just an agent demo?"* → The agents are the subject under test. The product is the eval harness.

### D2 — Orchestration framework
- **Options:** LangGraph · CrewAI · AutoGen/AG2 · OpenAI Agents SDK · Google ADK
- **Choice:** LangGraph
- **Rationale:** 2026 production default — stateful graphs, durable execution, HITL, checkpoints; native LangSmith pairing
- **Pushback:** *"CrewAI is simpler."* → It is, and it hides the state transitions I need to instrument. My eval reads a span tree; I need explicit control over node boundaries.

### D7 — Orchestration pattern
- **Options:** supervisor/hierarchical · sequential pipeline · network
- **Choice:** supervisor/hierarchical with plan-execute-replan
- **Rationale:** traces form a tree, so failures are attributable and a reference trajectory is definable. Network topologies are neither.
- **Pushback:** *"Network is more flexible."* → Flexibility I can't evaluate isn't a feature here.

### Agent roster — five nodes
Planner/Supervisor · SQL Analyst · Docs Analyst · Quant Analyst · Synthesizer, plus a deterministic Validator **node** (not an agent).
- **Rationale:** each specialist owns a distinct tool surface and failure domain. A "Critic Agent" and a "QA Agent" would be prompts wearing costumes.
- **Pushback:** *"Why not one agent with four tools?"* → **Measured, not asserted — see D20.**

---

## Protocols

### D3 — Tool protocol
- **Options:** custom API wrappers · MCP
- **Choice:** MCP, **building a custom FastMCP server** with all three primitives (tools, resources, prompts)
- **Rationale:** MCP is the agent↔tool standard; building a server (not just consuming one) is the rare signal. Most portfolios ship tools only; resources + prompts cost an hour.

### D8 — A2A depth
- **Options:** skip · minimal (agent card + one delegation path) · full
- **Choice:** minimal — extract **only the Docs Analyst** as a standalone A2A server
- **Rationale:** the Docs Analyst *is* Project 1, an independently operated system. That's the honest boundary. Applying A2A to in-process handoffs would be protocol theater.
- **Critical detail:** W3C `traceparent` propagates across the hop so remote spans join the parent trace — otherwise A2A becomes a hole in the eval.
- **Pushback:** *"Why not A2A everywhere?"* → MCP invokes a capability; A2A delegates to an independently operated agent. Only one of my agents qualifies.

---

## Domain and data

### D6 — Task domain
- **Options:** autonomous data analyst · research/literature agent · domain assistant
- **Choice:** autonomous **healthcare operations** analyst
- **Rationale:** the research agent has the *easier* multi-agent story (parallel fan-out over sub-questions) but the *impossible* eval story — open-web search has no reference trajectory and non-stationary results. The analyst domain gives executable ground truth, which is the precondition for everything this project claims.
- **Pushback:** *"Research agents show multi-agent value better."* → They do, and they'd have forced me to score with an LLM judge. I chose the domain that makes the eval defensible and then justified multi-agent empirically instead.

### D14 — Dataset
- **Options:** Synthea · CMS DE-SynPUF · NY SPARCS · MIMIC-IV · HCUP NIS/SID
- **Choice:** Synthea, plus a deterministic `messify.py` data-quality injection step
- **Rationale:** relational multi-table schema (real joins → real planning), longitudinal patient linkage (readmissions/LOS computable), operational *and* financial spines (justifies fan-out), and — decisively — no PHI, redistributable, seed-deterministic, so clone-and-run reproducibility actually holds.
- **Why not the others:** DE-SynPUF perturbs cross-file relationships, degrading readmission chains. SPARCS is a single flat table with no patient linkage. MIMIC-IV and HCUP require credentialing/DUA and can't be redistributed.
- **Stated caveat:** Synthea's population is module-generated, so epidemiological conclusions are meaningless. This project measures the agent's correctness, not clinical findings.
- **Why `messify.py`:** Synthea is unrealistically clean. Injected pathologies (duplicate rows, null discharge timestamps, inconsistent payer strings, `STOP < START`, mid-year org ID change) generate both the metrics-dictionary content and the hard eval tasks in one pass.

### Scope boundary
Operational analytics only (admissions, encounters, LOS, readmissions, payer mix, throughput). **Not clinical decision support** — enforced in the Synthesizer prompt and stated in the README.

---

## Reuse and integration

### D5 — Project 1 reuse
- **Choice:** expose Project 1's RAG as an MCP tool (`search_metric_definitions`)
- **Rationale:** coherent portfolio narrative; demonstrates composition across projects rather than disconnected demos.

### D15 — RAG integration path
- **Options:** call P1's FastAPI `/query` endpoint · in-process retrieval path
- **Choice:** in-process (`load_config → load_resources → build_retriever → retrieve`)
- **Rationale:** `/query` also runs generation — an LLM call, cost, and a key I don't need. The agent wants passages, not an answer. Retrieval-only also keeps the tool's latency and cost off the critical path.
- **Detail:** `chunk.parent_id → doc_id`; `chunk_id` and `score` passed through; retrieval metadata returned so RAGAS scores retrieval *in-trace* (nested eval).
- **Packaging:** `rag-eval` is an **optional extra**, git-tag-pinned. No absolute local paths in `pyproject.toml`. CI installs without it and runs from cassettes.

### D19 — Python version
- **Choice:** 3.12.3, matching Project 1
- **Rationale:** P1's package installs into P2's environment at Gate 1; version drift breaks the optional extra for no benefit.

---

## Reliability and context transfer

### D21 — Data movement between agents
- **Options:** pass result payloads through agent context · pass artifact references
- **Choice:** `ResultRef` — tools return a reference + schema + `row_count` + `head(5)`; full frames live in the artifact store and resolve inside the sandbox
- **Rationale:** bounds context, is the actual production pattern, and makes `context.bundle_tokens` a measurable per-step metric. Passing dataframes through an LLM context is the loudest junior tell in agentic code.

### Context-handoff strategy
No shared scratchpad (specialists receive only their subtask and input refs) · acceptance criteria travel with the subtask and are self-reported against · Pydantic validation at ingress **and** egress of every node · validation failures are recorded events routed to replan, never unhandled exceptions · provenance required on every claim · mandatory `assumptions_made` register.
- **Rationale:** the 2026 reliability consensus is that most agent failures are orchestration/context-transfer, not model failures. Each rule targets a specific mode: bloat, shape mismatch, silent corruption, silent loss.

### D9 — Agent memory
- **Options:** vector store · Mem0/Letta/Zep · none
- **Choice:** **none** in MVP. LangGraph checkpointer for durable execution.
- **Rationale:** cross-session memory adds state I'd then have to evaluate, and it corrupts trajectory determinism. The checkpointer is durable execution, *not* memory — keep the distinction sharp.
- **Trigger to revisit:** when the analyst must recall prior sessions' derived definitions.

---

## Evaluation

### D4 — Evaluation approach
- **Options:** final-answer pass/fail · trajectory-first
- **Choice:** trajectory-first with span tracing
- **Rationale:** final-answer-only misses 20–40% of failures; the failure surface is the step level.

### D18 — Reference trajectory representation
- **Options:** single golden path · partial-order constraint set
- **Choice:** constraint set — `required_tools`, `forbidden_tools`, `required_order` pairs, `min_steps`, `must_cite`
- **Rationale:** a golden sequence punishes valid alternate orderings and overfits the eval to one implementation. Constraints encode what must be true without dictating how.
- **Pushback:** *"How do you define a reference trajectory without overfitting?"* → This is the answer.

### D17 — Ground truth ownership
- **Choice:** `reference_sql` and `ground_truth` are **human-verified artifacts**. The coding agent may draft and execute candidates; the human signs off before anything becomes canonical.
- **Rationale:** if the same system writes both the analyst and its reference answers, errors are correlated and invisible — the eval measures its own assumptions.
- **Related rule:** a task is admissible only if its ground truth is fully determined by (reference SQL + metrics dictionary). Clinical inference is out of scope. This is what prevents drift toward LLM-judged answers.

### D20 — The single-agent baseline
- **Choice:** build a single ReAct agent with the same MCP tools and run it through the **same harness on the same task set**; publish side by side
- **Rationale:** converts the project's weakest interview question ("why not one agent?") into its strongest artifact. Costs ~half a day once tools and harness exist.
- **This is the highest-leverage decision in the project.**

### D10 — Observability + eval tooling
- **Options:** LangSmith · Arize Phoenix · DeepEval · combinations
- **Choice:** OTel as substrate · LangSmith (free tier, **sampled**) as viewer · DeepEval for CI metrics · RAGAS for the retrieval sub-call
- **Rationale:** the eval must not depend on a SaaS API. Spans dual-export to LangSmith (human viewing) and `runs/{run_id}/spans.jsonl` (source of truth for scoring). CI is hermetic and reproducible from a clean clone.
- **Sampling:** only `demo`/`video`/`manual` runs export to LangSmith — free-tier limits become structurally non-binding.
- **Why not Phoenix:** OTel-native means the viewer is a swappable backend. Not a decision I had to make.

### D16 — Replay architecture
- **Options:** per-component recorders (recorded sandbox, recorded retriever, recorded LLM) · intercept at seams
- **Choice:** **two seams only** — the LLM client and the MCP client
- **Rationale:** `run_sql`, `run_python`, and `search_metric_definitions` are all MCP tools, so one interceptor covers all three. Three bespoke mechanisms collapse to one `CassetteStore`.
- **Payoff:** demo-mode, CI determinism, and the trace viewer become the same system.
- **Details:** keyed on content hash; retrieval keys include `corpus_version` so editing a definition invalidates stale cassettes. A cassette miss in REPLAY mode is a **hard failure** — never fall through to live, or CI stops being hermetic.

### LLM-as-judge
Used only for claim-support and completeness. Judge model ≠ any generator model · anchored rubric, not free-form 1–10 · pairwise with both orderings and agreement required · judged over extracted claims, not raw prose · **validated against ~50 human labels with Cohen's κ reported** · nightly on a sample, never in the blocking gate.
- **Rationale:** a judge is an instrument with error. Calibrating it is the difference between "I used an LLM judge" and "I measured my judge."

### CI gate
Frozen 12–15 task smoke set, cassette-replayed. **Regression-gated against a committed baseline with a tolerance band**, absolute floors as backstop. Live nondeterminism handled with temperature 0, n=3, tolerance band — documented openly.
- **Pushback:** *"Isn't an LLM CI gate flaky?"* → Mine isn't, because it replays and scores deterministically. Live runs are nightly.

---

## Execution and cost

### D11 — Sandbox
- **Options:** E2B · Docker · both
- **Choice:** `SandboxBackend` protocol with **`LocalDockerSandbox` implemented only**
- **Rationale:** free-tier path; implementing an E2B adapter I never execute is dead code. The protocol makes it a swap-in.
- **Hardening:** `--network none`, read-only rootfs + tmpfs, memory/CPU caps, non-root, default seccomp, wall-clock kill, read-only artifact mounts.
- **Trigger for E2B:** multi-tenant untrusted execution I don't operate.

### D12 — Models per agent
- **Choice:** tiered — strong for Planner/Synthesizer, mid for SQL/Quant, cheap for Docs/Validator. IDs in `config/models.yaml`, resolved ID recorded in every run's `meta.json`.
- **Rationale:** plan quality dominates outcome; retrieval and validation don't need frontier reasoning.
- **Escalation:** model tier is an **eval sweep axis** (Gate 3) producing a published cost/quality frontier. The cost question gets a measured answer, not an opinion.

---

## Scope and delivery

### D13 — MVP cut line
**Gate 0** walking skeleton → **Gate 1 MVP complete** (a full portfolio flagship on its own: 5 tools, 5 nodes, typed contracts, recovery, 8 metrics × 25 tasks, baseline arm, demo link, video, green CI) → **Gate 2** A2A → **Gate 3** model sweep → **Gate 4** HITL.
- **Rule:** each gate ends with README written and a run committed. Never start gate N+1 until gate N is defensible.
- **Cut policy under time pressure:** cut task-set breadth and agent capability breadth **before** harness depth. 25 tasks × 8 metrics + a baseline beats 60 tasks × 3 metrics.

### Presentation tier
Demo-mode + video, not a product. Public Streamlit link over 5 committed `runs/` directories (including one failure-and-recovery run and one baseline comparison), 75s video, README leading with the eval table.
- **Rationale:** P2 is the hardest project to make product-shaped (latency, per-run cost, sandboxing) and its differentiator is the eval spine. Product polish belongs to P4.

---

## Explicitly not built (with triggers)

| Not built | Trigger |
|---|---|
| Cross-session agent memory | analyst must recall prior sessions' derived definitions |
| Full A2A layer | >1 agent independently operated |
| Network topology | never here — traces become unattributable |
| Critic Agent | deterministic validator node suffices |
| OAuth 2.1 on MCP | multi-tenant or external consumers |
| E2B sandbox | multi-tenant untrusted execution I don't operate |
| Polished consumer UI | P4 carries product weight |
| Custom trace viewer | LangSmith + `spans.jsonl` renderer suffices |
| MIMIC-IV / HCUP real data | when redistribution isn't required |

*Naming the trigger is the difference between "I skipped it" and "I scoped it."*

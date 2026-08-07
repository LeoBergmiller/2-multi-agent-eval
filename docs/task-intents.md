# Seed task intents (Gate 1a step 3.5)

**Draft. Prose only — no SQL, no numbers, no ground truth.** §1's ordering constraint governs *ground truth*, which requires the warehouse; it does not govern intent. These exist so step 4 can author the metrics dictionary task-intent-first rather than exhaustively, and step 7 turns them into `evals/tasks/*.yaml` with human-verified numbers.

They are provisional. Step 7 may reword a question once real row counts are known; what step 4 needs is the *shape* of each ambiguity, not the final wording.

**Admissibility (§2):** every intent below must be fully determined by reference SQL plus the metrics dictionary. Where a question is currently ambiguous, that is not a defect — it is the trap, and the dictionary entry named under it is what resolves it. A question that stayed ambiguous *after* the dictionary would be inadmissible.

---

## 1 — Multi-table join, no definitional ambiguity

**Question.** Which organizations had the most inpatient encounters in a given year, with the organization's name and city rather than its ID?

**Ambiguity.** None, deliberately. `ENCOUNTERCLASS` is named explicitly, the year is explicit, and no definition-laden term appears. This is the control: it establishes that the system can do ordinary multi-hop analytic work, so a failure elsewhere is attributable to the *definition* rather than to basic competence.

**Plausible-but-wrong.** Nothing definitional. The available error is mechanical — grouping by `ORGANIZATION` rather than by organization identity, which the step-3 merged-organization injection punishes by splitting one hospital across two IDs. That makes this quietly less trivial than it looks, and is why it sits first rather than being dropped.

**Exercises.** `describe_schema`, `describe_table`, `run_sql`. Metrics: `task_success`, `tool_call_accuracy`, `trajectory_efficiency` (a clean floor for step count).

---

## 2 — Wrong without the definition lookup

**Question.** How many admissions were there last year?

**Ambiguity.** What counts as an admission. `encounters` mixes wellness, ambulatory, outpatient, emergency, urgentcare, inpatient, home, hospice, snf and virtual in one relation, and the non-inpatient classes outnumber inpatient by roughly an order of magnitude.

**Plausible-but-wrong.** A competent analyst who does not look up the definition counts every encounter row, and is wrong by more than 40×. The answer is not subtly off — it is confidently, enormously wrong, and it looks like a perfectly good number. This is the highest-value trap in the set because the naive answer requires no mistake in SQL at all.

Secondary trap, from step 3: still-admitted patients have a null `STOP`, so an analyst who joins on discharge or filters `STOP IS NOT NULL` drops them and undercounts.

**Dictionary entry.** `admission` — which `ENCOUNTERCLASS` values count, that emergency encounters are not admissions unless followed by a separate inpatient row, that observation stays are outpatient, that still-admitted encounters count, and that the unit is encounters rather than patients.

**Exercises.** `search_metric_definitions` → `run_sql`, `required_order`, `must_cite`. Metrics: `task_success`, `tool_call_accuracy`, and RAGAS on the retrieval sub-call.

---

## 3 — Requires computation over a result set

**Question.** What is the distribution of inpatient length of stay — median, 90th percentile, and the share of stays exceeding a week?

**Ambiguity.** How length of stay is counted, and what to do with stays that cannot be measured.

**Plausible-but-wrong.** Subtracting timestamps and reporting elapsed days. That gets same-day discharges wrong (they consume no bed-night but are not zero under an hours-based reading), and it silently includes the step-3 reversed stays, whose negative durations drag the mean down without erroring. Reporting only a mean is also wrong-ish on its own terms: length of stay is right-skewed, so the mean overstates the typical stay — which is why the question asks for a distribution.

**Dictionary entries.** `length_of_stay` (midnights, same-day = 0, outlier truncation, still-admitted excluded) and the `reversed_stays` data-quality rule (invalid, excluded rather than clamped).

**Exercises.** `run_sql` → `run_python`, `ResultRef` passing. This is the **first task that resolves a `ResultRef` to its underlying frame**, so it is where the RECORD-mode test named in §3 is due — replay covers the cassetted `ExecResult`, not the artifact behind the ref. Metrics: `task_success`, `context_transfer_integrity`.

---

## 4 — Needs both docs and quant

**Question.** What was the 30-day readmission rate for inpatient discharges last year, and how did it differ between the two busiest organizations?

**Ambiguity.** Nearly every clause. Which admissions are eligible; whether the window runs from discharge or admission; whether a readmission at a different facility counts; whether planned readmissions count; how a patient readmitted twice is counted; and what to do with discharges too near the end of the period to have an observable window.

**Plausible-but-wrong.** Anchoring the window on admission rather than discharge. This is the subtle one: it produces a *lower* rate, biased non-uniformly (longer index stays lose more window), and the number looks entirely reasonable. Nothing about the output signals the error. A second plausible-but-wrong is restricting to same-facility readmissions, which undercounts and is a genuinely different metric.

**Dictionary entry.** `readmission_30day`, plus the attributed-organization rule for the per-facility split.

**Exercises.** Genuine fan-out — the docs lookup and the SQL work are separate `SubTask`s with a `required_order` dependency, then computation over the result. Bounded handoffs. Metrics: `context_transfer_integrity` (does the SQL Analyst re-derive what the Docs Analyst already established?), `tool_call_accuracy`, `trajectory_efficiency`.

---

## 5 — Answerable in SQL alone (over-tooling trap)

**Question.** What share of inpatient encounters last year were covered by each payer?

**Ambiguity.** The payer-mix denominator — encounters, distinct patients, or member-months — which changes the answer materially. But the *computation*, once the denominator is fixed, is a single aggregate.

**Plausible-but-wrong.** Two ways. Definitionally, choosing distinct patients when the dictionary specifies encounters. Mechanically, grouping by payer name without normalising it — the step-3 casing-and-whitespace injection splits three payers into separate buckets, so the shares are wrong and still sum to one, which is exactly why nothing looks broken.

**The trap being measured, though, is over-tooling.** `forbidden_tools: [run_python]`. Everything here is expressible in SQL, and reaching for the sandbox to compute percentages is a real failure mode for an agent with a Python tool available — it burns steps and cost for nothing. This task exists to measure restraint, which is why its definitional content is kept modest.

**Dictionary entries.** `payer_mix_denominator`, and the `payer_name_normalisation` data-quality rule.

**Exercises.** `search_metric_definitions` → `run_sql`, `forbidden_tools`. Metrics: `tool_call_accuracy` (the forbidden-set half, which nothing else in the set exercises), `trajectory_efficiency`, `cost_usd`.

---

## 6 — Turns on a `messify.py` pathology

**Question.** How many inpatient encounters started in 2023?

**This is the Gate 0 task, and step 3 changed what it is.** It was admissible at Gate 0 precisely because it was definitionally unambiguous — that was the point of naming `ENCOUNTERCLASS` explicitly. The duplicate-encounter injection has made it ambiguous: the feed now double-posts inpatient rows, so "how many encounters" has two defensible readings — rows, or distinct encounters — and two different numbers.

Under §2 it is **not admissible in its current form**: its ground truth is no longer determined by reference SQL alone. It does not get retired, though. An ordinary question that a data-quality defect has quietly made ambiguous is a better trap than one designed to be tricky, because that is how this failure actually presents in a real warehouse. It becomes the messify-pathology slot.

**Plausible-but-wrong.** `count(*)`. The duplicates are byte-identical rows with the same `Id` and no primary key to object, so nothing in the schema, the result shape, or the query plan hints that anything is wrong. The answer is plausible, stable across re-runs, and too high.

**Dictionary entry.** A dedupe rule — that encounters are counted distinctly by `Id` because the source feed can double-post, and that a duplicate is not a second encounter. This becomes one of the ~10 load-bearing entries at step 4.

**Note for step 7.** Its ground truth is currently `draft` and has now moved twice (fixture → Synthea, then Synthea → messified). Sign it once, after the dictionary exists and the warehouse is final — signing an intermediate number devalues the protocol.

**Exercises.** `search_metric_definitions` → `run_sql`, data-quality reasoning. Metrics: `task_success`, `must_cite`.

---

## 7 — Two similar dictionary entries, one correct

**Question.** What was the readmission rate for inpatient discharges last year, counting only readmissions back to the same organization?

**Ambiguity.** The question is *deliberately unambiguous to a reader who retrieves the right entry* — it names the same-facility restriction explicitly. The difficulty is entirely in retrieval: the corpus contains `readmission_30day` (30-day, any-facility, all-cause) and near-miss distractors including same-facility-only and a 90-day variant. All three are topically identical, lexically near-identical, and differ by a few words that change the answer.

**Plausible-but-wrong.** Retrieving the default 30-day any-facility entry and applying it. The result is a *higher* rate computed correctly against the wrong definition — well-formed SQL, sound arithmetic, cited evidence, wrong answer. An agent that cites the entry it retrieved will look more trustworthy here, not less, which is the point.

**Dictionary entries.** `readmission_30day` plus its distractors. These distractors are why the corpus needs ~15–20 near-misses rather than ten clean documents: with ten, retrieval is trivially perfect and RAGAS measures nothing.

**Exercises.** Distractor-sensitive retrieval. Metrics: **RAGAS context precision/recall** on the sub-call — the task where retrieval quality, not SQL, decides the outcome — plus `must_cite` checking that the *cited* entry is the correct one rather than merely a retrieved one.

---

## Coverage check

| Task | Primary trap | New tool/mechanism exercised |
|---|---|---|
| 1 | none (control) | `describe_schema`, `describe_table` |
| 2 | definitional, order-of-magnitude | `required_order`, `must_cite` |
| 3 | definitional + data quality | `run_python`, `ResultRef` resolution |
| 4 | definitional, subtle and non-uniform | fan-out, `context_transfer_integrity` |
| 5 | over-tooling | `forbidden_tools` |
| 6 | data quality (duplicates) | dedupe reasoning |
| 7 | retrieval | RAGAS, distractor sensitivity |

Every one of the five `messify.py` pathologies is load-bearing for at least one task: duplicates (6), open stays (2), reversed stays (3), payer casing (5), merged organization (1). None is decorative — an injection that silently stopped landing would take a task's trap with it, which is why `messify.verify` asserts its counts.

**Not covered here, by design:** failure injection and recovery. `recovery_rate` needs the replan edge and the injection machinery, both of which are 1b. That task gets authored there, not retrofitted into this set.

**Dictionary entries implied by these seven** (the load-bearing set for step 4): `admission`, `length_of_stay`, `readmission_30day`, `payer_mix_denominator`, `attributed_organization`, plus one per pathology — `encounter_deduplication`, `open_stays`, `reversed_stays`, `payer_name_normalisation`, `organization_identity`. That is ten, arrived at from task intent rather than by aiming for a round number.

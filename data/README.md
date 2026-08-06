# Data

## Gate 0: fixture warehouse (temporary)

`fixtures/` holds a small, hand-authored CSV warehouse — three tables, a few hundred rows —
that exists only so `run_sql` has a real DuckDB to hit before Synthea ingest is built. It is
committed on purpose: `make demo` must work from a clean clone with no network.

Column names are verbatim from Synthea's exporter source — `CSVConstants.java`, the class
that literally writes the header lines — verified 2026-08-03:
<https://github.com/synthetichealth/synthea/blob/master/src/main/java/org/mitre/synthea/export/CSVConstants.java>

**Use the source, not the wiki.** The [CSV data dictionary wiki page][wiki] renders columns in
TitleCase (`Id, BirthDate, …`); real Synthea output is `Id` followed by UPPERCASE
(`Id,BIRTHDATE,…`, `Id,START,STOP,…`). DuckDB identifiers are case-insensitive so SQL works
either way, but the committed headers match real output so the Gate 1 swap is byte-clean.

[wiki]: https://github.com/synthetichealth/synthea/wiki/CSV-File-Data-Dictionary

That is the whole point of the fixture's design. **Gate 1 must be a data swap, not a rewrite** —
if the fixture invented its own schema, replacing it would also mean rewriting the SQL Analyst
prompt, the `describe_table` output shape, and the eval task's `reference_sql`.

Tables (Gate 0 subset of architecture.md §2's twelve):

| Table | Rows | Notes |
|---|---|---|
| `patients` | 50 | |
| `encounters` | 200 | Real `ENCOUNTERCLASS` values; **6 rows have a null `STOP`** |
| `organizations` | 5 | |

Encounter composition, chosen so the Gate 0 task has a checkable answer with live traps:

| `ENCOUNTERCLASS` | Year | Rows | |
|---|---|---|---|
| `inpatient` | 2023 | 37 | **the answer** (6 of them still admitted) |
| `inpatient` | 2022 | 18 | year distractor |
| `ambulatory` | 2023 | 55 | |
| `wellness` | 2023 | 44 | the classic "admission" trap class |
| `emergency` | 2023 | 28 | |
| `urgentcare` | 2023 | 18 | |

So "how many inpatient encounters started in 2023?" is **37**. A query that drops
still-admitted patients returns 31; one that ignores `ENCOUNTERCLASS` returns 182.

The null `STOP` values represent still-admitted patients. They are deliberate: a query that
assumes every encounter has been discharged (a stray `STOP IS NOT NULL`, or a join that drops
open encounters) returns a wrong answer. They make the Gate 0 eval task non-trivial without
making its *definition* ambiguous — which matters because the metrics dictionary does not exist
until Gate 1, so Gate 0 ground truth must be determined by reference SQL alone
(architecture.md §2, task admissibility rule).

### TODO — DELETE AT GATE 1

When Synthea ingest lands (`make data` generating from a fixed seed) and `messify.py` injects
the real data-quality pathologies:

1. Delete `data/fixtures/` entirely.
2. Delete `data/load_fixtures.py`.
3. Point `make data` at the Synthea ingest path.
4. Re-verify the Gate 0 eval task's `ground_truth` against the real warehouse — the number
   **will** change, and it needs human sign-off again (architecture.md §13, D17).
5. Delete this section.

The fixture is scaffolding. It should not survive Gate 1.

## `metrics_dictionary/` — the RAG corpus (committed)

Authored Markdown, read by `make index` through Project 1's `local` corpus source and
hashed into `corpus_version`, which is part of the retrieval cassette key
(architecture.md §6.2). Editing a definition therefore **invalidates stale cassettes
instead of silently replaying a retrieval the edit was meant to correct**.

`doc_id` is the filename stem, so `readmission_30day.md` is cited as
`docs://metrics/readmission_30day`. Stems must be unique across subdirectories.

**Nothing but corpus documents belongs in that directory.** Every `.md` and `.txt`
under it is ingested as a document — which is why this section lives here rather than
in a `metrics_dictionary/README.md` that would index itself as a metric definition.

### Status: provisional (Gate 1a step 1)

Three entries — `admission`, `length_of_stay`, `readmission_30day` — exist so the
Project 1 spike has something real to retrieve over. They are the first of the
load-bearing set, not the finished corpus.

**Step 4 authors the real dictionary:** ~10 load-bearing entries (one per seed-task
definition, plus one per `messify.py` pathology) and ~15–20 near-miss distractors. The
distractors are the point — with three documents retrieval is trivially perfect and
RAGAS measures nothing.

Cassettes recorded against this provisional corpus are **disposable by design**. When
step 4 lands, `corpus_version` changes and invalidates every one of them. That is the
mechanism working. Re-record after step 4; do not carry them forward.

Current `corpus_version`: `c24dc219e69d4e63` (3 documents, 3 chunks).

## Gitignored paths

`synthea/`, `warehouse.duckdb`, and `index/` are generated, never committed.
`metrics_dictionary/` is **not** generated — it is authored source and is committed.

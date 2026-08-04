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

## Gitignored paths

`synthea/`, `warehouse.duckdb`, and `index/` are generated, never committed.

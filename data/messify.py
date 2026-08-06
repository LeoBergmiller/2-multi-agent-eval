"""Inject real hospital-warehouse pathologies into the Synthea warehouse.

    python data/messify.py [--warehouse PATH]

Synthea is unrealistically clean: every encounter is closed, every payer name is
spelled one way, no row is double-posted. Real operational warehouses are not, and an
analyst agent that has never met a duplicated feed row has not been evaluated on the
thing that actually goes wrong.

**These injections are eval infrastructure, not decoration.** Seed tasks 2 and 6 depend
on them directly — in particular `still_admitted` is 0 in raw Synthea output, so the
null-`STOP` trap that the Gate 0 fixture carried by hand exists *only* because this
module puts it there. If an injection silently no-ops, those tasks quietly stop testing
what they claim to test while still passing.

So every injection is **counted and asserted after the fact** (`verify`), not assumed
from the fact that the UPDATE ran. That is the seventh silent-failure lesson applied:
verify the outcome, not the argument.

Deterministic: a fixed seed, and row selection ordered by primary key so the same rows
are chosen on every machine. Runs after ingest, and re-running `make data` re-runs it.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent
WAREHOUSE = DATA_DIR / "warehouse.duckdb"
#: Committed alongside the code: the counts reference SQL has to account for.
SUMMARY_FILE = DATA_DIR / "messify_summary.json"

#: Fixed, and mixed into every ordering so selection is reproducible across machines
#: without depending on DuckDB's scan order.
SEED = 20260806

# Injection sizes. Deliberately small relative to 137k encounters: the pathologies must
# be findable by a careful analyst and missable by a careless one. Large enough to be
# statistically visible, small enough that ignoring them is a *subtle* error.
N_DUPLICATE_ENCOUNTERS = 220
N_OPEN_STAYS = 140
N_REVERSED_STAYS = 35
N_PAYER_CASING = 3
MERGED_ORG_SUFFIX = "-OLD"

#: Date boundaries the injections key on. Named rather than buried in the SQL: they tie
#: the pathologies to particular periods, so reference SQL and any future re-seed have
#: to be able to see them.
OPEN_STAYS_FROM = "2025-01-01"  # still-admitted patients are recent by definition
REVERSED_STAYS_BEFORE = "2025-01-01"
ORG_MERGER_DATE = "2025-07-01"  # encounters before this keep the old organization id


@dataclass(frozen=True)
class Injection:
    """One pathology, its intended count, and what actually landed."""

    name: str
    description: str
    intended: int
    observed: int

    @property
    def ok(self) -> bool:
        return self.intended == self.observed


def _scalar(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    row = con.execute(sql).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def inject_duplicate_encounters(con: duckdb.DuckDBPyConnection) -> Injection:
    """A double-posted feed: the same encounter row delivered twice.

    Same `Id`. `encounters` has no primary key in Synthea's export, so the duplicate is
    genuinely indistinguishable from the original — which is the point. `count(*)`
    overcounts; `count(DISTINCT Id)` does not.
    """
    con.execute(
        f"""
        CREATE TEMP TABLE _dupes AS
        SELECT * FROM encounters
        WHERE ENCOUNTERCLASS = 'inpatient'
        ORDER BY hash(Id || {SEED})
        LIMIT {N_DUPLICATE_ENCOUNTERS}
        """
    )
    con.execute("INSERT INTO encounters SELECT * FROM _dupes")
    observed = _scalar(
        con,
        "SELECT count(*) FROM ("
        "  SELECT Id FROM encounters GROUP BY Id HAVING count(*) > 1"
        ")",
    )
    return Injection(
        "duplicate_encounters",
        "inpatient encounter rows double-posted; count(*) overcounts",
        N_DUPLICATE_ENCOUNTERS,
        observed,
    )


def inject_open_stays(con: duckdb.DuckDBPyConnection) -> Injection:
    """Still-admitted patients: a real NULL in a real TIMESTAMP column.

    Raw Synthea closes every encounter, so this pathology is entirely manufactured
    here. A query that assumes every stay ended (a stray `STOP IS NOT NULL`, or an
    inner join on discharge) silently drops these and undercounts admissions.
    """
    con.execute(
        f"""
        UPDATE encounters SET STOP = NULL
        WHERE Id IN (
            SELECT Id FROM encounters
            WHERE ENCOUNTERCLASS = 'inpatient' AND STOP IS NOT NULL
              AND START >= TIMESTAMP '{OPEN_STAYS_FROM}'
            ORDER BY hash(Id || {SEED + 1})
            LIMIT {N_OPEN_STAYS}
        )
        """
    )
    observed = _scalar(con, "SELECT count(*) FROM encounters WHERE STOP IS NULL")
    return Injection(
        "open_stays",
        "inpatient encounters with NULL STOP (still admitted)",
        N_OPEN_STAYS,
        observed,
    )


def inject_reversed_stays(con: duckdb.DuckDBPyConnection) -> Injection:
    """`STOP < START`: a data-quality artifact, not a real same-day stay.

    Length-of-stay arithmetic over these produces negative durations, which quietly
    drag an average down instead of erroring.
    """
    con.execute(
        f"""
        UPDATE encounters SET STOP = START - INTERVAL 2 DAY
        WHERE Id IN (
            SELECT Id FROM encounters
            WHERE ENCOUNTERCLASS = 'inpatient' AND STOP IS NOT NULL
              AND START <  TIMESTAMP '{REVERSED_STAYS_BEFORE}'
            ORDER BY hash(Id || {SEED + 2})
            LIMIT {N_REVERSED_STAYS}
        )
        """
    )
    observed = _scalar(con, "SELECT count(*) FROM encounters WHERE STOP < START")
    return Injection(
        "reversed_stays",
        "encounters with STOP < START (invalid, excluded not clamped)",
        N_REVERSED_STAYS,
        observed,
    )


def inject_payer_casing(con: duckdb.DuckDBPyConnection) -> Injection:
    """Inconsistent casing and trailing whitespace on payer names.

    `GROUP BY NAME` then splits one payer across several rows. DuckDB's string
    comparison is case-SENSITIVE (unlike its identifiers), so this is a real split and
    not a cosmetic one — payer mix computed naively is wrong and looks fine.
    """
    con.execute(
        f"""
        UPDATE payers SET NAME = upper(NAME) || '  '
        WHERE Id IN (
            SELECT Id FROM payers
            WHERE NAME IS NOT NULL AND NAME <> ''
            ORDER BY hash(Id || {SEED + 3})
            LIMIT {N_PAYER_CASING}
        )
        """
    )
    # Trailing whitespace only. An earlier version also counted `NAME = upper(NAME)`
    # and observed 4 rather than 3, because Synthea already ships an all-caps payer
    # name — the check was measuring pre-existing state instead of this injection.
    observed = _scalar(con, "SELECT count(*) FROM payers WHERE NAME <> rtrim(NAME)")
    return Injection(
        "payer_casing",
        "payer names with uppercase + trailing whitespace; naive GROUP BY splits them",
        N_PAYER_CASING,
        observed,
    )


def inject_merged_organization(con: duckdb.DuckDBPyConnection) -> Injection:
    """One organization that changed its ID mid-year.

    The busiest org keeps its old ID on encounters before the cutover and gains a new
    one after, with both rows present in `organizations` under the same NAME. Grouping
    by `ORGANIZATION` splits one hospital in two; grouping by NAME does not.
    """
    row = con.execute(
        """
        SELECT e.ORGANIZATION, o.NAME
        FROM encounters e JOIN organizations o ON o.Id = e.ORGANIZATION
        WHERE e.ENCOUNTERCLASS = 'inpatient'
        GROUP BY 1, 2 ORDER BY count(*) DESC, e.ORGANIZATION LIMIT 1
        """
    ).fetchone()
    if row is None:
        return Injection("merged_organization", "no organization found", 1, 0)
    org_id, name = row[0], row[1]
    old_id = f"{org_id}{MERGED_ORG_SUFFIX}"

    con.execute(
        "INSERT INTO organizations "
        "SELECT ?, NAME, ADDRESS, CITY, STATE, ZIP, LAT, LON, PHONE, REVENUE, "
        "UTILIZATION FROM organizations WHERE Id = ?",
        [old_id, org_id],
    )
    con.execute(
        "UPDATE encounters SET ORGANIZATION = ? "
        "WHERE ORGANIZATION = ? AND START < CAST(? AS TIMESTAMP)",
        [old_id, org_id, ORG_MERGER_DATE],
    )
    # Count the row this injection created. An earlier version counted organizations
    # sharing a NAME and observed 52: Synthea already reuses names across sites, so
    # that measured the corpus rather than the injection.
    observed = _scalar(
        con,
        f"SELECT count(*) FROM organizations WHERE Id LIKE '%{MERGED_ORG_SUFFIX}'",
    )
    logger.info("  merged org %s -> %s (%s)", org_id, old_id, name)
    return Injection(
        "merged_organization",
        f"organization {name} changed ID mid-2025; grouping by ID splits it",
        1,
        observed,
    )


INJECTIONS = (
    inject_duplicate_encounters,
    inject_open_stays,
    inject_reversed_stays,
    inject_payer_casing,
    inject_merged_organization,
)


def verify(results: list[Injection]) -> None:
    """Assert every pathology actually landed.

    The whole reason this function exists: an UPDATE that matches zero rows is not an
    error in SQL. A filter that silently stopped selecting rows — a changed date
    boundary, a re-seeded population, an encounter class that no longer appears — would
    leave the warehouse clean, the script exiting 0, and seed tasks 2 and 6 passing
    while testing nothing. Trusting the write is exactly the mistake `-r` taught.
    """
    failed = [r for r in results if not r.ok]
    if failed:
        detail = "\n".join(
            f"  {r.name}: intended {r.intended}, observed {r.observed}" for r in failed
        )
        raise ValueError(
            "Injection count mismatch — the warehouse is NOT in the state the eval "
            f"tasks assume:\n{detail}\n"
            "An injection that silently no-ops leaves seed tasks passing while "
            "testing nothing. Fix the injection or the expected count; do not "
            "proceed with a clean warehouse."
        )


def messify(warehouse: Path = WAREHOUSE) -> list[Injection]:
    if not warehouse.is_file():
        raise FileNotFoundError(
            f"Warehouse not found at {warehouse}. Run `make data` first."
        )

    con = duckdb.connect(str(warehouse))
    try:
        already = _scalar(con, "SELECT count(*) FROM encounters WHERE STOP IS NULL")
        if already:
            raise ValueError(
                f"{warehouse} already has {already} open stays, so messify has "
                "probably already run. It is NOT idempotent — injecting twice would "
                "double the duplicates and invalidate every count. Rebuild with "
                "`make data`."
            )

        logger.info("injecting pathologies (seed=%s)", SEED)
        results = [injection(con) for injection in INJECTIONS]
        verify(results)
    finally:
        con.close()

    for r in results:
        logger.info("  %-22s %6d  %s", r.name, r.observed, r.description)

    SUMMARY_FILE.write_text(
        json.dumps(
            {
                "seed": SEED,
                "injections": [
                    {"name": r.name, "count": r.observed, "description": r.description}
                    for r in results
                ],
            },
            indent=2,
        )
        + "\n"
    )
    logger.info("wrote %s", SUMMARY_FILE.name)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warehouse", type=Path, default=WAREHOUSE)
    args = parser.parse_args()
    try:
        messify(args.warehouse)
    except (OSError, ValueError, duckdb.Error):
        logger.exception("messify failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

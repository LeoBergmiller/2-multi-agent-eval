"""Build `data/warehouse.duckdb` from the committed CSV fixtures.

GATE 0 ONLY. This whole module is deleted when Synthea ingest lands — see the
TODO in data/README.md.

Typing is deliberate: DuckDB's CSV sniffer would infer `STOP` as VARCHAR because
the column contains empty strings, and every downstream date comparison would
then silently compare strings. Columns are declared explicitly so a still-
admitted patient is a real SQL NULL in a real TIMESTAMP column.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent
FIXTURES = DATA_DIR / "fixtures"
WAREHOUSE = DATA_DIR / "warehouse.duckdb"

# Column types for the three Gate 0 tables. Names and order are verbatim from
# Synthea's CSVConstants.java (verified 2026-08-03), so replacing these CSVs
# with real Synthea output is a data swap and nothing more.
SCHEMAS: dict[str, dict[str, str]] = {
    "patients": {
        "Id": "VARCHAR",
        "BIRTHDATE": "DATE",
        "DEATHDATE": "DATE",
        "SSN": "VARCHAR",
        "DRIVERS": "VARCHAR",
        "PASSPORT": "VARCHAR",
        "PREFIX": "VARCHAR",
        "FIRST": "VARCHAR",
        "MIDDLE": "VARCHAR",
        "LAST": "VARCHAR",
        "SUFFIX": "VARCHAR",
        "MAIDEN": "VARCHAR",
        "MARITAL": "VARCHAR",
        "RACE": "VARCHAR",
        "ETHNICITY": "VARCHAR",
        "GENDER": "VARCHAR",
        "BIRTHPLACE": "VARCHAR",
        "ADDRESS": "VARCHAR",
        "CITY": "VARCHAR",
        "STATE": "VARCHAR",
        "COUNTY": "VARCHAR",
        "FIPS": "VARCHAR",
        "ZIP": "VARCHAR",
        "LAT": "DOUBLE",
        "LON": "DOUBLE",
        "HEALTHCARE_EXPENSES": "DOUBLE",
        "HEALTHCARE_COVERAGE": "DOUBLE",
        "INCOME": "BIGINT",
    },
    "encounters": {
        "Id": "VARCHAR",
        "START": "TIMESTAMP",
        "STOP": "TIMESTAMP",
        "PATIENT": "VARCHAR",
        "ORGANIZATION": "VARCHAR",
        "PROVIDER": "VARCHAR",
        "PAYER": "VARCHAR",
        "ENCOUNTERCLASS": "VARCHAR",
        "CODE": "VARCHAR",
        "DESCRIPTION": "VARCHAR",
        "BASE_ENCOUNTER_COST": "DOUBLE",
        "TOTAL_CLAIM_COST": "DOUBLE",
        "PAYER_COVERAGE": "DOUBLE",
        "REASONCODE": "VARCHAR",
        "REASONDESCRIPTION": "VARCHAR",
    },
    "organizations": {
        "Id": "VARCHAR",
        "NAME": "VARCHAR",
        "ADDRESS": "VARCHAR",
        "CITY": "VARCHAR",
        "STATE": "VARCHAR",
        "ZIP": "VARCHAR",
        "LAT": "DOUBLE",
        "LON": "DOUBLE",
        "PHONE": "VARCHAR",
        "REVENUE": "DOUBLE",
        "UTILIZATION": "BIGINT",
    },
}


def build(warehouse: Path = WAREHOUSE, fixtures: Path = FIXTURES) -> None:
    missing = [t for t in SCHEMAS if not (fixtures / f"{t}.csv").is_file()]
    if missing:
        raise FileNotFoundError(
            f"Missing fixture CSVs for {missing} in {fixtures}. "
            "The fixtures are committed; a clean clone should already have them."
        )

    # Rebuild from scratch: an incrementally-mutated warehouse is not
    # reproducible, and reproducibility is priority 1 (§0).
    warehouse.unlink(missing_ok=True)

    con = duckdb.connect(str(warehouse))
    try:
        for table, columns in SCHEMAS.items():
            csv_path = fixtures / f"{table}.csv"
            types = ", ".join(f"'{c}': '{t}'" for c, t in columns.items())
            con.execute(
                # Table names come from SCHEMAS above, never from input.
                f"CREATE TABLE {table} AS "
                f"SELECT * FROM read_csv('{csv_path}', header=true, "
                f"columns={{{types}}}, nullstr='')"
            )
            count = con.execute(f"SELECT count(*) FROM {table}").fetchone()
            logger.info("%-14s %4d rows", table, count[0] if count else -1)

        open_encounters = con.execute(
            "SELECT count(*) FROM encounters WHERE STOP IS NULL"
        ).fetchone()
        logger.info(
            "still-admitted encounters (STOP IS NULL): %d",
            open_encounters[0] if open_encounters else -1,
        )
    finally:
        con.close()

    logger.info("wrote %s", warehouse)


def main() -> int:
    try:
        build()
    except (FileNotFoundError, duckdb.Error):
        logger.exception("fixture load failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

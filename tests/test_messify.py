"""`messify.py` — determinism, and that its injections actually land.

architecture.md §7.7 names "messify.py is deterministic under a fixed seed" as one of
the few load-bearing integration tests. It earns that: the injected pathologies are the
substance of seed tasks 2 and 6, and `still_admitted` is 0 in raw Synthea, so the
null-`STOP` trap exists *only* because this module creates it.

These build their own miniature warehouse rather than using the real one, which is
gitignored and takes a JDK plus minutes to produce.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_messify():  # type: ignore[no-untyped-def]
    """Import `data/messify.py` by path — `data/` is deliberately not a package."""
    spec = importlib.util.spec_from_file_location(
        "messify", REPO_ROOT / "data" / "messify.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["messify"] = module
    spec.loader.exec_module(module)
    return module


messify_mod = _load_messify()


@pytest.fixture
def clean_warehouse(tmp_path: Path) -> Path:
    """A Synthea-shaped warehouse with no pathologies: every stay closed."""
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE encounters (Id VARCHAR, START TIMESTAMP, STOP TIMESTAMP,"
            " PATIENT VARCHAR, ORGANIZATION VARCHAR, ENCOUNTERCLASS VARCHAR)"
        )
        con.execute(
            "CREATE TABLE organizations (Id VARCHAR, NAME VARCHAR, ADDRESS VARCHAR,"
            " CITY VARCHAR, STATE VARCHAR, ZIP VARCHAR, LAT DOUBLE, LON DOUBLE,"
            " PHONE VARCHAR, REVENUE DOUBLE, UTILIZATION BIGINT)"
        )
        con.execute("CREATE TABLE payers (Id VARCHAR, NAME VARCHAR)")
        con.execute(
            "INSERT INTO organizations SELECT 'org' || i, 'Hospital ' || i,"
            " 'a', 'Boston', 'MA', '02101', 0.0, 0.0, 'p', 0.0, 0 FROM range(3) t(i)"
        )
        con.execute(
            "INSERT INTO payers SELECT 'pay' || i, 'Payer ' || i FROM range(6) t(i)"
        )
        # Must straddle messify's date boundaries: open stays are taken from on or
        # after OPEN_STAYS_FROM and reversed stays from before it, so a fixture on one
        # side only would silently inject nothing.
        con.execute(
            "INSERT INTO encounters "
            "SELECT 'old' || i, TIMESTAMP '2024-01-01' + INTERVAL (i) HOUR,"
            "  TIMESTAMP '2024-01-03' + INTERVAL (i) HOUR,"
            "  'p' || (i % 40), 'org' || (i % 3), 'inpatient' "
            "FROM range(1000) t(i)"
        )
        con.execute(
            "INSERT INTO encounters "
            "SELECT 'new' || i, TIMESTAMP '2025-08-01' + INTERVAL (i) HOUR,"
            "  TIMESTAMP '2025-08-03' + INTERVAL (i) HOUR,"
            "  'p' || (i % 40), 'org' || (i % 3), 'inpatient' "
            "FROM range(1000) t(i)"
        )
    finally:
        con.close()
    return path


def _counts(path: Path) -> dict[str, int]:
    con = duckdb.connect(str(path), read_only=True)
    try:
        return {
            "open": con.execute(
                "SELECT count(*) FROM encounters WHERE STOP IS NULL"
            ).fetchone()[0],
            "reversed": con.execute(
                "SELECT count(*) FROM encounters WHERE STOP < START"
            ).fetchone()[0],
            "dupes": con.execute(
                "SELECT count(*) FROM (SELECT Id FROM encounters "
                "GROUP BY Id HAVING count(*) > 1)"
            ).fetchone()[0],
            "padded_payers": con.execute(
                "SELECT count(*) FROM payers WHERE NAME <> rtrim(NAME)"
            ).fetchone()[0],
            "old_orgs": con.execute(
                "SELECT count(*) FROM organizations WHERE Id LIKE '%-OLD'"
            ).fetchone()[0],
        }
    finally:
        con.close()


def test_every_pathology_lands(clean_warehouse: Path) -> None:
    """The counts the reference SQL will have to account for."""
    assert _counts(clean_warehouse)["open"] == 0  # precondition: clean

    messify_mod.messify(clean_warehouse)

    counts = _counts(clean_warehouse)
    assert counts["open"] == messify_mod.N_OPEN_STAYS
    assert counts["reversed"] == messify_mod.N_REVERSED_STAYS
    assert counts["dupes"] == messify_mod.N_DUPLICATE_ENCOUNTERS
    assert counts["padded_payers"] == messify_mod.N_PAYER_CASING
    assert counts["old_orgs"] == 1


def test_deterministic_under_a_fixed_seed(
    tmp_path: Path, clean_warehouse: Path
) -> None:
    """Same seed, same rows — not merely the same counts.

    Counts alone would pass even if a different set of encounters were opened each
    run, which would move every ground truth while looking stable.
    """
    import shutil

    second = tmp_path / "second.duckdb"
    shutil.copy(clean_warehouse, second)

    messify_mod.messify(clean_warehouse)
    messify_mod.messify(second)

    def opened(path: Path) -> list[str]:
        con = duckdb.connect(str(path), read_only=True)
        try:
            return [
                r[0]
                for r in con.execute(
                    "SELECT Id FROM encounters WHERE STOP IS NULL ORDER BY Id"
                ).fetchall()
            ]
        finally:
            con.close()

    assert opened(clean_warehouse) == opened(second)


def test_running_twice_is_refused(clean_warehouse: Path) -> None:
    """Not idempotent, and says so rather than silently doubling the duplicates.

    A second pass would insert 220 more duplicate rows and invalidate every count in
    `messify_summary.json` — with no error, since inserting rows always "works".
    """
    messify_mod.messify(clean_warehouse)

    with pytest.raises(ValueError, match="already"):
        messify_mod.messify(clean_warehouse)


def test_verify_rejects_an_injection_that_did_not_land() -> None:
    """The guard itself.

    An `UPDATE` matching zero rows is not a SQL error. Without this check a filter
    that stopped selecting rows — a changed date boundary, a re-seeded population —
    would leave a clean warehouse, exit 0, and let seed tasks 2 and 6 pass while
    testing nothing.
    """
    landed = messify_mod.Injection("ok", "d", 5, 5)
    missed = messify_mod.Injection("open_stays", "d", 140, 0)

    messify_mod.verify([landed])  # does not raise

    with pytest.raises(ValueError, match="intended 140, observed 0"):
        messify_mod.verify([landed, missed])

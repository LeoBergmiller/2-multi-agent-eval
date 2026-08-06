"""Cassette staleness: "this recording is old" vs "the agent was wrong".

A cassette replays faithfully forever, which is its job and also its blind spot — it
cannot notice that the data it recorded has been replaced. After Gate 1a step 2 that
distinction became load-bearing: the committed cassettes describe the deleted CSV
fixtures, so a mismatched metric says nothing about the agent.

Both states fail and both exit non-zero. Only one is a bug.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analyst.replay import manifest as m
from evals.report import FAIL, PASS, STALE, verdict
from evals.runner import EvalReport

REPO_ROOT = Path(__file__).resolve().parents[1]


def _report(*, passed: bool, stale: str | None) -> EvalReport:
    """A minimally-populated report; only the verdict inputs matter here."""
    from evals.metrics.task_success import TaskSuccessResult
    from evals.trajectory import TrajectorySummary

    return EvalReport(
        run_id="r",
        task_id="t",
        cassette_mode="replay",
        passed=passed,
        task_success=TaskSuccessResult(
            score=1.0 if passed else 0.0,
            passed=passed,
            expected=1.0,
            tolerance=0.0,
            produced=1.0,
            detail="d",
            ground_truth_status="verified" if passed else "draft",
        ),
        trajectory=TrajectorySummary(step_count=1),
        cost_usd=0.01,
        price_table_hash="h",
        price_table_checked="2026-08-03",
        git_sha="abc",
        stale_reason=stale,
    )


class TestVerdict:
    def test_pass_when_passing_and_current(self) -> None:
        assert verdict(_report(passed=True, stale=None)) == PASS

    def test_fail_when_failing_and_current(self) -> None:
        """A genuine miss against current data is a FAIL and must stay one."""
        assert verdict(_report(passed=False, stale=None)) == FAIL

    def test_stale_when_failing_against_old_cassettes(self) -> None:
        assert verdict(_report(passed=False, stale="warehouse moved")) == STALE

    def test_staleness_never_upgrades_a_failure_to_a_pass(self) -> None:
        """STALE explains a failure; it must never excuse one.

        The whole point is a legible transitional state — if it could turn a red run
        green it would be a way to hide real regressions behind a data change.
        """
        assert verdict(_report(passed=False, stale="anything")) != PASS


class TestStalenessDetection:
    def test_absent_manifest_means_fixture_era(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cassettes older than the mechanism are stale by definition."""
        monkeypatch.setattr(m, "manifest_path", lambda: tmp_path / "missing.json")
        monkeypatch.setattr(m, "current_warehouse_version", lambda: "synthea-v4")

        note = m.staleness_note()

        assert note is not None
        assert "predate" in note

    def test_matching_versions_are_not_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(m, "manifest_path", lambda: tmp_path / "manifest.json")
        monkeypatch.setattr(m, "current_warehouse_version", lambda: "synthea-v4")
        m.write_manifest("synthea-v4", "corpus-1", "sha")

        assert m.staleness_note() is None

    def test_a_changed_warehouse_is_stale(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-seeding or re-pinning Synthea must invalidate the recordings.

        This is the guard that outlives Gate 1a: any future change to the generation
        parameters silently changes every number, and the cassettes would keep
        replaying the old world without it.
        """
        monkeypatch.setattr(m, "manifest_path", lambda: tmp_path / "manifest.json")
        m.write_manifest("synthea-v4-s1", "corpus-1", "sha")
        monkeypatch.setattr(m, "current_warehouse_version", lambda: "synthea-v4-s2")

        note = m.staleness_note()

        assert note is not None
        assert "s1" in note and "s2" in note

    def test_committed_warehouse_version_is_present(self) -> None:
        """`data/warehouse_version.txt` is committed even though the warehouse is not.

        If it were gitignored the check would only work on a machine that had already
        run `make data` — i.e. never in CI, which is where it matters.
        """
        assert m.warehouse_version_path().is_file()
        assert m.current_warehouse_version().startswith("synthea-")


def test_manifest_follows_the_monkeypatched_cassette_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cassette hygiene: the manifest must move with `cassettes_root`.

    Two ways this broke in one sitting. First `manifest_path` was computed from the
    repo root, so the RECORD-path test wrote a real manifest despite monkeypatching
    `cassettes_root` — which silently flipped `make demo` from STALE to FAIL by
    asserting the cassettes matched the current warehouse. Then the fix imported
    `cassettes_root` by name, binding it at import time so the patch still missed it.

    Neither failure looked like a leak. Both looked like a slightly different verdict.
    """
    monkeypatch.setattr("analyst.replay.store.cassettes_root", lambda: tmp_path)

    assert m.manifest_path() == tmp_path / "manifest.json"
    m.write_manifest("w", "c", "sha")
    assert (tmp_path / "manifest.json").is_file()

"""The smoke task runs in REPLAY with no API key (architecture.md §12, §7.7).

This is the definition of done: `make demo` must work from a clean clone with
no P1 install, no index, and no API key. It is also what makes the CI job
meaningful — that runner has no `ANTHROPIC_API_KEY` secret configured, so if
this path ever needed one the build would fail rather than quietly succeed.

The test runs the real graph end to end against the committed cassettes. It
asserts on the *number*, never on prose or prompt content (§7.7).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from analyst.contracts import load_models_config
from analyst.replay import CassetteMode, CassetteStore, build_llm_client
from analyst.runner import run_task
from analyst.telemetry.attrs import GATE0_REQUIRED
from evals.runner import score_run

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK = REPO_ROOT / "evals" / "tasks" / "gate0_inpatient_encounters_2023.yaml"
EXPECTED_ANSWER = 37.0


@pytest.fixture
def no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove every credential the SDK would resolve.

    An unset ANTHROPIC_API_KEY is not on its own proof of hermeticity — the SDK
    also reads ANTHROPIC_AUTH_TOKEN and an `ant auth login` profile — so all
    three are cleared.
    """
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_PROFILE", "__nonexistent__")


@pytest.mark.integration
class TestReplayIsHermetic:
    def test_replay_never_constructs_a_live_client(self, no_api_key: None) -> None:
        """Structural, not behavioural: in REPLAY the live client is never even
        built, which is why no credential is needed.

        This reaches past the public surface deliberately. The behavioural tests
        below would also pass if a client were constructed but never called, and
        the guarantee being asserted is that construction does not happen.
        """
        client = build_llm_client(
            CassetteStore(CassetteMode.REPLAY), load_models_config()
        )
        assert client._inner is None

    def test_smoke_task_replays_without_credentials(
        self, no_api_key: None, runs_root: Path
    ) -> None:
        run_dir = asyncio.run(run_task(TASK, "test-replay", CassetteMode.REPLAY))

        final = run_dir.read_final()
        assert final.numeric_value == EXPECTED_ANSWER
        assert final.evidence, "answer carries no provenance (rule 4)"

    def test_replay_needs_no_warehouse(
        self, no_api_key: None, runs_root: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A replayed run resolves no SQL, so it must not open DuckDB at all.

        Pointed at a warehouse path that does not exist: if anything tried to
        open it, SqlRunner would raise FileNotFoundError.
        """
        run_dir = asyncio.run(
            run_task(
                TASK,
                "test-no-warehouse",
                CassetteMode.REPLAY,
                warehouse=Path("/nonexistent/warehouse.duckdb"),
            )
        )
        assert run_dir.read_final().numeric_value == EXPECTED_ANSWER

    def test_run_directory_is_complete(self, no_api_key: None, runs_root: Path) -> None:
        run_dir = asyncio.run(run_task(TASK, "test-artifacts", CassetteMode.REPLAY))
        for path in (
            run_dir.meta_path,
            run_dir.plan_path,
            run_dir.final_path,
            run_dir.spans_path,
        ):
            assert path.is_file(), f"{path.name} missing from the run directory"

    def test_all_required_span_attributes_are_emitted(
        self, no_api_key: None, runs_root: Path
    ) -> None:
        """Every capability ships with the span attributes that measure it
        (§13). A silent regression that drops one would otherwise only surface
        as a metric quietly reading zero."""
        run_dir = asyncio.run(run_task(TASK, "test-spans", CassetteMode.REPLAY))
        seen: set[str] = set()
        for line in run_dir.spans_path.read_text().splitlines():
            seen |= set(json.loads(line).get("attributes", {}))
        assert not (GATE0_REQUIRED - seen)

    def test_replayed_run_reports_the_recorded_cost(
        self, no_api_key: None, runs_root: Path
    ) -> None:
        """Replay must report real cost, not zero — the recorded run's cost."""
        run_dir = asyncio.run(run_task(TASK, "test-cost", CassetteMode.REPLAY))
        assert run_dir.read_meta().cost_usd > 0


@pytest.mark.integration
class TestGateVerdict:
    def test_scored_run_passes_the_gate(
        self, no_api_key: None, runs_root: Path
    ) -> None:
        asyncio.run(run_task(TASK, "test-gate", CassetteMode.REPLAY))
        report = score_run("test-gate")
        assert report.passed
        assert report.task_success.score == 1.0
        assert report.task_success.ground_truth_status == "verified"
        assert report.trajectory.validation_failures == 0
        assert report.trajectory.repeated_tool_calls == 0

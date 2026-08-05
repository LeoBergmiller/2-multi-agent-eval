"""RECORD mode end to end, with a stubbed model but everything else real.

Why this exists: REPLAY exercises almost the whole system, but it deliberately
skips the one branch that produces every cassette — the branch where
`build_llm_client` constructs a *live* client and `run_task` spawns the MCP
server subprocess. That branch was only ever verified by spending money on a
real run, which means it silently stopped being verified the moment anything
around it was refactored.

So the model is stubbed and nothing else is. This test really does:

  * take the non-REPLAY branch of `build_llm_client` (live client constructed)
  * spawn `analyst.mcp.server` as a subprocess and speak MCP over stdio
  * execute real SQL against a real DuckDB built from the committed fixtures
  * write a real Parquet artifact and a real ResultRef
  * write cassettes for both seams
  * thread the tracer through `RunContext` and emit spans

No API call, no cost. What it cannot check is whether the vendor's wire format
changed — only a real run does that, which is what `make record` is for.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from analyst.artifacts import RunDirectory
from analyst.contracts import AgentRole, ModelsConfig
from analyst.llm.client import LLMRequest, LLMResponse
from analyst.replay import CassetteMode
from analyst.runner import run_task
from analyst.telemetry.attrs import GATE0_REQUIRED

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK = REPO_ROOT / "evals" / "tasks" / "gate0_inpatient_encounters_2023.yaml"

#: What the stub returns per role. Shapes match the json_schema each node asks
#: for; the SQL is real and is really executed.
CANNED: dict[AgentRole, str] = {
    AgentRole.PLANNER: json.dumps(
        {
            "subtasks": [
                {
                    "id": "s1",
                    "goal": "Count inpatient encounters starting in 2023",
                    "assigned_role": "sql_analyst",
                    "acceptance_criteria": ["returns a single integer count"],
                }
            ]
        }
    ),
    AgentRole.SQL_ANALYST: json.dumps(
        {
            "sql": (
                "SELECT count(*) AS n FROM encounters "
                "WHERE ENCOUNTERCLASS = 'inpatient' "
                "AND START >= TIMESTAMP '2023-01-01' "
                "AND START < TIMESTAMP '2024-01-01'"
            ),
            "assumptions": [],
            "criteria_met": [True],
            "confidence": 0.95,
        }
    ),
    AgentRole.SYNTHESIZER: json.dumps(
        {
            "answer": "37 inpatient encounters started in 2023 [q001].",
            "numeric_value": 37,
            "cited_refs": ["q001"],
            "caveats": ["Synthetic data."],
            "confidence": 0.95,
        }
    ),
}


class StubLLMClient:
    """Stands in for `AnthropicLLMClient`, same constructor and same protocol.

    Reports non-zero token usage so the cost path is exercised rather than
    trivially summing to zero.
    """

    def __init__(self, models: ModelsConfig) -> None:
        self._models = models
        self.calls: list[AgentRole] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request.agent_role)
        spec = self._models.roles[request.agent_role]
        in_tokens, out_tokens = 1000, 200
        return LLMResponse(
            text=CANNED[request.agent_role],
            model=spec.id,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=spec.cost_usd(input_tokens=in_tokens, output_tokens=out_tokens),
            stop_reason="end_turn",
        )


@pytest.fixture
def stub_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap the live client for the stub.

    Patched on `analyst.llm.client` because `build_llm_client` imports it at
    call time — so this substitutes into the real non-REPLAY code path rather
    than bypassing it.
    """
    monkeypatch.setattr("analyst.llm.client.AnthropicLLMClient", StubLLMClient)


@pytest.mark.integration
class TestRecordPath:
    def _record(self, warehouse: Path, run_id: str = "test-record") -> RunDirectory:
        return asyncio.run(
            run_task(TASK, run_id, CassetteMode.RECORD, warehouse=warehouse)
        )

    def test_record_run_produces_the_right_answer(
        self, stub_llm: None, runs_root: Path, cassettes_root: Path, warehouse: Path
    ) -> None:
        """The number comes from real SQL against a real warehouse — only the
        model's choice of SQL is canned."""
        run_dir = self._record(warehouse)
        assert run_dir.read_final().numeric_value == 37.0

    def test_live_client_branch_is_taken(
        self, stub_llm: None, runs_root: Path, cassettes_root: Path, warehouse: Path
    ) -> None:
        """The branch REPLAY never exercises: a live client is constructed and
        actually called, once per node."""
        self._record(warehouse)
        # Three nodes ran, so the live client was built and used three times.
        cassettes = list((cassettes_root / "llm").glob("*.json"))
        assert len(cassettes) == 3

    def test_both_seams_are_recorded(
        self, stub_llm: None, runs_root: Path, cassettes_root: Path, warehouse: Path
    ) -> None:
        self._record(warehouse)
        assert list((cassettes_root / "llm").glob("*.json"))
        assert list((cassettes_root / "mcp").glob("*.json")), (
            "no MCP cassette — the server subprocess or the seam did not run"
        )

    def test_real_parquet_artifact_is_written(
        self, stub_llm: None, runs_root: Path, cassettes_root: Path, warehouse: Path
    ) -> None:
        """A recorded run carries its results; a replayed one does not, because
        the recorded artefact is the ResultRef, not the frame."""
        run_dir = self._record(warehouse)
        artifacts = list((run_dir.path / "results").glob("*.parquet"))
        assert artifacts, "run_sql did not materialise a Parquet result"

    def test_tracer_threading_survives(
        self, stub_llm: None, runs_root: Path, cassettes_root: Path, warehouse: Path
    ) -> None:
        """Guards the refactor that moved the tracer off the OTel global: if it
        regressed, spans would land in another run's file or nowhere."""
        run_dir = self._record(warehouse)
        seen: set[str] = set()
        for line in run_dir.spans_path.read_text().splitlines():
            seen |= set(json.loads(line).get("attributes", {}))
        assert not (GATE0_REQUIRED - seen)

    def test_cost_is_accumulated(
        self, stub_llm: None, runs_root: Path, cassettes_root: Path, warehouse: Path
    ) -> None:
        run_dir = self._record(warehouse)
        meta = run_dir.read_meta()
        assert meta.cost_usd > 0
        assert meta.total_input_tokens == 3000, "three nodes at 1000 input tokens each"
        assert meta.cassette_mode == "record"

    def test_two_runs_in_one_process_both_get_spans(
        self, stub_llm: None, runs_root: Path, cassettes_root: Path, warehouse: Path
    ) -> None:
        """The exact failure the global tracer provider caused: the second run
        in a process silently produced no spans of its own. This is what the
        Gate 3 model-tier sweep will do all day."""
        first = self._record(warehouse, "sweep-a")
        second = self._record(warehouse, "sweep-b")
        for run in (first, second):
            assert run.spans_path.read_text().strip(), (
                "a run produced no spans — tracing is process-global again"
            )


@pytest.mark.integration
class TestRecordThenReplay:
    def test_a_recorded_run_can_be_replayed(
        self, stub_llm: None, runs_root: Path, cassettes_root: Path, warehouse: Path
    ) -> None:
        """The round trip the whole design rests on: what RECORD writes, REPLAY
        must be able to serve — with no live client and no warehouse."""
        asyncio.run(run_task(TASK, "rec", CassetteMode.RECORD, warehouse=warehouse))

        replayed = asyncio.run(
            run_task(
                TASK,
                "rep",
                CassetteMode.REPLAY,
                warehouse=Path("/nonexistent/warehouse.duckdb"),
            )
        )
        assert replayed.read_final().numeric_value == 37.0

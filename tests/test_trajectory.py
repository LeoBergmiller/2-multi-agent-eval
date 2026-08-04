"""Span-tree -> Trajectory reconstruction (architecture.md §7.1, §7.7).

Every trajectory here is hand-built. Reconstruction must be testable without
running an agent, or the metrics that depend on it can only be checked by
running the thing they are supposed to be judging.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analyst.telemetry import attrs
from evals.trajectory import Trajectory, TrajectorySummary, load_trajectory
from tests.conftest import span, write_spans


def a_run(tmp_path: Path, records: list[dict]) -> Trajectory:
    return load_trajectory(write_spans(tmp_path / "spans.jsonl", records), "r1")


class TestReconstruction:
    def test_missing_file_raises_actionably(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Run the task before scoring"):
            load_trajectory(tmp_path / "nope.jsonl")

    def test_steps_are_ordered_by_start_not_file_order(self, tmp_path: Path) -> None:
        """Spans are written on end, so file order is completion order. A child
        that finishes first must not sort ahead of the parent that began first."""
        traj = a_run(
            tmp_path,
            [
                span("node", span_id="b" * 16, parent="a" * 16, start_ns=200),
                span("run", span_id="a" * 16, start_ns=100),
            ],
        )
        assert [s.name for s in traj.steps] == ["run", "node"]

    def test_parent_links_are_preserved(self, tmp_path: Path) -> None:
        traj = a_run(
            tmp_path,
            [
                span("run", span_id="a" * 16, start_ns=1),
                span("node", span_id="b" * 16, parent="a" * 16, start_ns=2),
            ],
        )
        assert traj.steps[1].parent_span_id == traj.steps[0].span_id

    def test_attributes_are_lifted_onto_steps(self, tmp_path: Path) -> None:
        traj = a_run(
            tmp_path,
            [
                span(
                    "tool.call",
                    start_ns=1,
                    **{
                        attrs.TOOL_NAME: "run_sql",
                        attrs.TOOL_ARGS_HASH: "deadbeef",
                        attrs.RESULT_REF: "q001",
                        attrs.AGENT_ROLE: "sql_analyst",
                    },
                )
            ],
        )
        step = traj.steps[0]
        assert step.tool == "run_sql"
        assert step.args_hash == "deadbeef"
        assert step.result_ref == "q001"
        assert step.agent_role == "sql_analyst"


class TestDerivedMetrics:
    def test_cost_excludes_the_root_span(self, tmp_path: Path) -> None:
        """The run span repeats the total; summing everything double-counts."""
        traj = a_run(
            tmp_path,
            [
                span("run", span_id="a" * 16, start_ns=1, **{attrs.COST_USD: 0.03}),
                span("node", span_id="b" * 16, start_ns=2, **{attrs.COST_USD: 0.01}),
                span("node", span_id="c" * 16, start_ns=3, **{attrs.COST_USD: 0.02}),
            ],
        )
        assert traj.total_cost_usd == pytest.approx(0.03)

    def test_step_count_ignores_transport_spans(self, tmp_path: Path) -> None:
        """The MCP SDK emits its own protocol spans; those describe transport,
        not agent behaviour, and must not inflate trajectory_efficiency."""
        traj = a_run(
            tmp_path,
            [
                span("run", span_id="a" * 16, start_ns=1),
                span("node", span_id="b" * 16, start_ns=2),
                span("tool.call", span_id="c" * 16, start_ns=3),
                span("MCP send tools/call run_sql", span_id="d" * 16, start_ns=4),
            ],
        )
        assert traj.step_count == 2

    def test_validation_failures_are_counted(self, tmp_path: Path) -> None:
        traj = a_run(
            tmp_path,
            [
                span(
                    "node",
                    span_id="a" * 16,
                    start_ns=1,
                    **{attrs.VALIDATION_PASSED: True},
                ),
                span(
                    "node",
                    span_id="b" * 16,
                    start_ns=2,
                    **{attrs.VALIDATION_PASSED: False},
                ),
            ],
        )
        assert traj.validation_failures == 1

    def test_repeated_tool_calls_detected(self, tmp_path: Path) -> None:
        """Adversarial: the same (tool, args_hash) twice is the raw signal
        behind loop_rate at Gate 1."""
        same = {attrs.TOOL_NAME: "run_sql", attrs.TOOL_ARGS_HASH: "same"}
        traj = a_run(
            tmp_path,
            [
                span("tool.call", span_id="a" * 16, start_ns=1, **same),
                span("tool.call", span_id="b" * 16, start_ns=2, **same),
                span(
                    "tool.call",
                    span_id="c" * 16,
                    start_ns=3,
                    **{attrs.TOOL_NAME: "run_sql", attrs.TOOL_ARGS_HASH: "other"},
                ),
            ],
        )
        assert traj.repeated_tool_calls == (("run_sql", "same"),)

    def test_distinct_args_are_not_a_loop(self, tmp_path: Path) -> None:
        traj = a_run(
            tmp_path,
            [
                span(
                    "tool.call",
                    span_id="a" * 16,
                    start_ns=1,
                    **{attrs.TOOL_NAME: "run_sql", attrs.TOOL_ARGS_HASH: "x"},
                ),
                span(
                    "tool.call",
                    span_id="b" * 16,
                    start_ns=2,
                    **{attrs.TOOL_NAME: "run_sql", attrs.TOOL_ARGS_HASH: "y"},
                ),
            ],
        )
        assert traj.repeated_tool_calls == ()


class TestSummary:
    def test_max_bundle_tokens_is_reported(self, tmp_path: Path) -> None:
        """context.bundle_tokens is what makes the bounded-handoff rule
        measurable rather than merely asserted."""
        traj = a_run(
            tmp_path,
            [
                span(
                    "node",
                    span_id="a" * 16,
                    start_ns=1,
                    **{attrs.CONTEXT_BUNDLE_TOKENS: 120},
                ),
                span(
                    "node",
                    span_id="b" * 16,
                    start_ns=2,
                    **{attrs.CONTEXT_BUNDLE_TOKENS: 640},
                ),
            ],
        )
        assert TrajectorySummary.of(traj).max_bundle_tokens == 640

    def test_summary_of_empty_run(self, tmp_path: Path) -> None:
        traj = a_run(tmp_path, [span("run", start_ns=1)])
        summary = TrajectorySummary.of(traj)
        assert summary.step_count == 0
        assert summary.max_bundle_tokens is None

"""Trajectory reconstruction from `spans.jsonl` (architecture.md §7.1).

The harness reads JSONL and nothing else — never a SaaS API (§8, D10). That is
what makes scoring reproducible from a clean clone and keeps the eval honest if
the observability vendor changes.

`spans.jsonl` is a flat log; `parent_span_id` is what turns it back into a tree.
Steps are ordered by start time, which is safe because the exporter is a
`SimpleSpanProcessor` — a batching exporter would reorder writes and the order
here is part of the data, not an artefact of it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import Field

from analyst.contracts import Contract
from analyst.telemetry import attrs


class Step(Contract):
    """One node transition, model call, or tool call."""

    span_id: str | None
    parent_span_id: str | None
    name: str
    agent_role: str | None = None
    tool: str | None = None
    args_hash: str | None = None
    result_ref: str | None = None
    subtask_id: str | None = None
    model_id: str | None = None
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    bundle_tokens: int | None = None
    validation_passed: bool | None = None
    cassette_mode: str | None = None
    duration_ms: float | None = None
    status: str | None = None


class Trajectory(Contract):
    """An ordered, tree-linked view of one run."""

    run_id: str
    steps: tuple[Step, ...] = ()

    @property
    def tool_calls(self) -> tuple[str, ...]:
        return tuple(s.tool for s in self.steps if s.tool)

    @property
    def total_cost_usd(self) -> float:
        # Only leaf spans carry per-call cost; the root `run` span repeats the
        # total, so summing every span would double-count it.
        return sum(s.cost_usd for s in self.steps if s.name != attrs.SPAN_RUN)

    @property
    def step_count(self) -> int:
        """Steps that represent work: node transitions and tool calls.

        Excludes the root span and the MCP SDK's own protocol spans, which
        describe transport rather than agent behaviour.
        """
        return sum(
            1 for s in self.steps if s.name in {attrs.SPAN_NODE, attrs.SPAN_TOOL_CALL}
        )

    @property
    def validation_failures(self) -> int:
        return sum(1 for s in self.steps if s.validation_passed is False)

    #: Repeated (tool, args_hash) pairs — the raw signal behind `loop_rate` and
    #: `context_transfer_integrity` at Gate 1. Computed here so those metrics
    #: do not need to re-parse spans.
    @property
    def repeated_tool_calls(self) -> tuple[tuple[str, str], ...]:
        seen: set[tuple[str, str]] = set()
        repeats: list[tuple[str, str]] = []
        for s in self.steps:
            if s.tool and s.args_hash:
                key = (s.tool, s.args_hash)
                if key in seen:
                    repeats.append(key)
                seen.add(key)
        return tuple(repeats)


def _attr(record: dict[str, Any], key: str) -> Any:
    return record.get("attributes", {}).get(key)


def step_from_record(record: dict[str, Any]) -> Step:
    return Step(
        span_id=record.get("span_id"),
        parent_span_id=record.get("parent_span_id"),
        name=record.get("name", ""),
        agent_role=_attr(record, attrs.AGENT_ROLE),
        tool=_attr(record, attrs.TOOL_NAME),
        args_hash=_attr(record, attrs.TOOL_ARGS_HASH),
        result_ref=_attr(record, attrs.RESULT_REF),
        subtask_id=_attr(record, attrs.SUBTASK_ID),
        model_id=_attr(record, attrs.MODEL_ID),
        cost_usd=float(_attr(record, attrs.COST_USD) or 0.0),
        input_tokens=int(_attr(record, attrs.GEN_AI_USAGE_INPUT_TOKENS) or 0),
        output_tokens=int(_attr(record, attrs.GEN_AI_USAGE_OUTPUT_TOKENS) or 0),
        bundle_tokens=_attr(record, attrs.CONTEXT_BUNDLE_TOKENS),
        validation_passed=_attr(record, attrs.VALIDATION_PASSED),
        cassette_mode=_attr(record, attrs.CASSETTE_MODE),
        duration_ms=record.get("duration_ms"),
        status=record.get("status"),
    )


def load_trajectory(spans_path: Path, run_id: str = "") -> Trajectory:
    """Rebuild a `Trajectory` from a run's span log."""
    if not spans_path.is_file():
        raise FileNotFoundError(
            f"No spans at {spans_path}. Run the task before scoring it."
        )

    records = [
        json.loads(line) for line in spans_path.read_text().splitlines() if line.strip()
    ]
    # A span is written on *end*, so file order is completion order. Sorting by
    # start time recovers the order in which work actually began, which is what
    # a trajectory describes.
    records.sort(key=lambda r: r.get("start_time_ns") or 0)
    return Trajectory(
        run_id=run_id or spans_path.parent.name,
        steps=tuple(step_from_record(r) for r in records),
    )


class TrajectorySummary(Contract):
    """Compact view written into `eval.json`."""

    step_count: int
    tool_calls: tuple[str, ...] = ()
    total_cost_usd: float = 0.0
    validation_failures: int = 0
    repeated_tool_calls: int = 0
    max_bundle_tokens: int | None = Field(
        default=None,
        description="Largest handoff seen. The bounded-handoff rule, measured.",
    )

    @classmethod
    def of(cls, trajectory: Trajectory) -> TrajectorySummary:
        bundles = [s.bundle_tokens for s in trajectory.steps if s.bundle_tokens]
        return cls(
            step_count=trajectory.step_count,
            tool_calls=trajectory.tool_calls,
            total_cost_usd=round(trajectory.total_cost_usd, 6),
            validation_failures=trajectory.validation_failures,
            repeated_tool_calls=len(trajectory.repeated_tool_calls),
            max_bundle_tokens=max(bundles) if bundles else None,
        )

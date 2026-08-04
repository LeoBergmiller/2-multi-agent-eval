"""Contract validation and round-tripping (architecture.md §6.1, §7.7)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from analyst.contracts import (
    AgentResult,
    AgentRole,
    ColumnSchema,
    ContextTransferError,
    Evidence,
    FinalAnswer,
    Plan,
    ResultRef,
    SubTask,
    TaskSpec,
)


def a_ref(ref_id: str = "q001") -> ResultRef:
    return ResultRef(
        ref_id=ref_id,
        format="parquet",
        schema=[ColumnSchema(name="n", dtype="BIGINT")],
        row_count=1,
        head=[{"n": 37}],
    )


def a_subtask(sid: str = "s1") -> SubTask:
    return SubTask(
        id=sid,
        goal="count things",
        assigned_role=AgentRole.SQL_ANALYST,
        acceptance_criteria=("returns a single integer",),
    )


class TestFrozenAndStrict:
    def test_contracts_are_frozen(self) -> None:
        task = TaskSpec(goal="x")
        with pytest.raises(ValidationError):
            task.goal = "y"  # type: ignore[misc]

    def test_unknown_fields_are_rejected(self) -> None:
        """extra=forbid is load-bearing: silently dropping an unknown key is
        how a producer/consumer mismatch survives to production."""
        with pytest.raises(ValidationError):
            TaskSpec(goal="x", tpyo=1)  # type: ignore[call-arg]

    def test_round_trip_preserves_values(self) -> None:
        ref = a_ref()
        assert ResultRef.model_validate_json(ref.model_dump_json()) == ref


class TestResultRef:
    def test_schema_alias_is_exposed_as_schema_(self) -> None:
        assert a_ref().schema_[0].name == "n"

    def test_negative_row_count_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ResultRef(ref_id="q", format="parquet", schema=[], row_count=-1)


class TestEvidence:
    """Rule 4 — provenance or it didn't happen."""

    def test_requires_exactly_one_source(self) -> None:
        with pytest.raises(ValidationError):
            Evidence(claim="c")
        with pytest.raises(ValidationError):
            Evidence(claim="c", result_ref="q001", doc_id="d1")

    def test_accepts_either_source_alone(self) -> None:
        assert Evidence(claim="c", result_ref="q001").doc_id is None
        assert Evidence(claim="c", doc_id="d1").result_ref is None


class TestAgentResult:
    """Rule 5 — the assumptions register."""

    def test_low_confidence_requires_assumptions(self) -> None:
        with pytest.raises(ValidationError):
            AgentResult(subtask_id="s1", status="ok", confidence=0.5)

    def test_low_confidence_with_assumptions_is_accepted(self) -> None:
        result = AgentResult(
            subtask_id="s1",
            status="ok",
            confidence=0.5,
            assumptions_made=("assumed inpatient means ENCOUNTERCLASS='inpatient'",),
        )
        assert result.assumptions_made

    def test_high_confidence_needs_no_assumptions(self) -> None:
        assert AgentResult(subtask_id="s1", status="ok", confidence=0.95)

    def test_confidence_is_bounded(self) -> None:
        with pytest.raises(ValidationError):
            AgentResult(subtask_id="s1", status="ok", confidence=1.5)


class TestSubTask:
    def test_acceptance_criteria_are_required(self) -> None:
        """Rule 2 — criteria travel with the subtask, so a subtask without any
        cannot be handed off."""
        with pytest.raises(ValidationError):
            SubTask(
                id="s1",
                goal="g",
                assigned_role=AgentRole.SQL_ANALYST,
                acceptance_criteria=(),
            )


class TestPlan:
    def test_duplicate_subtask_ids_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Plan(subtasks=(a_subtask("s1"), a_subtask("s1")))

    def test_edge_to_unknown_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Plan(subtasks=(a_subtask("s1"),), edges=(("s1", "nope"),))

    def test_depends_on_unknown_id_rejected(self) -> None:
        bad = SubTask(
            id="s2",
            goal="g",
            assigned_role=AgentRole.SQL_ANALYST,
            acceptance_criteria=("c",),
            depends_on=("ghost",),
        )
        with pytest.raises(ValidationError):
            Plan(subtasks=(bad,))

    def test_empty_plan_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Plan(subtasks=())


class TestValidationEvents:
    """Rule 3 — a boundary failure becomes a recorded event, not an exception
    that escapes the node."""

    def test_error_converts_to_event(self) -> None:
        err = ContextTransferError(
            role=AgentRole.PLANNER,
            boundary="egress",
            detail="bad json",
            subtask_id="s1",
        )
        event = err.as_event()
        assert event.role is AgentRole.PLANNER
        assert event.boundary == "egress"
        assert event.subtask_id == "s1"
        assert "bad json" in event.detail


class TestFinalAnswer:
    def test_numeric_value_is_optional(self) -> None:
        assert (
            FinalAnswer(answer="no number here", confidence=0.9).numeric_value is None
        )

    def test_carries_evidence(self) -> None:
        final = FinalAnswer(
            answer="37",
            evidence=(Evidence(claim="37", result_ref="q001"),),
            confidence=0.95,
            numeric_value=37.0,
        )
        assert final.evidence[0].result_ref == "q001"

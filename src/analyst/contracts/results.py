"""Specialist output and final answer contracts (architecture.md §6.1)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from analyst.contracts.base import Contract
from analyst.contracts.refs import Evidence, ResultRef

ResultStatus = Literal["ok", "partial", "failed"]


class AgentResult(Contract):
    """What a specialist returns for one subtask."""

    subtask_id: str
    status: ResultStatus
    findings: dict[str, object] = Field(default_factory=dict)
    artifact_refs: tuple[ResultRef, ...] = ()
    criteria_met: dict[str, bool] = Field(
        default_factory=dict,
        description="Self-report against SubTask.acceptance_criteria (rule 2)",
    )
    assumptions_made: tuple[str, ...] = Field(
        default=(),
        description="Mandatory register; surfaces silent context loss (rule 5)",
    )
    unresolved: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    cost_usd: float = Field(ge=0.0, default=0.0)

    @model_validator(mode="after")
    def _assumptions_required_when_unconfident(self) -> AgentResult:
        # Handoff rule 5 (§6.1): a low-confidence result that claims it assumed
        # nothing is not humble, it is unexamined. Force the register to be
        # populated so the assumption is inspectable rather than implicit.
        if self.confidence < 0.8 and not self.assumptions_made:
            raise ValueError(
                f"AgentResult for {self.subtask_id!r} has confidence "
                f"{self.confidence} (< 0.8) but an empty assumptions_made register"
            )
        return self


class FinalAnswer(Contract):
    """The run's output, with provenance for every claim."""

    answer: str
    evidence: tuple[Evidence, ...] = ()
    caveats: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    numeric_value: float | None = Field(
        default=None,
        description=(
            "Extracted scalar the task_success metric compares against "
            "ground_truth. None when the run failed or produced no number."
        ),
    )

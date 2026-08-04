"""`task_success` — the one metric scored at Gate 0 (architecture.md §7.3).

Definition: numeric match within tolerance. Deliberately narrow — no LLM judge
anywhere near it, because this metric gates CI (§7.4, §13).

The scorer is a pure function of (produced value, expected value, tolerance) so
it can be tested against hand-built inputs without running an agent (§7.7). The
one piece of policy it carries is the ground-truth gate: an unverified expected
value can never produce a pass, per D17.
"""

from __future__ import annotations

from typing import Literal

from analyst.contracts import Contract

GroundTruthStatus = Literal["draft", "verified"]


class TaskSuccessResult(Contract):
    """Outcome of scoring one task."""

    score: float
    passed: bool
    produced: float | None
    expected: float
    tolerance: float
    detail: str
    ground_truth_status: GroundTruthStatus

    @property
    def abs_error(self) -> float | None:
        if self.produced is None:
            return None
        return abs(self.produced - self.expected)


def score_task_success(
    produced: float | None,
    *,
    expected: float,
    tolerance: float = 0.0,
    ground_truth_status: GroundTruthStatus = "draft",
    require_verified: bool = True,
) -> TaskSuccessResult:
    """Score a numeric answer against human-verified ground truth."""
    if produced is None:
        return TaskSuccessResult(
            score=0.0,
            passed=False,
            produced=None,
            expected=expected,
            tolerance=tolerance,
            detail="Run produced no numeric answer.",
            ground_truth_status=ground_truth_status,
        )

    within = abs(produced - expected) <= tolerance
    score = 1.0 if within else 0.0

    # D17: the coding agent may draft and execute a ground truth, but a human
    # signs off before it counts. A draft value is still scored and reported —
    # silence would be worse — it just cannot turn the gate green.
    if within and require_verified and ground_truth_status != "verified":
        return TaskSuccessResult(
            score=score,
            passed=False,
            produced=produced,
            expected=expected,
            tolerance=tolerance,
            detail=(
                f"Answer {produced:g} matches, but ground_truth.status is "
                f"{ground_truth_status!r}. A draft ground truth cannot pass "
                "(config/eval.yaml: require_verified_ground_truth)."
            ),
            ground_truth_status=ground_truth_status,
        )

    detail = (
        f"{produced:g} == {expected:g} (±{tolerance:g})"
        if within
        else f"{produced:g} != {expected:g} (±{tolerance:g}), off by "
        f"{abs(produced - expected):g}"
    )
    return TaskSuccessResult(
        score=score,
        passed=within,
        produced=produced,
        expected=expected,
        tolerance=tolerance,
        detail=detail,
        ground_truth_status=ground_truth_status,
    )

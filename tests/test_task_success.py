"""The `task_success` scorer (architecture.md §7.3, §7.7, D17)."""

from __future__ import annotations

import pytest

from evals.metrics.task_success import score_task_success


class TestNumericMatching:
    def test_exact_match_passes(self) -> None:
        r = score_task_success(37.0, expected=37.0, ground_truth_status="verified")
        assert r.passed and r.score == 1.0

    def test_wrong_answer_fails(self) -> None:
        r = score_task_success(31.0, expected=37.0, ground_truth_status="verified")
        assert not r.passed
        assert r.score == 0.0
        assert r.abs_error == 6.0

    def test_the_still_admitted_trap_is_scored_as_a_miss(self) -> None:
        """31 is what a query that drops still-admitted patients returns. It
        must not pass — that trap is the point of the fixture."""
        assert not score_task_success(
            31.0, expected=37.0, ground_truth_status="verified"
        ).passed

    def test_the_all_classes_trap_is_scored_as_a_miss(self) -> None:
        """182 is what ignoring ENCOUNTERCLASS returns."""
        assert not score_task_success(
            182.0, expected=37.0, ground_truth_status="verified"
        ).passed

    @pytest.mark.parametrize(
        ("produced", "should_pass"),
        [(0.183, True), (0.1845, True), (0.186, False)],
    )
    def test_tolerance_band(self, produced: float, should_pass: bool) -> None:
        r = score_task_success(
            produced, expected=0.183, tolerance=0.002, ground_truth_status="verified"
        )
        assert r.passed is should_pass

    def test_zero_tolerance_is_exact(self) -> None:
        assert not score_task_success(
            37.0001, expected=37.0, tolerance=0.0, ground_truth_status="verified"
        ).passed


class TestNoAnswer:
    def test_missing_value_scores_zero(self) -> None:
        r = score_task_success(None, expected=37.0, ground_truth_status="verified")
        assert not r.passed
        assert r.score == 0.0
        assert r.abs_error is None
        assert "no numeric answer" in r.detail


class TestGroundTruthGate:
    """D17: a human signs off before a number counts."""

    def test_draft_ground_truth_cannot_pass_even_when_correct(self) -> None:
        r = score_task_success(37.0, expected=37.0, ground_truth_status="draft")
        assert r.score == 1.0, "the score is still reported"
        assert not r.passed, "but it cannot turn the gate green"
        assert "draft" in r.detail

    def test_verified_ground_truth_passes(self) -> None:
        assert score_task_success(
            37.0, expected=37.0, ground_truth_status="verified"
        ).passed

    def test_gate_can_be_disabled_explicitly(self) -> None:
        """Opt-out exists for local iteration, but defaults to on."""
        assert score_task_success(
            37.0, expected=37.0, ground_truth_status="draft", require_verified=False
        ).passed

    def test_draft_and_wrong_still_fails(self) -> None:
        r = score_task_success(31.0, expected=37.0, ground_truth_status="draft")
        assert not r.passed
        assert r.score == 0.0

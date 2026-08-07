"""Score a run directory into `eval.json`.

    python -m evals.runner --run-id <id>

Reads only `runs/{run_id}/` and the task YAML. It never imports the graph and
never calls a model — scoring must be reproducible from committed artefacts
alone, which is what lets CI re-score without an API key.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from analyst.artifacts import RunDirectory
from analyst.contracts import Contract, load_eval_config
from analyst.replay import manifest
from evals.metrics.task_success import (
    GroundTruthStatus,
    TaskSuccessResult,
    score_task_success,
)
from evals.trajectory import TrajectorySummary, load_trajectory

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TASKS_DIR = Path(__file__).resolve().parent / "tasks"


class GroundTruth(Contract):
    value: float
    tolerance: float = 0.0
    status: GroundTruthStatus = "draft"


class TaskFile(Contract):
    """A task YAML. The graph reads `prompt`; this reads the human-owned half
    (§13, D17) plus the reference trajectory.

    The reference trajectory is a **partial-order constraint set, not a golden
    path** (§7.2, D18). Every field of it is modelled here even though Gate 0
    scores only `ground_truth` — `extra="forbid"` means an unmodelled field is a
    hard error, so recording them now is what stops the task schema churning
    when `tool_call_accuracy` and `trajectory_efficiency` land at Gate 1.
    """

    id: str
    prompt: str
    ground_truth: GroundTruth
    reference_sql: str | None = None

    # Recorded, not yet scored. Gate 1 metrics read these.
    required_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    required_order: tuple[tuple[str, str], ...] = ()
    must_cite: tuple[str, ...] = ()
    min_steps: int = 1
    failure_injection: dict[str, Any] | None = None


def load_task_file(path: Path) -> TaskFile:
    raw: dict[str, Any] = yaml.safe_load(path.read_text())
    # `verification` is an audit trail for humans, not an input to scoring.
    gt = dict(raw.get("ground_truth", {}))
    gt.pop("verification", None)
    return TaskFile.model_validate({**raw, "ground_truth": gt})


def find_task_for(task_id: str) -> Path:
    path = TASKS_DIR / f"{task_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"No task spec for {task_id!r} at {path}")
    return path


class EvalReport(Contract):
    """`eval.json`. One metric at Gate 0; seven more arrive at Gate 1."""

    run_id: str
    task_id: str
    cassette_mode: str
    passed: bool
    task_success: TaskSuccessResult
    trajectory: TrajectorySummary
    cost_usd: float
    price_table_hash: str
    price_table_checked: str
    git_sha: str
    notes: tuple[str, ...] = ()
    #: Set when the committed cassettes were recorded against a different dataset than
    #: the one committed now. A mismatched metric then means "the recording is old",
    #: not "the agent was wrong" — different states, different verdicts.
    stale_reason: str | None = None


def score_run(run_id: str) -> EvalReport:
    run_dir = RunDirectory(run_id)
    meta = run_dir.read_meta()
    cfg = load_eval_config()
    task = load_task_file(find_task_for(meta.task_id))
    trajectory = load_trajectory(run_dir.spans_path, run_id)

    produced: float | None = None
    notes: list[str] = []
    if run_dir.final_path.is_file():
        final = run_dir.read_final()
        produced = final.numeric_value
        if produced is None:
            notes.append("Run completed but the answer carried no numeric value.")
    else:
        notes.append("No final.json — the run failed before the Synthesizer.")

    result = score_task_success(
        produced,
        expected=task.ground_truth.value,
        tolerance=task.ground_truth.tolerance,
        ground_truth_status=task.ground_truth.status,
        require_verified=cfg.require_verified_ground_truth,
    )

    if trajectory.validation_failures:
        notes.append(
            f"{trajectory.validation_failures} validation failure(s) recorded — "
            "see spans.jsonl."
        )
    if result.score < cfg.task_success_floor:
        notes.append(
            f"task_success {result.score:.2f} is below the floor "
            f"{cfg.task_success_floor:.2f}."
        )

    # Only a replayed run can be stale: a live or recording run reads the current
    # warehouse by definition.
    stale = manifest.staleness_note() if meta.cassette_mode == "replay" else None

    return EvalReport(
        run_id=run_id,
        task_id=meta.task_id,
        cassette_mode=meta.cassette_mode,
        passed=result.passed and result.score >= cfg.task_success_floor,
        task_success=result,
        trajectory=TrajectorySummary.of(trajectory),
        cost_usd=meta.cost_usd,
        price_table_hash=meta.price_table_hash,
        price_table_checked=meta.price_table_checked,
        git_sha=meta.git_sha,
        notes=tuple(notes),
        stale_reason=stale,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Score a run directory")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    report = score_run(args.run_id)
    RunDirectory(args.run_id).write_eval(report.model_dump(mode="json"))
    logger.info("wrote runs/%s/eval.json", args.run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())

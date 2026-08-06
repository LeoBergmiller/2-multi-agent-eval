"""Render `eval.json` as the eval line (architecture.md §7, §10).

`make demo` printing this line is Gate 0's definition of done. It is also the
row that becomes the README table at Gate 1, so it carries the fields that
table needs — score, steps, cost, and the provenance of the price it was costed
against.

Exit code is the gate: non-zero when the run did not pass, so CI and a human
get the same verdict.
"""

from __future__ import annotations

import argparse
import sys

from analyst.artifacts import RunDirectory
from evals.runner import EvalReport

PASS = "PASS"
FAIL = "FAIL"
#: A third verdict, and the reason it exists: after the warehouse changed under the
#: committed cassettes, a mismatched metric no longer distinguished "the agent was
#: wrong" from "this recording is older than the data it describes". Both are failures
#: and both exit non-zero — but only one of them is a bug, and a transitional state
#: that looks like a broken build gets ignored or, worse, "fixed" by pinning a number.
STALE = "STALE"


def format_line(report: EvalReport) -> str:
    ts = report.task_success
    produced = "none" if ts.produced is None else f"{ts.produced:g}"
    return (
        f"{report.task_id}  "
        f"task_success={ts.score:.2f}  "
        f"answer={produced} (expected {ts.expected:g}±{ts.tolerance:g})  "
        f"steps={report.trajectory.step_count}  "
        f"tools={len(report.trajectory.tool_calls)}  "
        f"cost=${report.cost_usd:.4f}  "
        f"mode={report.cassette_mode}  "
        f"ground_truth={ts.ground_truth_status}"
    )


def render(report: EvalReport) -> str:
    lines = [
        format_line(report),
        f"  {ts_detail(report)}",
        (
            f"  priced with table {report.price_table_hash} "
            f"checked {report.price_table_checked} @ {report.git_sha}"
        ),
    ]
    if report.trajectory.max_bundle_tokens is not None:
        lines.append(
            f"  max handoff bundle: {report.trajectory.max_bundle_tokens} tokens; "
            f"repeated tool calls: {report.trajectory.repeated_tool_calls}"
        )
    lines.extend(f"  note: {n}" for n in report.notes)
    if report.stale_reason:
        lines.append(f"  stale: {report.stale_reason}")
    lines.append("")
    lines.append(f"GATE 0: {verdict(report)}")
    if report.stale_reason:
        lines.append(
            "  Cassettes are fixture-era and the ground truth is draft; both are "
            "resolved by the re-record in Gate 1a step 7. Expected state, not a "
            "broken build."
        )
    return "\n".join(lines)


def verdict(report: EvalReport) -> str:
    """PASS, STALE, or FAIL. STALE and FAIL both exit non-zero."""
    if report.passed:
        return PASS
    if report.stale_reason:
        return STALE
    return FAIL


def ts_detail(report: EvalReport) -> str:
    return report.task_success.detail


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a run's eval line")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    payload = RunDirectory(args.run_id).read_eval()
    report = EvalReport.model_validate(payload)
    print(render(report))
    # The exit code IS the gate: a failing run must fail the command, or CI
    # would go green on a printed FAIL.
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())

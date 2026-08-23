"""Stable JSON, CSV, and Markdown projections for coordination runs."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .coordination_architecture_contracts import CoordinationRuntime
from .coordination_architecture_review import build_coordination_review_queue, review_queue_summary
from .coordination_architecture_quality import run_coordination_quality_gate


def coordination_runtime_json(runtime: CoordinationRuntime) -> str:
    return json.dumps(runtime.to_dict(), indent=2, sort_keys=True) + "\n"


def coordination_quality_json(runtime: CoordinationRuntime) -> str:
    return json.dumps(run_coordination_quality_gate(runtime).to_dict(), indent=2, sort_keys=True) + "\n"


def coordination_review_csv(runtime: CoordinationRuntime) -> str:
    queue = build_coordination_review_queue(runtime.evaluation.executions)
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=("review_id", "case_id", "operation_id", "priority", "issue_codes", "sla_band", "state", "content_address"),
        lineterminator="\n",
    )
    writer.writeheader()
    for item in queue:
        writer.writerow(
            {
                "review_id": item.review_id,
                "case_id": item.case_id,
                "operation_id": item.operation_id,
                "priority": item.priority,
                "issue_codes": "|".join(item.issue_codes),
                "sla_band": item.sla_band,
                "state": item.state.value,
                "content_address": item.content_address,
            }
        )
    return output.getvalue()


def coordination_summary(runtime: CoordinationRuntime) -> dict[str, Any]:
    queue = build_coordination_review_queue(runtime.evaluation.executions)
    quality = run_coordination_quality_gate(runtime)
    return {
        "run_id": runtime.run_id,
        "fixture_id": runtime.fixture_id,
        "state": runtime.state.value,
        "stage_count": len(runtime.stages),
        "operation_count": len(runtime.plan.nodes),
        "case_count": len(runtime.evaluation.executions),
        "accepted_cases": runtime.evaluation.passed_cases,
        "failed_cases": runtime.evaluation.failed_cases,
        "review_queue": review_queue_summary(queue),
        "quality": {"accepted": quality.accepted, "passed_checks": quality.passed_checks, "failed_checks": quality.failed_checks},
        "content_address": runtime.content_address,
    }


def coordination_report_markdown(runtime: CoordinationRuntime) -> str:
    summary = coordination_summary(runtime)
    lines = [
        "# Coordination architecture runtime",
        "",
        "This report is a public aggregate coordination-control projection.",
        "",
        f"- Run: `{summary['run_id']}`",
        f"- Fixture: `{summary['fixture_id']}`",
        f"- State: `{summary['state']}`",
        f"- Stages: `{summary['stage_count']}`",
        f"- Operations: `{summary['operation_count']}`",
        f"- Cases: `{summary['case_count']}`",
        f"- Reconciled cases: `{summary['accepted_cases']}`",
        f"- Review queue: `{summary['review_queue']['total']}`",
        f"- Quality: `{summary['quality']['passed_checks']}/{summary['quality']['passed_checks'] + summary['quality']['failed_checks']}` checks passed",
        "",
        "Controls remain review-only; this projection does not make biological,",
        "clinical, performance, or treatment claims.",
        "",
    ]
    return "\n".join(lines)


__all__ = ["coordination_runtime_json", "coordination_quality_json", "coordination_review_csv", "coordination_summary", "coordination_report_markdown"]

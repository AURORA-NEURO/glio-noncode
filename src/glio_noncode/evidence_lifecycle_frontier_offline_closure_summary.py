"""Deep reviewer summaries for every D14 closure projection."""

from __future__ import annotations

import csv
import io
from collections import Counter
from typing import Any

from .evidence_lifecycle_frontier_offline_closure_contracts import (
    EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_OPERATION_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_REVIEW_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_SCENARIO_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
    EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT,
    EvidenceLifecycleClosureOperationSummary,
    EvidenceLifecycleClosureSummary,
    EvidenceLifecycleClosureSummaryAudit,
    evidence_lifecycle_closure_check,
)
from .evidence_lifecycle_frontier_offline_closure_support import all_rows, csv_text
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .serialization import canonical_json, content_hash

EVIDENCE_LIFECYCLE_CLOSURE_SUMMARY_VERSION = "evidence-lifecycle-closure-summary-v1"


def _operation_summary(
    operation: str,
    records: tuple[dict[str, Any], ...],
    executions: tuple[dict[str, Any], ...],
    checks: tuple[dict[str, Any], ...],
    queue: tuple[dict[str, Any], ...],
) -> EvidenceLifecycleClosureOperationSummary:
    selected = tuple(row for row in records if row.get("operation") == operation)
    ids = {row.get("record_id") for row in selected}
    selected_exec = tuple(row for row in executions if row.get("record_id") in ids)
    selected_checks = tuple(row for row in checks if row.get("record_id") in ids)
    selected_queue = tuple(row for row in queue if row.get("record_id") in ids)
    states = tuple(
        sorted(Counter(str(row.get("observed_state", "unknown")) for row in selected_exec).items())
    )
    body = {
        "operation": operation,
        "record_count": len(selected),
        "positive_count": sum(row.get("role") == "positive" for row in selected),
        "control_count": sum(row.get("role") == "control" for row in selected),
        "accepted_count": sum(bool(row.get("accepted")) for row in selected_exec),
        "held_count": sum(row.get("disposition") == "hold_for_repair" for row in selected_queue),
        "issue_count": sum(bool(row.get("issue_codes")) for row in selected_exec),
        "check_count": len(selected_checks),
        "passed_check_count": sum(bool(row.get("passed")) for row in selected_checks),
        "states": states,
    }
    return EvidenceLifecycleClosureOperationSummary(
        **body,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-operation-summary"),
    )


def build_evidence_lifecycle_closure_summary(
    bundle: EvidenceLifecycleOfflineBundle,
) -> EvidenceLifecycleClosureSummary:
    rows = all_rows(bundle)
    operations = tuple(sorted(str(row.get("operation")) for row in rows["operations"]))
    operation_summaries = tuple(
        _operation_summary(
            operation, rows["records"], rows["executions"], rows["checks"], rows["queue"]
        )
        for operation in operations
    )
    queue_counts = Counter(str(row.get("disposition")) for row in rows["queue"])
    state_counts = Counter(str(row.get("observed_state", "unknown")) for row in rows["records"])
    issue_count = sum(bool(row.get("issue_codes")) for row in rows["executions"])
    counters = {
        "artifact_count": len(rows["artifacts"]),
        "record_count": len(rows["records"]),
        "source_count": len(rows["sources"]),
        "operation_count": len(rows["operations"]),
        "execution_count": len(rows["executions"]),
        "evaluation_check_count": len(rows["checks"]),
        "passed_evaluation_check_count": sum(bool(row.get("passed")) for row in rows["checks"]),
        "issue_execution_count": issue_count,
        "lineage_edge_count": len(rows["edges"]),
        "queue_count": len(rows["queue"]),
        "queue_ready_count": queue_counts.get("ready_for_review", 0),
        "queue_held_count": queue_counts.get("hold_for_repair", 0),
        "review_count": len(rows["reviews"]),
        "scenario_count": len(rows["scenarios"]),
        "source_runtime_stage_count": len(rows["stages"]),
        "source_observability_event_count": len(rows["events"]),
    }
    states = tuple(
        {
            "state": state,
            "record_count": count,
            "content_address": content_hash(
                {"state": state, "record_count": count},
                prefix="evidence-lifecycle-closure-summary-state",
            ),
        }
        for state, count in sorted(state_counts.items())
    )
    queue = tuple(
        {
            "disposition": disposition,
            "record_count": count,
            "content_address": content_hash(
                {"disposition": disposition, "record_count": count},
                prefix="evidence-lifecycle-closure-summary-queue",
            ),
        }
        for disposition, count in sorted(queue_counts.items())
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "counters": tuple(sorted(counters.items())),
        "operations": operation_summaries,
        "queue": queue,
        "states": states,
        "accepted": bundle.ready
        and len(operation_summaries) == EVIDENCE_LIFECYCLE_CLOSURE_OPERATION_COUNT,
    }
    return EvidenceLifecycleClosureSummary(
        **body, content_address=content_hash(body, prefix="evidence-lifecycle-closure-summary")
    )


def audit_evidence_lifecycle_closure_summary(
    summary: EvidenceLifecycleClosureSummary,
) -> EvidenceLifecycleClosureSummaryAudit:
    counter = summary.counter_map
    checks = (
        evidence_lifecycle_closure_check(
            "summary-accepted",
            "summary",
            summary.accepted,
            summary.accepted,
            True,
            "closure summary source is accepted",
        ),
        evidence_lifecycle_closure_check(
            "summary-artifacts",
            "summary",
            counter.get("artifact_count") == EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
            counter.get("artifact_count"),
            EVIDENCE_LIFECYCLE_CLOSURE_ARTIFACT_COUNT,
            "summary conserves artifacts",
        ),
        evidence_lifecycle_closure_check(
            "summary-records",
            "summary",
            counter.get("record_count") == EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            counter.get("record_count"),
            EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            "summary conserves records",
        ),
        evidence_lifecycle_closure_check(
            "summary-sources",
            "summary",
            counter.get("source_count") == EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
            counter.get("source_count"),
            EVIDENCE_LIFECYCLE_CLOSURE_SOURCE_COUNT,
            "summary conserves sources",
        ),
        evidence_lifecycle_closure_check(
            "summary-operations",
            "summary",
            counter.get("operation_count") == EVIDENCE_LIFECYCLE_CLOSURE_OPERATION_COUNT,
            counter.get("operation_count"),
            EVIDENCE_LIFECYCLE_CLOSURE_OPERATION_COUNT,
            "summary conserves operations",
        ),
        evidence_lifecycle_closure_check(
            "summary-executions",
            "summary",
            counter.get("execution_count") == EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            counter.get("execution_count"),
            EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            "summary conserves executions",
        ),
        evidence_lifecycle_closure_check(
            "summary-evaluation-checks",
            "summary",
            counter.get("evaluation_check_count")
            == EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT,
            counter.get("evaluation_check_count"),
            EVIDENCE_LIFECYCLE_CLOSURE_EVALUATION_CHECK_COUNT,
            "summary conserves evaluation checks",
        ),
        evidence_lifecycle_closure_check(
            "summary-lineage",
            "summary",
            counter.get("lineage_edge_count") == EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
            counter.get("lineage_edge_count"),
            EVIDENCE_LIFECYCLE_CLOSURE_LINEAGE_EDGE_COUNT,
            "summary conserves lineage",
        ),
        evidence_lifecycle_closure_check(
            "summary-queue",
            "summary",
            counter.get("queue_count") == EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT
            and counter.get("queue_ready_count") == 4
            and counter.get("queue_held_count") == 12,
            {
                key: counter.get(key)
                for key in ("queue_count", "queue_ready_count", "queue_held_count")
            },
            {"queue_count": 16, "queue_ready_count": 4, "queue_held_count": 12},
            "summary conserves queue dispositions",
        ),
        evidence_lifecycle_closure_check(
            "summary-review",
            "summary",
            counter.get("review_count") == EVIDENCE_LIFECYCLE_CLOSURE_REVIEW_COUNT,
            counter.get("review_count"),
            EVIDENCE_LIFECYCLE_CLOSURE_REVIEW_COUNT,
            "summary conserves reviews",
        ),
        evidence_lifecycle_closure_check(
            "summary-scenarios",
            "summary",
            counter.get("scenario_count") == EVIDENCE_LIFECYCLE_CLOSURE_SCENARIO_COUNT,
            counter.get("scenario_count"),
            EVIDENCE_LIFECYCLE_CLOSURE_SCENARIO_COUNT,
            "summary conserves scenarios",
        ),
        evidence_lifecycle_closure_check(
            "summary-runtime",
            "summary",
            counter.get("source_runtime_stage_count") == EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT,
            counter.get("source_runtime_stage_count"),
            EVIDENCE_LIFECYCLE_CLOSURE_STAGE_COUNT,
            "summary conserves source runtime stages",
        ),
        evidence_lifecycle_closure_check(
            "summary-observability",
            "summary",
            counter.get("source_observability_event_count") == 26,
            counter.get("source_observability_event_count"),
            26,
            "summary retains source observability",
        ),
        evidence_lifecycle_closure_check(
            "summary-operations-balanced",
            "summary",
            len(summary.operations) == 4
            and all(
                item.record_count == 4 and item.check_count == 28 for item in summary.operations
            ),
            [(item.operation, item.record_count, item.check_count) for item in summary.operations],
            "four operations with twenty-eight record checks",
            "operation partitions conserve records and checks",
        ),
        evidence_lifecycle_closure_check(
            "summary-state-total",
            "summary",
            sum(int(item.get("record_count", 0)) for item in summary.states)
            == EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            sum(int(item.get("record_count", 0)) for item in summary.states),
            EVIDENCE_LIFECYCLE_CLOSURE_RECORD_COUNT,
            "state projection closes records",
        ),
        evidence_lifecycle_closure_check(
            "summary-queue-total",
            "summary",
            sum(int(item.get("record_count", 0)) for item in summary.queue)
            == EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT,
            sum(int(item.get("record_count", 0)) for item in summary.queue),
            EVIDENCE_LIFECYCLE_CLOSURE_QUEUE_COUNT,
            "queue projection closes records",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": summary.bundle_id, "checks": checks, "accepted": accepted}
    return EvidenceLifecycleClosureSummaryAudit(
        bundle_id=summary.bundle_id,
        checks=checks,
        accepted=accepted,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-summary-audit"),
    )


def evidence_lifecycle_closure_summary_markdown(summary: EvidenceLifecycleClosureSummary) -> str:
    counter = summary.counter_map
    lines = [
        "# Evidence lifecycle closure summary",
        "",
        f"Bundle: `{summary.bundle_id}`",
        f"Accepted: `{str(summary.accepted).lower()}`",
        "",
        "## Denominators",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    lines.extend(f"| `{key}` | {value} |" for key, value in sorted(counter.items()))
    lines.extend(
        (
            "",
            "## Operations",
            "",
            "| Operation | Records | Positives | Controls | Accepted | Held | Issues | Checks | "
            "Passed |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        )
    )
    for item in summary.operations:
        values = [
            f"`{item.operation}`",
            str(item.record_count),
            str(item.positive_count),
            str(item.control_count),
            str(item.accepted_count),
            str(item.held_count),
            str(item.issue_count),
            str(item.check_count),
            str(item.passed_check_count),
        ]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines) + "\n"


def export_evidence_lifecycle_closure_summary_csv(summary: EvidenceLifecycleClosureSummary) -> str:
    fields = (
        "operation",
        "record_count",
        "positive_count",
        "control_count",
        "accepted_count",
        "held_count",
        "issue_count",
        "check_count",
        "passed_check_count",
        "states",
    )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in summary.operations:
        writer.writerow(
            {
                field: canonical_json(dict(item.states))
                if field == "states"
                else getattr(item, field)
                for field in fields
            }
        )
    return stream.getvalue()


def export_evidence_lifecycle_closure_summary_rows(summary: EvidenceLifecycleClosureSummary) -> str:
    """Provide a stable generic CSV for downstream tabular tooling."""

    rows = [{"resource": "counter", "key": key, "value": value} for key, value in summary.counters]
    rows.extend({"resource": "queue", **item} for item in summary.queue)
    rows.extend({"resource": "state", **item} for item in summary.states)
    return csv_text(rows)


__all__ = [
    "EVIDENCE_LIFECYCLE_CLOSURE_SUMMARY_VERSION",
    "audit_evidence_lifecycle_closure_summary",
    "build_evidence_lifecycle_closure_summary",
    "evidence_lifecycle_closure_summary_markdown",
    "export_evidence_lifecycle_closure_summary_csv",
    "export_evidence_lifecycle_closure_summary_rows",
]

"""Operation, state, severity, and denominator summaries for the D15 closure."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .serialization import content_hash
from .workbench_release_frontier_offline_closure_contracts import (
    WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
    WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT,
    WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_OPERATION_COUNT,
    WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
    WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
    WORKBENCH_RELEASE_CLOSURE_VIEW_COUNT,
    WorkbenchReleaseClosureOperationSummary,
    WorkbenchReleaseClosureSummary,
    WorkbenchReleaseClosureSummaryAudit,
    workbench_release_closure_check,
)
from .workbench_release_frontier_offline_closure_support import all_rows, csv_text
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle

WORKBENCH_RELEASE_CLOSURE_SUMMARY_VERSION = "workbench-release-closure-summary-v1"


def _operation_summary(
    operation: str,
    records: tuple[dict[str, Any], ...],
    executions: tuple[dict[str, Any], ...],
    checks: tuple[dict[str, Any], ...],
    validation: tuple[dict[str, Any], ...],
    evidence: tuple[dict[str, Any], ...],
    queue: tuple[dict[str, Any], ...],
) -> WorkbenchReleaseClosureOperationSummary:
    selected = tuple(row for row in records if row.get("operation") == operation)
    ids = {str(row.get("record_id")) for row in selected}
    selected_exec = tuple(row for row in executions if str(row.get("record_id")) in ids)
    selected_checks = tuple(row for row in checks if str(row.get("record_id")) in ids)
    selected_validation = tuple(row for row in validation if str(row.get("record_id")) in ids)
    selected_evidence = tuple(row for row in evidence if str(row.get("record_id")) in ids)
    selected_queue = tuple(row for row in queue if str(row.get("record_id")) in ids)
    states = tuple(
        sorted(Counter(str(row.get("observed_state", "unknown")) for row in selected_exec).items())
    )
    body = {
        "operation": operation,
        "record_count": len(selected),
        "positive_count": sum(row.get("role") == "positive" for row in selected),
        "control_count": sum(row.get("role") == "control" for row in selected),
        "accepted_count": sum(bool(row.get("accepted")) for row in selected_exec),
        "held_count": len(selected_queue),
        "issue_count": sum(bool(row.get("issue_codes")) for row in selected_exec),
        "check_count": len(selected_checks),
        "validation_count": len(selected_validation),
        "evidence_count": len(selected_evidence),
        "states": states,
    }
    return WorkbenchReleaseClosureOperationSummary(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-operation-summary"),
    )


def build_workbench_release_closure_summary(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseClosureSummary:
    """Materialize stable counters for every D15 public projection."""

    rows = all_rows(bundle)
    operations = tuple(sorted(str(row.get("operation")) for row in rows["operations"]))
    operation_summaries = tuple(
        _operation_summary(
            operation,
            rows["records"],
            rows["executions"],
            rows["checks"],
            rows["validation"],
            rows["evidence"],
            rows["queue"],
        )
        for operation in operations
    )
    state_counts = Counter(str(row.get("observed_state", "unknown")) for row in rows["records"])
    severity_counts = Counter(str(row.get("severity", "unknown")) for row in rows["diagnostics"])
    priority_counts = Counter(str(row.get("priority", "unknown")) for row in rows["queue"])
    issue_count = sum(bool(row.get("issue_codes")) for row in rows["executions"])
    counters = {
        "artifact_count": len(rows["artifacts"]),
        "record_count": len(rows["records"]),
        "source_count": len(rows["sources"]),
        "operation_count": len(rows["operations"]),
        "execution_count": len(rows["executions"]),
        "evaluation_check_count": len(rows["checks"]),
        "passed_evaluation_check_count": sum(bool(row.get("passed")) for row in rows["checks"]),
        "validation_cell_count": len(rows["validation"]),
        "passed_validation_cell_count": sum(bool(row.get("passed")) for row in rows["validation"]),
        "evidence_cell_count": len(rows["evidence"]),
        "lineage_edge_count": len(rows["edges"]),
        "view_count": len(rows["views"]),
        "queue_count": len(rows["queue"]),
        "issue_execution_count": issue_count,
        "diagnostic_count": len(rows["diagnostics"]),
        "source_runtime_stage_count": len(rows["stages"]),
        "stage_index_count": len(rows["stage_index"]),
        "control_count": len(rows["controls"]),
        "failure_case_count": len(rows["failures"]),
        "high_priority_count": priority_counts.get("high", 0),
        "medium_severity_count": severity_counts.get("medium", 0),
        "error_severity_count": severity_counts.get("error", 0),
    }
    states = tuple(
        {
            "state": state,
            "record_count": count,
            "content_address": content_hash(
                {"state": state, "record_count": count},
                prefix="workbench-release-closure-summary-state",
            ),
        }
        for state, count in sorted(state_counts.items())
    )
    severities = tuple(
        {
            "severity": severity,
            "diagnostic_count": count,
            "content_address": content_hash(
                {"severity": severity, "diagnostic_count": count},
                prefix="workbench-release-closure-summary-severity",
            ),
        }
        for severity, count in sorted(severity_counts.items())
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "counters": tuple(sorted(counters.items())),
        "operations": operation_summaries,
        "states": states,
        "severities": severities,
        "accepted": bundle.accepted
        and len(operation_summaries) == WORKBENCH_RELEASE_CLOSURE_OPERATION_COUNT,
    }
    return WorkbenchReleaseClosureSummary(
        **body,
        content_address=content_hash(body, prefix="workbench-release-closure-summary"),
    )


def audit_workbench_release_closure_summary(
    summary: WorkbenchReleaseClosureSummary,
) -> WorkbenchReleaseClosureSummaryAudit:
    """Audit summary denominators independently from the source bundle."""

    counter = summary.counter_map
    operation_shape = tuple(
        (
            item.operation,
            item.record_count,
            item.check_count,
            item.validation_count,
            item.evidence_count,
        )
        for item in summary.operations
    )
    checks = (
        workbench_release_closure_check(
            "summary-accepted",
            "summary",
            summary.accepted,
            summary.accepted,
            True,
            "summary is accepted",
        ),
        workbench_release_closure_check(
            "summary-artifacts",
            "summary",
            counter.get("artifact_count") == WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            counter.get("artifact_count"),
            WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "summary conserves artifacts",
        ),
        workbench_release_closure_check(
            "summary-records",
            "summary",
            counter.get("record_count") == WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            counter.get("record_count"),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "summary conserves records",
        ),
        workbench_release_closure_check(
            "summary-sources",
            "summary",
            counter.get("source_count") == WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
            counter.get("source_count"),
            WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
            "summary conserves sources",
        ),
        workbench_release_closure_check(
            "summary-operations",
            "summary",
            counter.get("operation_count") == WORKBENCH_RELEASE_CLOSURE_OPERATION_COUNT
            and len(summary.operations) == WORKBENCH_RELEASE_CLOSURE_OPERATION_COUNT,
            (counter.get("operation_count"), len(summary.operations)),
            WORKBENCH_RELEASE_CLOSURE_OPERATION_COUNT,
            "summary conserves operations",
        ),
        workbench_release_closure_check(
            "summary-executions",
            "summary",
            counter.get("execution_count") == WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT,
            counter.get("execution_count"),
            WORKBENCH_RELEASE_CLOSURE_EXECUTION_COUNT,
            "summary conserves executions",
        ),
        workbench_release_closure_check(
            "summary-evaluation",
            "summary",
            counter.get("evaluation_check_count")
            == WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT
            and counter.get("passed_evaluation_check_count")
            == WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
            (counter.get("evaluation_check_count"), counter.get("passed_evaluation_check_count")),
            WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
            "all evaluation checks pass",
        ),
        workbench_release_closure_check(
            "summary-validation",
            "summary",
            counter.get("validation_cell_count") == WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT
            and counter.get("passed_validation_cell_count")
            == WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
            (counter.get("validation_cell_count"), counter.get("passed_validation_cell_count")),
            WORKBENCH_RELEASE_CLOSURE_VALIDATION_CELL_COUNT,
            "all validation cells pass",
        ),
        workbench_release_closure_check(
            "summary-evidence",
            "summary",
            counter.get("evidence_cell_count") == WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            counter.get("evidence_cell_count"),
            WORKBENCH_RELEASE_CLOSURE_EVIDENCE_CELL_COUNT,
            "summary conserves evidence",
        ),
        workbench_release_closure_check(
            "summary-lineage",
            "summary",
            counter.get("lineage_edge_count") == WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            counter.get("lineage_edge_count"),
            WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
            "summary conserves lineage",
        ),
        workbench_release_closure_check(
            "summary-views",
            "summary",
            counter.get("view_count") == WORKBENCH_RELEASE_CLOSURE_VIEW_COUNT,
            counter.get("view_count"),
            WORKBENCH_RELEASE_CLOSURE_VIEW_COUNT,
            "summary conserves views",
        ),
        workbench_release_closure_check(
            "summary-queue",
            "summary",
            counter.get("queue_count") == WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT
            and counter.get("high_priority_count") == 4,
            (counter.get("queue_count"), counter.get("high_priority_count")),
            (WORKBENCH_RELEASE_CLOSURE_QUEUE_COUNT, 4),
            "summary conserves review queue",
        ),
        workbench_release_closure_check(
            "summary-diagnostics",
            "summary",
            counter.get("diagnostic_count") == WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
            counter.get("diagnostic_count"),
            WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
            "summary conserves diagnostics",
        ),
        workbench_release_closure_check(
            "summary-runtime",
            "summary",
            counter.get("source_runtime_stage_count")
            == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT
            and counter.get("stage_index_count") == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            (counter.get("source_runtime_stage_count"), counter.get("stage_index_count")),
            WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
            "summary conserves runtime stages",
        ),
        workbench_release_closure_check(
            "summary-controls",
            "summary",
            counter.get("control_count") == 4,
            counter.get("control_count"),
            4,
            "summary conserves control rows",
        ),
        workbench_release_closure_check(
            "summary-failures",
            "summary",
            counter.get("failure_case_count") == 4,
            counter.get("failure_case_count"),
            4,
            "summary conserves failure fixtures",
        ),
        workbench_release_closure_check(
            "summary-operations-balanced",
            "summary",
            all(
                item.record_count == 4
                and item.check_count == 20
                and item.validation_count == 20
                and item.evidence_count == 4
                for item in summary.operations
            ),
            operation_shape,
            "four records, twenty checks, twenty cells, four evidence rows per operation",
            "operation partitions balance",
        ),
        workbench_release_closure_check(
            "summary-states",
            "summary",
            sum(int(item["record_count"]) for item in summary.states)
            == WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            sum(int(item["record_count"]) for item in summary.states),
            WORKBENCH_RELEASE_CLOSURE_RECORD_COUNT,
            "state partitions conserve records",
        ),
        workbench_release_closure_check(
            "summary-severities",
            "summary",
            sum(int(item["diagnostic_count"]) for item in summary.severities)
            == WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
            sum(int(item["diagnostic_count"]) for item in summary.severities),
            WORKBENCH_RELEASE_CLOSURE_DIAGNOSTIC_COUNT,
            "severity partitions conserve diagnostics",
        ),
    )
    body = {
        "bundle_id": summary.bundle_id,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    return WorkbenchReleaseClosureSummaryAudit(
        **body, content_address=content_hash(body, prefix="workbench-release-closure-summary-audit")
    )


def workbench_release_closure_summary_csv(summary: WorkbenchReleaseClosureSummary) -> str:
    """Export operation summaries as deterministic CSV."""

    return csv_text(item.to_dict() for item in summary.operations)


def workbench_release_closure_summary_markdown(summary: WorkbenchReleaseClosureSummary) -> str:
    lines = [
        "# Workbench release closure summary",
        "",
        f"Bundle: `{summary.bundle_id}`",
        f"Accepted: `{str(summary.accepted).lower()}`",
        "",
        "| Counter | Value |",
        "| --- | ---: |",
    ]
    lines.extend(f"| `{key}` | `{value}` |" for key, value in summary.counters)
    lines.extend(
        [
            "",
            "| Operation | Records | Checks | Validation | Evidence | Issues |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    lines.extend(
        f"| `{item.operation}` | {item.record_count} | {item.check_count} | "
        f"{item.validation_count} | {item.evidence_count} | {item.issue_count} |"
        for item in summary.operations
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "WORKBENCH_RELEASE_CLOSURE_SUMMARY_VERSION",
    "audit_workbench_release_closure_summary",
    "build_workbench_release_closure_summary",
    "workbench_release_closure_summary_csv",
    "workbench_release_closure_summary_markdown",
]

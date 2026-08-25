"""Reviewer summaries for D16 deployment closure denominators."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .deployment_frontier_offline_closure_contracts import (
    DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EXECUTION_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_OPERATION_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_VIEW_COUNT,
    DeploymentFrontierClosureOperationSummary,
    DeploymentFrontierClosureSummary,
    DeploymentFrontierClosureSummaryAudit,
    deployment_frontier_closure_check,
)
from .deployment_frontier_offline_closure_support import all_rows, csv_text
from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .serialization import content_hash

DEPLOYMENT_FRONTIER_CLOSURE_SUMMARY_VERSION = "deployment-frontier-closure-summary-v1"


def _operation_summary(
    operation: str,
    records: tuple[dict[str, Any], ...],
    executions: tuple[dict[str, Any], ...],
    checks: tuple[dict[str, Any], ...],
    validation: tuple[dict[str, Any], ...],
    evidence: tuple[dict[str, Any], ...],
    queue: tuple[dict[str, Any], ...],
) -> DeploymentFrontierClosureOperationSummary:
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
    return DeploymentFrontierClosureOperationSummary(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-closure-operation-summary"),
    )


def build_deployment_frontier_closure_summary(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierClosureSummary:
    rows = all_rows(bundle)
    operation_names = tuple(sorted(str(row.get("operation")) for row in rows["operations"]))
    operations = tuple(
        _operation_summary(
            operation,
            rows["records"],
            rows["executions"],
            rows["checks"],
            rows["validation"],
            rows["evidence"],
            rows["queue"],
        )
        for operation in operation_names
    )
    state_counts = Counter(str(row.get("expected_state", "unknown")) for row in rows["records"])
    severity_counts = Counter(str(row.get("severity", "unknown")) for row in rows["diagnostics"])
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
        "runtime_stage_count": len(rows["stages"]),
        "stage_index_count": len(rows["stage_index"]),
        "audit_event_count": len(rows["audit_events"]),
        "transcript_event_count": len(rows["transcript_events"]),
        "trace_observation_count": len(rows["trace_observations"]),
        "control_count": len(rows["controls"]),
        "failure_case_count": len(rows["failures"]),
        "blocking_diagnostic_count": severity_counts.get("blocking", 0),
    }
    states = tuple(
        {
            "state": state,
            "record_count": count,
            "content_address": content_hash(
                {"state": state, "record_count": count},
                prefix="deployment-frontier-closure-summary-state",
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
                prefix="deployment-frontier-closure-summary-severity",
            ),
        }
        for severity, count in sorted(severity_counts.items())
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "counters": tuple(sorted(counters.items())),
        "operations": operations,
        "states": states,
        "severities": severities,
        "accepted": bundle.accepted
        and len(operations) == DEPLOYMENT_FRONTIER_CLOSURE_OPERATION_COUNT,
    }
    return DeploymentFrontierClosureSummary(
        **body, content_address=content_hash(body, prefix="deployment-frontier-closure-summary")
    )


def audit_deployment_frontier_closure_summary(
    summary: DeploymentFrontierClosureSummary,
) -> DeploymentFrontierClosureSummaryAudit:
    counter = summary.counter_map
    shape = tuple(
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
        deployment_frontier_closure_check(
            "summary-accepted",
            "summary",
            summary.accepted,
            summary.accepted,
            True,
            "summary is accepted",
        ),
        deployment_frontier_closure_check(
            "summary-artifacts",
            "summary",
            counter.get("artifact_count") == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            counter.get("artifact_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            "summary conserves artifacts",
        ),
        deployment_frontier_closure_check(
            "summary-sources",
            "summary",
            counter.get("source_count") == DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            counter.get("source_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            "summary conserves sources",
        ),
        deployment_frontier_closure_check(
            "summary-records",
            "summary",
            counter.get("record_count") == DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            counter.get("record_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            "summary conserves records",
        ),
        deployment_frontier_closure_check(
            "summary-operations",
            "summary",
            counter.get("operation_count") == DEPLOYMENT_FRONTIER_CLOSURE_OPERATION_COUNT
            and len(summary.operations) == DEPLOYMENT_FRONTIER_CLOSURE_OPERATION_COUNT,
            (counter.get("operation_count"), len(summary.operations)),
            DEPLOYMENT_FRONTIER_CLOSURE_OPERATION_COUNT,
            "summary conserves operations",
        ),
        deployment_frontier_closure_check(
            "summary-executions",
            "summary",
            counter.get("execution_count") == DEPLOYMENT_FRONTIER_CLOSURE_EXECUTION_COUNT,
            counter.get("execution_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_EXECUTION_COUNT,
            "summary conserves executions",
        ),
        deployment_frontier_closure_check(
            "summary-evaluation",
            "summary",
            counter.get("evaluation_check_count")
            == DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT
            and counter.get("passed_evaluation_check_count")
            == DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            (counter.get("evaluation_check_count"), counter.get("passed_evaluation_check_count")),
            DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            "evaluation checks pass",
        ),
        deployment_frontier_closure_check(
            "summary-validation",
            "summary",
            counter.get("validation_cell_count")
            == DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT
            and counter.get("passed_validation_cell_count")
            == DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
            (counter.get("validation_cell_count"), counter.get("passed_validation_cell_count")),
            DEPLOYMENT_FRONTIER_CLOSURE_VALIDATION_CELL_COUNT,
            "validation cells pass",
        ),
        deployment_frontier_closure_check(
            "summary-evidence",
            "summary",
            counter.get("evidence_cell_count") == DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
            counter.get("evidence_cell_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_EVIDENCE_CELL_COUNT,
            "summary conserves evidence",
        ),
        deployment_frontier_closure_check(
            "summary-lineage",
            "summary",
            counter.get("lineage_edge_count") == DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            counter.get("lineage_edge_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            "summary conserves lineage",
        ),
        deployment_frontier_closure_check(
            "summary-views",
            "summary",
            counter.get("view_count") == DEPLOYMENT_FRONTIER_CLOSURE_VIEW_COUNT,
            counter.get("view_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_VIEW_COUNT,
            "summary conserves views",
        ),
        deployment_frontier_closure_check(
            "summary-queue",
            "summary",
            counter.get("queue_count") == DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
            counter.get("queue_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_QUEUE_COUNT,
            "summary conserves queue",
        ),
        deployment_frontier_closure_check(
            "summary-diagnostics",
            "summary",
            counter.get("diagnostic_count") == DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
            counter.get("diagnostic_count"),
            DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
            "summary conserves diagnostics",
        ),
        deployment_frontier_closure_check(
            "summary-runtime",
            "summary",
            counter.get("runtime_stage_count") == DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT
            and counter.get("stage_index_count") == DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            (counter.get("runtime_stage_count"), counter.get("stage_index_count")),
            DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            "summary conserves runtime stages",
        ),
        deployment_frontier_closure_check(
            "summary-audit-log",
            "summary",
            counter.get("audit_event_count") == 32,
            counter.get("audit_event_count"),
            32,
            "summary conserves audit events",
        ),
        deployment_frontier_closure_check(
            "summary-transcript",
            "summary",
            counter.get("transcript_event_count") == 33,
            counter.get("transcript_event_count"),
            33,
            "summary conserves transcript events",
        ),
        deployment_frontier_closure_check(
            "summary-trace",
            "summary",
            counter.get("trace_observation_count") == 37,
            counter.get("trace_observation_count"),
            37,
            "summary conserves trace observations",
        ),
        deployment_frontier_closure_check(
            "summary-controls",
            "summary",
            counter.get("control_count") == 12,
            counter.get("control_count"),
            12,
            "summary conserves controls",
        ),
        deployment_frontier_closure_check(
            "summary-failures",
            "summary",
            counter.get("failure_case_count") == 12,
            counter.get("failure_case_count"),
            12,
            "summary conserves failure cases",
        ),
        deployment_frontier_closure_check(
            "summary-operation-balance",
            "summary",
            all(
                item.record_count == 4
                and item.check_count == 20
                and item.validation_count == 16
                and item.evidence_count == 4
                for item in summary.operations
            ),
            shape,
            "four records, twenty checks, sixteen validation cells, four evidence "
            "rows per operation",
            "operation partitions balance",
        ),
        deployment_frontier_closure_check(
            "summary-state-partition",
            "summary",
            sum(int(item["record_count"]) for item in summary.states)
            == DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            sum(int(item["record_count"]) for item in summary.states),
            DEPLOYMENT_FRONTIER_CLOSURE_RECORD_COUNT,
            "states conserve records",
        ),
        deployment_frontier_closure_check(
            "summary-severity-partition",
            "summary",
            sum(int(item["diagnostic_count"]) for item in summary.severities)
            == DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
            sum(int(item["diagnostic_count"]) for item in summary.severities),
            DEPLOYMENT_FRONTIER_CLOSURE_DIAGNOSTIC_COUNT,
            "severities conserve diagnostics",
        ),
    )
    body = {
        "bundle_id": summary.bundle_id,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    return DeploymentFrontierClosureSummaryAudit(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-closure-summary-audit"),
    )


def deployment_frontier_closure_summary_csv(summary: DeploymentFrontierClosureSummary) -> str:
    return csv_text(item.to_dict() for item in summary.operations)


def deployment_frontier_closure_summary_markdown(summary: DeploymentFrontierClosureSummary) -> str:
    lines = [
        "# Deployment frontier closure summary",
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
    "DEPLOYMENT_FRONTIER_CLOSURE_SUMMARY_VERSION",
    "audit_deployment_frontier_closure_summary",
    "build_deployment_frontier_closure_summary",
    "deployment_frontier_closure_summary_csv",
    "deployment_frontier_closure_summary_markdown",
]

"""Compact reviewer summaries derived from D15 offline artifacts."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .serialization import canonical_json, content_hash, jsonable
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle
from .workbench_release_frontier_offline_query import _payload, _rows

WORKBENCH_RELEASE_OFFLINE_SUMMARY_VERSION = "workbench-release-offline-summary-v1"


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineOperationSummary:
    operation: str
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    issue_count: int
    states: tuple[tuple[str, int], ...]
    content_address: str

    @property
    def acceptance_rate(self) -> float:
        return (
            0.0 if self.positive_count == 0 else round(self.accepted_count / self.positive_count, 6)
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"acceptance_rate": self.acceptance_rate}


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineSummary:
    version: str
    bundle_id: str
    fixture_id: str
    boundary: str
    record_count: int
    source_count: int
    positive_count: int
    control_count: int
    execution_count: int
    evaluation_check_count: int
    passed_evaluation_check_count: int
    runtime_stage_count: int
    lineage_edge_count: int
    evidence_cell_count: int
    validation_cell_count: int
    review_row_count: int
    queue_row_count: int
    blocked_count: int
    review_count: int
    accepted_count: int
    operation_summaries: tuple[WorkbenchReleaseOfflineOperationSummary, ...]
    accepted: bool
    content_address: str

    @property
    def evaluation_pass_rate(self) -> float:
        return (
            0.0
            if self.evaluation_check_count == 0
            else round(self.passed_evaluation_check_count / self.evaluation_check_count, 6)
        )

    @property
    def queue_hold_rate(self) -> float:
        return (
            0.0 if self.queue_row_count == 0 else round(self.queue_row_count / self.record_count, 6)
        )

    def by_operation(self, operation: str) -> WorkbenchReleaseOfflineOperationSummary:
        return next(item for item in self.operation_summaries if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "evaluation_pass_rate": self.evaluation_pass_rate,
            "queue_hold_rate": self.queue_hold_rate,
        }


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineSummaryCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineSummaryAudit:
    bundle_id: str
    checks: tuple[WorkbenchReleaseOfflineSummaryCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": sum(item.passed for item in self.checks),
            "failed_count": sum(not item.passed for item in self.checks),
        }


def _operation_summary(
    operation: str, records: tuple[dict[str, Any], ...], executions: dict[str, dict[str, Any]]
) -> WorkbenchReleaseOfflineOperationSummary:
    selected = tuple(item for item in records if item.get("operation") == operation)
    selected_executions = tuple(executions.get(str(item.get("record_id")), {}) for item in selected)
    states: dict[str, int] = {}
    for item in selected_executions:
        state = str(item.get("observed_state", "missing"))
        states[state] = states.get(state, 0) + 1
    body = {
        "operation": operation,
        "record_count": len(selected),
        "positive_count": sum(item.get("role") == "positive" for item in selected),
        "control_count": sum(item.get("role") == "control" for item in selected),
        "accepted_count": sum(not item.get("issue_codes") for item in selected_executions),
        "issue_count": sum(bool(item.get("issue_codes")) for item in selected_executions),
        "states": tuple(sorted(states.items())),
    }
    return WorkbenchReleaseOfflineOperationSummary(
        **body,
        content_address=content_hash(body, prefix="workbench-release-offline-operation-summary"),
    )


def build_workbench_release_offline_summary(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseOfflineSummary:
    """Build a bounded denominator summary without embedding payload text."""

    records = _rows(bundle, "fixture", "records")
    sources = _rows(bundle, "fixture", "sources")
    executions = {
        str(item.get("record_id")): item for item in _rows(bundle, "evaluation", "executions")
    }
    states = [str(item.get("observed_state", "")) for item in executions.values()]
    operations = tuple(sorted({str(item.get("operation")) for item in records}))
    operation_summaries = tuple(
        _operation_summary(operation, records, executions) for operation in operations
    )
    lineage = _payload(bundle, "lineage") or {}
    evidence = _payload(bundle, "evidence") or {}
    validation = _payload(bundle, "validation") or {}
    body = {
        "version": WORKBENCH_RELEASE_OFFLINE_SUMMARY_VERSION,
        "bundle_id": bundle.bundle_id,
        "fixture_id": bundle.fixture_id,
        "boundary": bundle.boundary,
        "record_count": len(records),
        "source_count": len(sources),
        "positive_count": sum(item.get("role") == "positive" for item in records),
        "control_count": sum(item.get("role") == "control" for item in records),
        "execution_count": len(executions),
        "evaluation_check_count": len(_rows(bundle, "evaluation", "checks")),
        "passed_evaluation_check_count": sum(
            bool(item.get("passed")) for item in _rows(bundle, "evaluation", "checks")
        ),
        "runtime_stage_count": len(_rows(bundle, "runtime", "stages")),
        "lineage_edge_count": sum(
            len(value) for value in lineage.get("source_to_records", {}).values()
        )
        + len(lineage.get("record_to_execution", {}))
        if isinstance(lineage.get("source_to_records"), dict)
        and isinstance(lineage.get("record_to_execution"), dict)
        else 0,
        "evidence_cell_count": len(evidence.get("cells", ()))
        if isinstance(evidence.get("cells"), list)
        else 0,
        "validation_cell_count": len(validation.get("cells", ()))
        if isinstance(validation.get("cells"), list)
        else 0,
        "review_row_count": len(_rows(bundle, "view", "rows")),
        "queue_row_count": len(_rows(bundle, "review-queue", "rows")),
        "blocked_count": states.count("blocked"),
        "review_count": states.count("review"),
        "accepted_count": sum(not item.get("issue_codes") for item in executions.values()),
        "operation_summaries": operation_summaries,
        "accepted": bundle.ready
        and len(records) == 16
        and len(sources) == 5
        and len(executions) == 16
        and len(operation_summaries) == 4,
    }
    return WorkbenchReleaseOfflineSummary(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-summary")
    )


def audit_workbench_release_offline_summary(
    summary: WorkbenchReleaseOfflineSummary,
) -> WorkbenchReleaseOfflineSummaryAudit:
    def check(
        check_id: str, passed: bool, observed: Any, required: Any, detail: str
    ) -> WorkbenchReleaseOfflineSummaryCheck:
        body = {
            "check_id": check_id,
            "passed": bool(passed),
            "observed": observed,
            "required": required,
            "detail": detail,
        }
        return WorkbenchReleaseOfflineSummaryCheck(
            **body,
            content_address=content_hash(body, prefix="workbench-release-offline-summary-check"),
        )

    checks = (
        check(
            "summary-accepted",
            summary.accepted,
            summary.accepted,
            True,
            "summary source bundle is accepted",
        ),
        check(
            "record-count",
            summary.record_count == 16,
            summary.record_count,
            16,
            "summary conserves records",
        ),
        check(
            "source-count",
            summary.source_count == 5,
            summary.source_count,
            5,
            "summary conserves sources",
        ),
        check(
            "positive-count",
            summary.positive_count == 4,
            summary.positive_count,
            4,
            "summary conserves positives",
        ),
        check(
            "control-count",
            summary.control_count == 12,
            summary.control_count,
            12,
            "summary conserves controls",
        ),
        check(
            "execution-count",
            summary.execution_count == 16,
            summary.execution_count,
            16,
            "summary conserves executions",
        ),
        check(
            "evaluation-check-count",
            summary.evaluation_check_count == 80,
            summary.evaluation_check_count,
            80,
            "summary conserves evaluation checks",
        ),
        check(
            "stage-count",
            summary.runtime_stage_count == 49,
            summary.runtime_stage_count,
            49,
            "summary conserves runtime stages",
        ),
        check(
            "lineage-count",
            summary.lineage_edge_count == 52,
            summary.lineage_edge_count,
            52,
            "summary conserves source and record lineage links",
        ),
        check(
            "evidence-count",
            summary.evidence_cell_count == 16,
            summary.evidence_cell_count,
            16,
            "summary conserves evidence cells",
        ),
        check(
            "validation-count",
            summary.validation_cell_count == 80,
            summary.validation_cell_count,
            80,
            "summary conserves validation checks",
        ),
        check(
            "review-count",
            summary.review_row_count == 16,
            summary.review_row_count,
            16,
            "summary conserves review rows",
        ),
        check(
            "queue-count",
            summary.queue_row_count == 12,
            summary.queue_row_count,
            12,
            "summary conserves held queue rows",
        ),
        check(
            "operation-count",
            len(summary.operation_summaries) == 4
            and all(item.record_count == 4 for item in summary.operation_summaries),
            len(summary.operation_summaries),
            4,
            "summary conserves four balanced operations",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": summary.bundle_id, "checks": checks, "accepted": accepted}
    return WorkbenchReleaseOfflineSummaryAudit(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-summary-audit")
    )


def workbench_release_offline_summary_markdown(summary: WorkbenchReleaseOfflineSummary) -> str:
    lines = [
        "# Workbench release offline summary",
        "",
        f"Bundle: `{summary.bundle_id}`",
        f"Boundary: `{summary.boundary}`",
        f"Accepted: `{str(summary.accepted).lower()}`",
        "",
        "| Operation | Records | Positives | Controls | Accepted | Issues | States |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    lines.extend(
        f"| `{item.operation}` | {item.record_count} | {item.positive_count} | "
        f"{item.control_count} | {item.accepted_count} | {item.issue_count} | "
        f"{canonical_json(dict(item.states))} |"
        for item in summary.operation_summaries
    )
    lines.extend(
        (
            "",
            "## Denominators",
            "",
            f"- Records: {summary.record_count}",
            f"- Sources: {summary.source_count}",
            f"- Evaluation checks: "
            f"{summary.passed_evaluation_check_count}/{summary.evaluation_check_count}",
            f"- Runtime stages: {summary.runtime_stage_count}",
            f"- Lineage links: {summary.lineage_edge_count}",
            f"- Review queue: {summary.queue_row_count} held",
        )
    )
    return "\n".join(lines) + "\n"


def export_workbench_release_offline_summary_csv(summary: WorkbenchReleaseOfflineSummary) -> str:
    stream = io.StringIO()
    fields = (
        "operation",
        "record_count",
        "positive_count",
        "control_count",
        "accepted_count",
        "issue_count",
        "acceptance_rate",
        "states",
    )
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in summary.operation_summaries:
        writer.writerow(
            {
                "operation": item.operation,
                "record_count": item.record_count,
                "positive_count": item.positive_count,
                "control_count": item.control_count,
                "accepted_count": item.accepted_count,
                "issue_count": item.issue_count,
                "acceptance_rate": item.acceptance_rate,
                "states": canonical_json(dict(item.states)),
            }
        )
    return stream.getvalue()


__all__ = [
    "WORKBENCH_RELEASE_OFFLINE_SUMMARY_VERSION",
    "WorkbenchReleaseOfflineOperationSummary",
    "WorkbenchReleaseOfflineSummary",
    "WorkbenchReleaseOfflineSummaryAudit",
    "WorkbenchReleaseOfflineSummaryCheck",
    "audit_workbench_release_offline_summary",
    "build_workbench_release_offline_summary",
    "export_workbench_release_offline_summary_csv",
    "workbench_release_offline_summary_markdown",
]

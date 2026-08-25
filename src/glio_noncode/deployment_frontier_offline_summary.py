"""Compact release summaries and reviewer exports for D16 handoffs."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .deployment_frontier_offline_query import _payload, _rows
from .serialization import canonical_json, content_hash, jsonable


DEPLOYMENT_FRONTIER_OFFLINE_SUMMARY_VERSION = "deployment-frontier-offline-summary-v1"


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineOperationSummary:
    operation: str
    record_count: int
    positive_count: int
    control_count: int
    accepted_count: int
    issue_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineSummary:
    version: str
    bundle_id: str
    fixture_id: str
    accepted: bool
    artifact_count: int
    source_count: int
    record_count: int
    positive_count: int
    control_count: int
    execution_count: int
    evaluation_check_count: int
    runtime_stage_count: int
    operation_count: int
    issue_category_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    operation_summaries: tuple[DeploymentFrontierOfflineOperationSummary, ...]
    queue_row_count: int
    lineage_edge_count: int
    component_count: int
    passed_bundle_checks: int
    failed_bundle_checks: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineSummaryCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineSummaryAudit:
    bundle_id: str
    checks: tuple[DeploymentFrontierOfflineSummaryCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": sum(item.passed for item in self.checks),
            "failed_count": sum(not item.passed for item in self.checks),
        }


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> DeploymentFrontierOfflineSummaryCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return DeploymentFrontierOfflineSummaryCheck(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-summary-check"),
    )


def _component_count(bundle: DeploymentFrontierOfflineBundle) -> int:
    return sum(
        item.kind.value not in {"fixture", "runtime", "review_csv", "sources_csv", "executions_csv"}
        for item in bundle.artifacts
    )


def build_deployment_frontier_offline_summary(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierOfflineSummary:
    records = _rows(bundle, "fixture", "records")
    sources = _rows(bundle, "fixture", "sources")
    executions = _rows(bundle, "evaluation", "executions")
    checks = _rows(bundle, "evaluation", "checks")
    stages = _rows(bundle, "runtime", "stages")
    queue_value = _payload(bundle, "queue")
    queue = (
        tuple(queue_value.get("items", ()))
        if isinstance(queue_value, dict)
        else _rows(bundle, "queue", "rows")
    )
    lineage = _payload(bundle, "lineage")
    state_value = _payload(bundle, "state-index") or {}
    issue_value = _payload(bundle, "issue-index") or {}
    state_counts = (
        dict(state_value.get("state_counts", {})) if isinstance(state_value, dict) else {}
    )
    issue_counts = (
        dict(issue_value.get("issue_counts", {})) if isinstance(issue_value, dict) else {}
    )
    operation_summaries: list[DeploymentFrontierOfflineOperationSummary] = []
    for operation in sorted({str(item.get("operation")) for item in records}):
        selected = tuple(item for item in executions if item.get("operation") == operation)
        body = {
            "operation": operation,
            "record_count": len(selected),
            "positive_count": sum(item.get("role") == "positive" for item in selected),
            "control_count": sum(item.get("role") == "control" for item in selected),
            "accepted_count": sum(bool(item.get("accepted")) for item in selected),
            "issue_count": sum(len(item.get("issue_codes", ())) for item in selected),
        }
        operation_summaries.append(
            DeploymentFrontierOfflineOperationSummary(
                **body,
                content_address=content_hash(
                    body, prefix="deployment-frontier-offline-operation-summary"
                ),
            )
        )
    body = {
        "version": DEPLOYMENT_FRONTIER_OFFLINE_SUMMARY_VERSION,
        "bundle_id": bundle.bundle_id,
        "fixture_id": bundle.fixture_id,
        "accepted": bundle.ready,
        "artifact_count": bundle.artifact_count,
        "source_count": len(sources),
        "record_count": len(records),
        "positive_count": sum(item.get("role") == "positive" for item in records),
        "control_count": sum(item.get("role") == "control" for item in records),
        "execution_count": len(executions),
        "evaluation_check_count": len(checks),
        "runtime_stage_count": len(stages),
        "operation_count": len(operation_summaries),
        "issue_category_count": len(issue_counts),
        "state_counts": state_counts,
        "issue_counts": issue_counts,
        "operation_summaries": tuple(operation_summaries),
        "queue_row_count": len(queue),
        "lineage_edge_count": len(lineage.get("edges", ())) if isinstance(lineage, dict) else 0,
        "component_count": _component_count(bundle),
        "passed_bundle_checks": bundle.passed_check_count,
        "failed_bundle_checks": bundle.failed_check_count,
    }
    return DeploymentFrontierOfflineSummary(
        **body, content_address=content_hash(body, prefix="deployment-frontier-offline-summary")
    )


def audit_deployment_frontier_offline_summary(
    summary: DeploymentFrontierOfflineSummary,
) -> DeploymentFrontierOfflineSummaryAudit:
    checks = (
        _check(
            "accepted", summary.accepted, summary.accepted, True, "summary reflects a ready bundle"
        ),
        _check(
            "artifact-count",
            summary.artifact_count == 51,
            summary.artifact_count,
            51,
            "summary conserves artifacts",
        ),
        _check(
            "source-count",
            summary.source_count == 5,
            summary.source_count,
            5,
            "summary conserves sources",
        ),
        _check(
            "record-count",
            summary.record_count == 16,
            summary.record_count,
            16,
            "summary conserves records",
        ),
        _check(
            "positive-count",
            summary.positive_count == 4,
            summary.positive_count,
            4,
            "summary conserves positive rows",
        ),
        _check(
            "control-count",
            summary.control_count == 12,
            summary.control_count,
            12,
            "summary conserves control rows",
        ),
        _check(
            "execution-count",
            summary.execution_count == 16,
            summary.execution_count,
            16,
            "summary conserves executions",
        ),
        _check(
            "evaluation-check-count",
            summary.evaluation_check_count == 80,
            summary.evaluation_check_count,
            80,
            "summary conserves evaluation checks",
        ),
        _check(
            "runtime-stage-count",
            summary.runtime_stage_count == 38,
            summary.runtime_stage_count,
            38,
            "summary conserves runtime stages",
        ),
        _check(
            "operation-count",
            summary.operation_count == 4
            and all(item.record_count == 4 for item in summary.operation_summaries),
            summary.operation_count,
            4,
            "summary conserves balanced operations",
        ),
        _check(
            "state-counts",
            sum(summary.state_counts.values()) == 16,
            summary.state_counts,
            16,
            "state counts reconcile with executions",
        ),
        _check(
            "issue-counts",
            summary.issue_category_count == 13,
            summary.issue_category_count,
            13,
            "issue categories are explicit",
        ),
        _check(
            "operation-addresses",
            all(
                item.content_address.startswith("deployment-frontier-offline-operation-summary:")
                for item in summary.operation_summaries
            ),
            True,
            True,
            "operation summaries are addressed",
        ),
        _check(
            "component-depth",
            summary.component_count >= 40,
            summary.component_count,
            ">=40",
            "major D16 component planes are retained",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": summary.bundle_id, "checks": checks, "accepted": accepted}
    return DeploymentFrontierOfflineSummaryAudit(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-summary-audit"),
    )


def export_deployment_frontier_offline_summary_csv(
    summary: DeploymentFrontierOfflineSummary,
) -> str:
    stream = io.StringIO()
    fields = (
        "operation",
        "record_count",
        "positive_count",
        "control_count",
        "accepted_count",
        "issue_count",
        "content_address",
    )
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in summary.operation_summaries:
        writer.writerow(item.to_dict())
    return stream.getvalue()


def deployment_frontier_offline_summary_markdown(summary: DeploymentFrontierOfflineSummary) -> str:
    lines = [
        "# Deployment frontier offline summary",
        "",
        f"Bundle: `{summary.bundle_id}`",
        f"Accepted: `{str(summary.accepted).lower()}`",
        f"Artifacts: `{summary.artifact_count}`",
        f"Runtime stages: `{summary.runtime_stage_count}`",
        "",
        "| Operation | Records | Positive | Controls | Accepted | Issues |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(
        f"| `{item.operation}` | {item.record_count} | {item.positive_count} | "
        f"{item.control_count} | {item.accepted_count} | {item.issue_count} |"
        for item in summary.operation_summaries
    )
    lines.extend(
        (
            "",
            "## State counts",
            "",
            "```json",
            canonical_json(summary.state_counts),
            "```",
            "",
            "## Issue counts",
            "",
            "```json",
            canonical_json(summary.issue_counts),
            "```",
        )
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "DEPLOYMENT_FRONTIER_OFFLINE_SUMMARY_VERSION",
    "DeploymentFrontierOfflineOperationSummary",
    "DeploymentFrontierOfflineSummary",
    "DeploymentFrontierOfflineSummaryAudit",
    "DeploymentFrontierOfflineSummaryCheck",
    "audit_deployment_frontier_offline_summary",
    "build_deployment_frontier_offline_summary",
    "deployment_frontier_offline_summary_markdown",
    "export_deployment_frontier_offline_summary_csv",
]

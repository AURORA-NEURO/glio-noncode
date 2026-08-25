"""Compact reviewer summaries derived from D14 offline artifacts."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from .serialization import canonical_json, content_hash, jsonable
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle

EVIDENCE_LIFECYCLE_OFFLINE_SUMMARY_VERSION = "evidence-lifecycle-offline-summary-v1"


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineOperationSummary:
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
        return 0.0 if self.positive_count == 0 else round(self.accepted_count / self.positive_count, 6)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"acceptance_rate": self.acceptance_rate}


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineSummary:
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
    observability_event_count: int
    lineage_edge_count: int
    review_row_count: int
    queue_item_count: int
    ready_queue_count: int
    held_queue_count: int
    operation_summaries: tuple[EvidenceLifecycleOfflineOperationSummary, ...]
    accepted: bool
    content_address: str

    @property
    def evaluation_pass_rate(self) -> float:
        return 0.0 if self.evaluation_check_count == 0 else round(self.passed_evaluation_check_count / self.evaluation_check_count, 6)

    @property
    def queue_hold_rate(self) -> float:
        return 0.0 if self.queue_item_count == 0 else round(self.held_queue_count / self.queue_item_count, 6)

    def by_operation(self, operation: str) -> EvidenceLifecycleOfflineOperationSummary:
        return next(item for item in self.operation_summaries if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"evaluation_pass_rate": self.evaluation_pass_rate, "queue_hold_rate": self.queue_hold_rate}


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineSummaryCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineSummaryAudit:
    bundle_id: str
    checks: tuple[EvidenceLifecycleOfflineSummaryCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": sum(item.passed for item in self.checks), "failed_count": sum(not item.passed for item in self.checks)}


def _payload(bundle: EvidenceLifecycleOfflineBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return None
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return None


def _rows(value: Any, key: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, dict) or not isinstance(value.get(key), list):
        return ()
    return tuple(item for item in value[key] if isinstance(item, dict))


def _operation_summary(operation: str, records: tuple[dict[str, Any], ...], executions: dict[str, dict[str, Any]]) -> EvidenceLifecycleOfflineOperationSummary:
    selected = tuple(item for item in records if item.get("operation") == operation)
    selected_executions = tuple(executions.get(str(item.get("record_id")), {}) for item in selected)
    states: dict[str, int] = {}
    for item in selected_executions:
        state = str(item.get("state", "missing"))
        states[state] = states.get(state, 0) + 1
    body = {
        "operation": operation,
        "record_count": len(selected),
        "positive_count": sum(item.get("role") == "positive" for item in selected),
        "control_count": sum(item.get("role") == "control" for item in selected),
        "accepted_count": sum(bool(item.get("accepted")) for item in selected_executions),
        "issue_count": sum(bool(item.get("issue_codes")) for item in selected_executions),
        "states": tuple(sorted(states.items())),
    }
    return EvidenceLifecycleOfflineOperationSummary(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-operation-summary"))


def build_evidence_lifecycle_offline_summary(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineSummary:
    """Build a bounded summary without exposing operation payload text."""

    fixture = _payload(bundle, "fixture")
    evaluation = _payload(bundle, "evaluation")
    lineage = _payload(bundle, "lineage")
    observability = _payload(bundle, "observability")
    review = _payload(bundle, "review")
    queue = _payload(bundle, "review-queue")
    records = _rows(fixture, "records")
    sources = _rows(fixture, "sources")
    executions = {str(item.get("record_id")): item for item in _rows(evaluation, "executions")}
    operations = tuple(sorted({str(item.get("operation")) for item in records}))
    operation_summaries = tuple(_operation_summary(operation, records, executions) for operation in operations)
    body = {
        "version": EVIDENCE_LIFECYCLE_OFFLINE_SUMMARY_VERSION,
        "bundle_id": bundle.bundle_id,
        "fixture_id": bundle.fixture_id,
        "boundary": bundle.boundary,
        "record_count": len(records),
        "source_count": len(sources),
        "positive_count": sum(item.get("role") == "positive" for item in records),
        "control_count": sum(item.get("role") == "control" for item in records),
        "execution_count": len(executions),
        "evaluation_check_count": len(_rows(evaluation, "checks")),
        "passed_evaluation_check_count": sum(bool(item.get("passed")) for item in _rows(evaluation, "checks")),
        "runtime_stage_count": len(_rows(_payload(bundle, "runtime"), "stages")),
        "observability_event_count": len(_rows(observability, "events")),
        "lineage_edge_count": len(_rows(lineage, "edges")),
        "review_row_count": len(_rows(review, "rows")),
        "queue_item_count": len(_rows(queue, "items")),
        "ready_queue_count": sum(item.get("disposition") == "ready_for_review" for item in _rows(queue, "items")),
        "held_queue_count": sum(item.get("disposition") == "hold_for_repair" for item in _rows(queue, "items")),
        "operation_summaries": operation_summaries,
        "accepted": bundle.ready and len(records) == 16 and len(sources) == 5 and len(executions) == 16 and len(operation_summaries) == 4,
    }
    return EvidenceLifecycleOfflineSummary(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-summary"))


def audit_evidence_lifecycle_offline_summary(summary: EvidenceLifecycleOfflineSummary) -> EvidenceLifecycleOfflineSummaryAudit:
    def check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> EvidenceLifecycleOfflineSummaryCheck:
        body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
        return EvidenceLifecycleOfflineSummaryCheck(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-summary-check"))

    checks = (
        check("summary-accepted", summary.accepted, summary.accepted, True, "summary source bundle is accepted"),
        check("record-count", summary.record_count == 16, summary.record_count, 16, "summary conserves records"),
        check("source-count", summary.source_count == 5, summary.source_count, 5, "summary conserves receipts"),
        check("positive-count", summary.positive_count == 4, summary.positive_count, 4, "summary conserves positives"),
        check("control-count", summary.control_count == 12, summary.control_count, 12, "summary conserves controls"),
        check("execution-count", summary.execution_count == 16, summary.execution_count, 16, "summary conserves executions"),
        check("evaluation-check-count", summary.evaluation_check_count == 120, summary.evaluation_check_count, 120, "summary conserves evaluation checks"),
        check("stage-count", summary.runtime_stage_count == 10, summary.runtime_stage_count, 10, "summary conserves runtime stages"),
        check("event-count", summary.observability_event_count == 26, summary.observability_event_count, 26, "summary conserves events"),
        check("lineage-count", summary.lineage_edge_count == 36, summary.lineage_edge_count, 36, "summary conserves lineage edges"),
        check("review-count", summary.review_row_count == 16, summary.review_row_count, 16, "summary conserves review rows"),
        check("queue-count", summary.queue_item_count == 16 and summary.ready_queue_count == 4 and summary.held_queue_count == 12, {"items": summary.queue_item_count, "ready": summary.ready_queue_count, "held": summary.held_queue_count}, {"items": 16, "ready": 4, "held": 12}, "summary conserves queue disposition"),
        check("operation-count", len(summary.operation_summaries) == 4 and all(item.record_count == 4 for item in summary.operation_summaries), len(summary.operation_summaries), 4, "summary conserves four balanced operations"),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": summary.bundle_id, "checks": checks, "accepted": accepted}
    return EvidenceLifecycleOfflineSummaryAudit(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-summary-audit"))


def evidence_lifecycle_offline_summary_markdown(summary: EvidenceLifecycleOfflineSummary) -> str:
    lines = ["# Evidence lifecycle offline summary", "", f"Bundle: `{summary.bundle_id}`", f"Boundary: `{summary.boundary}`", f"Accepted: `{str(summary.accepted).lower()}`", "", "| Operation | Records | Positives | Controls | Accepted | Issues | States |", "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    lines.extend(f"| `{item.operation}` | {item.record_count} | {item.positive_count} | {item.control_count} | {item.accepted_count} | {item.issue_count} | {canonical_json(dict(item.states))} |" for item in summary.operation_summaries)
    lines.extend(("", "## Denominators", "", f"- Records: {summary.record_count}", f"- Sources: {summary.source_count}", f"- Evaluation checks: {summary.passed_evaluation_check_count}/{summary.evaluation_check_count}", f"- Runtime stages: {summary.runtime_stage_count}", f"- Observability events: {summary.observability_event_count}", f"- Lineage edges: {summary.lineage_edge_count}", f"- Review queue: {summary.ready_queue_count} ready, {summary.held_queue_count} held",))
    return "\n".join(lines) + "\n"


def export_evidence_lifecycle_offline_summary_csv(summary: EvidenceLifecycleOfflineSummary) -> str:
    stream = io.StringIO()
    fields = ("operation", "record_count", "positive_count", "control_count", "accepted_count", "issue_count", "acceptance_rate", "states")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in summary.operation_summaries:
        writer.writerow({"operation": item.operation, "record_count": item.record_count, "positive_count": item.positive_count, "control_count": item.control_count, "accepted_count": item.accepted_count, "issue_count": item.issue_count, "acceptance_rate": item.acceptance_rate, "states": canonical_json(dict(item.states))})
    return stream.getvalue()


__all__ = [
    "EVIDENCE_LIFECYCLE_OFFLINE_SUMMARY_VERSION",
    "EvidenceLifecycleOfflineOperationSummary",
    "EvidenceLifecycleOfflineSummary",
    "EvidenceLifecycleOfflineSummaryAudit",
    "EvidenceLifecycleOfflineSummaryCheck",
    "audit_evidence_lifecycle_offline_summary",
    "build_evidence_lifecycle_offline_summary",
    "evidence_lifecycle_offline_summary_markdown",
    "export_evidence_lifecycle_offline_summary_csv",
]

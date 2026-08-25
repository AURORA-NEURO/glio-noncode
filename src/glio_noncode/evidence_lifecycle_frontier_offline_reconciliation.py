"""Independent denominator and address reconciliation for D14 handoffs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle

EVIDENCE_LIFECYCLE_OFFLINE_RECONCILIATION_VERSION = "evidence-lifecycle-offline-reconciliation-v1"


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineReconciliationCheck:
    check_id: str
    plane: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineReconciliationReport:
    version: str
    bundle_id: str
    checks: tuple[EvidenceLifecycleOfflineReconciliationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_count(self) -> int:
        return len(self.checks) - self.passed_count

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count, "failed_count": self.failed_count, "failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineReconciliationDelta:
    bundle_id: str
    left_address: str
    right_address: str
    changed_artifacts: tuple[str, ...]
    changed_counts: dict[str, tuple[Any, Any]]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _payload(bundle: EvidenceLifecycleOfflineBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return None
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return None


def _check(check_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str) -> EvidenceLifecycleOfflineReconciliationCheck:
    body = {"check_id": check_id, "plane": plane, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    return EvidenceLifecycleOfflineReconciliationCheck(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-reconciliation-check"))


def _list(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or not isinstance(value.get(field), list):
        return []
    return [item for item in value[field] if isinstance(item, dict)]


def _strings(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, dict) or not isinstance(value.get(field), list):
        return ()
    return tuple(str(item) for item in value[field])


def reconcile_evidence_lifecycle_offline_bundle(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineReconciliationReport:
    """Reconcile independent materialized projections without producer objects."""

    fixture = _payload(bundle, "fixture")
    catalog = _payload(bundle, "catalog")
    evaluation = _payload(bundle, "evaluation")
    metrics = _payload(bundle, "metrics")
    lineage = _payload(bundle, "lineage")
    reconciliation = _payload(bundle, "reconciliation")
    release = _payload(bundle, "release")
    replay = _payload(bundle, "replay")
    review = _payload(bundle, "review")
    queue = _payload(bundle, "review-queue")
    observability = _payload(bundle, "observability")
    runtime = _payload(bundle, "runtime")
    records = _list(fixture, "records")
    sources = _list(fixture, "sources")
    executions = _list(evaluation, "executions")
    evaluation_checks = _list(evaluation, "checks")
    catalog_records = _strings(catalog, "record_ids")
    catalog_sources = _strings(catalog, "source_ids")
    review_rows = _list(review, "rows")
    queue_items = _list(queue, "items")
    events = _list(observability, "events")
    stages = _list(runtime, "stages")
    record_ids = tuple(str(item.get("record_id")) for item in records)
    execution_ids = tuple(str(item.get("record_id")) for item in executions)
    source_ids = tuple(str(item.get("source_id")) for item in sources)
    checks = (
        _check("fixture-records", "denominator", len(records) == 16, len(records), 16, "fixture records are conserved"),
        _check("fixture-sources", "denominator", len(sources) == 5, len(sources), 5, "fixture sources are conserved"),
        _check("fixture-roles", "denominator", sum(item.get("role") == "positive" for item in records) == 4 and sum(item.get("role") == "control" for item in records) == 12, {"positive": sum(item.get("role") == "positive" for item in records), "control": sum(item.get("role") == "control" for item in records)}, {"positive": 4, "control": 12}, "positive and control denominators are balanced"),
        _check("catalog-records", "join", catalog_records == record_ids, catalog_records, record_ids, "catalog record identities equal fixture identities"),
        _check("catalog-sources", "join", catalog_sources == source_ids, catalog_sources, source_ids, "catalog source identities equal fixture identities"),
        _check("evaluation-records", "join", tuple(execution_ids) == record_ids, execution_ids, record_ids, "every fixture record has exactly one execution"),
        _check("evaluation-checks", "denominator", len(evaluation_checks) == 120, len(evaluation_checks), 120, "evaluation check denominator is conserved"),
        _check("evaluation-addresses", "address", all(str(item.get("content_address", "")).startswith("sha256:") for item in executions), sum(str(item.get("content_address", "")).startswith("sha256:") for item in executions), 16, "execution addresses are retained"),
        _check("metrics-record-count", "metrics", isinstance(metrics, dict) and any(item.get("metric_id") == "execution_acceptance_rate" and item.get("denominator") == 16 for item in _list(metrics, "metrics")), True, True, "metrics retain the record denominator"),
        _check("lineage-edge-count", "lineage", isinstance(lineage, dict) and len(_list(lineage, "edges")) == 36, len(_list(lineage, "edges")), 36, "lineage retains source and execution edges"),
        _check("reconciliation-state", "reconciliation", isinstance(reconciliation, dict) and bool(reconciliation.get("reconciled")), reconciliation.get("reconciled") if isinstance(reconciliation, dict) else None, True, "source reconciliation is accepted"),
        _check("release-accepted", "release", isinstance(release, dict) and bool(release.get("accepted")), release.get("accepted") if isinstance(release, dict) else None, True, "release manifest is accepted"),
        _check("replay-accepted", "replay", isinstance(replay, dict) and bool(replay.get("accepted")), replay.get("accepted") if isinstance(replay, dict) else None, True, "replay receipt is accepted"),
        _check("review-records", "projection", len(review_rows) == 16, len(review_rows), 16, "review rows close the fixture record set"),
        _check("queue-records", "projection", len(queue_items) == 16, len(queue_items), 16, "queue items close the fixture record set"),
        _check("observability-events", "observability", len(events) == 26, len(events), 26, "observability events close runtime and execution events"),
        _check("runtime-stages", "runtime", len(stages) == 10 and [item.get("sequence") for item in stages] == list(range(1, 11)), len(stages), 10, "runtime stages are ordered"),
        _check("runtime-address", "runtime", isinstance(runtime, dict) and runtime.get("content_address") == bundle.runtime_address, runtime.get("content_address") if isinstance(runtime, dict) else None, bundle.runtime_address, "runtime address joins the root manifest"),
        _check("root-accepted", "closure", bundle.ready, bundle.accepted, True, "root bundle remains ready"),
    )
    accepted = all(item.passed for item in checks)
    body = {"version": EVIDENCE_LIFECYCLE_OFFLINE_RECONCILIATION_VERSION, "bundle_id": bundle.bundle_id, "checks": checks, "accepted": accepted}
    return EvidenceLifecycleOfflineReconciliationReport(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-reconciliation"))


def _artifact_map(bundle: EvidenceLifecycleOfflineBundle) -> dict[str, str]:
    return {item.artifact_id: item.content_address for item in bundle.artifacts}


def compare_evidence_lifecycle_offline_bundles(left: EvidenceLifecycleOfflineBundle, right: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineReconciliationDelta:
    """Compare two handoffs by artifact addresses and conserved counts."""

    left_map = _artifact_map(left)
    right_map = _artifact_map(right)
    changed = tuple(sorted(item for item in set(left_map) | set(right_map) if left_map.get(item) != right_map.get(item)))
    count_fields = ("records", "sources", "executions", "checks", "events", "stages")
    left_values = {"records": len(_list(_payload(left, "fixture"), "records")), "sources": len(_list(_payload(left, "fixture"), "sources")), "executions": len(_list(_payload(left, "evaluation"), "executions")), "checks": len(_list(_payload(left, "evaluation"), "checks")), "events": len(_list(_payload(left, "observability"), "events")), "stages": len(_list(_payload(left, "runtime"), "stages"))}
    right_values = {"records": len(_list(_payload(right, "fixture"), "records")), "sources": len(_list(_payload(right, "fixture"), "sources")), "executions": len(_list(_payload(right, "evaluation"), "executions")), "checks": len(_list(_payload(right, "evaluation"), "checks")), "events": len(_list(_payload(right, "observability"), "events")), "stages": len(_list(_payload(right, "runtime"), "stages"))}
    changed_counts = {field: (left_values[field], right_values[field]) for field in count_fields if left_values[field] != right_values[field]}
    body = {"bundle_id": right.bundle_id, "left_address": left.content_address, "right_address": right.content_address, "changed_artifacts": changed, "changed_counts": changed_counts, "accepted": not changed and not changed_counts}
    return EvidenceLifecycleOfflineReconciliationDelta(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-reconciliation-delta"))


def evidence_lifecycle_offline_reconciliation_markdown(report: EvidenceLifecycleOfflineReconciliationReport) -> str:
    """Render an address-free reviewer summary of reconciliation checks."""

    lines = ["# Evidence lifecycle offline reconciliation", "", f"Bundle: `{report.bundle_id}`", f"Accepted: `{str(report.accepted).lower()}`", f"Checks: `{report.passed_count}/{len(report.checks)}`", "", "| Check | State | Detail |", "| --- | --- | --- |"]
    lines.extend(f"| `{item.check_id}` | `{_state_label(item.passed)}` | {item.detail} |" for item in report.checks)
    return "\n".join(lines) + "\n"


def _state_label(passed: bool) -> str:
    return "pass" if passed else "hold"


__all__ = [
    "EVIDENCE_LIFECYCLE_OFFLINE_RECONCILIATION_VERSION",
    "EvidenceLifecycleOfflineReconciliationCheck",
    "EvidenceLifecycleOfflineReconciliationDelta",
    "EvidenceLifecycleOfflineReconciliationReport",
    "compare_evidence_lifecycle_offline_bundles",
    "evidence_lifecycle_offline_reconciliation_markdown",
    "reconcile_evidence_lifecycle_offline_bundle",
]

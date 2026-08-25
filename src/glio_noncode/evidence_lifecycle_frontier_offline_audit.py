"""Independent cross-artifact audit for D14 offline handoffs."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable
from .evidence_lifecycle_frontier_offline_contracts import (
    EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT,
    EvidenceLifecycleOfflineBundle,
)

EVIDENCE_LIFECYCLE_OFFLINE_AUDIT_VERSION = "evidence-lifecycle-offline-audit-v1"


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleOfflineAuditCheck:
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
class EvidenceLifecycleOfflineAudit:
    version: str
    bundle_id: str
    checks: tuple[EvidenceLifecycleOfflineAuditCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_check_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_check_count": self.passed_check_count,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _check(check_id: str, plane: str, passed: bool, observed: Any, required: Any, detail: str) -> EvidenceLifecycleOfflineAuditCheck:
    body = {"check_id": check_id, "plane": plane, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    return EvidenceLifecycleOfflineAuditCheck(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-audit-check"))


def _payload(bundle: EvidenceLifecycleOfflineBundle, artifact_id: str) -> Any:
    artifact = next((item for item in bundle.artifacts if item.artifact_id == artifact_id), None)
    if artifact is None or artifact.payload is None:
        return None
    try:
        return json.loads(artifact.payload)
    except json.JSONDecodeError:
        return None


def _accepted(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("accepted"))


def audit_evidence_lifecycle_offline_bundle(bundle: EvidenceLifecycleOfflineBundle) -> EvidenceLifecycleOfflineAudit:
    """Reconcile the fixture, evaluation, release, and projection artifacts."""

    fixture = _payload(bundle, "fixture")
    evaluation = _payload(bundle, "evaluation")
    runtime = _payload(bundle, "runtime")
    observability = _payload(bundle, "observability")
    release = _payload(bundle, "release")
    reconciliation = _payload(bundle, "reconciliation")
    quality = _payload(bundle, "quality")
    review = _payload(bundle, "review")
    queue = _payload(bundle, "review-queue")
    artifacts = _payload(bundle, "artifacts")
    replay = _payload(bundle, "replay")
    checks: list[EvidenceLifecycleOfflineAuditCheck] = []
    checks.append(_check("artifact-count", "manifest", bundle.artifact_count == EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT, bundle.artifact_count, EVIDENCE_LIFECYCLE_OFFLINE_BUNDLE_ARTIFACT_COUNT, "offline artifact inventory is closed"))
    checks.append(_check("artifact-id-closure", "manifest", len({item.artifact_id for item in bundle.artifacts}) == bundle.artifact_count, len({item.artifact_id for item in bundle.artifacts}), bundle.artifact_count, "artifact identities are unique"))
    checks.append(_check("artifact-path-closure", "manifest", len({item.relative_path for item in bundle.artifacts}) == bundle.artifact_count, len({item.relative_path for item in bundle.artifacts}), bundle.artifact_count, "artifact paths are unique"))
    checks.append(_check("artifact-address-closure", "artifact", all(item.content_address.startswith("evidence-lifecycle-bundle-artifact:") and item.payload is not None for item in bundle.artifacts), sum(item.payload is not None for item in bundle.artifacts), bundle.artifact_count, "every artifact has an exact-byte address and payload"))
    json_values = [_payload(bundle, item.artifact_id) for item in bundle.artifacts if item.media_type == "application/json"]
    public_ok = all(not _has_forbidden_key(item) and not contains_private_key(item) for item in json_values)
    checks.append(_check("public-json-closure", "public_boundary", public_ok, public_ok, True, "all hydrated JSON artifacts remain public aggregate data"))
    records = fixture.get("records", ()) if isinstance(fixture, dict) else ()
    sources = fixture.get("sources", ()) if isinstance(fixture, dict) else ()
    checks.append(_check("fixture-record-count", "fixture", isinstance(records, list) and len(records) == 16, len(records) if isinstance(records, list) else 0, 16, "fixture retains sixteen records"))
    checks.append(_check("fixture-source-count", "fixture", isinstance(sources, list) and len(sources) == 5, len(sources) if isinstance(sources, list) else 0, 5, "fixture retains five source receipts"))
    record_ids = {str(item.get("record_id")) for item in records if isinstance(item, dict)}
    checks.append(_check("fixture-record-identities", "fixture", len(record_ids) == 16, len(record_ids), 16, "fixture record IDs are unique"))
    source_ids = {str(item.get("source_id")) for item in sources if isinstance(item, dict)}
    joins = all(set(item.get("source_ids", ())) <= source_ids for item in records if isinstance(item, dict))
    checks.append(_check("fixture-source-joins", "fixture", joins, joins, True, "every record source binding resolves"))
    checks.append(_check("fixture-https-receipts", "fixture", all(str(item.get("uri", "")).startswith("https://") for item in sources if isinstance(item, dict)), True, True, "all source receipts remain HTTPS"))
    executions = evaluation.get("executions", ()) if isinstance(evaluation, dict) else ()
    evaluation_checks = evaluation.get("checks", ()) if isinstance(evaluation, dict) else ()
    checks.append(_check("evaluation-accepted", "evaluation", _accepted(evaluation), evaluation.get("accepted") if isinstance(evaluation, dict) else None, True, "evaluation artifact is accepted"))
    checks.append(_check("evaluation-execution-count", "evaluation", isinstance(executions, list) and len(executions) == 16, len(executions) if isinstance(executions, list) else 0, 16, "each fixture record has one execution"))
    checks.append(_check("evaluation-check-count", "evaluation", isinstance(evaluation_checks, list) and len(evaluation_checks) == 120, len(evaluation_checks) if isinstance(evaluation_checks, list) else 0, 120, "evaluation retains all 120 checks"))
    execution_ids = {str(item.get("record_id")) for item in executions if isinstance(item, dict)}
    checks.append(_check("execution-record-closure", "evaluation", execution_ids == record_ids, len(execution_ids), len(record_ids), "execution identities close fixture identities"))
    stages = runtime.get("stages", ()) if isinstance(runtime, dict) else ()
    ordinals = [item.get("sequence") for item in stages if isinstance(item, dict)]
    checks.append(_check("runtime-stage-count", "runtime", isinstance(stages, list) and len(stages) == 10, len(stages) if isinstance(stages, list) else 0, 10, "runtime retains ten ordered stages"))
    checks.append(_check("runtime-stage-order", "runtime", ordinals == list(range(1, 11)), ordinals, list(range(1, 11)), "runtime stages are contiguous"))
    checks.append(_check("runtime-address-closure", "runtime", isinstance(runtime, dict) and runtime.get("content_address") == bundle.runtime_address, runtime.get("content_address") if isinstance(runtime, dict) else None, bundle.runtime_address, "manifest runtime address matches runtime artifact"))
    events = observability.get("events", ()) if isinstance(observability, dict) else ()
    checks.append(_check("observability-event-count", "runtime", isinstance(events, list) and len(events) == 26, len(events) if isinstance(events, list) else 0, 26, "observability retains ten stages and sixteen executions"))
    checks.append(_check("reconciliation-accepted", "closure", isinstance(reconciliation, dict) and bool(reconciliation.get("reconciled")), reconciliation.get("reconciled") if isinstance(reconciliation, dict) else None, True, "expected lifecycle state reconciliation is accepted"))
    checks.append(_check("quality-accepted", "closure", _accepted(quality), quality.get("accepted") if isinstance(quality, dict) else None, True, "quality gate is accepted"))
    checks.append(_check("release-accepted", "closure", _accepted(release), release.get("accepted") if isinstance(release, dict) else None, True, "release manifest is accepted"))
    checks.append(_check("replay-accepted", "replay", _accepted(replay), replay.get("accepted") if isinstance(replay, dict) else None, True, "replay receipt is accepted"))
    review_rows = review.get("rows", ()) if isinstance(review, dict) else ()
    queue_items = queue.get("items", ()) if isinstance(queue, dict) else ()
    inventory_items = artifacts.get("artifacts", ()) if isinstance(artifacts, dict) else ()
    checks.append(_check("review-row-count", "projection", isinstance(review_rows, list) and len(review_rows) == 16, len(review_rows) if isinstance(review_rows, list) else 0, 16, "review view retains one row per record"))
    checks.append(_check("queue-item-count", "projection", isinstance(queue_items, list) and len(queue_items) == 16, len(queue_items) if isinstance(queue_items, list) else 0, 16, "review queue retains one item per record"))
    checks.append(_check("inventory-item-count", "projection", isinstance(inventory_items, list) and len(inventory_items) == 7, len(inventory_items) if isinstance(inventory_items, list) else 0, 7, "source artifact inventory retains seven lineage nodes"))
    csv_artifact = next((item for item in bundle.artifacts if item.artifact_id == "review-csv"), None)
    csv_rows = max(0, sum(1 for _ in csv.reader(io.StringIO(csv_artifact.payload or ""))) - 1) if csv_artifact is not None else 0
    checks.append(_check("review-csv-count", "projection", csv_rows == 16, csv_rows, 16, "review CSV retains one row per record"))
    accepted = all(item.passed for item in checks)
    body = {"version": EVIDENCE_LIFECYCLE_OFFLINE_AUDIT_VERSION, "bundle_id": bundle.bundle_id, "checks": tuple(checks), "accepted": accepted}
    return EvidenceLifecycleOfflineAudit(**body, content_address=content_hash(body, prefix="evidence-lifecycle-offline-audit"))


__all__ = [
    "EVIDENCE_LIFECYCLE_OFFLINE_AUDIT_VERSION",
    "EvidenceLifecycleOfflineAudit",
    "EvidenceLifecycleOfflineAuditCheck",
    "audit_evidence_lifecycle_offline_bundle",
]

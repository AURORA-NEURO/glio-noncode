"""Depth audit for Domain 14 lifecycle coverage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_fixture_eval import evaluate_evidence_lifecycle_fixture
from .evidence_lifecycle_frontier_public_data import (
    audit_evidence_lifecycle_data,
    default_evidence_lifecycle_fixture,
)
from .evidence_lifecycle_frontier_replay import evidence_lifecycle_replay_is_deterministic
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleDepthCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleDepthAudit:
    audit_id: str
    checks: tuple[EvidenceLifecycleDepthCheck, ...]
    accepted: bool
    passed_count: int
    failed_check_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_evidence_lifecycle_depth() -> EvidenceLifecycleDepthAudit:
    fixture = default_evidence_lifecycle_fixture()
    evaluation = evaluate_evidence_lifecycle_fixture(fixture)
    data = audit_evidence_lifecycle_data(fixture)
    observations = (("data_audit", data.accepted, True), ("evaluation", evaluation.accepted, True), ("record_count", len(fixture.records), 16), ("positive_count", len(fixture.positive_records), 4), ("control_count", len(fixture.control_records), 12), ("source_count", len(fixture.sources), 5), ("operation_count", len(set(item.operation for item in fixture.records)), 4), ("evaluation_checks", len(evaluation.checks), 120), ("passed_checks", evaluation.passed_checks, 120), ("failed_checks", len(evaluation.failed_check_ids), 0), ("addressed_records", sum(item.content_address.startswith("sha256:") for item in fixture.records), 16), ("addressed_executions", sum(item.content_address.startswith("sha256:") for item in evaluation.executions), 16), ("positive_acceptance", sum(item.accepted for item in evaluation.executions if item.role.value == "positive"), 4), ("control_rejection", sum(not item.accepted for item in evaluation.executions if item.role.value == "control"), 12), ("issue_rows", sum(bool(item.issue_codes) for item in evaluation.executions), 13), ("state_values", len({item.state for item in evaluation.executions}), 8), ("issue_values", len({code for item in evaluation.executions for code in item.issue_codes}), 13), ("context_exact", len({item.context_key for item in fixture.records}), 1), ("replay_stable", evidence_lifecycle_replay_is_deterministic(fixture), True), ("boundary", fixture.evidence_boundary, "public_aggregate_non_patient"))
    checks = []
    for check_id, observed, required in observations:
        body = {"check_id": f"depth:{check_id}", "passed": observed == required, "observed": observed, "required": required}
        checks.append(EvidenceLifecycleDepthCheck(**body, content_address=content_hash(body)))
    failed = tuple(item.check_id for item in checks if not item.passed)
    body = {"audit_id": "evidence-lifecycle-depth", "checks": tuple(checks), "accepted": not failed, "passed_count": len(checks) - len(failed), "failed_check_ids": failed}
    return EvidenceLifecycleDepthAudit(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleDepthAudit", "EvidenceLifecycleDepthCheck", "audit_evidence_lifecycle_depth"]

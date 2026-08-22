"""Expected-versus-observed reconciliation for Domain 14 lifecycle records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_fixture_eval import EvidenceLifecycleEvaluation
from .evidence_lifecycle_frontier_policy import EvidenceLifecyclePolicy
from .evidence_lifecycle_frontier_public_data import EvidenceLifecycleFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    matched: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReconciliation:
    fixture_id: str
    items: tuple[EvidenceLifecycleReconciliationItem, ...]
    mismatched_record_ids: tuple[str, ...]
    reconciled: bool
    policy_decision_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def reconcile_evidence_lifecycle(fixture: EvidenceLifecycleFixture, evaluation: EvidenceLifecycleEvaluation, policy: EvidenceLifecyclePolicy) -> EvidenceLifecycleReconciliation:
    execution_map = evaluation.execution_map()
    items: list[EvidenceLifecycleReconciliationItem] = []
    for record in fixture.records:
        execution = execution_map[record.record_id]
        body = {"record_id": record.record_id, "expected_state": record.expected_state, "observed_state": execution.state, "expected_issue_codes": tuple(sorted(record.expected_issue_codes)), "observed_issue_codes": execution.issue_codes, "matched": record.expected_state == execution.state and tuple(sorted(record.expected_issue_codes)) == execution.issue_codes}
        items.append(EvidenceLifecycleReconciliationItem(**body, content_address=content_hash(body)))
    mismatched = tuple(item.record_id for item in items if not item.matched)
    body = {"fixture_id": fixture.fixture_id, "items": tuple(items), "mismatched_record_ids": mismatched, "reconciled": not mismatched, "policy_decision_count": len(policy.decide(evaluation))}
    return EvidenceLifecycleReconciliation(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleReconciliation", "EvidenceLifecycleReconciliationItem", "reconcile_evidence_lifecycle"]

"""Reconcile Domain 13 fixture expectations with observed planning states."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_fixture_eval import ValidationFrontierEvaluation
from .validation_frontier_policy import ValidationFrontierDecision, ValidationFrontierPolicy
from .validation_frontier_public_data import ValidationFrontierFixture


@dataclass(frozen=True, slots=True)
class ValidationFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool
    policy_decision: ValidationFrontierDecision
    content_address: str

    @property
    def reconciled(self) -> bool:
        return self.state_match and self.issue_match

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"reconciled": self.reconciled}


@dataclass(frozen=True, slots=True)
class ValidationFrontierReconciliation:
    fixture_id: str
    items: tuple[ValidationFrontierReconciliationItem, ...]
    evaluation_accepted: bool
    reconciled: bool
    content_address: str

    @property
    def mismatched_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.items if not item.reconciled)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"mismatched_record_ids": list(self.mismatched_record_ids)}


def reconcile_validation_frontier(fixture: ValidationFrontierFixture, evaluation: ValidationFrontierEvaluation, policy: ValidationFrontierPolicy) -> ValidationFrontierReconciliation:
    decisions = {item.operation: item for item in policy.decide(evaluation)}
    items = []
    for record in fixture.records:
        execution = evaluation.execution_map()[record.record_id]
        decision = decisions[record.operation]
        body = {"record_id": record.record_id, "expected_state": record.expected_state, "observed_state": execution.state, "expected_issue_codes": tuple(sorted(record.expected_issue_codes)), "observed_issue_codes": execution.issue_codes, "state_match": record.expected_state == execution.state, "issue_match": tuple(sorted(record.expected_issue_codes)) == execution.issue_codes, "policy_decision": decision.decision}
        items.append(ValidationFrontierReconciliationItem(**body, content_address=content_hash(body)))
    body = {"fixture_id": fixture.fixture_id, "items": tuple(items), "evaluation_accepted": evaluation.accepted, "reconciled": evaluation.accepted and all(item.reconciled for item in items)}
    return ValidationFrontierReconciliation(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierReconciliation", "ValidationFrontierReconciliationItem", "reconcile_validation_frontier"]

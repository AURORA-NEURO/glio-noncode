"""Reconcile expected fixture boundaries, adapter outputs, and policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_fixture_eval import SequenceGrammarEvaluation
from .sequence_grammar_frontier_policy import SequenceGrammarPolicyReport
from .sequence_grammar_frontier_public_data import SequenceGrammarFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    policy_decision: str
    matched: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id.strip():
            raise ValidationError("reconciliation item requires record ID")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "expected_state": self.expected_state,
                        "observed_state": self.observed_state,
                        "expected_issue_codes": self.expected_issue_codes,
                        "observed_issue_codes": self.observed_issue_codes,
                        "policy_decision": self.policy_decision,
                        "matched": self.matched,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarReconciliation:
    accepted: bool
    fixture_id: str
    items: tuple[SequenceGrammarReconciliationItem, ...]
    failed_record_ids: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.items:
            raise ValidationError("reconciliation requires items")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "accepted": self.accepted,
                        "fixture_id": self.fixture_id,
                        "items": self.items,
                        "failed_record_ids": self.failed_record_ids,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "fixture_id": self.fixture_id,
            "item_count": len(self.items),
            "failed_record_ids": list(self.failed_record_ids),
            "items": [item.to_dict() for item in self.items],
            "content_address": self.content_address,
        }


def reconcile_sequence_grammar(
    fixture: SequenceGrammarFixture,
    evaluation: SequenceGrammarEvaluation,
    policy: SequenceGrammarPolicyReport,
) -> SequenceGrammarReconciliation:
    policy_map = {item.record_id: item for item in policy.decisions}
    items: list[SequenceGrammarReconciliationItem] = []
    for execution in evaluation.executions:
        policy_item = policy_map[execution.record_id]
        matched = execution.accepted and execution.record_id in policy_map
        items.append(
            SequenceGrammarReconciliationItem(
                execution.record_id,
                execution.expected_state.value,
                execution.adapter_state.value,
                execution.expected_issue_codes,
                execution.issue_codes,
                policy_item.decision.value,
                matched,
            )
        )
    failures = tuple(item.record_id for item in items if not item.matched)
    return SequenceGrammarReconciliation(not failures, fixture.fixture_id, tuple(items), failures)


__all__ = [
    "SequenceGrammarReconciliation",
    "SequenceGrammarReconciliationItem",
    "reconcile_sequence_grammar",
]

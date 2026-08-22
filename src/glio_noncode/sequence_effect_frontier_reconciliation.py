"""Reconcile fixture expectations, execution state, and policy decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_fixture_eval import SequenceEffectEvaluation
from .sequence_effect_frontier_policy import SequenceEffectPolicyReport
from .sequence_effect_frontier_public_data import SequenceEffectFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectReconciliationItem:
    record_id: str
    passed: bool
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    decision: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self, "content_address", content_hash(jsonable(self) | {"content_address": ""})
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectReconciliation:
    items: tuple[SequenceEffectReconciliationItem, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"items": self.items, "accepted": self.accepted}),
            )

    @property
    def failed_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.items if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "failed_record_ids": list(self.failed_record_ids),
            "items": [item.to_dict() for item in self.items],
            "content_address": self.content_address,
        }


def reconcile_sequence_effect(
    fixture: SequenceEffectFixture,
    evaluation: SequenceEffectEvaluation,
    policy: SequenceEffectPolicyReport,
) -> SequenceEffectReconciliation:
    execution_map = evaluation.execution_map()
    policy_map = {item.record_id: item for item in policy.decisions}
    items: list[SequenceEffectReconciliationItem] = []
    for record in fixture.records:
        execution = execution_map[record.record_id]
        decision = policy_map[record.record_id]
        passed = (
            execution.adapter_state.value == record.expected_state.value
            and set(record.expected_issue_codes) <= set(execution.issue_codes)
            and decision.record_id == record.record_id
        )
        items.append(
            SequenceEffectReconciliationItem(
                record.record_id,
                passed,
                record.expected_state.value,
                execution.adapter_state.value,
                record.expected_issue_codes,
                execution.issue_codes,
                decision.decision.value,
            )
        )
    return SequenceEffectReconciliation(
        tuple(items), all(item.passed for item in items) and policy.accepted
    )


__all__ = [
    "SequenceEffectReconciliation",
    "SequenceEffectReconciliationItem",
    "reconcile_sequence_effect",
]

"""Review-oriented projections for sequence grammar results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_fixture_eval import (
    SequenceGrammarEvaluation,
    SequenceGrammarExecution,
)
from .sequence_grammar_frontier_policy import SequenceGrammarDecision, SequenceGrammarPolicyReport
from .sequence_grammar_frontier_public_data import (
    SequenceGrammarFixture,
    SequenceGrammarOperation,
    SequenceGrammarRole,
    SequenceGrammarState,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarReviewEntry:
    record_id: str
    operation: SequenceGrammarOperation
    role: SequenceGrammarRole
    state: SequenceGrammarState
    priority: int
    issue_codes: tuple[str, ...]
    review_action: str
    publishable: bool
    result_address: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if (
            not self.record_id.strip()
            or self.priority < 1
            or not self.result_address.startswith("sha256:")
        ):
            raise ValidationError("review entry is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "operation": self.operation,
                        "role": self.role,
                        "state": self.state,
                        "priority": self.priority,
                        "issue_codes": self.issue_codes,
                        "review_action": self.review_action,
                        "publishable": self.publishable,
                        "result_address": self.result_address,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarOperationView:
    operation: SequenceGrammarOperation
    total_count: int
    supported_count: int
    review_count: int
    control_count: int
    entries: tuple[SequenceGrammarReviewEntry, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "operation": self.operation,
                        "total_count": self.total_count,
                        "supported_count": self.supported_count,
                        "review_count": self.review_count,
                        "control_count": self.control_count,
                        "entries": self.entries,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarView:
    fixture_id: str
    accepted: bool
    entries: tuple[SequenceGrammarReviewEntry, ...]
    operation_views: tuple[SequenceGrammarOperationView, ...]
    review_count: int
    publishable_count: int
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.entries or not self.operation_views:
            raise ValidationError("sequence grammar view requires entries and operations")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "fixture_id": self.fixture_id,
                        "accepted": self.accepted,
                        "entries": self.entries,
                        "operation_views": self.operation_views,
                        "review_count": self.review_count,
                        "publishable_count": self.publishable_count,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "accepted": self.accepted,
            "review_count": self.review_count,
            "publishable_count": self.publishable_count,
            "entries": [entry.to_dict() for entry in self.entries],
            "operation_views": [view.to_dict() for view in self.operation_views],
            "content_address": self.content_address,
        }


def _priority(execution: SequenceGrammarExecution) -> tuple[int, str]:
    if execution.adapter_state is SequenceGrammarState.INVALID:
        return 1, "repair invalid input"
    if execution.role is SequenceGrammarRole.CONTROL:
        return 2, "review control boundary"
    if execution.adapter_state is SequenceGrammarState.ABSTAINED:
        return 3, "supply missing support"
    if execution.adapter_state in {SequenceGrammarState.PARTIAL, SequenceGrammarState.AMBIGUOUS}:
        return 4, "resolve ambiguity"
    return 5, "retain positive research evidence"


def build_sequence_grammar_view(
    fixture: SequenceGrammarFixture,
    evaluation: SequenceGrammarEvaluation,
    policy: SequenceGrammarPolicyReport | None = None,
) -> SequenceGrammarView:
    policy_map = {item.record_id: item for item in policy.decisions} if policy else {}
    entries: list[SequenceGrammarReviewEntry] = []
    for execution in evaluation.executions:
        priority, action = _priority(execution)
        policy_item = policy_map.get(execution.record_id)
        publishable = bool(
            policy_item and policy_item.decision is SequenceGrammarDecision.ALLOW_RESEARCH
        )
        entries.append(
            SequenceGrammarReviewEntry(
                execution.record_id,
                execution.operation,
                execution.role,
                execution.adapter_state,
                priority,
                execution.issue_codes,
                action,
                publishable,
                execution.adapter_address,
            )
        )
    operation_views = tuple(
        SequenceGrammarOperationView(
            operation,
            sum(entry.operation is operation for entry in entries),
            sum(
                entry.operation is operation and entry.state is SequenceGrammarState.SUPPORTED
                for entry in entries
            ),
            sum(
                entry.operation is operation and entry.state is not SequenceGrammarState.SUPPORTED
                for entry in entries
            ),
            sum(
                entry.operation is operation and entry.role is SequenceGrammarRole.CONTROL
                for entry in entries
            ),
            tuple(entry for entry in entries if entry.operation is operation),
        )
        for operation in SequenceGrammarOperation
    )
    return SequenceGrammarView(
        fixture.fixture_id,
        evaluation.accepted,
        tuple(entries),
        operation_views,
        sum(entry.role is SequenceGrammarRole.CONTROL for entry in entries),
        sum(entry.publishable for entry in entries),
    )


def filter_sequence_grammar_review_queue(
    view: SequenceGrammarView,
    *,
    maximum_priority: int | None = None,
    operation: SequenceGrammarOperation | None = None,
) -> tuple[SequenceGrammarReviewEntry, ...]:
    rows = tuple(
        entry
        for entry in view.entries
        if (
            entry.role is SequenceGrammarRole.CONTROL
            or entry.state is not SequenceGrammarState.SUPPORTED
        )
        and (maximum_priority is None or entry.priority <= maximum_priority)
        and (operation is None or entry.operation is operation)
    )
    return tuple(sorted(rows, key=lambda entry: (entry.priority, entry.record_id)))


def sequence_grammar_review_summary(view: SequenceGrammarView) -> dict[str, Any]:
    return {
        "fixture_id": view.fixture_id,
        "accepted": view.accepted,
        "total_count": len(view.entries),
        "accepted_count": sum(
            entry.state is SequenceGrammarState.SUPPORTED for entry in view.entries
        ),
        "review_count": view.review_count,
        "publishable_count": view.publishable_count,
        "by_operation": {item.operation.value: item.total_count for item in view.operation_views},
        "content_address": view.content_address,
    }


__all__ = [
    "SequenceGrammarOperationView",
    "SequenceGrammarReviewEntry",
    "SequenceGrammarView",
    "build_sequence_grammar_view",
    "filter_sequence_grammar_review_queue",
    "sequence_grammar_review_summary",
]

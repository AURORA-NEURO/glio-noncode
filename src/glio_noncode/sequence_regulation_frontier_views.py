"""Stable consumer-facing rows for C09-C12 results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .sequence_regulation_frontier_policy import SequenceRegulationPolicyReport
from .sequence_regulation_frontier_public_data import SequenceRegulationFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationViewRow:
    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: tuple[str, ...]
    release_allowed: bool
    detail: str
    result_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceRegulationView:
    fixture_id: str
    rows: tuple[SequenceRegulationViewRow, ...]
    column_order: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.rows or not self.column_order:
            raise ValidationError("view requires rows and columns")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def by_operation(self, operation: str) -> tuple[SequenceRegulationViewRow, ...]:
        return tuple(row for row in self.rows if row.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_regulation_view(
    fixture: SequenceRegulationFixture,
    evaluation: SequenceRegulationEvaluation,
    policy: SequenceRegulationPolicyReport,
) -> SequenceRegulationView:
    decisions = {decision.record_id: decision for decision in policy.decisions}
    rows = tuple(
        SequenceRegulationViewRow(
            record_id=item.record_id,
            operation=item.adapter.operation.value,
            role=item.role,
            state=item.observed_state.value,
            issue_codes=item.observed_issue_codes,
            release_allowed=decisions[item.record_id].release_allowed,
            detail=item.adapter.detail,
            result_address=item.adapter.content_address,
        )
        for item in evaluation.records
    )
    columns = (
        "record_id",
        "operation",
        "role",
        "state",
        "issue_codes",
        "release_allowed",
        "detail",
        "result_address",
    )
    return SequenceRegulationView(
        fixture.fixture_id,
        rows,
        columns,
        len(rows) == len(fixture.records)
        and all(row.result_address.startswith("sha256:") for row in rows),
    )


__all__ = ["SequenceRegulationView", "SequenceRegulationViewRow", "build_sequence_regulation_view"]

"""Record-level execution and expected-path reconciliation for C09-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_alpha_frontier_adapters import (
    ChromatinAlphaFrontierAdapterResult,
    execute_chromatin_alpha_frontier_record,
)
from .chromatin_alpha_frontier_public_data import (
    ChromatinAlphaFrontierFixture,
    ChromatinAlphaFrontierRecord,
    ChromatinAlphaFrontierRole,
    default_chromatin_alpha_frontier_fixture,
)
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierRecordEvaluation:
    record_id: str
    operation: str
    role: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    state_match: bool
    issue_match: bool
    accepted: bool
    adapter: ChromatinAlphaFrontierAdapterResult
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id or not self.operation or not self.role:
            raise ValidationError("record evaluation identity is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierEvaluation:
    fixture_id: str
    records: tuple[ChromatinAlphaFrontierRecordEvaluation, ...]
    positive_count: int
    control_count: int
    state_match_count: int
    issue_match_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.records:
            raise ValidationError("evaluation requires fixture and records")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.records if not item.accepted)

    @property
    def results(self) -> tuple[ChromatinAlphaFrontierAdapterResult, ...]:
        return tuple(item.adapter for item in self.records)

    def by_operation(self, operation: str) -> tuple[ChromatinAlphaFrontierRecordEvaluation, ...]:
        return tuple(item for item in self.records if item.operation == operation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "record_count": len(self.records),
            "positive_count": self.positive_count,
            "control_count": self.control_count,
            "state_match_count": self.state_match_count,
            "issue_match_count": self.issue_match_count,
            "failed_record_ids": list(self.failed_record_ids),
            "accepted": self.accepted,
            "records": [record.to_dict() for record in self.records],
            "content_address": self.content_address,
        }


def _record_lookup(
    fixture: ChromatinAlphaFrontierFixture,
) -> dict[str, ChromatinAlphaFrontierRecord]:
    return {record.record_id: record for record in fixture.records}


def evaluate_chromatin_alpha_frontier_fixture(
    fixture: ChromatinAlphaFrontierFixture | None = None,
) -> ChromatinAlphaFrontierEvaluation:
    """Execute every row and require expected state and issue floors."""

    selected = fixture or default_chromatin_alpha_frontier_fixture()
    evaluations: list[ChromatinAlphaFrontierRecordEvaluation] = []
    for record in selected.records:
        result = execute_chromatin_alpha_frontier_record(record)
        state_match = result.state == record.expected_state
        issue_match = set(record.expected_issue_codes) <= set(result.issue_codes)
        evaluations.append(
            ChromatinAlphaFrontierRecordEvaluation(
                record_id=record.record_id,
                operation=record.operation.value,
                role=record.role.value,
                expected_state=record.expected_state,
                observed_state=result.state,
                expected_issue_codes=record.expected_issue_codes,
                observed_issue_codes=result.issue_codes,
                state_match=state_match,
                issue_match=issue_match,
                accepted=state_match and issue_match,
                adapter=result,
            )
        )
    values = tuple(evaluations)
    lookup = _record_lookup(selected)
    return ChromatinAlphaFrontierEvaluation(
        fixture_id=selected.fixture_id,
        records=values,
        positive_count=sum(
            lookup[item.record_id].role is ChromatinAlphaFrontierRole.POSITIVE for item in values
        ),
        control_count=sum(
            lookup[item.record_id].role is ChromatinAlphaFrontierRole.CONTROL for item in values
        ),
        state_match_count=sum(item.state_match for item in values),
        issue_match_count=sum(item.issue_match for item in values),
        accepted=all(item.accepted for item in values),
    )


__all__ = [
    "ChromatinAlphaFrontierEvaluation",
    "ChromatinAlphaFrontierRecordEvaluation",
    "evaluate_chromatin_alpha_frontier_fixture",
]

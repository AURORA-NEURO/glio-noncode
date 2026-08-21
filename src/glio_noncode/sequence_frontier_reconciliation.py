"""Expected/observed reconciliation for Domain 06 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sequence_frontier_fixture_eval import SequenceFrontierEvaluationReport
from .sequence_frontier_public_data import SequenceFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceFrontierReconciliationItem:
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierReconciliationReport:
    fixture_id: str
    items: tuple[SequenceFrontierReconciliationItem, ...]
    checks: tuple[tuple[str, bool], ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(item.passed for item in self.items) and all(passed for _, passed in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_record_ids": [item.record_id for item in self.items if not item.passed],
        }


def reconcile_sequence_frontier(
    fixture: SequenceFrontierFixture, evaluation: SequenceFrontierEvaluationReport
) -> SequenceFrontierReconciliationReport:
    records = fixture.record_map()
    items: list[SequenceFrontierReconciliationItem] = []
    for receipt in evaluation.receipts:
        record = records[receipt.record_id]
        passed = receipt.adapter_state == record.expected_state and not set(
            record.expected_issue_codes
        ) - set(receipt.observed_issue_codes)
        body = {
            "record_id": receipt.record_id,
            "expected_state": record.expected_state,
            "observed_state": receipt.adapter_state,
            "expected_issue_codes": record.expected_issue_codes,
            "observed_issue_codes": receipt.observed_issue_codes,
            "passed": passed,
            "detail": "state and issue floors reconcile",
        }
        items.append(SequenceFrontierReconciliationItem(**body, content_address=content_hash(body)))
    checks = (
        ("record-count", len(items) == len(fixture.records)),
        ("positive-floor", evaluation.positive_count == len(fixture.positive_records)),
        ("control-floor", evaluation.control_count == len(fixture.control_records)),
        ("evaluation-accepted", evaluation.accepted),
    )
    body = {"fixture_id": fixture.fixture_id, "items": items, "checks": checks}
    return SequenceFrontierReconciliationReport(
        fixture.fixture_id, tuple(items), checks, content_hash(body)
    )


__all__ = [
    "SequenceFrontierReconciliationItem",
    "SequenceFrontierReconciliationReport",
    "reconcile_sequence_frontier",
]

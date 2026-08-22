"""Expected-versus-observed state reconciliation for Domain 08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_state_frontier_fixture_eval import CellStateFrontierEvaluationReport
from .cell_state_frontier_public_data import CellStateFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellStateFrontierReconciliationItem:
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
class CellStateFrontierReconciliationReport:
    fixture_id: str
    items: tuple[CellStateFrontierReconciliationItem, ...]
    checks: tuple[tuple[str, bool], ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(item.passed for item in self.items) and all(passed for _, passed in self.checks)

    @property
    def failed_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.items if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "failed_record_ids": list(self.failed_record_ids)}


def reconcile_cell_state_frontier(
    fixture: CellStateFrontierFixture,
    evaluation: CellStateFrontierEvaluationReport,
) -> CellStateFrontierReconciliationReport:
    records = fixture.record_map()
    items: list[CellStateFrontierReconciliationItem] = []
    for receipt in evaluation.receipts:
        record = records[receipt.record_id]
        expected = set(record.expected_issue_codes)
        observed = set(receipt.observed_issue_codes)
        passed = receipt.adapter_state == record.expected_state and expected <= observed
        body = {
            "record_id": receipt.record_id,
            "expected_state": record.expected_state,
            "observed_state": receipt.adapter_state,
            "expected_issue_codes": record.expected_issue_codes,
            "observed_issue_codes": receipt.observed_issue_codes,
            "passed": passed,
            "detail": "expected state and issue floor reconcile" if passed else "state or issue floor differs",
        }
        items.append(CellStateFrontierReconciliationItem(**body, content_address=content_hash(body)))
    checks = (
        ("record-count", len(items) == len(fixture.records) == 16),
        ("positive-floor", sum(item.expected_state == "supported" for item in items) == 4),
        ("control-floor", sum(item.expected_state != "supported" for item in items) == 12),
    )
    body = {"fixture_id": fixture.fixture_id, "items": items, "checks": checks}
    return CellStateFrontierReconciliationReport(fixture.fixture_id, tuple(items), checks, content_hash(body))


__all__ = [
    "CellStateFrontierReconciliationItem",
    "CellStateFrontierReconciliationReport",
    "reconcile_cell_state_frontier",
]

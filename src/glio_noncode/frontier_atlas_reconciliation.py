"""Reconcile C13-C16 fixture expectations with adapter receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .frontier_atlas_fixture_eval import FrontierAtlasEvaluationReport
from .frontier_atlas_public_data import FrontierAtlasFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class FrontierAtlasReconciliationItem:
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
class FrontierAtlasReconciliationReport:
    fixture_id: str
    items: tuple[FrontierAtlasReconciliationItem, ...]
    checks: tuple[tuple[str, bool], ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(item.passed for item in self.items) and all(passed for _, passed in self.checks)

    @property
    def failed_record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.items if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_record_ids": list(self.failed_record_ids),
        }


def reconcile_frontier_atlas(
    fixture: FrontierAtlasFixture, evaluation: FrontierAtlasEvaluationReport
) -> FrontierAtlasReconciliationReport:
    record_map = fixture.record_map()
    items: list[FrontierAtlasReconciliationItem] = []
    for receipt in evaluation.receipts:
        record = record_map[receipt.record_id]
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
        items.append(FrontierAtlasReconciliationItem(**body, content_address=content_hash(body)))
    checks = (
        ("record-count", len(items) == len(fixture.records)),
        ("positive-floor", evaluation.positive_count == len(fixture.positive_records)),
        ("control-floor", evaluation.control_count == len(fixture.control_records)),
        ("evaluation-accepted", evaluation.accepted),
    )
    body = {"fixture_id": fixture.fixture_id, "items": items, "checks": checks}
    return FrontierAtlasReconciliationReport(
        fixture.fixture_id, tuple(items), checks, content_hash(body)
    )


__all__ = [
    "FrontierAtlasReconciliationItem",
    "FrontierAtlasReconciliationReport",
    "reconcile_frontier_atlas",
]

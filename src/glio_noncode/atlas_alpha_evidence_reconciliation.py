"""Reconcile fixture expectations, adapter receipts, and source scope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .atlas_alpha_evidence_fixture_eval import AtlasAlphaEvidenceEvaluationReport
from .atlas_alpha_evidence_public_data import AtlasAlphaEvidenceFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceReconciliationItem:
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
class AtlasAlphaEvidenceReconciliationReport:
    fixture_id: str
    items: tuple[AtlasAlphaEvidenceReconciliationItem, ...]
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


def reconcile_atlas_alpha_evidence(
    fixture: AtlasAlphaEvidenceFixture, evaluation: AtlasAlphaEvidenceEvaluationReport
) -> AtlasAlphaEvidenceReconciliationReport:
    """Compare every expected state and issue floor with its receipt."""

    record_map = fixture.record_map()
    items: list[AtlasAlphaEvidenceReconciliationItem] = []
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
        items.append(
            AtlasAlphaEvidenceReconciliationItem(**body, content_address=content_hash(body))
        )
    checks = (
        ("record-count", len(items) == len(fixture.records)),
        ("positive-floor", evaluation.positive_count == len(fixture.positive_records)),
        ("control-floor", evaluation.control_count == len(fixture.control_records)),
        ("evaluation-accepted", evaluation.accepted),
    )
    body = {"fixture_id": fixture.fixture_id, "items": items, "checks": checks}
    return AtlasAlphaEvidenceReconciliationReport(
        fixture.fixture_id, tuple(items), checks, content_hash(body)
    )


__all__ = [
    "AtlasAlphaEvidenceReconciliationItem",
    "AtlasAlphaEvidenceReconciliationReport",
    "reconcile_atlas_alpha_evidence",
]

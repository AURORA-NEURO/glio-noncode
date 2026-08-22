"""Review rows and filters for the Domain 14 lifecycle frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_fixture_eval import EvidenceLifecycleEvaluation
from .evidence_lifecycle_frontier_policy import EvidenceLifecyclePolicyDecision
from .evidence_lifecycle_frontier_public_data import (
    EvidenceLifecycleFixture,
    EvidenceLifecycleOperation,
    EvidenceLifecycleRole,
)
from .evidence_lifecycle_frontier_release import EvidenceLifecycleReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReviewRow:
    record_id: str
    operation: EvidenceLifecycleOperation
    role: EvidenceLifecycleRole
    state: str
    accepted: bool
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    release_state: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleReviewView:
    fixture_id: str
    rows: tuple[EvidenceLifecycleReviewRow, ...]
    content_address: str

    def accepted_rows(self) -> tuple[EvidenceLifecycleReviewRow, ...]:
        return tuple(item for item in self.rows if item.accepted)

    def issue_rows(self) -> tuple[EvidenceLifecycleReviewRow, ...]:
        return tuple(item for item in self.rows if item.issue_codes)

    def by_operation(self, operation: EvidenceLifecycleOperation) -> tuple[EvidenceLifecycleReviewRow, ...]:
        return tuple(item for item in self.rows if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_lifecycle_review_view(fixture: EvidenceLifecycleFixture, evaluation: EvidenceLifecycleEvaluation, decisions: tuple[EvidenceLifecyclePolicyDecision, ...], release: EvidenceLifecycleReleaseManifest) -> EvidenceLifecycleReviewView:
    decision_map = {item.operation: item for item in decisions}
    execution_map = evaluation.execution_map()
    rows = []
    for record in fixture.records:
        execution = execution_map[record.record_id]
        body = {"record_id": record.record_id, "operation": record.operation, "role": record.role, "state": execution.state, "accepted": execution.accepted, "issue_codes": execution.issue_codes, "source_ids": record.source_ids, "release_state": release.state.value if decision_map[record.operation].publishable else "review_required"}
        rows.append(EvidenceLifecycleReviewRow(**body, content_address=content_hash(body)))
    body = {"fixture_id": fixture.fixture_id, "rows": tuple(rows)}
    return EvidenceLifecycleReviewView(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleReviewRow", "EvidenceLifecycleReviewView", "build_evidence_lifecycle_review_view"]

"""Sanitized release payload with only review-safe aggregate fields."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_fixture_eval import CohortAlphaFrontierEvaluation
from .cohort_alpha_frontier_governance import CohortAlphaFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleasePayloadRow:
    record_id: str
    operation: str
    state: str
    disposition: str
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReleasePayload:
    release_id: str
    rows: tuple[CohortAlphaFrontierReleasePayloadRow, ...]
    claim_ceiling: str
    raw_payload_included: bool
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_release_payload(evaluation: CohortAlphaFrontierEvaluation, policy: CohortAlphaFrontierPolicy) -> CohortAlphaFrontierReleasePayload:
    rows = tuple(CohortAlphaFrontierReleasePayloadRow(row.record_id, row.operation, row.observed_state.value, policy.for_record(row.record_id).disposition.value, policy.for_record(row.record_id).rationale, content_hash({"record_id": row.record_id, "operation": row.operation, "state": row.observed_state.value, "disposition": policy.for_record(row.record_id).disposition.value}, prefix="alpha-release-payload-row")) for row in evaluation.rows)
    ceiling = "descriptive aggregate evidence only"
    return CohortAlphaFrontierReleasePayload("cohort-alpha-frontier-c09-c12-payload", rows, ceiling, False, len(rows) == 16 and not False and all(item.content_address for item in rows), content_hash({"rows": rows, "ceiling": ceiling, "raw": False}, prefix="alpha-release-payload"))


__all__ = ["CohortAlphaFrontierReleasePayload", "CohortAlphaFrontierReleasePayloadRow", "build_cohort_alpha_frontier_release_payload"]

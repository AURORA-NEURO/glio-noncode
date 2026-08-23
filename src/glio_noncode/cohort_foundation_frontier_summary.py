"""One-page machine-readable summary for the C01-C04 handoff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_runtime import CohortFoundationRuntimeReport


@dataclass(frozen=True, slots=True)
class CohortFoundationSummary:
    summary_id: str
    fixture_id: str
    context_key: str
    record_count: int
    positive_count: int
    control_count: int
    stage_count: int
    accepted: bool
    release_state: str
    review_count: int
    quarantine_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_foundation_frontier_summary(runtime: CohortFoundationRuntimeReport) -> CohortFoundationSummary:
    quarantine_count = sum(item.disposition.value == "quarantine" for item in runtime.policy.decisions)
    body = {"summary_id": "cohort-foundation-frontier-summary", "fixture_id": runtime.fixture.fixture_id, "context": runtime.fixture.context_key, "records": len(runtime.fixture.records), "positive": len(runtime.fixture.positive_records), "controls": len(runtime.fixture.control_records), "stages": len(runtime.stages), "accepted": runtime.accepted, "release": runtime.release.state.value, "review": len(runtime.review.items), "quarantine": quarantine_count}
    return CohortFoundationSummary(body["summary_id"], runtime.fixture.fixture_id, runtime.fixture.context_key, body["records"], body["positive"], body["controls"], body["stages"], runtime.accepted, body["release"], body["review"], quarantine_count, content_hash(body))


__all__ = ["CohortFoundationSummary", "build_cohort_foundation_frontier_summary"]

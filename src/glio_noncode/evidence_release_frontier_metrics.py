"""State and issue metrics for evidence-release review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_release_frontier_common import issue_counts, state_counts
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseMetrics:
    row_count: int
    positive_count: int
    control_count: int
    state_counts: dict[str, int]
    issue_counts: dict[str, int]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def measure_evidence_release(evaluation: Any) -> EvidenceReleaseMetrics:
    states = state_counts(evaluation)
    issues = issue_counts(evaluation)
    positive = sum(item.role.value == "positive" for item in evaluation.executions)
    body = {"row_count": len(evaluation.executions), "positive_count": positive, "control_count": len(evaluation.executions) - positive, "state_counts": states, "issue_counts": issues}
    return EvidenceReleaseMetrics(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseMetrics", "measure_evidence_release"]

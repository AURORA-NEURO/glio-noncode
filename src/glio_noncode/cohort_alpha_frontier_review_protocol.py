"""Evidence review protocol for non-publishable paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierReviewQueue
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewProtocolStep:
    order: int
    step_id: str
    question: str
    evidence: tuple[str, ...]
    disposition_if_missing: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierReviewProtocol:
    steps: tuple[CohortAlphaFrontierReviewProtocolStep, ...]
    queue_count: int
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_review_protocol(queue: CohortAlphaFrontierReviewQueue) -> CohortAlphaFrontierReviewProtocol:
    raw = (("context", "Does the record match the target context?", ("context key", "source receipt"), "quarantine"), ("completeness", "Are all operation-specific channels present?", ("schema receipt", "phase receipt"), "review"), ("direction", "Do cohorts agree where replication is claimed?", ("cohort effects", "concordance receipt"), "review"), ("ceiling", "Does the proposed wording stay descriptive?", ("claim boundary", "policy decision"), "quarantine"))
    steps = tuple(CohortAlphaFrontierReviewProtocolStep(index, step_id, question, evidence, disposition, content_hash({"order": index, "id": step_id, "question": question, "evidence": evidence, "missing": disposition}, prefix="alpha-review-protocol")) for index, (step_id, question, evidence, disposition) in enumerate(raw, 1))
    return CohortAlphaFrontierReviewProtocol(steps, queue.open_count, queue.accepted and len(steps) == 4 and all(item.evidence for item in steps), content_hash({"steps": steps, "queue": queue.content_address}, prefix="alpha-review-protocol-report"))


__all__ = ["CohortAlphaFrontierReviewProtocol", "CohortAlphaFrontierReviewProtocolStep", "build_cohort_alpha_frontier_review_protocol"]

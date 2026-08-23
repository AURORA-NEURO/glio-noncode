"""Short runtime digest for logs and handoff summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_runtime_types import CohortAlphaFrontierRuntimeStage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierRuntimeDigest:
    digest_id: str
    first_stage: str
    last_stage: str
    stage_count: int
    accepted_count: int
    failed_count: int
    text: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_runtime_digest(stages: tuple[CohortAlphaFrontierRuntimeStage, ...]) -> CohortAlphaFrontierRuntimeDigest:
    accepted = sum(item.accepted for item in stages)
    failed = len(stages) - accepted
    text = f"{stages[0].stage_id} -> {stages[-1].stage_id}; stages={len(stages)}; accepted={accepted}; failed={failed}"
    body = {"id": "cohort-alpha-frontier-runtime-digest", "first": stages[0].stage_id if stages else "", "last": stages[-1].stage_id if stages else "", "count": len(stages), "accepted": accepted, "failed": failed, "text": text}
    return CohortAlphaFrontierRuntimeDigest(body["id"], body["first"], body["last"], len(stages), accepted, failed, text, content_hash(body, prefix="alpha-runtime-digest"))


__all__ = ["CohortAlphaFrontierRuntimeDigest", "build_cohort_alpha_frontier_runtime_digest"]

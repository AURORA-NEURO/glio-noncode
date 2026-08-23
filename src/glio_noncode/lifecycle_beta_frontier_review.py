"""Review packet projection with explicit issue and ownership rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReviewPacket:
    packet_id: str
    record_id: str
    state: LifecycleBetaFrontierState
    priority: float
    issue_codes: tuple[str, ...]
    owner_roles: tuple[str, ...]
    questions: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierReviewPacketSet:
    fixture_id: str
    packets: tuple[LifecycleBetaFrontierReviewPacket, ...]
    unresolved_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_lifecycle_beta_frontier_review_packets(evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierReviewPacketSet:
    packets = []
    weights = {LifecycleBetaFrontierState.CONTRADICTORY: 1.0, LifecycleBetaFrontierState.SPLIT_DECISION: 0.98, LifecycleBetaFrontierState.OUT_OF_DOMAIN: 0.95, LifecycleBetaFrontierState.PARTIAL: 0.88, LifecycleBetaFrontierState.REVIEW_REQUIRED: 0.84, LifecycleBetaFrontierState.ABSTAINED: 0.76, LifecycleBetaFrontierState.REJECTED: 0.72}
    for item in evaluation.executions:
        unresolved = bool(item.issue_codes) or item.state in weights
        questions = tuple(f"resolve:{issue}" for issue in item.issue_codes) or ("confirm:research-boundary",)
        body = {"packet_id": content_hash({"record_id": item.record_id, "execution": item.content_address}, prefix="packet"), "record_id": item.record_id, "state": item.state, "priority": weights.get(item.state, 0.35), "issue_codes": item.issue_codes, "owner_roles": ("domain_expert", "data_provenance") if unresolved else ("data_provenance",), "questions": questions, "accepted": True}
        packets.append(LifecycleBetaFrontierReviewPacket(**body, content_address=content_hash(body)))
    packets.sort(key=lambda item: (-item.priority, item.record_id))
    return LifecycleBetaFrontierReviewPacketSet(evaluation.fixture_id, tuple(packets), sum(bool(item.issue_codes) for item in evaluation.executions), content_hash({"packets": tuple(packets)}))


__all__ = ["LifecycleBetaFrontierReviewPacket", "LifecycleBetaFrontierReviewPacketSet", "build_lifecycle_beta_frontier_review_packets"]

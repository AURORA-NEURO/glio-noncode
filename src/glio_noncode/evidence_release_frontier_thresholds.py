"""Boundary probes for transition thresholds and lifecycle states."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .evidence_release_frontier_operations import evaluate_reclassification
from .evidence_release_frontier_contracts import EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseThresholdReport:
    probes: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_threshold_report() -> EvidenceReleaseThresholdReport:
    base = {"evidence_id": "threshold", "context_key": EVIDENCE_RELEASE_FRONTIER_CONTEXT_KEY, "previous_tier": "provisional", "proposed_tier": "supported", "threshold": 0.75, "reviewer_ids": ["a", "b"], "source_ids": ["s1", "s2"]}
    probes = []
    for label, score, state in (("below", 0.74, "review"), ("exact", 0.75, "reclassified"), ("above", 0.76, "reclassified")):
        observed = evaluate_reclassification(base | {"evidence_score": score})
        probes.append({"probe": label, "score": score, "observed": observed.state.value, "required": state, "passed": observed.state.value == state})
    body = {"probes": tuple(probes), "accepted": all(item["passed"] for item in probes)}
    return EvidenceReleaseThresholdReport(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseThresholdReport", "build_evidence_release_threshold_report"]

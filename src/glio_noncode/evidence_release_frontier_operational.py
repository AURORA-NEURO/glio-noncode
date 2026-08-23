"""State-to-action matrix for operations staff and reviewers."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseOperationalMatrix:
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_operational_matrix(evaluation: Any) -> EvidenceReleaseOperationalMatrix:
    actions = {"reclassified": "record transition and retain prior tier", "superseded": "close chain and retain history", "bundled": "store bundle receipt", "signed": "verify before publication", "review": "route to reviewer", "blocked": "quarantine context", "rejected": "repair input and rerun"}
    rows = tuple({"record_id": item.record_id, "state": item.observed_state.value, "action": actions[item.observed_state.value]} for item in evaluation.executions)
    body = {"rows": rows, "accepted": len(rows) == len(evaluation.executions)}
    return EvidenceReleaseOperationalMatrix(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseOperationalMatrix", "build_evidence_release_operational_matrix"]

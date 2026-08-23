"""Model eligibility matrix with explicit dimensions."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EligibilityMatrix:
    dimensions: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_eligibility_matrix(observations: tuple[dict[str, Any], ...]) -> EligibilityMatrix:
    dimensions = ("model_system", "cell_state", "context_key", "evidence_strength", "supports_context", "blockers")
    rows = tuple({key: row.get(key) for key in dimensions} | {"model_id": row.get("model_id")} for row in observations)
    accepted = bool(rows) and all(row.get("model_id") and row.get("context_key") for row in rows)
    body = {"dimensions": dimensions, "rows": rows, "accepted": accepted}
    return EligibilityMatrix(dimensions, rows, accepted, content_hash(body, prefix="eligibility-matrix"))
__all__ = ["EligibilityMatrix", "build_eligibility_matrix"]

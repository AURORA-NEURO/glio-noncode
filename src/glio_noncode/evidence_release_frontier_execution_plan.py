"""Dependency-safe operation order for lifecycle release."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseExecutionPlan:
    steps: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_execution_plan() -> EvidenceReleaseExecutionPlan:
    names = ("data-audit", "schema", "adapters", "fixture-evaluation", "metrics", "lineage", "reconciliation", "quality-gate", "replay", "release", "review", "integrity", "depth", "package", "bundle")
    steps = tuple({"sequence": index, "stage_id": name, "depends_on": (names[index - 2],) if index > 1 else ()} for index, name in enumerate(names, start=1))
    body = {"steps": steps, "accepted": all(item["sequence"] == index for index, item in enumerate(steps, start=1))}
    return EvidenceReleaseExecutionPlan(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseExecutionPlan", "build_evidence_release_execution_plan"]

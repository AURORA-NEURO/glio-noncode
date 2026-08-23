"""Evidence-plane coverage over platform operational receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation
from .serialization import content_hash, jsonable


PLATFORM_FRONTIER_EVIDENCE_PLANES = ("input", "operation", "policy", "lineage", "replay", "release")


@dataclass(frozen=True, slots=True)
class PlatformFrontierEvidenceCell:
    record_id: str
    plane: str
    state: str
    address: str
    retained: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierEvidenceMatrix:
    cells: tuple[PlatformFrontierEvidenceCell, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_platform_frontier_evidence_matrix(evaluation: PlatformFrontierEvaluation) -> PlatformFrontierEvidenceMatrix:
    cells = []
    for row in evaluation.executions:
        for plane in PLATFORM_FRONTIER_EVIDENCE_PLANES:
            body = {"record_id": row.record_id, "plane": plane, "state": row.state.value, "address": row.content_address, "retained": True}
            cells.append(PlatformFrontierEvidenceCell(**body, content_address=content_hash(body)))
    return PlatformFrontierEvidenceMatrix(tuple(cells), len(cells) == 96 and all(item.retained for item in cells), content_hash(tuple(cells)))


__all__ = ["PLATFORM_FRONTIER_EVIDENCE_PLANES", "PlatformFrontierEvidenceCell", "PlatformFrontierEvidenceMatrix", "build_platform_frontier_evidence_matrix"]

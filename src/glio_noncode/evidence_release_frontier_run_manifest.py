"""Run manifest that closes the planned and observed stage list."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseRunManifest:
    run_id: str
    plan_address: str
    provenance_address: str
    stage_ids: tuple[str, ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_run_manifest(run_id: str, plan: Any, provenance: Any, stage_ids: tuple[str, ...]) -> EvidenceReleaseRunManifest:
    body = {"run_id": run_id, "plan_address": plan.content_address, "provenance_address": provenance.content_address, "stage_ids": stage_ids, "accepted": bool(stage_ids)}
    return EvidenceReleaseRunManifest(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseRunManifest", "build_evidence_release_run_manifest"]

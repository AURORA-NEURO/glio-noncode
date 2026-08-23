"""Immutable run provenance for a local evidence-release rehearsal."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseProvenance:
    run_id: str
    fixture_id: str
    plan_address: str
    policy_address: str
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_provenance(run_id: str, fixture: Any, plan: Any, policy: Any) -> EvidenceReleaseProvenance:
    body = {"run_id": run_id, "fixture_id": fixture.fixture_id, "plan_address": plan.content_address, "policy_address": policy.content_address}
    return EvidenceReleaseProvenance(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseProvenance", "build_evidence_release_provenance"]

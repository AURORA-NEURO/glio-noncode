"""Failure rehearsal for malformed, foreign, and unverifiable release inputs."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .evidence_release_frontier_operations import evaluate_reclassification, evaluate_reproducibility_bundle, evaluate_supersession, sign_dossier, verify_signed_dossier
from .evidence_release_frontier_public_data import _bundle, _dossier, _reclassification, _supersession
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseFailureReport:
    cases: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def run_evidence_release_failure_injections() -> EvidenceReleaseFailureReport:
    signed = sign_dossier(_dossier()).output
    cases = ({"case": "invalid-reclassification", "state": evaluate_reclassification({}).state.value, "required": "rejected"}, {"case": "empty-supersession", "state": evaluate_supersession(_supersession(records=[])).state.value, "required": "superseded"}, {"case": "empty-bundle", "state": evaluate_reproducibility_bundle(_bundle(sections=[])).state.value, "required": "review"}, {"case": "wrong-signature", "state": verify_signed_dossier({"signed_dossier": signed}, signing_key="wrong-material").state.value, "required": "rejected"})
    body = {"cases": cases, "accepted": all(item["state"] == item["required"] for item in cases)}
    return EvidenceReleaseFailureReport(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseFailureReport", "run_evidence_release_failure_injections"]

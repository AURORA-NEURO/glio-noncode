"""Safe bundle assembly for release, summary, and artifact receipts."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseBundle:
    manifest_address: str
    artifact_address: str
    summary_address: str
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def assemble_evidence_release_bundle(package: Any, artifacts: Any, summary: Any) -> EvidenceReleaseBundle:
    body = {"manifest_address": package.content_address, "artifact_address": artifacts.content_address, "summary_address": summary.content_address, "accepted": package.complete and artifacts.complete and summary.accepted}
    return EvidenceReleaseBundle(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseBundle", "assemble_evidence_release_bundle"]

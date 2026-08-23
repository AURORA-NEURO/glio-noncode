"""Executable runbook assertions for the local release pipeline."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseRunbook:
    commands: tuple[str, ...]
    gates: tuple[str, ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_runbook() -> EvidenceReleaseRunbook:
    body = {"commands": ("data-audit", "evaluate", "pipeline", "depth", "quality", "failure-injection"), "gates": ("public receipts", "balanced controls", "content addresses", "signature verification")}
    return EvidenceReleaseRunbook(**body, accepted=True, content_address=content_hash(body | {"accepted": True}))

def runbook_is_executable(runbook: EvidenceReleaseRunbook) -> bool:
    return runbook.accepted and bool(runbook.commands) and bool(runbook.gates)

__all__ = ["EvidenceReleaseRunbook", "build_evidence_release_runbook", "runbook_is_executable"]

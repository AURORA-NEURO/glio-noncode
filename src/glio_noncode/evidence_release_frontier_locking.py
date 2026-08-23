"""Deterministic lock identity for one release run."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseLock:
    lock_key: str
    owner: str
    acquired: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def acquire_evidence_release_lock(run_id: str) -> EvidenceReleaseLock:
    body = {"lock_key": "evidence-release:" + run_id, "owner": "local-run", "acquired": bool(run_id)}
    return EvidenceReleaseLock(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseLock", "acquire_evidence_release_lock"]

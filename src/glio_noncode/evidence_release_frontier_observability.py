"""Structured run trace with ordered stage identities."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .serialization import content_hash, jsonable

@dataclass(frozen=True, slots=True)
class EvidenceReleaseTrace:
    run_id: str
    events: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def build_evidence_release_trace(run_id: str, events: tuple[dict[str, Any], ...], *, accepted: bool) -> EvidenceReleaseTrace:
    ordered = tuple(dict(event, sequence=index) for index, event in enumerate(events, start=1))
    body = {"run_id": run_id, "events": ordered, "accepted": accepted and all(item.get("sequence") == index for index, item in enumerate(ordered, start=1))}
    return EvidenceReleaseTrace(**body, content_address=content_hash(body))

__all__ = ["EvidenceReleaseTrace", "build_evidence_release_trace"]

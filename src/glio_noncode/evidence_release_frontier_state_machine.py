"""State transition table for safe lifecycle progression."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_release_frontier_contracts import EvidenceReleaseState
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseStateTransition:
    source: str
    event: str
    target: str
    allowed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceReleaseStateMachine:
    transitions: tuple[EvidenceReleaseStateTransition, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_state_machine() -> EvidenceReleaseStateMachine:
    rows = (("ready", "reclassify", "reclassified"), ("ready", "supersede", "superseded"), ("ready", "bundle", "bundled"), ("ready", "sign", "signed"), ("signed", "verify", "verified"), ("ready", "review", "review"), ("review", "repair", "ready"), ("ready", "context-failure", "blocked"), ("ready", "schema-failure", "rejected"))
    transitions = tuple(EvidenceReleaseStateTransition(source, event, target, source in {item.value for item in EvidenceReleaseState} and target in {item.value for item in EvidenceReleaseState}, content_hash({"source": source, "event": event, "target": target})) for source, event, target in rows)
    body = {"transitions": transitions, "accepted": all(item.allowed for item in transitions)}
    return EvidenceReleaseStateMachine(**body, content_address=content_hash(body))


def transition_is_allowed(machine: EvidenceReleaseStateMachine, source: str, target: str) -> bool:
    return any(item.source == source and item.target == target and item.allowed for item in machine.transitions)


__all__ = ["EvidenceReleaseStateMachine", "EvidenceReleaseStateTransition", "build_evidence_release_state_machine", "transition_is_allowed"]

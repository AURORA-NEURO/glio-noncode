"""Operator console projection for release gates and next actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseOperatorConsole:
    headline: str
    next_actions: tuple[str, ...]
    gate_state: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_operator_console(runtime: Any) -> EvidenceReleaseOperatorConsole:
    blocked = sum(item.observed_state.value == "blocked" for item in runtime.evaluation.executions)
    review = sum(item.observed_state.value == "review" for item in runtime.evaluation.executions)
    actions = ("review blocked rows", "review held rows", "verify signed dossier") if blocked or review else ("publish release receipt",)
    body = {"headline": f"{len(runtime.evaluation.executions)} lifecycle rows evaluated", "next_actions": actions, "gate_state": "hold" if not runtime.accepted else "ready"}
    return EvidenceReleaseOperatorConsole(**body, content_address=content_hash(body))


__all__ = ["EvidenceReleaseOperatorConsole", "build_evidence_release_operator_console"]

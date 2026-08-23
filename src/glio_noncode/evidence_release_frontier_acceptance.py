"""Acceptance record that joins all independent release planes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseAcceptance:
    gate_values: dict[str, bool]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_acceptance(**gates: bool) -> EvidenceReleaseAcceptance:
    values = {str(key): bool(value) for key, value in sorted(gates.items())}
    body = {"gate_values": values, "accepted": bool(values) and all(values.values())}
    return EvidenceReleaseAcceptance(**body, content_address=content_hash(body))


def acceptance_reason(acceptance: EvidenceReleaseAcceptance) -> tuple[str, ...]:
    return tuple(key for key, value in acceptance.gate_values.items() if not value)


__all__ = ["EvidenceReleaseAcceptance", "acceptance_reason", "build_evidence_release_acceptance"]

"""Append-only decision ledger for lifecycle transitions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .evidence_release_frontier_common import receipt
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class EvidenceReleaseDecisionLedger:
    entries: tuple[dict[str, Any], ...]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_evidence_release_decision_ledger(executions: Iterable[Any]) -> EvidenceReleaseDecisionLedger:
    entries = tuple({"sequence": index, "record_id": item.record_id, "state": item.observed_state.value, "address": item.content_address} for index, item in enumerate(executions, start=1))
    result = receipt("decision-ledger", bool(entries), {"entries": entries})
    return EvidenceReleaseDecisionLedger(entries=entries, closed=result.accepted, content_address=result.content_address)


def ledger_is_append_only(ledger: EvidenceReleaseDecisionLedger) -> bool:
    return tuple(item["sequence"] for item in ledger.entries) == tuple(range(1, len(ledger.entries) + 1))


__all__ = ["EvidenceReleaseDecisionLedger", "build_evidence_release_decision_ledger", "ledger_is_append_only"]

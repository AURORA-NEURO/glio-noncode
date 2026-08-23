"""Append-only provenance ledger for source, execution, and release receipts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable

from .cohort_beta_frontier_public_data import CohortBetaFrontierFixture
from .cohort_beta_frontier_runtime_types import CohortBetaFrontierRuntimeStage
from .serialization import content_hash, jsonable


class CohortBetaFrontierLedgerEvent(StrEnum):
    SOURCE_REGISTERED = "source_registered"
    INPUT_ACCEPTED = "input_accepted"
    RESULT_EMITTED = "result_emitted"
    POLICY_APPLIED = "policy_applied"
    RELEASE_BUILT = "release_built"


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierLedgerEntry:
    sequence: int
    event: CohortBetaFrontierLedgerEvent
    subject_id: str
    parent_address: str
    payload_address: str
    immutable: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortBetaFrontierProvenanceLedger:
    fixture_id: str
    entries: tuple[CohortBetaFrontierLedgerEntry, ...]
    head_address: str
    closed: bool
    content_address: str

    def entry_for(self, subject_id: str) -> tuple[CohortBetaFrontierLedgerEntry, ...]:
        return tuple(item for item in self.entries if item.subject_id == subject_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_beta_frontier_provenance_ledger(fixture: CohortBetaFrontierFixture, stages: Iterable[CohortBetaFrontierRuntimeStage]) -> CohortBetaFrontierProvenanceLedger:
    entries: list[CohortBetaFrontierLedgerEntry] = []
    sequence = 1
    previous = "root"
    for source in fixture.sources:
        payload_address = source.content_address
        body = {"sequence": sequence, "event": CohortBetaFrontierLedgerEvent.SOURCE_REGISTERED, "subject_id": source.source_id, "parent_address": previous, "payload_address": payload_address}
        entry = CohortBetaFrontierLedgerEntry(sequence, CohortBetaFrontierLedgerEvent.SOURCE_REGISTERED, source.source_id, previous, payload_address, True, content_hash(body, prefix="ledger-entry"))
        entries.append(entry); previous = entry.content_address; sequence += 1
    for stage in stages:
        event = CohortBetaFrontierLedgerEvent.RESULT_EMITTED if stage.accepted else CohortBetaFrontierLedgerEvent.POLICY_APPLIED
        body = {"sequence": sequence, "event": event, "subject_id": stage.stage_id, "parent_address": previous, "payload_address": stage.output_address}
        entry = CohortBetaFrontierLedgerEntry(sequence, event, stage.stage_id, previous, stage.output_address, True, content_hash(body, prefix="ledger-entry"))
        entries.append(entry); previous = entry.content_address; sequence += 1
    values = tuple(entries)
    closed = bool(values) and all(item.immutable for item in values) and tuple(item.sequence for item in values) == tuple(range(1, len(values) + 1))
    return CohortBetaFrontierProvenanceLedger(fixture.fixture_id, values, previous, closed, content_hash({"fixture": fixture.fixture_id, "entries": values, "head": previous}, prefix="provenance-ledger"))


def verify_cohort_beta_frontier_provenance_ledger(ledger: CohortBetaFrontierProvenanceLedger) -> bool:
    if not ledger.closed or not ledger.entries or ledger.head_address != ledger.entries[-1].content_address:
        return False
    return all(item.parent_address == "root" if item.sequence == 1 else item.parent_address == ledger.entries[item.sequence - 2].content_address for item in ledger.entries)


__all__ = ["CohortBetaFrontierLedgerEntry", "CohortBetaFrontierLedgerEvent", "CohortBetaFrontierProvenanceLedger", "build_cohort_beta_frontier_provenance_ledger", "verify_cohort_beta_frontier_provenance_ledger"]

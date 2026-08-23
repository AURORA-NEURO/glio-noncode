"""Append-only provenance ledger over source and result addresses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_governance import CohortAlphaFrontierLineage
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierLedgerEntry:
    sequence: int
    parent: str
    child: str
    relation: str
    operation: str
    previous_address: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierProvenanceLedger:
    entries: tuple[CohortAlphaFrontierLedgerEntry, ...]
    closed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_provenance_ledger(lineage: CohortAlphaFrontierLineage) -> CohortAlphaFrontierProvenanceLedger:
    previous = "root"
    entries = []
    for index, edge in enumerate(lineage.edges, 1):
        body = {"sequence": index, "parent": edge.parent, "child": edge.child, "relation": edge.relation, "operation": edge.operation, "previous": previous}
        address = content_hash(body, prefix="alpha-ledger-entry")
        entries.append(CohortAlphaFrontierLedgerEntry(index, edge.parent, edge.child, edge.relation, edge.operation, previous, address))
        previous = address
    values = tuple(entries)
    return CohortAlphaFrontierProvenanceLedger(values, lineage.closed and bool(values) and values[-1].content_address == previous and tuple(item.sequence for item in values) == tuple(range(1, len(values) + 1)), content_hash(values, prefix="alpha-provenance-ledger"))


__all__ = ["CohortAlphaFrontierLedgerEntry", "CohortAlphaFrontierProvenanceLedger", "build_cohort_alpha_frontier_provenance_ledger"]

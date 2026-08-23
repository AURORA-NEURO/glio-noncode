"""Public source registry and receipt closure checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningFixture, PlanningSourceReceipt
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningSourceEntry:
    receipt: PlanningSourceReceipt
    allowed_operations: tuple[str, ...]
    citation_role: str
    public_only: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlanningSourceRegistry:
    entries: tuple[PlanningSourceEntry, ...]
    unknown_joins: tuple[str, ...]
    duplicate_ids: tuple[str, ...]
    accepted: bool
    content_address: str

    def for_source(self, source_id: str) -> PlanningSourceEntry:
        return next(item for item in self.entries if item.receipt.source_id == source_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_source_registry(fixture: PlanningFixture) -> PlanningSourceRegistry:
    operation_names = tuple(operation.value for operation in fixture.operations)
    roles = {
        "ncbi-refseq": ("guide_oligo_adaptation", "sequence context"),
        "addgene": ("guide_oligo_adaptation", "perturbation planning"),
        "encode": ("model_system_eligibility", "regulatory context"),
        "pubmed": ("power_replication", "literature context"),
        "gtex": ("model_system_eligibility", "expression context"),
    }
    entries = []
    for receipt in fixture.sources:
        allowed = tuple(dict.fromkeys((roles.get(receipt.source_id, ("aggregate_review", "public context"))[0], "aggregate_review")))
        body = {"receipt": receipt, "allowed_operations": allowed, "citation_role": roles.get(receipt.source_id, ("aggregate_review", "public context"))[1], "public_only": True}
        entries.append(PlanningSourceEntry(**body, content_address=content_hash(body, prefix="planning-source-entry")))
    known = {item.receipt.source_id for item in entries}
    joins = {source_id for record in fixture.records for source_id in record.source_ids}
    unknown = tuple(sorted(joins - known))
    ids = [item.receipt.source_id for item in entries]
    duplicate = tuple(sorted({source_id for source_id in ids if ids.count(source_id) > 1}))
    accepted = bool(entries and not unknown and not duplicate and all(item.public_only and item.receipt.uri.startswith("https://") for item in entries))
    body = {"entries": entries, "unknown_joins": unknown, "duplicate_ids": duplicate, "accepted": accepted}
    return PlanningSourceRegistry(tuple(entries), unknown, duplicate, accepted, content_hash(body, prefix="planning-source-registry"))


__all__ = ["PlanningSourceEntry", "PlanningSourceRegistry", "build_planning_source_registry"]

"""Operation catalog with inputs, outputs, and boundary behavior."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_contracts import CohortAlphaFrontierContractRegistry
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOperationCatalogEntry:
    operation: str
    title: str
    input_count: int
    review_trigger_count: int
    prohibited_claim_count: int
    output_state_set: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierOperationCatalog:
    entries: tuple[CohortAlphaFrontierOperationCatalogEntry, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_operation_catalog(contracts: CohortAlphaFrontierContractRegistry) -> CohortAlphaFrontierOperationCatalog:
    entries = tuple(CohortAlphaFrontierOperationCatalogEntry(contract.operation, contract.title, len(contract.required_fields), len(contract.review_triggers), len(contract.prohibited_claims), ("supported", "partial", "ambiguous", "out_of_domain", "abstained"), content_hash({"operation": contract.operation, "title": contract.title, "inputs": contract.required_fields, "triggers": contract.review_triggers, "prohibited": contract.prohibited_claims}, prefix="alpha-operation-catalog")) for contract in contracts.contracts)
    return CohortAlphaFrontierOperationCatalog(entries, len(entries) == 4 and all(item.input_count >= 5 and item.review_trigger_count >= 3 and item.prohibited_claim_count >= 3 for item in entries), content_hash(entries, prefix="alpha-operation-catalog-report"))


__all__ = ["CohortAlphaFrontierOperationCatalog", "CohortAlphaFrontierOperationCatalogEntry", "build_cohort_alpha_frontier_operation_catalog"]

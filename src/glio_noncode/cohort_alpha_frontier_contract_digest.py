"""Compact digest of contract, schema, and adapter closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_alpha_frontier_adapters import CohortAlphaFrontierAdapterRegistry
from .cohort_alpha_frontier_contracts import CohortAlphaFrontierContractRegistry
from .cohort_alpha_frontier_schema import CohortAlphaFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CohortAlphaFrontierContractDigest:
    operation_count: int
    adapter_count: int
    schema_field_count: int
    contract_address: str
    adapter_address: str
    schema_address: str
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_cohort_alpha_frontier_contract_digest(contracts: CohortAlphaFrontierContractRegistry, adapters: CohortAlphaFrontierAdapterRegistry, schema: CohortAlphaFrontierSchemaReport) -> CohortAlphaFrontierContractDigest:
    body = {"operations": len(contracts.contracts), "adapters": len(adapters.specs), "fields": len(schema.fields), "contracts": contracts.content_address, "adapters_address": adapters.content_address, "schema": schema.content_address}
    return CohortAlphaFrontierContractDigest(body["operations"], body["adapters"], body["fields"], body["contracts"], body["adapters_address"], body["schema"], body["operations"] == 4 and body["adapters"] == 4 and body["fields"] >= 16 and schema.accepted, content_hash(body, prefix="alpha-contract-digest"))


__all__ = ["CohortAlphaFrontierContractDigest", "build_cohort_alpha_frontier_contract_digest"]

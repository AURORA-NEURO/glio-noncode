"""Conformance checks between contracts, adapters, fixture records, and outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_adapters import LinkGraphAlphaFrontierAdapterRegistry
from .link_graph_alpha_frontier_contracts import LinkGraphAlphaFrontierContractReport
from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierConformanceReport:
    checks: tuple[Any, ...]
    operation_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "operation_ids": self.operation_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_conformance(contracts: LinkGraphAlphaFrontierContractReport, adapters: LinkGraphAlphaFrontierAdapterRegistry, evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierConformanceReport:
    contract_ids = {item.operation.value for item in contracts.contracts}
    adapter_ids = {item.operation.value for item in adapters.specs}
    observed_ids = {item.operation for item in evaluation.rows}
    checks = (check("contract_adapter_match", contract_ids == adapter_ids, "contracts and adapters cover the same operations"), check("adapter_replay_match", adapter_ids == observed_ids, "adapters and replay cover the same operations"), check("output_addresses", all(row.adapter.content_address.startswith("sha256:") for row in evaluation.rows), "every output is addressed"), check("contract_acceptance", contracts.accepted and adapters.accepted, "upstream registries accepted"))
    return LinkGraphAlphaFrontierConformanceReport(checks, tuple(sorted(contract_ids)), all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierConformanceReport", "build_link_graph_alpha_frontier_conformance"]

"""Aggregate assurance report joining the independent depth controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_conformance import LinkGraphAlphaFrontierConformanceReport
from .link_graph_alpha_frontier_evidence_matrix import LinkGraphAlphaFrontierEvidenceMatrix
from .link_graph_alpha_frontier_failure_catalog import LinkGraphAlphaFrontierFailureCatalog
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierAssuranceReport:
    checks: tuple[Any, ...]
    component_addresses: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "component_addresses": self.component_addresses, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_alpha_frontier_assurance(conformance: LinkGraphAlphaFrontierConformanceReport, evidence: LinkGraphAlphaFrontierEvidenceMatrix, failures: LinkGraphAlphaFrontierFailureCatalog) -> LinkGraphAlphaFrontierAssuranceReport:
    checks = (check("conformance", conformance.accepted, "adapter and contract conformance"), check("evidence_matrix", evidence.accepted, "method matrix covers the replay"), check("failure_catalog", failures.accepted, "all observed issues have definitions"), check("addresses", all(address.startswith("sha256:") for address in (conformance.content_address, evidence.content_address, failures.content_address)), "assurance components are addressed"))
    return LinkGraphAlphaFrontierAssuranceReport(checks, (conformance.content_address, evidence.content_address, failures.content_address), all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierAssuranceReport", "build_link_graph_alpha_frontier_assurance"]

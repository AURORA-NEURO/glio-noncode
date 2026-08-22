"""Release acceptance checks that compose the alpha assurance planes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_claim_boundary import TopologyAlphaFrontierClaimBoundaryReport
from .topology_alpha_frontier_conformance import TopologyAlphaFrontierConformanceReport
from .topology_alpha_frontier_evidence_matrix import TopologyAlphaFrontierEvidenceMatrix
from .topology_alpha_frontier_failure_catalog import TopologyAlphaFrontierFailureCatalog
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_source_checks import TopologyAlphaFrontierSourceCheckReport


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierAcceptanceCheck:
    check_id: str
    passed: bool
    observed: Any
    requirement: str
    failure_action: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierAcceptanceReport:
    checks: tuple[TopologyAlphaFrontierAcceptanceCheck, ...]
    release_label: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def failed(self) -> tuple[TopologyAlphaFrontierAcceptanceCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "release_label": self.release_label, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_topology_alpha_frontier_acceptance(evaluation: TopologyAlphaFrontierEvaluation, evidence: TopologyAlphaFrontierEvidenceMatrix, claims: TopologyAlphaFrontierClaimBoundaryReport, conformance: TopologyAlphaFrontierConformanceReport, failures: TopologyAlphaFrontierFailureCatalog, sources: TopologyAlphaFrontierSourceCheckReport) -> TopologyAlphaFrontierAcceptanceReport:
    checks = (
        TopologyAlphaFrontierAcceptanceCheck("evaluation", evaluation.accepted, evaluation.state_match_count, "all expected states and issues replay", "retain the failing records"),
        TopologyAlphaFrontierAcceptanceCheck("evidence", evidence.accepted and evidence.record_count == 16, evidence.record_count, "one complete evidence cell per record", "repair source or result receipts"),
        TopologyAlphaFrontierAcceptanceCheck("claims", claims.accepted, claims.receipt_complete_count, "every row has allowed and blocked interpretation boundaries", "restore uncertainty fields"),
        TopologyAlphaFrontierAcceptanceCheck("conformance", conformance.accepted, len(conformance.failed()), "field envelopes are closed or explicitly incomplete", "inspect missing operation fields"),
        TopologyAlphaFrontierAcceptanceCheck("failures", failures.accepted, failures.unknown_codes, "all observed issue codes are catalogued", "add a typed failure definition"),
        TopologyAlphaFrontierAcceptanceCheck("sources", sources.accepted, len(sources.failed()), "source receipts are public, hashed, contextual, and used", "quarantine the source boundary"),
    )
    return TopologyAlphaFrontierAcceptanceReport(checks, "topology-alpha-frontier-accepted" if all(item.passed for item in checks) else "topology-alpha-frontier-review", all(item.passed for item in checks))


__all__ = ["TopologyAlphaFrontierAcceptanceCheck", "TopologyAlphaFrontierAcceptanceReport", "evaluate_topology_alpha_frontier_acceptance"]

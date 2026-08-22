"""Allowed descriptions and blocked interpretations for alpha outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierClaim:
    claim_id: str
    operation: str
    result_state: str
    allowed_statement: str
    blocked_statement: str
    required_receipts: tuple[str, ...]
    uncertainty_fields: tuple[str, ...]
    release_scope: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierClaimBoundaryReport:
    claims: tuple[TopologyAlphaFrontierClaim, ...]
    allowed_count: int
    blocked_count: int
    receipt_complete_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_operation(self, operation: str) -> tuple[TopologyAlphaFrontierClaim, ...]:
        return tuple(item for item in self.claims if item.operation == operation)

    def for_state(self, state: str) -> tuple[TopologyAlphaFrontierClaim, ...]:
        return tuple(item for item in self.claims if item.result_state == state)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"claims": [item.to_dict() for item in self.claims], "allowed_count": self.allowed_count, "blocked_count": self.blocked_count, "receipt_complete_count": self.receipt_complete_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_claim_boundary(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierClaimBoundaryReport:
    statements = {
        "boundary_motif": ("The aggregate reports context-qualified boundary motif orientation observations.", "The orientation output proves insulation, enhancer activity, or a clinical effect."),
        "ctcf_cohesin": ("The aggregate compares declared CTCF and cohesin channel values.", "The channel deltas prove occupancy, mechanism, or intervention response."),
        "idh_insulator": ("The aggregate summarizes IDH-state insulator and methylation measurements.", "The summary proves a disease mechanism or patient-specific outcome."),
        "sv_rewire": ("The aggregate simulates declared contact-edge loss, gain, and rewiring.", "The simulation proves a structural event occurred in a subject or predicts phenotype."),
    }
    claims = tuple(
        TopologyAlphaFrontierClaim(
            f"claim-{index:02d}",
            row.operation,
            row.observed_state,
            statements[row.operation][0],
            statements[row.operation][1],
            ("context_key", "source_ids", "content_address"),
            ("state", "issue_codes", "evidence_ids", "source_versions"),
            "public_aggregate_research",
        )
        for index, row in enumerate(evaluation.rows, start=1)
    )
    complete = sum(bool(item.required_receipts) and bool(item.uncertainty_fields) for item in claims)
    return TopologyAlphaFrontierClaimBoundaryReport(claims, len(claims), len(claims), complete, len(claims) == 16 and complete == 16)


def allowed_topology_alpha_frontier_claims(report: TopologyAlphaFrontierClaimBoundaryReport) -> tuple[TopologyAlphaFrontierClaim, ...]:
    return tuple(item for item in report.claims if item.result_state == "supported")


__all__ = ["TopologyAlphaFrontierClaim", "TopologyAlphaFrontierClaimBoundaryReport", "allowed_topology_alpha_frontier_claims", "build_topology_alpha_frontier_claim_boundary"]

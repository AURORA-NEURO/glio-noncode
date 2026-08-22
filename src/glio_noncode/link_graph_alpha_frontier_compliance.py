"""Boundary compliance checks for public aggregate and non-clinical outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .link_graph_alpha_frontier_public_data import LinkGraphAlphaFrontierFixture
from .link_graph_alpha_frontier_support import check
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierBoundaryReport:
    boundary: str
    claims_allowed: tuple[str, ...]
    claims_blocked: tuple[str, ...]
    checks: tuple[Any, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"boundary": self.boundary, "claims_allowed": self.claims_allowed, "claims_blocked": self.claims_blocked, "checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_link_graph_alpha_frontier_boundary(fixture: LinkGraphAlphaFrontierFixture, evaluation: LinkGraphAlphaFrontierEvaluation) -> LinkGraphAlphaFrontierBoundaryReport:
    allowed = ("candidate link generation", "state and issue accounting", "source receipt inspection", "aggregate replay")
    blocked = ("clinical interpretation", "patient-level inference", "causal mechanism claim", "preferred target selection")
    checks = (
        check("aggregate_boundary", fixture.boundary == "public_aggregate_non_patient", "fixture boundary is public aggregate"),
        check("blocked_claims_declared", len(blocked) == 4, "blocked claims are explicit"),
        check("context_controls_pass", all(row.observed_state == "out_of_domain" for row in evaluation.rows if row.record_id.endswith("C3")), "foreign context controls remain outside the slice"),
        check("no_clinical_rows", all("patient" not in record.context_key.lower() for record in fixture.records), "fixture records are not patient-labeled"),
    )
    return LinkGraphAlphaFrontierBoundaryReport(fixture.boundary, allowed, blocked, checks, all(item.passed for item in checks))


__all__ = ["LinkGraphAlphaFrontierBoundaryReport", "evaluate_link_graph_alpha_frontier_boundary"]

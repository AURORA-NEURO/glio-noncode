"""Control definitions for missing, foreign, weak, and contradictory rows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierControlDefinition:
    control_id: str
    operation: str
    issue_code: str
    expected_state: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierControlCatalog:
    controls: tuple[LinkGraphBetaFrontierControlDefinition, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_issue(self, issue_code: str) -> tuple[LinkGraphBetaFrontierControlDefinition, ...]:
        return tuple(item for item in self.controls if item.issue_code == issue_code)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"controls": [item.to_dict() for item in self.controls], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_link_graph_beta_frontier_control_catalog(evaluation: LinkGraphBetaFrontierEvaluation | None = None) -> LinkGraphBetaFrontierControlCatalog:
    controls = (LinkGraphBetaFrontierControlDefinition("missing-evidence", "all", "missing_evidence", "abstained", "empty input must not become negative evidence"), LinkGraphBetaFrontierControlDefinition("foreign-context", "all", "context_mismatch", "out_of_domain", "foreign context is not transported"), LinkGraphBetaFrontierControlDefinition("weak-q", "molecular_qtl", "weak_q_value", "partial", "weak q-value remains descriptive"), LinkGraphBetaFrontierControlDefinition("direction-conflict", "allele_specific", "direction_conflict", "contradictory", "gain and loss remain contradictory"), LinkGraphBetaFrontierControlDefinition("replicate-pair", "activity_by_contact", "replicate_pair", "partial", "replicate observations remain method-limited"), LinkGraphBetaFrontierControlDefinition("alternative-gene", "coaccessibility", "alternative_gene", "partial", "alternative genes remain visible"))
    accepted = evaluation is None or all(any(issue in row.observed_issue_codes for issue in (control.issue_code,)) for control in controls for row in evaluation.rows if control.issue_code in row.observed_issue_codes)
    return LinkGraphBetaFrontierControlCatalog(controls, accepted)


__all__ = ["LinkGraphBetaFrontierControlCatalog", "LinkGraphBetaFrontierControlDefinition", "build_link_graph_beta_frontier_control_catalog"]

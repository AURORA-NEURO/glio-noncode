"""Failure definitions and deterministic remediation guidance."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_alpha_frontier_fixture_eval import LinkGraphAlphaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierFailureDefinition:
    failure_code: str
    severity: str
    meaning: str
    remediation: str
    blocks_release: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphAlphaFrontierFailureCatalog:
    definitions: tuple[LinkGraphAlphaFrontierFailureDefinition, ...]
    observed_codes: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def definition(self, failure_code: str) -> LinkGraphAlphaFrontierFailureDefinition:
        for item in self.definitions:
            if item.failure_code == failure_code:
                return item
        raise KeyError(failure_code)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"definitions": [item.to_dict() for item in self.definitions], "observed_codes": self.observed_codes, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_alpha_frontier_failure_definitions() -> tuple[LinkGraphAlphaFrontierFailureDefinition, ...]:
    return (
        LinkGraphAlphaFrontierFailureDefinition("context_mismatch", "boundary", "evidence context differs from requested context", "retain as out_of_domain and inspect transport", True),
        LinkGraphAlphaFrontierFailureDefinition("direction_disagreement", "review", "perturbation directions disagree", "inspect source methods and do not collapse directions", True),
        LinkGraphAlphaFrontierFailureDefinition("contradictory_evidence", "review", "graph evidence carries contradiction", "inspect edge-level source paths", True),
        LinkGraphAlphaFrontierFailureDefinition("low_support", "review", "perturbation support is weak", "retain the row with review disposition", False),
        LinkGraphAlphaFrontierFailureDefinition("weak_contact", "review", "contact signal is weak", "retain assay scale and resolution", False),
        LinkGraphAlphaFrontierFailureDefinition("alternative_gene", "review", "more than one candidate gene remains", "retain all alternatives", True),
        LinkGraphAlphaFrontierFailureDefinition("single_method", "review", "only one method is present", "do not treat a single path as consensus", False),
        LinkGraphAlphaFrontierFailureDefinition("single_assay", "review", "only one contact assay is present", "retain assay identity", False),
        LinkGraphAlphaFrontierFailureDefinition("single_evidence", "review", "only one graph evidence path is present", "retain graph edge as partial", False),
        LinkGraphAlphaFrontierFailureDefinition("missing_components", "abstain", "tethering components are incomplete", "abstain until required components arrive", True),
        LinkGraphAlphaFrontierFailureDefinition("tethering_ambiguity", "review", "tethering candidates tie", "retain all candidate genes", True),
    )


def classify_link_graph_alpha_frontier_issues(evaluation: LinkGraphAlphaFrontierEvaluation) -> dict[str, tuple[str, ...]]:
    return {row.record_id: row.observed_issue_codes for row in evaluation.rows}


def build_link_graph_alpha_frontier_failure_catalog(evaluation: LinkGraphAlphaFrontierEvaluation | None = None) -> LinkGraphAlphaFrontierFailureCatalog:
    definitions = default_link_graph_alpha_frontier_failure_definitions()
    observed = tuple(sorted({code for row in (evaluation.rows if evaluation else ()) for code in row.observed_issue_codes}))
    return LinkGraphAlphaFrontierFailureCatalog(definitions, observed, all(code in {item.failure_code for item in definitions} for code in observed))


__all__ = ["LinkGraphAlphaFrontierFailureCatalog", "LinkGraphAlphaFrontierFailureDefinition", "build_link_graph_alpha_frontier_failure_catalog", "classify_link_graph_alpha_frontier_issues", "default_link_graph_alpha_frontier_failure_definitions"]

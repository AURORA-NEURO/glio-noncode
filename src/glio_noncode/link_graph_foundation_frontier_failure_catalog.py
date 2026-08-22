"""Known baseline issue definitions and remediation rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_foundation_frontier_fixture_eval import LinkGraphFoundationFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierFailureDefinition:
    code: str
    severity: str
    meaning: str
    remediation: str
    blocks_release: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphFoundationFrontierFailureCatalog:
    definitions: tuple[LinkGraphFoundationFrontierFailureDefinition, ...]
    observed_codes: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def definition(self, code: str) -> LinkGraphFoundationFrontierFailureDefinition:
        for item in self.definitions:
            if item.code == code:
                return item
        raise KeyError(code)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"definitions": [item.to_dict() for item in self.definitions], "observed_codes": self.observed_codes, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_foundation_frontier_failure_definitions() -> tuple[LinkGraphFoundationFrontierFailureDefinition, ...]:
    return tuple(LinkGraphFoundationFrontierFailureDefinition(code, severity, meaning, remediation, blocks) for code, severity, meaning, remediation, blocks in (("context_mismatch", "boundary", "row context is outside the requested slice", "retain out_of_domain or abstain", True), ("multiple_overlaps", "review", "multiple intervals overlap", "retain every element", True), ("no_overlap", "review", "no interval overlaps", "retain absent as descriptive", False), ("distance_tie", "review", "nearest genes tie", "retain all tied genes", True), ("distance_window", "abstain", "nearest distance exceeds window", "inspect a broader declared window", True), ("multiple_ccres", "review", "multiple cCREs overlap", "retain all assignments", True), ("no_ccre", "review", "no cCRE matches", "retain absent assignment", False), ("single_method", "review", "only one evidence method is present", "do not call consensus", False), ("contradictory_evidence", "review", "evidence paths disagree", "inspect each method", True)))


def build_link_graph_foundation_frontier_failure_catalog(evaluation: LinkGraphFoundationFrontierEvaluation | None = None) -> LinkGraphFoundationFrontierFailureCatalog:
    definitions = default_link_graph_foundation_frontier_failure_definitions()
    observed = tuple(sorted({code for row in (evaluation.rows if evaluation else ()) for code in row.observed_issue_codes}))
    return LinkGraphFoundationFrontierFailureCatalog(definitions, observed, all(code in {item.code for item in definitions} for code in observed))


__all__ = ["LinkGraphFoundationFrontierFailureCatalog", "LinkGraphFoundationFrontierFailureDefinition", "build_link_graph_foundation_frontier_failure_catalog", "default_link_graph_foundation_frontier_failure_definitions"]

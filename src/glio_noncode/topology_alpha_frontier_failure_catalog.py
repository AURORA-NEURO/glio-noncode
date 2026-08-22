"""Failure semantics and remediation guidance for alpha review paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierFailureDefinition:
    code: str
    category: str
    severity: str
    affected_operations: tuple[str, ...]
    state_effect: str
    reviewer_action: str
    release_effect: str
    detectable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierFailureCatalog:
    definitions: tuple[TopologyAlphaFrontierFailureDefinition, ...]
    observed_codes: tuple[str, ...]
    unknown_codes: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_code(self, code: str) -> TopologyAlphaFrontierFailureDefinition:
        for item in self.definitions:
            if item.code == code:
                return item
        raise KeyError(code)

    def by_category(self, category: str) -> tuple[TopologyAlphaFrontierFailureDefinition, ...]:
        return tuple(item for item in self.definitions if item.category == category)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"definitions": [item.to_dict() for item in self.definitions], "observed_codes": self.observed_codes, "unknown_codes": self.unknown_codes, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_topology_alpha_frontier_failure_definitions() -> tuple[TopologyAlphaFrontierFailureDefinition, ...]:
    operations = ("boundary_motif", "ctcf_cohesin", "idh_insulator", "sv_rewire")
    return (
        TopologyAlphaFrontierFailureDefinition("context_mismatch", "context", "error", operations, "out_of_domain", "verify the exact context before reuse", "block transport"),
        TopologyAlphaFrontierFailureDefinition("orientation_ambiguity", "disagreement", "warning", ("boundary_motif",), "ambiguous", "inspect opposing motif orientations", "retain review"),
        TopologyAlphaFrontierFailureDefinition("channel_disagreement", "disagreement", "warning", ("ctcf_cohesin",), "ambiguous", "inspect CTCF and cohesin channel spread", "retain review"),
        TopologyAlphaFrontierFailureDefinition("invalid_idh_insulator_row", "validation", "error", ("idh_insulator",), "partial", "repair the molecular state vocabulary", "block qualified interpretation"),
        TopologyAlphaFrontierFailureDefinition("missing_edge_edit", "missingness", "warning", ("sv_rewire",), "partial", "request the edge edit receipt", "retain explicit missingness"),
        TopologyAlphaFrontierFailureDefinition("unknown_edge_id", "integrity", "warning", ("sv_rewire",), "partial", "resolve the edge against the contact set", "retain review"),
    )


def build_topology_alpha_frontier_failure_catalog(evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierFailureCatalog:
    definitions = default_topology_alpha_frontier_failure_definitions()
    observed = tuple(sorted({code for row in evaluation.rows for code in row.observed_issue_codes}))
    known = {item.code for item in definitions}
    unknown = tuple(sorted(set(observed) - known))
    return TopologyAlphaFrontierFailureCatalog(definitions, observed, unknown, not unknown and all(item.detectable for item in definitions))


def classify_topology_alpha_frontier_issues(catalog: TopologyAlphaFrontierFailureCatalog) -> dict[str, tuple[str, ...]]:
    return {category: tuple(item.code for item in catalog.by_category(category)) for category in sorted({item.category for item in catalog.definitions})}


__all__ = ["TopologyAlphaFrontierFailureCatalog", "TopologyAlphaFrontierFailureDefinition", "build_topology_alpha_frontier_failure_catalog", "classify_topology_alpha_frontier_issues", "default_topology_alpha_frontier_failure_definitions"]

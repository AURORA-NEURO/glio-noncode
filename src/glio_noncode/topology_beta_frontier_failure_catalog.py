"""Failure semantics and remediation guidance for beta review paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierFailureDefinition:
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
class TopologyBetaFrontierFailureCatalog:
    definitions: tuple[TopologyBetaFrontierFailureDefinition, ...]
    observed_codes: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_code(self, code: str) -> TopologyBetaFrontierFailureDefinition:
        for item in self.definitions:
            if item.code == code:
                return item
        raise KeyError(code)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"definitions": [item.to_dict() for item in self.definitions], "observed_codes": self.observed_codes, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_topology_beta_frontier_failure_definitions() -> tuple[TopologyBetaFrontierFailureDefinition, ...]:
    return (
        TopologyBetaFrontierFailureDefinition("missing_loop_metadata", "metadata", "warning", ("loop_stripe",), "partial", "request resolution and caller receipt", "retain in review"),
        TopologyBetaFrontierFailureDefinition("missing_bait_id", "metadata", "warning", ("promoter_capture",), "partial", "request bait identity receipt", "retain in review"),
        TopologyBetaFrontierFailureDefinition("replicate_disagreement", "replicate", "warning", ("loop_stripe", "promoter_capture", "enhancer_promoter_contact"), "ambiguous", "inspect replicate spread and assay agreement", "do not collapse to support"),
        TopologyBetaFrontierFailureDefinition("component_disagreement", "replicate", "warning", ("activity_by_contact",), "ambiguous", "inspect activity and contact component spread", "do not publish an unqualified product"),
        TopologyBetaFrontierFailureDefinition("context_mismatch", "context", "error", ("loop_stripe", "promoter_capture", "enhancer_promoter_contact", "activity_by_contact"), "out_of_domain", "verify exact context before reuse", "block transport"),
        TopologyBetaFrontierFailureDefinition("no_contact_observations", "missingness", "warning", ("enhancer_promoter_contact",), "absent", "record missing contact evidence", "retain explicit absence"),
        TopologyBetaFrontierFailureDefinition("missing_activity", "missingness", "warning", ("activity_by_contact",), "abstained", "record missing activity evidence", "retain abstention"),
    )


def build_topology_beta_frontier_failure_catalog(evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierFailureCatalog:
    definitions = default_topology_beta_frontier_failure_definitions()
    observed = tuple(sorted({code for row in evaluation.rows for code in row.observed_issue_codes}))
    known = {item.code for item in definitions}
    return TopologyBetaFrontierFailureCatalog(definitions, observed, set(observed) <= known and all(item.detectable for item in definitions))


def classify_topology_beta_frontier_issues(catalog: TopologyBetaFrontierFailureCatalog) -> dict[str, tuple[str, ...]]:
    return {category: tuple(item.code for item in catalog.definitions if item.category == category) for category in sorted({item.category for item in catalog.definitions})}


__all__ = ["TopologyBetaFrontierFailureCatalog", "TopologyBetaFrontierFailureDefinition", "build_topology_beta_frontier_failure_catalog", "classify_topology_beta_frontier_issues", "default_topology_beta_frontier_failure_definitions"]

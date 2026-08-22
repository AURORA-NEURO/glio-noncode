"""Failure definitions for beta data, replay, and release gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .link_graph_beta_frontier_fixture_eval import LinkGraphBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierFailureDefinition:
    failure_id: str
    trigger: str
    severity: str
    response: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LinkGraphBetaFrontierFailureCatalog:
    definitions: tuple[LinkGraphBetaFrontierFailureDefinition, ...]
    observed_failure_ids: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"definitions": [item.to_dict() for item in self.definitions], "observed_failure_ids": self.observed_failure_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_link_graph_beta_frontier_failure_definitions() -> tuple[LinkGraphBetaFrontierFailureDefinition, ...]:
    return (LinkGraphBetaFrontierFailureDefinition("missing-evidence", "empty observations", "review", "abstain"), LinkGraphBetaFrontierFailureDefinition("context-mismatch", "only foreign context rows", "blocking", "quarantine"), LinkGraphBetaFrontierFailureDefinition("direction-conflict", "gain and loss in one group", "review", "retain contradiction"), LinkGraphBetaFrontierFailureDefinition("replay-mismatch", "expected state or issue differs", "blocking", "hold release"), LinkGraphBetaFrontierFailureDefinition("receipt-break", "source ID or checksum is invalid", "blocking", "hold release"))


def build_link_graph_beta_frontier_failure_catalog(evaluation: LinkGraphBetaFrontierEvaluation | None = None) -> LinkGraphBetaFrontierFailureCatalog:
    definitions = default_link_graph_beta_frontier_failure_definitions()
    observed = set()
    if evaluation is not None:
        for row in evaluation.rows:
            observed.update({"replay-mismatch"} if not row.state_match or not row.issue_match else set())
            observed.update({"missing-evidence"} if "missing_evidence" in row.observed_issue_codes else set())
            observed.update({"context-mismatch"} if "context_mismatch" in row.observed_issue_codes else set())
            observed.update({"direction-conflict"} if "direction_conflict" in row.observed_issue_codes else set())
    return LinkGraphBetaFrontierFailureCatalog(definitions, tuple(sorted(observed)), evaluation is None or evaluation.accepted)


__all__ = ["LinkGraphBetaFrontierFailureCatalog", "LinkGraphBetaFrontierFailureDefinition", "build_link_graph_beta_frontier_failure_catalog", "default_link_graph_beta_frontier_failure_definitions"]

"""Invariant checks for Domain 14 lifecycle boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleInvariant:
    invariant_id: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleInvariantResult:
    invariant_id: str
    passed: bool
    observed: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleInvariantReport:
    results: tuple[EvidenceLifecycleInvariantResult, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_evidence_lifecycle_invariants() -> tuple[EvidenceLifecycleInvariant, ...]:
    return tuple(EvidenceLifecycleInvariant(item, detail, content_hash({"invariant_id": item, "detail": detail})) for item, detail in (("context-preserved", "all fixture records retain one exact context"), ("positive-control-separated", "positive and control roles remain separate"), ("citation-issues-visible", "malformed citation rows remain visible"), ("graph-history-retained", "superseded claims remain in history"), ("edge-no-averaging", "edge reports do not average conflicting claims"), ("disagreement-visible", "contradictory observations remain separate"), ("source-addressed", "source receipts have content addresses"), ("execution-addressed", "executions have content addresses"), ("replay-stable", "replay is deterministic"), ("research-boundary", "release uses remain research scoped")))


def validation_lifecycle_observation_map(*, context_preserved: bool, positive_control_separated: bool, citation_issues_visible: bool, graph_history_retained: bool, edge_no_averaging: bool, disagreement_visible: bool, source_addressed: bool, execution_addressed: bool, replay_stable: bool, research_boundary: bool) -> dict[str, bool]:
    return {"context-preserved": context_preserved, "positive-control-separated": positive_control_separated, "citation-issues-visible": citation_issues_visible, "graph-history-retained": graph_history_retained, "edge-no-averaging": edge_no_averaging, "disagreement-visible": disagreement_visible, "source-addressed": source_addressed, "execution-addressed": execution_addressed, "replay-stable": replay_stable, "research-boundary": research_boundary}


def run_evidence_lifecycle_invariants(observations: dict[str, bool]) -> EvidenceLifecycleInvariantReport:
    results = []
    for invariant in default_evidence_lifecycle_invariants():
        observed = bool(observations.get(invariant.invariant_id, False))
        body = {"invariant_id": invariant.invariant_id, "passed": observed, "observed": observed}
        results.append(EvidenceLifecycleInvariantResult(**body, content_address=content_hash(body)))
    body = {"results": tuple(results), "accepted": all(item.passed for item in results)}
    return EvidenceLifecycleInvariantReport(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleInvariant", "EvidenceLifecycleInvariantReport", "EvidenceLifecycleInvariantResult", "default_evidence_lifecycle_invariants", "run_evidence_lifecycle_invariants", "validation_lifecycle_observation_map"]

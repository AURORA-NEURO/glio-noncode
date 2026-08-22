"""Reusable invariant checks for extension modules and release tooling."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .causal_frontier_public_data import CausalFrontierOperation
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CausalFrontierInvariant:
    invariant_id: str
    operation: CausalFrontierOperation | None
    description: str
    severity: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.invariant_id, "invariant_id")
        require_non_empty(self.description, "description")
        if self.severity not in {"review", "blocking"}:
            raise ValueError("invariant severity must be review or blocking")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierInvariantResult:
    invariant_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierInvariantReport:
    invariants: tuple[CausalFrontierInvariant, ...]
    results: tuple[CausalFrontierInvariantResult, ...]
    accepted: bool
    content_address: str

    @property
    def failed_ids(self) -> tuple[str, ...]:
        return tuple(item.invariant_id for item in self.results if not item.passed)

    def by_operation(self, operation: CausalFrontierOperation) -> tuple[CausalFrontierInvariantResult, ...]:
        ids = {item.invariant_id for item in self.invariants if item.operation is operation}
        return tuple(item for item in self.results if item.invariant_id in ids)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_ids": list(self.failed_ids)}


def default_causal_frontier_invariants() -> tuple[CausalFrontierInvariant, ...]:
    rows = (
        ("context-preserved", None, "every operation retains the exact context key", "blocking"),
        ("content-addressed", None, "every receipt has a content address", "blocking"),
        ("positive-control-separated", None, "positive and control roles do not collapse", "blocking"),
        ("bounded-posterior", CausalFrontierOperation.POSTERIOR_DECOMPOSITION, "posterior component values remain bounded", "blocking"),
        ("support-threshold-visible", CausalFrontierOperation.DRIVER_POSTERIOR, "support threshold and low-support state remain visible", "review"),
        ("abstention-visible", CausalFrontierOperation.SELECTIVE_PREDICTION, "uncertainty and abstention remain visible", "blocking"),
        ("dossier-addressed", CausalFrontierOperation.DOSSIER_PUBLICATION, "dossier binds evidence addresses", "blocking"),
        ("source-receipts", None, "all cited source IDs resolve", "blocking"),
        ("issue-vocabulary", None, "all issue codes are declared", "blocking"),
        ("replay-stable", None, "repeated runs produce stable addresses", "blocking"),
    )
    return tuple(CausalFrontierInvariant(*row, content_hash(row)) for row in rows)


def run_causal_frontier_invariants(
    observations: dict[str, Any],
    *,
    invariants: Iterable[CausalFrontierInvariant] | None = None,
) -> CausalFrontierInvariantReport:
    selected = tuple(invariants or default_causal_frontier_invariants())
    results: list[CausalFrontierInvariantResult] = []
    for invariant in selected:
        value = observations.get(invariant.invariant_id, False)
        passed = bool(value)
        body = {
            "invariant_id": invariant.invariant_id,
            "passed": passed,
            "observed": value,
            "expected": True,
            "detail": invariant.description,
        }
        results.append(CausalFrontierInvariantResult(**body, content_address=content_hash(body)))
    body = {"invariants": selected, "results": tuple(results), "accepted": all(item.passed for item in results)}
    return CausalFrontierInvariantReport(**body, content_address=content_hash(body))


def causal_frontier_observation_map(
    *,
    context_preserved: bool,
    content_addressed: bool,
    positive_control_separated: bool,
    bounded_posterior: bool,
    support_threshold_visible: bool,
    abstention_visible: bool,
    dossier_addressed: bool,
    source_receipts: bool,
    issue_vocabulary: bool,
    replay_stable: bool,
) -> dict[str, bool]:
    return {
        "context-preserved": context_preserved,
        "content-addressed": content_addressed,
        "positive-control-separated": positive_control_separated,
        "bounded-posterior": bounded_posterior,
        "support-threshold-visible": support_threshold_visible,
        "abstention-visible": abstention_visible,
        "dossier-addressed": dossier_addressed,
        "source-receipts": source_receipts,
        "issue-vocabulary": issue_vocabulary,
        "replay-stable": replay_stable,
    }


__all__ = [
    "CausalFrontierInvariant",
    "CausalFrontierInvariantReport",
    "CausalFrontierInvariantResult",
    "causal_frontier_observation_map",
    "default_causal_frontier_invariants",
    "run_causal_frontier_invariants",
]

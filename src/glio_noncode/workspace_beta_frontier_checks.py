"""Cross-layer invariants for the C05-C08 projection frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_public_data import BetaFrontierFixture


@dataclass(frozen=True, slots=True)
class BetaFrontierInvariant:
    invariant_id: str
    severity: str
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.invariant_id, "invariant_id")
        require_non_empty(self.severity, "severity")
        require_non_empty(self.detail, "detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierInvariantResult:
    invariant_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierInvariantReport:
    fixture_id: str
    results: tuple[BetaFrontierInvariantResult, ...]
    accepted: bool
    failed_ids: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.results)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def default_beta_frontier_invariants() -> tuple[BetaFrontierInvariant, ...]:
    values = (
        ("context-exact", "blocking", "fixture rows use the declared context"),
        ("source-addressed", "blocking", "source receipts are content addressed"),
        ("execution-addressed", "blocking", "execution receipts are content addressed"),
        ("positive-paths", "blocking", "each operation has one positive path"),
        ("control-paths", "blocking", "each operation has three control paths"),
        ("state-visible", "blocking", "partial, absent, and contradiction states stay visible"),
        ("foreign-context", "blocking", "foreign context has an explicit issue"),
        ("topology-edge-bound", "advisory", "topology output declares edge count"),
        ("causal-alternatives", "advisory", "causal alternatives are retained"),
        ("posterior-residual", "advisory", "posterior residual remains inspectable"),
        ("table-facets", "advisory", "table output retains facets"),
        ("output-jsonable", "blocking", "all execution output is serializable"),
        ("fixture-versioned", "blocking", "fixture version is declared"),
        ("boundary-declared", "blocking", "public aggregate boundary is declared"),
        ("operation-coverage", "blocking", "all four operations are present"),
        ("replay-shape", "advisory", "execution count matches fixture count"),
        ("issue-shape", "advisory", "control issues are non-empty"),
        ("empty-visible", "advisory", "at least one absent output exists"),
        ("partial-visible", "advisory", "at least one partial output exists"),
        ("address-format", "blocking", "addresses use sha256 prefix"),
    )
    return tuple(BetaFrontierInvariant(invariant_id=item[0], severity=item[1], detail=item[2], content_address=content_hash(item)) for item in values)


def _result(invariant: BetaFrontierInvariant, passed: bool, observed: Any, required: Any) -> BetaFrontierInvariantResult:
    body = {"invariant_id": invariant.invariant_id, "passed": passed, "observed": observed, "required": required, "detail": invariant.detail}
    return BetaFrontierInvariantResult(**body, content_address=content_hash(body))


def run_beta_frontier_invariants(fixture: BetaFrontierFixture, evaluation: BetaFrontierEvaluation) -> BetaFrontierInvariantReport:
    """Evaluate deterministic package-wide invariants."""

    execution_outputs = [item.output for item in evaluation.executions]
    executions = evaluation.executions
    observed = {
        "context-exact": all(item.context_key == fixture.context_key for item in fixture.records),
        "source-addressed": all(item.content_address.startswith("sha256:") for item in fixture.sources),
        "execution-addressed": all(item.content_address.startswith("sha256:") for item in executions),
        "positive-paths": sum(item.role.value == "positive" for item in executions) == 4,
        "control-paths": sum(item.role.value == "control" for item in executions) == 12,
        "state-visible": all(item.state for item in executions),
        "foreign-context": any("context_mismatch" in item.issue_codes for item in executions),
        "topology-edge-bound": all("edge_count" in item.output for item in executions if item.operation.value == "topology_viewport" and item.state != "invalid"),
        "causal-alternatives": any(item.output.get("alternative_edge_ids") for item in executions if item.operation.value == "causal_chain"),
        "posterior-residual": all("residual" in item.output for item in executions if item.operation.value == "posterior_decomposition"),
        "table-facets": all("facets" in item.output for item in executions if item.operation.value == "evidence_table"),
        "output-jsonable": all(isinstance(item, dict) for item in execution_outputs),
        "fixture-versioned": bool(fixture.fixture_version),
        "boundary-declared": fixture.evidence_boundary == "public_aggregate_non_patient",
        "operation-coverage": len({item.operation for item in executions}) == 4,
        "replay-shape": len(executions) == len(fixture.records),
        "issue-shape": all(item.issue_codes for item in executions if item.role.value == "control"),
        "empty-visible": any(item.state == "absent" for item in executions),
        "partial-visible": any(item.state == "partial" for item in executions),
        "address-format": all(item.content_address.startswith("sha256:") for item in executions),
    }
    results = tuple(_result(item, bool(observed[item.invariant_id]), observed[item.invariant_id], True) for item in default_beta_frontier_invariants())
    failed = tuple(item.invariant_id for item in results if not item.passed)
    body = {"fixture_id": fixture.fixture_id, "results": results, "accepted": not failed, "failed_ids": failed}
    return BetaFrontierInvariantReport(**body, content_address=content_hash(body))


def beta_frontier_invariants_from_execution(fixture: BetaFrontierFixture, evaluation: BetaFrontierEvaluation) -> BetaFrontierInvariantReport:
    return run_beta_frontier_invariants(fixture, evaluation)


def beta_frontier_observation_map(evaluation: BetaFrontierEvaluation) -> dict[str, dict[str, Any]]:
    return {item.record_id: {"state": item.state, "issues": item.issue_codes, "address": item.content_address} for item in evaluation.executions}


__all__ = ["BetaFrontierInvariant", "BetaFrontierInvariantReport", "BetaFrontierInvariantResult", "beta_frontier_invariants_from_execution", "beta_frontier_observation_map", "default_beta_frontier_invariants", "run_beta_frontier_invariants"]

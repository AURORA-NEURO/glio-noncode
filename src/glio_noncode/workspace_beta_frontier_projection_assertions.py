"""Operation-specific assertions for the C05-C08 projection outputs.

The core projection module validates its own dataclasses.  This layer validates
the cross-operation shape that a release package exposes after serialization.
It is intentionally independent from the quality gate so a failed assertion
can be inspected without changing the promotion decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation, BetaFrontierExecution
from .workspace_beta_frontier_public_data import BetaFrontierOperation


@dataclass(frozen=True, slots=True)
class BetaFrontierProjectionAssertion:
    """One serialized projection assertion."""

    assertion_id: str
    record_id: str | None
    operation: BetaFrontierOperation | None
    passed: bool
    severity: str
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("assertion_id", "severity", "detail", "content_address"):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierProjectionAudit:
    """Independent serialized-output audit."""

    fixture_id: str
    assertions: tuple[BetaFrontierProjectionAssertion, ...]
    accepted: bool
    blocking_failures: tuple[str, ...]
    advisory_failures: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.assertions)

    @property
    def blocking_count(self) -> int:
        return sum(not item.passed and item.severity == "blocking" for item in self.assertions)

    def for_operation(self, operation: BetaFrontierOperation) -> tuple[BetaFrontierProjectionAssertion, ...]:
        return tuple(item for item in self.assertions if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count, "blocking_count": self.blocking_count}


def _assertion(
    index: int,
    record_id: str | None,
    operation: BetaFrontierOperation | None,
    passed: bool,
    severity: str,
    observed: Any,
    required: Any,
    detail: str,
) -> BetaFrontierProjectionAssertion:
    body = {
        "assertion_id": f"projection-assertion-{index:03d}",
        "record_id": record_id,
        "operation": operation,
        "passed": passed,
        "severity": severity,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return BetaFrontierProjectionAssertion(**body, content_address=content_hash(body))


def _generic_assertions(index: int, execution: BetaFrontierExecution) -> tuple[BetaFrontierProjectionAssertion, ...]:
    return (
        _assertion(index, execution.record_id, execution.operation, bool(execution.output), "blocking", bool(execution.output), True, "serialized output is retained"),
        _assertion(index + 1, execution.record_id, execution.operation, execution.content_address.startswith("sha256:"), "blocking", execution.content_address, "sha256:", "execution receipt is content addressed"),
        _assertion(index + 2, execution.record_id, execution.operation, execution.state == str(execution.output.get("state", execution.state)), "advisory", execution.state, execution.output.get("state", execution.state), "top-level state agrees with serialized output"),
    )


def _topology_assertions(index: int, execution: BetaFrontierExecution) -> tuple[BetaFrontierProjectionAssertion, ...]:
    output = execution.output
    if execution.state == "invalid":
        return (_assertion(index, execution.record_id, execution.operation, "error" in output, "blocking", tuple(output), "error", "invalid topology retains an error receipt"),)
    return (
        _assertion(index, execution.record_id, execution.operation, output.get("edge_count", 0) <= 1000, "blocking", output.get("edge_count", 0), 1000, "topology edge output is bounded"),
        _assertion(index + 1, execution.record_id, execution.operation, output.get("node_count", 0) <= 500, "blocking", output.get("node_count", 0), 500, "topology node output is bounded"),
        _assertion(index + 2, execution.record_id, execution.operation, "focus" in output, "blocking", "focus" in output, True, "topology focus is retained"),
        _assertion(index + 3, execution.record_id, execution.operation, "warnings" in output, "advisory", "warnings" in output, True, "topology warnings are retained"),
    )


def _causal_assertions(index: int, execution: BetaFrontierExecution) -> tuple[BetaFrontierProjectionAssertion, ...]:
    output = execution.output
    missing = output.get("missing_mediator_kinds", ())
    edges = output.get("edges", ())
    return (
        _assertion(index, execution.record_id, execution.operation, "nodes" in output and "edges" in output, "blocking", tuple(key for key in ("nodes", "edges") if key in output), ("nodes", "edges"), "chain graph retains nodes and edges"),
        _assertion(index + 1, execution.record_id, execution.operation, isinstance(missing, list | tuple), "blocking", type(missing).__name__, "sequence", "missing mediator field remains a sequence"),
        _assertion(index + 2, execution.record_id, execution.operation, all("evidence_ids" in edge and "negative_evidence_ids" in edge for edge in edges), "blocking", len(edges), "all edges", "causal edges retain positive and negative receipt fields"),
        _assertion(index + 3, execution.record_id, execution.operation, "alternative_edge_ids" in output, "advisory", "alternative_edge_ids" in output, True, "alternative path field remains visible"),
    )


def _posterior_assertions(index: int, execution: BetaFrontierExecution) -> tuple[BetaFrontierProjectionAssertion, ...]:
    output = execution.output
    residual = output.get("residual")
    return (
        _assertion(index, execution.record_id, execution.operation, all(key in output for key in ("declared_prior", "evidence_support", "posterior_proxy")), "blocking", tuple(key for key in ("declared_prior", "evidence_support", "posterior_proxy") if key in output), ("declared_prior", "evidence_support", "posterior_proxy"), "posterior metadata is retained"),
        _assertion(index + 1, execution.record_id, execution.operation, "components" in output, "blocking", "components" in output, True, "posterior components are retained"),
        _assertion(index + 2, execution.record_id, execution.operation, "normalized_shares" in output, "blocking", "normalized_shares" in output, True, "posterior shares are retained"),
        _assertion(index + 3, execution.record_id, execution.operation, residual is None or abs(float(residual)) <= 1.0, "blocking", residual, "[-1,1]", "posterior residual remains bounded"),
        _assertion(index + 4, execution.record_id, execution.operation, "calibration_status" in output, "advisory", "calibration_status" in output, True, "posterior calibration declaration remains visible"),
    )


def _table_assertions(index: int, execution: BetaFrontierExecution) -> tuple[BetaFrontierProjectionAssertion, ...]:
    output = execution.output
    facets = output.get("facets", {})
    required_facets = ("record_type", "state", "channel", "tier", "source_id")
    return (
        _assertion(index, execution.record_id, execution.operation, all(key in output for key in ("rows", "total_matches", "facets")), "blocking", tuple(key for key in ("rows", "total_matches", "facets") if key in output), ("rows", "total_matches", "facets"), "table page shape is retained"),
        _assertion(index + 1, execution.record_id, execution.operation, all(key in facets for key in required_facets), "blocking", tuple(facets), required_facets, "table facets retain every declared dimension"),
        _assertion(index + 2, execution.record_id, execution.operation, output.get("total_matches", 0) >= len(output.get("rows", ())), "blocking", (output.get("total_matches", 0), len(output.get("rows", ()))), "total>=page", "table total matches is not smaller than page size"),
        _assertion(index + 3, execution.record_id, execution.operation, "warnings" in output, "advisory", "warnings" in output, True, "table filtering warning remains visible"),
    )


def audit_beta_frontier_projections(evaluation: BetaFrontierEvaluation) -> BetaFrontierProjectionAudit:
    """Audit each serialized operation with operation-specific assertions."""

    assertions: list[BetaFrontierProjectionAssertion] = []
    index = 1
    for execution in evaluation.executions:
        assertions.extend(_generic_assertions(index, execution))
        index += 3
        if execution.operation is BetaFrontierOperation.TOPOLOGY_VIEWPORT:
            values = _topology_assertions(index, execution)
        elif execution.operation is BetaFrontierOperation.CAUSAL_CHAIN:
            values = _causal_assertions(index, execution)
        elif execution.operation is BetaFrontierOperation.POSTERIOR_DECOMPOSITION:
            values = _posterior_assertions(index, execution)
        else:
            values = _table_assertions(index, execution)
        assertions.extend(values)
        index += len(values)
    blocking = tuple(item.assertion_id for item in assertions if not item.passed and item.severity == "blocking")
    advisory = tuple(item.assertion_id for item in assertions if not item.passed and item.severity == "advisory")
    body = {"fixture_id": evaluation.fixture_id, "assertions": tuple(assertions), "accepted": not blocking, "blocking_failures": blocking, "advisory_failures": advisory}
    return BetaFrontierProjectionAudit(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierProjectionAssertion", "BetaFrontierProjectionAudit", "audit_beta_frontier_projections"]

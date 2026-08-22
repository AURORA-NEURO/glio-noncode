"""Independent serialized-output assertions for C09-C12 projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_gamma_frontier_fixture_eval import GammaFrontierEvaluation, GammaFrontierExecution
from .workspace_gamma_frontier_public_data import GammaFrontierOperation


@dataclass(frozen=True, slots=True)
class GammaFrontierProjectionAssertion:
    """One blocking or advisory assertion over a serialized result."""

    assertion_id: str
    record_id: str | None
    operation: GammaFrontierOperation | None
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
class GammaFrontierProjectionAudit:
    """Operation-aware projection audit independent of the quality gate."""

    fixture_id: str
    assertions: tuple[GammaFrontierProjectionAssertion, ...]
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

    def for_operation(
        self, operation: GammaFrontierOperation
    ) -> tuple[GammaFrontierProjectionAssertion, ...]:
        return tuple(item for item in self.assertions if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "blocking_count": self.blocking_count,
        }


def _assertion(
    index: int,
    execution: GammaFrontierExecution,
    passed: bool,
    severity: str,
    observed: Any,
    required: Any,
    detail: str,
) -> GammaFrontierProjectionAssertion:
    body = {
        "assertion_id": f"gamma-projection-{index:03d}",
        "record_id": execution.record_id,
        "operation": execution.operation,
        "passed": passed,
        "severity": severity,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return GammaFrontierProjectionAssertion(**body, content_address=content_hash(body))


def _surface_assertions(
    index: int, execution: GammaFrontierExecution
) -> tuple[GammaFrontierProjectionAssertion, ...]:
    output = execution.output
    return (
        _assertion(
            index,
            execution,
            bool(output),
            "blocking",
            bool(output),
            True,
            "result has a serialized payload",
        ),
        _assertion(
            index + 1,
            execution,
            output.get("state") == execution.state,
            "blocking",
            output.get("state"),
            execution.state,
            "top-level state agrees with execution state",
        ),
        _assertion(
            index + 2,
            execution,
            execution.content_address.startswith("sha256:"),
            "blocking",
            execution.content_address,
            "sha256:",
            "execution receipt is addressed",
        ),
        _assertion(
            index + 3,
            execution,
            "issues" in output or execution.operation is GammaFrontierOperation.SHAREABLE_SNAPSHOT,
            "advisory",
            tuple(output),
            "issue or verification fields",
            "negative evidence remains visible",
        ),
    )


def _board(
    index: int, execution: GammaFrontierExecution
) -> tuple[GammaFrontierProjectionAssertion, ...]:
    output = execution.output
    return (
        _assertion(
            index,
            execution,
            all(
                key in output
                for key in ("cards", "columns", "dependency_edges", "blocked_card_ids")
            ),
            "blocking",
            tuple(output),
            ("cards", "columns", "dependency_edges", "blocked_card_ids"),
            "board graph fields are retained",
        ),
        _assertion(
            index + 1,
            execution,
            len(output.get("columns", ())) == 6,
            "blocking",
            len(output.get("columns", ())),
            6,
            "all declared workflow columns are serialized",
        ),
        _assertion(
            index + 2,
            execution,
            all("accessible_label" in item for item in output.get("columns", ())),
            "advisory",
            output.get("columns", ()),
            "accessible labels",
            "board columns retain accessible labels",
        ),
    )


def _launch(
    index: int, execution: GammaFrontierExecution
) -> tuple[GammaFrontierProjectionAssertion, ...]:
    output = execution.output
    policies = tuple(output.get("network_policies", ()))
    return (
        _assertion(
            index,
            execution,
            all(
                "parameter_hash" in item and "network_policy" in item
                for item in output.get("launches", ())
            ),
            "blocking",
            output.get("launches", ()),
            "hash and network policy",
            "launch descriptors are reproducible",
        ),
        _assertion(
            index + 1,
            execution,
            all(
                policy in {"network_disabled", "declared_network_review_required"}
                for policy in policies
            ),
            "blocking",
            policies,
            "bounded network policies",
            "network behavior is explicit",
        ),
        _assertion(
            index + 2,
            execution,
            all("invocation" not in item for item in output.get("launches", ())),
            "advisory",
            tuple(output.get("launches", ())),
            "no executable code",
            "launch output remains declarative",
        ),
    )


def _snapshot(
    index: int, execution: GammaFrontierExecution
) -> tuple[GammaFrontierProjectionAssertion, ...]:
    output = execution.output
    return (
        _assertion(
            index,
            execution,
            output.get("algorithm") == "hmac-sha256",
            "blocking",
            output.get("algorithm"),
            "hmac-sha256",
            "integrity algorithm remains explicit",
        ),
        _assertion(
            index + 1,
            execution,
            all(key in output for key in ("signature_valid", "payload_hash_valid", "expired")),
            "blocking",
            tuple(output),
            ("signature_valid", "payload_hash_valid", "expired"),
            "verification dimensions are visible",
        ),
        _assertion(
            index + 2,
            execution,
            output.get("research_use_only", True) is True,
            "blocking",
            output.get("research_use_only", True),
            True,
            "research boundary is retained",
        ),
    )


def _access(
    index: int, execution: GammaFrontierExecution
) -> tuple[GammaFrontierProjectionAssertion, ...]:
    decisions = execution.output.get("decisions", ())
    return (
        _assertion(
            index,
            execution,
            all("policy_receipt" in item for item in decisions),
            "blocking",
            decisions,
            "policy receipts",
            "every decision carries a receipt",
        ),
        _assertion(
            index + 1,
            execution,
            all("allowed" in item and "reason" in item for item in decisions),
            "blocking",
            decisions,
            "allow and reason",
            "decisions explain their outcome",
        ),
        _assertion(
            index + 2,
            execution,
            execution.output.get("state") in {"allowed", "denied", "out_of_domain", "abstained"},
            "advisory",
            execution.output.get("state"),
            "explicit access state",
            "access state is not inferred from absence",
        ),
    )


def audit_gamma_frontier_projections(
    evaluation: GammaFrontierEvaluation,
) -> GammaFrontierProjectionAudit:
    """Run common and operation-specific assertions for every execution."""

    assertions: list[GammaFrontierProjectionAssertion] = []
    index = 1
    for execution in evaluation.executions:
        values = list(_surface_assertions(index, execution))
        index += len(values)
        if execution.operation is GammaFrontierOperation.EXPERIMENT_BOARD:
            values.extend(_board(index, execution))
        elif execution.operation is GammaFrontierOperation.LAUNCH_PLAN:
            values.extend(_launch(index, execution))
        elif execution.operation is GammaFrontierOperation.SHAREABLE_SNAPSHOT:
            values.extend(_snapshot(index, execution))
        else:
            values.extend(_access(index, execution))
        index += len(values) - (index - 1 if False else 0)
        assertions.extend(values)
    blocking = tuple(
        item.assertion_id for item in assertions if not item.passed and item.severity == "blocking"
    )
    advisory = tuple(
        item.assertion_id for item in assertions if not item.passed and item.severity == "advisory"
    )
    body = {
        "fixture_id": evaluation.fixture_id,
        "assertions": tuple(assertions),
        "accepted": not blocking,
        "blocking_failures": blocking,
        "advisory_failures": advisory,
    }
    return GammaFrontierProjectionAudit(**body, content_address=content_hash(body))


__all__ = [
    "GammaFrontierProjectionAssertion",
    "GammaFrontierProjectionAudit",
    "audit_gamma_frontier_projections",
]

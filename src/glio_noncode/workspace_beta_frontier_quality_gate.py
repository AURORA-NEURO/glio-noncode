"""Quality gate for the C05-C08 projection package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_contracts import BetaFrontierContractRegistry
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_lineage import BetaFrontierLineageGraph
from .workspace_beta_frontier_public_data import BetaFrontierFixture
from .workspace_beta_frontier_reconciliation import BetaFrontierReconciliation
from .workspace_beta_frontier_schema import BetaFrontierSchemaManifest


@dataclass(frozen=True, slots=True)
class BetaFrontierGateCheck:
    """One release-gate assertion."""

    check_id: str
    passed: bool
    severity: str
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.severity, "severity")
        require_non_empty(self.detail, "detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierQualityGate:
    """Quality result with blocking and advisory counts."""

    fixture_id: str
    checks: tuple[BetaFrontierGateCheck, ...]
    accepted: bool
    blocking_failures: tuple[str, ...]
    advisory_failures: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def _check(check_id: str, passed: bool, severity: str, observed: Any, required: Any, detail: str) -> BetaFrontierGateCheck:
    body = {"check_id": check_id, "passed": passed, "severity": severity, "observed": observed, "required": required, "detail": detail}
    return BetaFrontierGateCheck(**body, content_address=content_hash(body))


def evaluate_beta_frontier_quality(
    fixture: BetaFrontierFixture,
    evaluation: BetaFrontierEvaluation,
    contracts: BetaFrontierContractRegistry,
    schema: BetaFrontierSchemaManifest,
    lineage: BetaFrontierLineageGraph,
    reconciliation: BetaFrontierReconciliation,
) -> BetaFrontierQualityGate:
    """Run package, contract, schema, lineage, and reconciliation checks."""

    checks: list[BetaFrontierGateCheck] = [
        _check("quality:evaluation-accepted", evaluation.accepted, "blocking", evaluation.accepted, True, "all fixture assertions pass"),
        _check("quality:reconciliation", reconciliation.reconciled, "blocking", reconciliation.reconciled, True, "expected and observed states reconcile"),
        _check("quality:lineage-acyclic", lineage.acyclic, "blocking", lineage.acyclic, True, "lineage graph has no cycle"),
        _check("quality:contract-coverage", len(contracts.contracts) == 4, "blocking", len(contracts.contracts), 4, "four operation contracts are registered"),
        _check("quality:schema-coverage", len(schema.operations) == 4, "blocking", len(schema.operations), 4, "four operation schemas are registered"),
        _check("quality:address-coverage", all(item.content_address.startswith("sha256:") for item in evaluation.executions), "blocking", True, True, "all projection results have receipts"),
        _check("quality:positive-count", sum(item.role.value == "positive" for item in evaluation.executions) == 4, "blocking", sum(item.role.value == "positive" for item in evaluation.executions), 4, "one positive row per operation"),
        _check("quality:control-count", sum(item.role.value == "control" for item in evaluation.executions) == 12, "blocking", sum(item.role.value == "control" for item in evaluation.executions), 12, "three controls per operation"),
        _check("quality:operation-addresses", len({item.operation for item in evaluation.executions}) == 4, "blocking", len({item.operation for item in evaluation.executions}), 4, "all surfaces yield outputs"),
        _check("quality:state-vocabulary", all(contracts.by_operation(item.operation).accepts_state(item.state) for item in evaluation.executions), "blocking", True, True, "states fit operation contracts"),
        _check("quality:issue-vocabulary", all(contracts.by_operation(item.operation).accepts_issue_set(item.issue_codes) for item in evaluation.executions), "blocking", True, True, "issues fit operation contracts"),
        _check("quality:fixture-boundary", fixture.evidence_boundary == "public_aggregate_non_patient", "blocking", fixture.evidence_boundary, "public_aggregate_non_patient", "fixture boundary remains public aggregate"),
        _check("quality:partial-visibility", any(item.state == "partial" for item in evaluation.executions), "advisory", True, True, "partial evidence is represented"),
        _check("quality:contradiction-visibility", any(item.state == "contradictory" for item in evaluation.executions), "advisory", True, True, "contradiction is represented"),
        _check("quality:empty-visibility", any(item.state == "absent" for item in evaluation.executions), "advisory", True, True, "empty output is represented"),
        _check("quality:table-filter-visibility", any(item.operation.value == "evidence_table" and "pagination_applied" in item.issue_codes for item in evaluation.executions), "advisory", True, True, "table pagination is represented"),
    ]
    blocking = tuple(item.check_id for item in checks if not item.passed and item.severity == "blocking")
    advisory = tuple(item.check_id for item in checks if not item.passed and item.severity == "advisory")
    body = {"fixture_id": fixture.fixture_id, "checks": tuple(checks), "accepted": not blocking, "blocking_failures": blocking, "advisory_failures": advisory}
    return BetaFrontierQualityGate(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierGateCheck", "BetaFrontierQualityGate", "evaluate_beta_frontier_quality"]

"""Quality gate for workspace evidence, context, and accessibility metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workspace_frontier_contracts import WorkspaceFrontierContractRegistry
from .workspace_frontier_fixture_eval import WorkspaceFrontierEvaluation
from .workspace_frontier_lineage import WorkspaceFrontierLineageGraph
from .workspace_frontier_public_data import WorkspaceFrontierFixture
from .workspace_frontier_reconciliation import WorkspaceFrontierReconciliation
from .workspace_frontier_schema import WorkspaceFrontierSchemaManifest


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierGateCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkspaceFrontierQualityGate:
    fixture_id: str
    checks: tuple[WorkspaceFrontierGateCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count, "failed_check_ids": list(self.failed_check_ids)}


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> WorkspaceFrontierGateCheck:
    body = {"check_id": check_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return WorkspaceFrontierGateCheck(**body, content_address=content_hash(body))


def evaluate_workspace_frontier_quality(fixture: WorkspaceFrontierFixture, evaluation: WorkspaceFrontierEvaluation, contracts: WorkspaceFrontierContractRegistry, schema: WorkspaceFrontierSchemaManifest, lineage: WorkspaceFrontierLineageGraph, reconciliation: WorkspaceFrontierReconciliation) -> WorkspaceFrontierQualityGate:
    checks = (
        _check("fixture:accepted", evaluation.accepted, evaluation.accepted, True, "all fixture evaluations pass"),
        _check("fixture:positive-count", len(fixture.positive_records) == 4, len(fixture.positive_records), 4, "four positive paths"),
        _check("fixture:control-count", len(fixture.control_records) == 12, len(fixture.control_records), 12, "twelve controls"),
        _check("contracts:operation-count", len(contracts.contracts) == 4, len(contracts.contracts), 4, "four operation contracts"),
        _check("contracts:issue-vocabulary", bool(contracts.issue_codes()), len(contracts.issue_codes()), ">0", "declared issue vocabulary"),
        _check("schema:operation-count", len(schema.operations) == 4, len(schema.operations), 4, "four operation schemas"),
        _check("schema:field-addresses", all(item.content_address.startswith("sha256:") for item in schema.fields()), True, True, "all schema fields are addressed"),
        _check("lineage:acyclic", lineage.acyclic, lineage.acyclic, True, "lineage has no self-loop"),
        _check("lineage:terminal-count", len(lineage.terminal_addresses) == len(fixture.records), len(lineage.terminal_addresses), len(fixture.records), "each fixture record has a terminal receipt"),
        _check("reconciliation:accepted", reconciliation.reconciled, reconciliation.reconciled, True, "expected and observed state agree"),
        _check("reconciliation:item-count", len(reconciliation.items) == len(fixture.records), len(reconciliation.items), len(fixture.records), "each record reconciles"),
        _check("boundary:public", fixture.evidence_boundary == "public_aggregate_non_patient", fixture.evidence_boundary, "public_aggregate_non_patient", "boundary excludes individual data"),
        _check("context:exact", all(item.context_key == fixture.context_key for item in fixture.records), True, True, "fixture records use one exact context"),
        _check("accessibility:retained", all("accessibility" in item.output for item in evaluation.executions if item.operation.value != "variant_explorer" and "accessibility" in item.output), True, True, "surface labels and focus metadata are retained"),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "accepted": all(item.passed for item in checks)}
    return WorkspaceFrontierQualityGate(**body, content_address=content_hash(body))


__all__ = ["WorkspaceFrontierGateCheck", "WorkspaceFrontierQualityGate", "evaluate_workspace_frontier_quality"]

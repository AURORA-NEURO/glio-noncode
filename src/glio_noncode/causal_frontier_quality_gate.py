"""Multi-check quality gate for causal frontier release candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_frontier_contracts import CausalFrontierContractRegistry
from .causal_frontier_fixture_eval import CausalFrontierEvaluation
from .causal_frontier_lineage import CausalFrontierLineageGraph
from .causal_frontier_public_data import CausalFrontierFixture, audit_causal_frontier_data
from .causal_frontier_reconciliation import CausalFrontierReconciliation
from .causal_frontier_schema import CausalFrontierSchemaManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFrontierGateCheck:
    check_id: str
    passed: bool
    severity: str
    observed: Any
    required: Any
    rationale: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CausalFrontierQualityGate:
    gate_id: str
    checks: tuple[CausalFrontierGateCheck, ...]
    accepted: bool
    blocking_check_ids: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def evaluate_causal_frontier_quality(
    fixture: CausalFrontierFixture,
    evaluation: CausalFrontierEvaluation,
    contracts: CausalFrontierContractRegistry,
    schema: CausalFrontierSchemaManifest,
    lineage: CausalFrontierLineageGraph,
    reconciliation: CausalFrontierReconciliation,
) -> CausalFrontierQualityGate:
    data_audit = audit_causal_frontier_data(fixture)
    checks: list[CausalFrontierGateCheck] = []

    def add(check_id: str, passed: bool, observed: Any, required: Any, rationale: str, severity: str = "blocking") -> None:
        body = {"check_id": check_id, "passed": passed, "severity": severity, "observed": observed, "required": required, "rationale": rationale}
        checks.append(CausalFrontierGateCheck(**body, content_address=content_hash(body)))

    add("data-audit", data_audit.accepted, data_audit.failed_check_ids, (), "all public source and fixture checks pass")
    add("evaluation", evaluation.accepted, evaluation.passed_checks, len(evaluation.checks), "positive and control replay checks pass")
    add("contract-coverage", len(contracts.contracts) == 4, len(contracts.contracts), 4, "every operation has one contract")
    add("schema-coverage", len(schema.operations) == 4, len(schema.operations), 4, "every operation has a schema")
    add("lineage-acyclic", lineage.acyclic, lineage.acyclic, True, "source-to-output graph has no cycles")
    add("lineage-terminals", len(lineage.terminal_addresses) == len(fixture.records), len(lineage.terminal_addresses), len(fixture.records), "every record has a terminal receipt")
    add("reconciliation", reconciliation.reconciled, reconciliation.mismatched_record_ids, (), "expected and observed controls reconcile")
    add("content-addresses", all(bool(item.content_address) for item in evaluation.executions), True, True, "execution receipts are addressable")
    add("source-boundary", fixture.evidence_boundary == "public_aggregate_non_patient", fixture.evidence_boundary, "public_aggregate_non_patient", "release boundary is explicit")
    add("positive-controls", len(fixture.positive_records) == 4, len(fixture.positive_records), 4, "one positive per operation")
    add("negative-controls", len(fixture.control_records) == 12, len(fixture.control_records), 12, "three controls per operation")
    add("issue-vocabulary", all(set(item.issue_codes) <= set(contracts.issue_codes()) for item in evaluation.executions), True, True, "all issues are declared by contracts")
    blocking = tuple(item.check_id for item in checks if not item.passed and item.severity == "blocking")
    body = {"gate_id": "causal-frontier-quality-gate", "checks": tuple(checks), "accepted": not blocking, "blocking_check_ids": blocking}
    return CausalFrontierQualityGate(**body, content_address=content_hash(body))


__all__ = ["CausalFrontierGateCheck", "CausalFrontierQualityGate", "evaluate_causal_frontier_quality"]

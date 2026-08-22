"""Blocking quality checks for Domain 13 planning releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_contracts import ValidationFrontierContractRegistry
from .validation_frontier_fixture_eval import ValidationFrontierEvaluation
from .validation_frontier_lineage import ValidationFrontierLineageGraph
from .validation_frontier_public_data import (
    ValidationFrontierFixture,
    audit_validation_frontier_data,
)
from .validation_frontier_reconciliation import ValidationFrontierReconciliation
from .validation_frontier_schema import ValidationFrontierSchemaManifest


@dataclass(frozen=True, slots=True)
class ValidationFrontierGateCheck:
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
class ValidationFrontierQualityGate:
    gate_id: str
    checks: tuple[ValidationFrontierGateCheck, ...]
    accepted: bool
    blocking_check_ids: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def evaluate_validation_frontier_quality(fixture: ValidationFrontierFixture, evaluation: ValidationFrontierEvaluation, contracts: ValidationFrontierContractRegistry, schema: ValidationFrontierSchemaManifest, lineage: ValidationFrontierLineageGraph, reconciliation: ValidationFrontierReconciliation) -> ValidationFrontierQualityGate:
    audit = audit_validation_frontier_data(fixture)
    values = (("data-audit", audit.accepted, audit.failed_check_ids, (), "public fixture audit passes"), ("evaluation", evaluation.accepted, evaluation.passed_checks, len(evaluation.checks), "positive and control execution passes"), ("contract-coverage", len(contracts.contracts) == 4, len(contracts.contracts), 4, "four operation contracts"), ("schema-coverage", len(schema.operations) == 4, len(schema.operations), 4, "four operation schemas"), ("lineage-acyclic", lineage.acyclic, lineage.acyclic, True, "lineage has no cycle"), ("lineage-terminals", len(lineage.terminal_addresses) == len(fixture.records), len(lineage.terminal_addresses), len(fixture.records), "every record has a terminal"), ("reconciliation", reconciliation.reconciled, reconciliation.mismatched_record_ids, (), "expected and observed states match"), ("addresses", all(item.content_address.startswith("sha256:") for item in evaluation.executions), True, True, "execution addresses exist"), ("boundary", fixture.evidence_boundary == "public_aggregate_non_patient", fixture.evidence_boundary, "public_aggregate_non_patient", "boundary is exact"), ("positive-count", len(fixture.positive_records) == 4, len(fixture.positive_records), 4, "one positive per operation"), ("control-count", len(fixture.control_records) == 12, len(fixture.control_records), 12, "three controls per operation"), ("issue-vocabulary", all(set(item.issue_codes) <= set(contracts.issue_codes()) for item in evaluation.executions), True, True, "issue codes are declared"))
    checks = []
    for check_id, passed, observed, required, rationale in values:
        body = {"check_id": check_id, "passed": passed, "severity": "blocking", "observed": observed, "required": required, "rationale": rationale}
        checks.append(ValidationFrontierGateCheck(**body, content_address=content_hash(body)))
    blocking = tuple(item.check_id for item in checks if not item.passed)
    body = {"gate_id": "validation-frontier-quality-gate", "checks": tuple(checks), "accepted": not blocking, "blocking_check_ids": blocking}
    return ValidationFrontierQualityGate(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierGateCheck", "ValidationFrontierQualityGate", "evaluate_validation_frontier_quality"]

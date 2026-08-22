"""Blocking quality checks for the Domain 14 lifecycle release bundle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .evidence_lifecycle_frontier_contracts import EvidenceLifecycleContractRegistry
from .evidence_lifecycle_frontier_fixture_eval import EvidenceLifecycleEvaluation
from .evidence_lifecycle_frontier_lineage import EvidenceLifecycleLineageGraph
from .evidence_lifecycle_frontier_public_data import EvidenceLifecycleFixture
from .evidence_lifecycle_frontier_reconciliation import EvidenceLifecycleReconciliation
from .evidence_lifecycle_frontier_schema import EvidenceLifecycleSchemaManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleGateCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleQualityGate:
    gate_id: str
    checks: tuple[EvidenceLifecycleGateCheck, ...]
    accepted: bool
    passed_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> EvidenceLifecycleGateCheck:
    body = {"check_id": check_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return EvidenceLifecycleGateCheck(**body, content_address=content_hash(body))


def evaluate_evidence_lifecycle_quality(fixture: EvidenceLifecycleFixture, evaluation: EvidenceLifecycleEvaluation, contracts: EvidenceLifecycleContractRegistry, schema: EvidenceLifecycleSchemaManifest, lineage: EvidenceLifecycleLineageGraph, reconciliation: EvidenceLifecycleReconciliation) -> EvidenceLifecycleQualityGate:
    checks = (
        _check("gate:evaluation", evaluation.accepted, evaluation.accepted, True, "fixture evaluation passes"),
        _check("gate:positive-count", len(fixture.positive_records) == 4, len(fixture.positive_records), 4, "one positive per operation"),
        _check("gate:control-count", len(fixture.control_records) == 12, len(fixture.control_records), 12, "three controls per operation"),
        _check("gate:contracts", len(contracts.contracts) == 4, len(contracts.contracts), 4, "four operation contracts"),
        _check("gate:schema", len(schema.operations) == 4, len(schema.operations), 4, "four operation schemas"),
        _check("gate:lineage", lineage.acyclic and len(lineage.terminal_addresses) == 16, (lineage.acyclic, len(lineage.terminal_addresses)), (True, 16), "lineage is complete"),
        _check("gate:reconciliation", reconciliation.reconciled, reconciliation.reconciled, True, "expected and observed records reconcile"),
        _check("gate:addresses", all(item.content_address.startswith("sha256:") for item in evaluation.executions), True, True, "executions are addressed"),
        _check("gate:issue-vocabulary", all(set(item.issue_codes) <= set(contracts.issue_codes()) for item in evaluation.executions), True, True, "issues are declared"),
        _check("gate:boundary", fixture.evidence_boundary == "public_aggregate_non_patient", fixture.evidence_boundary, "public_aggregate_non_patient", "public boundary is exact"),
        _check("gate:source-receipts", all(item.uri.startswith("https://") for item in fixture.sources), True, True, "source receipts are HTTPS"),
        _check("gate:context", all(item.context_key == fixture.context_key for item in fixture.records), True, True, "record context is exact"),
    )
    body = {"gate_id": "evidence-lifecycle-quality", "checks": checks, "accepted": all(item.passed for item in checks), "passed_count": sum(item.passed for item in checks)}
    return EvidenceLifecycleQualityGate(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleGateCheck", "EvidenceLifecycleQualityGate", "evaluate_evidence_lifecycle_quality"]

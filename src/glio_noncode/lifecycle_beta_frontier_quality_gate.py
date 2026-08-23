"""Blocking quality gate for the Domain 14 beta-frontier package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_adapters import LifecycleBetaFrontierAdapterRegistry
from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_lineage import LifecycleBetaFrontierLineageReport, verify_lifecycle_beta_frontier_lineage
from .lifecycle_beta_frontier_metrics import LifecycleBetaFrontierMetrics
from .lifecycle_beta_frontier_policy import LifecycleBetaFrontierPolicy
from .lifecycle_beta_frontier_public_data import LifecycleBetaFrontierDataAudit
from .lifecycle_beta_frontier_reconciliation import LifecycleBetaFrontierReconciliationReport
from .lifecycle_beta_frontier_schema import LifecycleBetaFrontierSchema, validate_lifecycle_beta_frontier_schema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierQualityCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    blocking: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierQualityReport:
    fixture_id: str
    checks: tuple[LifecycleBetaFrontierQualityCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_lifecycle_beta_frontier_quality_gate(fixture: LifecycleBetaFrontierFixture, audit: LifecycleBetaFrontierDataAudit, evaluation: LifecycleBetaFrontierEvaluation, metrics: LifecycleBetaFrontierMetrics, adapters: LifecycleBetaFrontierAdapterRegistry, schema: LifecycleBetaFrontierSchema, policy: LifecycleBetaFrontierPolicy, lineage: LifecycleBetaFrontierLineageReport, reconciliation: LifecycleBetaFrontierReconciliationReport) -> LifecycleBetaFrontierQualityReport:
    values = (
        ("data-audit", audit.accepted, audit.accepted, True, "public data audit passes"),
        ("evaluation", evaluation.accepted, evaluation.accepted, True, "fixture controls reconcile"),
        ("record-count", metrics.record_count == 32, metrics.record_count, 32, "all records are measured"),
        ("operation-count", len(adapters.specs) == 8, len(adapters.specs), 8, "all adapters are registered"),
        ("schema", validate_lifecycle_beta_frontier_schema(schema), True, True, "schema is complete"),
        ("policy", len(policy.allowed_uses) == 4 and len(policy.excluded_uses) == 5, (len(policy.allowed_uses), len(policy.excluded_uses)), (4, 5), "policy boundary is explicit"),
        ("lineage", verify_lifecycle_beta_frontier_lineage(lineage), True, True, "lineage graph is closed"),
        ("reconciliation", reconciliation.reconciled, True, True, "expected and observed states reconcile"),
    )
    checks = []
    for check_id, passed, observed, required, detail in values:
        body = {"check_id": check_id, "passed": passed, "observed": observed, "required": required, "blocking": True, "detail": detail}
        checks.append(LifecycleBetaFrontierQualityCheck(**body, content_address=content_hash(body)))
    failed = tuple(item.check_id for item in checks if item.blocking and not item.passed)
    return LifecycleBetaFrontierQualityReport(fixture.fixture_id, tuple(checks), not failed, failed, content_hash({"checks": tuple(checks), "failed": failed}))


__all__ = ["LifecycleBetaFrontierQualityCheck", "LifecycleBetaFrontierQualityReport", "run_lifecycle_beta_frontier_quality_gate"]

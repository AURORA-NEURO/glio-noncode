"""Blocking quality gate for C01-C04 platform evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_adapters import PlatformFrontierAdapterRegistry
from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierFixture
from .platform_frontier_lineage import PlatformFrontierLineage
from .platform_frontier_metrics import PlatformFrontierMetrics
from .platform_frontier_policy import PlatformFrontierPolicy
from .platform_frontier_public_data import PlatformFrontierDataAudit
from .platform_frontier_reconciliation import PlatformFrontierReconciliation
from .platform_frontier_schema import PlatformFrontierSchema
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierQualityCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierQualityReport:
    fixture_id: str
    checks: tuple[PlatformFrontierQualityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_platform_frontier_quality_gate(fixture: PlatformFrontierFixture, audit: PlatformFrontierDataAudit, evaluation: PlatformFrontierEvaluation, metrics: PlatformFrontierMetrics, adapters: PlatformFrontierAdapterRegistry, schema: PlatformFrontierSchema, policy: PlatformFrontierPolicy, lineage: PlatformFrontierLineage, reconciliation: PlatformFrontierReconciliation) -> PlatformFrontierQualityReport:
    values = (
        ("data", audit.accepted, True, "aggregate data audit"),
        ("evaluation", evaluation.accepted, True, "positive and control rows"),
        ("metrics", metrics.record_count, len(fixture.records), "metrics count"),
        ("adapters", adapters.accepted, True, "four typed adapters"),
        ("schema", schema.accepted, True, "schema inventory"),
        ("policy", policy.accepted, True, "research-use policy"),
        ("lineage", lineage.accepted, True, "source lineage"),
        ("reconciliation", reconciliation.accepted, True, "expected versus observed"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(PlatformFrontierQualityCheck(**body, content_address=content_hash(body)))
    return PlatformFrontierQualityReport(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["PlatformFrontierQualityCheck", "PlatformFrontierQualityReport", "run_platform_frontier_quality_gate"]

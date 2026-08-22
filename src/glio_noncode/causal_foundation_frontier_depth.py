"""Depth audit for Domain 11 C01-C04 implementation surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_adapters import CausalFoundationFrontierAdapterRegistry
from .causal_foundation_frontier_contracts import CausalFoundationFrontierContractReport
from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_lineage import CausalFoundationFrontierLineage
from .causal_foundation_frontier_metrics import CausalFoundationFrontierMetrics
from .causal_foundation_frontier_provenance import CausalFoundationFrontierProvenanceGraph
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture
from .causal_foundation_frontier_schema import CausalFoundationFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierDepthCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"check_id": self.check_id, "passed": self.passed, "observed": self.observed, "required": self.required, "detail": self.detail}
        if include_address:
            value["content_address"] = self.content_address
        return value


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierDepthAudit:
    fixture_id: str
    checks: tuple[CausalFoundationFrontierDepthCheck, ...]
    passed_count: int
    required_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "checks": [item.to_dict() for item in self.checks], "passed_count": self.passed_count, "required_count": self.required_count, "failed_check_ids": self.failed_check_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_causal_foundation_frontier_depth(fixture: CausalFoundationFrontierFixture, evaluation: CausalFoundationFrontierEvaluation, adapters: CausalFoundationFrontierAdapterRegistry, contracts: CausalFoundationFrontierContractReport, schema: CausalFoundationFrontierSchemaReport, metrics: CausalFoundationFrontierMetrics, lineage: CausalFoundationFrontierLineage, provenance: CausalFoundationFrontierProvenanceGraph) -> CausalFoundationFrontierDepthAudit:
    raw = (
        ("adapter-closure", adapters.accepted, len(adapters.specs), 4, "all four primitive adapters are registered"),
        ("contract-closure", contracts.accepted, len(contracts.contracts), 4, "all four capability contracts are declared"),
        ("schema-closure", schema.accepted, len(schema.fields), 10, "record envelope fields are explicit"),
        ("fixture-replay", evaluation.accepted, evaluation.state_match_count, len(fixture.records), "positive and control rows replay"),
        ("metric-closure", metrics.accepted, metrics.issue_accuracy, 1.0, "state and issue metrics reconcile"),
        ("lineage-closure", lineage.accepted and len(lineage.record_edges) == len(fixture.records), len(lineage.record_edges), len(fixture.records), "every row has a result edge"),
        ("provenance-closure", provenance.accepted and len(provenance.nodes) == len(fixture.sources) + len(fixture.records) + len(evaluation.rows) + 1, len(provenance.nodes), len(fixture.sources) + len(fixture.records) + len(evaluation.rows) + 1, "sources, fixture, rows, and results are addressable"),
        ("source-density", len(fixture.sources) >= 5, len(fixture.sources), 5, "public receipts are present"),
        ("control-density", len(fixture.control_records) >= 3 * 4, len(fixture.control_records), 12, "each operation has three controls"),
        ("context-boundary", sum(item.context_key == fixture.foreign_context_key for item in fixture.records) == 4, sum(item.context_key == fixture.foreign_context_key for item in fixture.records), 4, "foreign contexts are represented"),
    )
    checks = tuple(CausalFoundationFrontierDepthCheck(check_id, bool(passed), observed, required, detail) for check_id, passed, observed, required, detail in raw)
    return CausalFoundationFrontierDepthAudit(fixture.fixture_id, checks, sum(item.passed for item in checks), len(checks), bool(checks) and all(item.passed for item in checks))


__all__ = ["CausalFoundationFrontierDepthAudit", "CausalFoundationFrontierDepthCheck", "audit_causal_foundation_frontier_depth"]

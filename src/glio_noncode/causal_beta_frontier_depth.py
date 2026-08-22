"""Depth audit for the C05-C08 beta frontier plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_adapters import CausalBetaFrontierAdapterRegistry
from .causal_beta_frontier_contracts import CausalBetaFrontierContractReport
from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_lineage import CausalBetaFrontierLineage
from .causal_beta_frontier_metrics import CausalBetaFrontierMetrics
from .causal_beta_frontier_provenance import CausalBetaFrontierProvenanceGraph
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .causal_beta_frontier_schema import CausalBetaFrontierSchemaReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierDepthCheck:
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
class CausalBetaFrontierDepthAudit:
    fixture_id: str
    checks: tuple[CausalBetaFrontierDepthCheck, ...]
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


def audit_causal_beta_frontier_depth(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation, adapters: CausalBetaFrontierAdapterRegistry, contracts: CausalBetaFrontierContractReport, schema: CausalBetaFrontierSchemaReport, metrics: CausalBetaFrontierMetrics, lineage: CausalBetaFrontierLineage, provenance: CausalBetaFrontierProvenanceGraph) -> CausalBetaFrontierDepthAudit:
    raw = (
        ("adapter-closure", adapters.accepted and len(adapters.specs) == 4, len(adapters.specs), 4, "four typed beta primitives are bound"),
        ("contract-closure", contracts.accepted and len(contracts.contracts) == 4, len(contracts.contracts), 4, "four capability contracts are closed"),
        ("schema-closure", schema.accepted and len(schema.fields) == 10, len(schema.fields), 10, "record envelope fields are declared"),
        ("fixture-replay", evaluation.accepted and evaluation.state_match_count == len(fixture.records), evaluation.state_match_count, len(fixture.records), "positive and control rows replay"),
        ("metric-closure", metrics.accepted and metrics.state_accuracy == 1.0 and metrics.issue_accuracy == 1.0, (metrics.state_accuracy, metrics.issue_accuracy), (1.0, 1.0), "state and issue metrics are exact"),
        ("lineage-closure", lineage.accepted and len(lineage.record_edges) == len(fixture.records), len(lineage.record_edges), len(fixture.records), "every row has a result edge"),
        ("provenance-closure", provenance.accepted and len(provenance.nodes) == len(fixture.sources) + len(fixture.records) + len(evaluation.rows) + 1, len(provenance.nodes), len(fixture.sources) + len(fixture.records) + len(evaluation.rows) + 1, "all sources, rows, and results are addressable"),
        ("source-density", len(fixture.sources) >= 5, len(fixture.sources), 5, "public receipts are present"),
        ("control-density", len(fixture.control_records) == 12, len(fixture.control_records), 12, "three controls per operation"),
        ("context-boundary", sum(item.context_key == fixture.foreign_context_key for item in fixture.records) == 4, sum(item.context_key == fixture.foreign_context_key for item in fixture.records), 4, "foreign contexts are represented"),
    )
    checks = tuple(CausalBetaFrontierDepthCheck(*item) for item in raw)
    return CausalBetaFrontierDepthAudit(fixture.fixture_id, checks, sum(item.passed for item in checks), len(checks), bool(checks) and all(item.passed for item in checks))


__all__ = ["CausalBetaFrontierDepthAudit", "CausalBetaFrontierDepthCheck", "audit_causal_beta_frontier_depth"]

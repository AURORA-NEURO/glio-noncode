"""Implementation-depth audit for the C09-C12 package."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_adapters import CausalAlphaFrontierAdapterRegistry
from .causal_alpha_frontier_contracts import CausalAlphaFrontierContractReport
from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_lineage import CausalAlphaFrontierLineage
from .causal_alpha_frontier_metrics import CausalAlphaFrontierMetrics
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .causal_alpha_frontier_schema import CausalAlphaFrontierSchemaReport
from .causal_alpha_frontier_provenance import CausalAlphaFrontierProvenanceGraph
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierDepthAudit:
    fixture_id: str
    checks: tuple[dict[str, Any], ...]
    implementation_modules: tuple[str, ...]
    test_modules: tuple[str, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item["check_id"] for item in self.checks if not item["passed"])

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "checks": self.checks, "failed_checks": self.failed_checks, "implementation_modules": self.implementation_modules, "test_modules": self.test_modules, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_causal_alpha_frontier_depth(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, adapters: CausalAlphaFrontierAdapterRegistry, contracts: CausalAlphaFrontierContractReport, schema: CausalAlphaFrontierSchemaReport, metrics: CausalAlphaFrontierMetrics, lineage: CausalAlphaFrontierLineage, provenance: CausalAlphaFrontierProvenanceGraph) -> CausalAlphaFrontierDepthAudit:
    checks = (
        {"check_id": "four-adapters", "passed": len(adapters.adapters) == 4 and adapters.accepted, "detail": "four operations have typed adapters"},
        {"check_id": "four-contracts", "passed": len(contracts.contracts) == 4 and contracts.accepted, "detail": "four capability contracts are closed"},
        {"check_id": "sixteen-results", "passed": len(evaluation.evaluation.results) == 16, "detail": "all fixture rows produced results"},
        {"check_id": "schema-accepted", "passed": schema.accepted, "detail": "record and output envelopes validate"},
        {"check_id": "metric-coverage", "passed": len(metrics.operations) == 4 and all(item.record_count == 4 for item in metrics.operations), "detail": "each operation has four cases"},
        {"check_id": "lineage-closed", "passed": lineage.accepted, "detail": "source-record-result lineage closes"},
        {"check_id": "provenance-closed", "passed": provenance.accepted, "detail": "provenance graph references resolve"},
        {"check_id": "boundaries", "passed": all("not" in item.limitation or "does not" in item.limitation for item in contracts.contracts), "detail": "limitations are explicit"},
    )
    checks = tuple({**item, "content_address": content_hash(item)} for item in checks)
    implementation = tuple(f"glio_noncode.causal_alpha_frontier_{name}" for name in ("public_data", "adapters", "fixture_eval", "contracts", "schema", "metrics", "policy", "lineage", "provenance", "runtime"))
    tests = tuple(f"tests.test_causal_alpha_frontier_{name}" for name in ("core", "contracts", "depth", "operational", "serialization"))
    return CausalAlphaFrontierDepthAudit(fixture.fixture_id, checks, implementation, tests, all(item["passed"] for item in checks))


__all__ = ["CausalAlphaFrontierDepthAudit", "audit_causal_alpha_frontier_depth"]

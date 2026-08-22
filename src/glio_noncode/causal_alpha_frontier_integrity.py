"""Address, source, and graph integrity checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_alpha_frontier_fixture_eval import CausalAlphaFrontierFixtureEvaluation
from .causal_alpha_frontier_lineage import CausalAlphaFrontierLineage
from .causal_alpha_frontier_provenance import CausalAlphaFrontierProvenanceGraph
from .causal_alpha_frontier_public_data import CausalAlphaFrontierFixture
from .serialization import content_hash


@dataclass(frozen=True, slots=True)
class CausalAlphaFrontierIntegrityReport:
    fixture_id: str
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_checks(self) -> tuple[str, ...]:
        return tuple(item["check_id"] for item in self.checks if not item["passed"])

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "checks": self.checks, "failed_checks": self.failed_checks, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_causal_alpha_frontier_integrity(fixture: CausalAlphaFrontierFixture, evaluation: CausalAlphaFrontierFixtureEvaluation, lineage: CausalAlphaFrontierLineage, provenance: CausalAlphaFrontierProvenanceGraph) -> CausalAlphaFrontierIntegrityReport:
    source_addresses = all(item.content_address.startswith("sha256:") for item in fixture.sources)
    record_addresses = all(item.content_address.startswith("sha256:") for item in fixture.records)
    result_addresses = all(item.content_address.startswith("sha256:") for item in evaluation.evaluation.results)
    checks = (
        {"check_id": "fixture-address", "passed": fixture.content_address.startswith("sha256:"), "detail": "fixture address present"},
        {"check_id": "source-addresses", "passed": source_addresses, "detail": "source receipts are addressed"},
        {"check_id": "record-addresses", "passed": record_addresses, "detail": "records are addressed"},
        {"check_id": "result-addresses", "passed": result_addresses, "detail": "results are addressed"},
        {"check_id": "lineage-accepted", "passed": lineage.accepted, "detail": "lineage closure accepted"},
        {"check_id": "provenance-accepted", "passed": provenance.accepted, "detail": "provenance closure accepted"},
        {"check_id": "edge-closure", "passed": all(parent in {item.node_id for item in lineage.nodes} and child in {item.node_id for item in lineage.nodes} for parent, child, _ in lineage.edges), "detail": "lineage edge endpoints resolve"},
        {"check_id": "node-count", "passed": len(provenance.nodes) == 38, "detail": "one fixture, five sources, sixteen records, sixteen results"},
    )
    checks = tuple({**item, "content_address": content_hash(item)} for item in checks)
    return CausalAlphaFrontierIntegrityReport(fixture.fixture_id, checks, all(item["passed"] for item in checks))


__all__ = ["CausalAlphaFrontierIntegrityReport", "evaluate_causal_alpha_frontier_integrity"]

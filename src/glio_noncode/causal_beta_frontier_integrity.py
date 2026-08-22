"""Address and graph integrity checks for C05-C08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_beta_frontier_fixture_eval import CausalBetaFrontierEvaluation
from .causal_beta_frontier_lineage import CausalBetaFrontierLineage
from .causal_beta_frontier_provenance import CausalBetaFrontierProvenanceGraph
from .causal_beta_frontier_public_data import CausalBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalBetaFrontierIntegrityCheck:
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
class CausalBetaFrontierIntegrityReport:
    fixture_id: str
    checks: tuple[CausalBetaFrontierIntegrityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"fixture_id": self.fixture_id, "checks": [item.to_dict() for item in self.checks], "failed_check_ids": self.failed_check_ids, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_causal_beta_frontier_integrity(fixture: CausalBetaFrontierFixture, evaluation: CausalBetaFrontierEvaluation, lineage: CausalBetaFrontierLineage, provenance: CausalBetaFrontierProvenanceGraph) -> CausalBetaFrontierIntegrityReport:
    source_ids = set(fixture.source_map())
    result_addresses = {row.adapter.content_address for row in evaluation.rows}
    node_addresses = {node.content_address for node in provenance.nodes}
    lineage_addresses = {edge.child_id.removeprefix("result:") for edge in lineage.record_edges}
    raw = (
        ("fixture-address", fixture.content_address.startswith("sha256:"), fixture.content_address, "sha256:*", "fixture receipt present"),
        ("record-addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), len(fixture.records), len(fixture.records), "record receipts present"),
        ("source-resolution", all(set(item.source_ids) <= source_ids for item in fixture.records), True, True, "source IDs resolve"),
        ("evaluation-addresses", result_addresses <= node_addresses, len(result_addresses), len(result_addresses), "results appear in provenance"),
        ("lineage-results", lineage_addresses == result_addresses, len(lineage_addresses), len(result_addresses), "lineage terminals match adapters"),
        ("provenance-accepted", provenance.accepted, provenance.accepted, True, "provenance graph reports accepted closure"),
        ("unique-sources", len({item.content_address for item in fixture.sources}) == len(fixture.sources), len(fixture.sources), len(fixture.sources), "source addresses unique"),
        ("unique-records", len(fixture.record_map()) == len(fixture.records), len(fixture.record_map()), len(fixture.records), "record IDs unique"),
        ("unique-lineage", len({item.content_address for item in lineage.edges}) == len(lineage.edges), len(lineage.edges), len(lineage.edges), "lineage addresses unique"),
    )
    checks = tuple(CausalBetaFrontierIntegrityCheck(*item) for item in raw)
    return CausalBetaFrontierIntegrityReport(fixture.fixture_id, checks, bool(checks) and all(item.passed for item in checks))


__all__ = ["CausalBetaFrontierIntegrityCheck", "CausalBetaFrontierIntegrityReport", "evaluate_causal_beta_frontier_integrity"]

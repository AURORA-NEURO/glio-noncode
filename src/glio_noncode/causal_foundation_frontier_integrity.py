"""Address, source, and graph integrity checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_foundation_frontier_fixture_eval import CausalFoundationFrontierEvaluation
from .causal_foundation_frontier_lineage import CausalFoundationFrontierLineage
from .causal_foundation_frontier_provenance import CausalFoundationFrontierProvenanceGraph
from .causal_foundation_frontier_public_data import CausalFoundationFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CausalFoundationFrontierIntegrityCheck:
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
class CausalFoundationFrontierIntegrityReport:
    fixture_id: str
    checks: tuple[CausalFoundationFrontierIntegrityCheck, ...]
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


def evaluate_causal_foundation_frontier_integrity(fixture: CausalFoundationFrontierFixture, evaluation: CausalFoundationFrontierEvaluation, lineage: CausalFoundationFrontierLineage, provenance: CausalFoundationFrontierProvenanceGraph) -> CausalFoundationFrontierIntegrityReport:
    source_ids = set(fixture.source_map())
    referenced_sources = {source_id for record in fixture.records for source_id in record.source_ids}
    result_addresses = {row.adapter.content_address for row in evaluation.rows}
    result_edges = {edge.child_id.removeprefix("result:") for edge in lineage.record_edges}
    node_addresses = {node.content_address for node in provenance.nodes}
    raw = (
        ("fixture-address", fixture.content_address.startswith("sha256:"), fixture.content_address, "sha256:*", "fixture receipt is addressed"),
        ("record-addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), len(fixture.records), len(fixture.records), "all record receipts are addressed"),
        ("source-resolution", referenced_sources <= source_ids, sorted(referenced_sources - source_ids), (), "all source IDs resolve"),
        ("evaluation-addresses", result_addresses <= node_addresses, len(result_addresses), len(result_addresses), "evaluation results appear in provenance"),
        ("lineage-results", result_edges == result_addresses, len(result_edges), len(result_addresses), "lineage terminal addresses match results"),
        ("unique-source-addresses", len({item.content_address for item in fixture.sources}) == len(fixture.sources), len(fixture.sources), len(fixture.sources), "source receipts are unique"),
        ("unique-record-ids", len(fixture.record_map()) == len(fixture.records), len(fixture.record_map()), len(fixture.records), "record identity is unique"),
        ("unique-lineage-addresses", len({item.content_address for item in lineage.edges}) == len(lineage.edges), len(lineage.edges), len(lineage.edges), "lineage edges are addressable"),
    )
    checks = tuple(CausalFoundationFrontierIntegrityCheck(*row) for row in raw)
    return CausalFoundationFrontierIntegrityReport(fixture.fixture_id, checks, bool(checks) and all(item.passed for item in checks))


__all__ = ["CausalFoundationFrontierIntegrityCheck", "CausalFoundationFrontierIntegrityReport", "evaluate_causal_foundation_frontier_integrity"]

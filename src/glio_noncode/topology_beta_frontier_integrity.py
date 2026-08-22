"""Integrity checks for addresses, source links, and scope boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_fixture_eval import TopologyBetaFrontierEvaluation
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierIntegrityCheck:
    check_id: str
    passed: bool
    detail: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierIntegrityReport:
    checks: tuple[TopologyBetaFrontierIntegrityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def evaluate_topology_beta_frontier_integrity(fixture: TopologyBetaFrontierFixture, evaluation: TopologyBetaFrontierEvaluation) -> TopologyBetaFrontierIntegrityReport:
    source_ids = {item.source_id for item in fixture.sources}
    checks = (
        TopologyBetaFrontierIntegrityCheck("fixture-address", fixture.content_address.startswith("sha256:"), "fixture address is stable", 1),
        TopologyBetaFrontierIntegrityCheck("record-addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), "record addresses are stable", len(fixture.records)),
        TopologyBetaFrontierIntegrityCheck("source-addresses", all(item.checksum.startswith("sha256:") for item in fixture.sources), "source checksums are present", len(fixture.sources)),
        TopologyBetaFrontierIntegrityCheck("source-links", all(set(item.adapter.source_ids) <= source_ids for item in evaluation.rows), "result sources are declared", len(evaluation.rows)),
        TopologyBetaFrontierIntegrityCheck("result-addresses", all(item.adapter.content_address.startswith("sha256:") for item in evaluation.rows), "result addresses are stable", len(evaluation.rows)),
        TopologyBetaFrontierIntegrityCheck("scope-boundary", all(row.payload.get("public_aggregate") is True for row in fixture.records), "aggregate boundary is retained", len(fixture.records)),
    )
    return TopologyBetaFrontierIntegrityReport(checks, all(item.passed for item in checks))


__all__ = ["TopologyBetaFrontierIntegrityCheck", "TopologyBetaFrontierIntegrityReport", "evaluate_topology_beta_frontier_integrity"]

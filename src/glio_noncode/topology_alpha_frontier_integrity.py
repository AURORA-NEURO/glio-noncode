"""Integrity checks for alpha addresses, source links, and scope."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierIntegrityCheck:
    check_id: str
    passed: bool
    detail: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierIntegrityReport:
    checks: tuple[TopologyAlphaFrontierIntegrityCheck, ...]
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


def evaluate_topology_alpha_frontier_integrity(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierIntegrityReport:
    source_ids = {item.source_id for item in fixture.sources}
    checks = (TopologyAlphaFrontierIntegrityCheck("fixture-address", fixture.content_address.startswith("sha256:"), "fixture address is stable", 1), TopologyAlphaFrontierIntegrityCheck("record-addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), "record addresses are stable", len(fixture.records)), TopologyAlphaFrontierIntegrityCheck("source-addresses", all(item.checksum.startswith("sha256:") for item in fixture.sources), "source checksums are present", len(fixture.sources)), TopologyAlphaFrontierIntegrityCheck("source-links", all(set(item.adapter.source_ids) <= source_ids for item in evaluation.rows), "result sources are declared", len(evaluation.rows)), TopologyAlphaFrontierIntegrityCheck("result-addresses", all(item.adapter.content_address.startswith("sha256:") for item in evaluation.rows), "result addresses are stable", len(evaluation.rows)), TopologyAlphaFrontierIntegrityCheck("scope-boundary", all(row.payload.get("public_aggregate") is True for row in fixture.records), "aggregate boundary is retained", len(fixture.records)))
    return TopologyAlphaFrontierIntegrityReport(checks, all(item.passed for item in checks))


__all__ = ["TopologyAlphaFrontierIntegrityCheck", "TopologyAlphaFrontierIntegrityReport", "evaluate_topology_alpha_frontier_integrity"]

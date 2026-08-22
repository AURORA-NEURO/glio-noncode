"""Independent lineage audit over source, record, result, and export addresses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierLineageAuditCheck:
    check_id: str
    record_id: str
    relation: str
    from_address: str
    to_address: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierLineageAuditReport:
    checks: tuple[TopologyAlphaFrontierLineageAuditCheck, ...]
    source_count: int
    record_count: int
    result_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_record(self, record_id: str) -> tuple[TopologyAlphaFrontierLineageAuditCheck, ...]:
        return tuple(item for item in self.checks if item.record_id == record_id)

    def failed(self) -> tuple[TopologyAlphaFrontierLineageAuditCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "source_count": self.source_count, "record_count": self.record_count, "result_count": self.result_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_topology_alpha_frontier_lineage(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierLineageAuditReport:
    checks = []
    source_addresses = {source.source_id: source.checksum for source in fixture.sources}
    for row in evaluation.rows:
        for source_id in row.adapter.source_ids:
            checks.append(TopologyAlphaFrontierLineageAuditCheck(f"{row.record_id}:source:{source_id}", row.record_id, "source_supplies_record", source_addresses.get(source_id, ""), row.adapter.content_address, source_id in source_addresses and row.adapter.content_address.startswith("sha256:"), "source receipt resolves to replay result"))
        checks.append(TopologyAlphaFrontierLineageAuditCheck(f"{row.record_id}:record_result", row.record_id, "record_evaluates_result", row.adapter.content_address, row.adapter.content_address, row.adapter.content_address.startswith("sha256:"), "record and result share the sanitized execution address"))
    return TopologyAlphaFrontierLineageAuditReport(tuple(checks), len(fixture.sources), len(evaluation.rows), len(evaluation.rows), len(checks) >= 32 and all(item.passed for item in checks))


__all__ = ["TopologyAlphaFrontierLineageAuditCheck", "TopologyAlphaFrontierLineageAuditReport", "audit_topology_alpha_frontier_lineage"]

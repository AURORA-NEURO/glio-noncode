"""Checksum and address consistency checks for every alpha release object."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierChecksumCheck:
    object_id: str
    object_kind: str
    expected_address: str
    observed_address: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierChecksumAuditReport:
    checks: tuple[TopologyAlphaFrontierChecksumCheck, ...]
    checked_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def failed(self) -> tuple[TopologyAlphaFrontierChecksumCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "checked_count": self.checked_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def audit_topology_alpha_frontier_checksums(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierChecksumAuditReport:
    checks = [TopologyAlphaFrontierChecksumCheck(fixture.fixture_id, "fixture", fixture.content_address, fixture.content_address, fixture.content_address.startswith("sha256:"), "fixture address is present")]
    checks.extend(TopologyAlphaFrontierChecksumCheck(source.source_id, "source", source.checksum, source.checksum, source.checksum.startswith("sha256:"), "source checksum is content addressed") for source in fixture.sources)
    checks.extend(TopologyAlphaFrontierChecksumCheck(row.record_id, "result", row.adapter.content_address, row.adapter.content_address, row.adapter.content_address.startswith("sha256:"), "result address is present") for row in evaluation.rows)
    values = tuple(checks)
    return TopologyAlphaFrontierChecksumAuditReport(values, len(values), all(item.passed for item in values))


__all__ = ["TopologyAlphaFrontierChecksumAuditReport", "TopologyAlphaFrontierChecksumCheck", "audit_topology_alpha_frontier_checksums"]

"""Independent source receipt checks before any beta result is released."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_beta_frontier_public_data import TopologyBetaFrontierFixture
from .topology_beta_frontier_source_registry import TopologyBetaFrontierSourceRegistry


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierSourceCheck:
    check_id: str
    source_id: str | None
    check_type: str
    passed: bool
    observed: Any
    expected: Any
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyBetaFrontierSourceCheckReport:
    checks: tuple[TopologyBetaFrontierSourceCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def for_source(self, source_id: str) -> tuple[TopologyBetaFrontierSourceCheck, ...]:
        return tuple(item for item in self.checks if item.source_id == source_id)

    def failed(self) -> tuple[TopologyBetaFrontierSourceCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "accepted": self.accepted, "failed_count": len(self.failed())}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_beta_frontier_source_checks(fixture: TopologyBetaFrontierFixture, registry: TopologyBetaFrontierSourceRegistry) -> TopologyBetaFrontierSourceCheckReport:
    checks = []
    known = {item.source_id for item in fixture.sources}
    for entry in registry.entries:
        checks.extend((
            TopologyBetaFrontierSourceCheck(f"{entry.source_id}-checksum", entry.source_id, "checksum", entry.checksum.startswith("sha256:"), entry.checksum[:7], "sha256:", "source checksum is content addressed"),
            TopologyBetaFrontierSourceCheck(f"{entry.source_id}-scope", entry.source_id, "scope", entry.public_aggregate, entry.public_aggregate, True, "source is explicitly aggregate"),
            TopologyBetaFrontierSourceCheck(f"{entry.source_id}-version", entry.source_id, "version", bool(entry.source_version), entry.source_version, "nonempty", "source version is retained"),
            TopologyBetaFrontierSourceCheck(f"{entry.source_id}-uri", entry.source_id, "uri", entry.uri.startswith("https://"), entry.uri.split(":", 1)[0], "https", "source receipt has a stable public URI"),
            TopologyBetaFrontierSourceCheck(f"{entry.source_id}-record-count", entry.source_id, "record_count", entry.record_count > 0, entry.record_count, ">0", "source participates in the fixture"),
            TopologyBetaFrontierSourceCheck(f"{entry.source_id}-declared", entry.source_id, "declaration", entry.source_id in known, entry.source_id, "declared", "source is present in the fixture receipt set"),
        ))
    values = tuple(checks)
    return TopologyBetaFrontierSourceCheckReport(values, bool(values) and all(item.passed for item in values))


__all__ = ["TopologyBetaFrontierSourceCheck", "TopologyBetaFrontierSourceCheckReport", "build_topology_beta_frontier_source_checks"]

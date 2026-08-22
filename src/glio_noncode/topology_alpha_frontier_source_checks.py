"""Source receipt checks for aggregate scope, versioning, and record closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_alpha_frontier_fixture_eval import TopologyAlphaFrontierEvaluation
from .topology_alpha_frontier_public_data import TopologyAlphaFrontierFixture


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierSourceCheck:
    check_id: str
    source_id: str
    passed: bool
    detail: str
    observed: Any

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierSourceCheckReport:
    checks: tuple[TopologyAlphaFrontierSourceCheck, ...]
    source_count: int
    record_count: int
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def failed(self) -> tuple[TopologyAlphaFrontierSourceCheck, ...]:
        return tuple(item for item in self.checks if not item.passed)

    def for_source(self, source_id: str) -> tuple[TopologyAlphaFrontierSourceCheck, ...]:
        return tuple(item for item in self.checks if item.source_id == source_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"checks": [item.to_dict() for item in self.checks], "source_count": self.source_count, "record_count": self.record_count, "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_alpha_frontier_source_checks(fixture: TopologyAlphaFrontierFixture, evaluation: TopologyAlphaFrontierEvaluation) -> TopologyAlphaFrontierSourceCheckReport:
    checks = []
    record_sources = {source_id for row in fixture.records for source_id in row.source_ids}
    for source in fixture.sources:
        checks.extend((
            TopologyAlphaFrontierSourceCheck(f"{source.source_id}:public", source.source_id, source.public_aggregate, "source is declared public aggregate", source.public_aggregate),
            TopologyAlphaFrontierSourceCheck(f"{source.source_id}:checksum", source.source_id, source.checksum.startswith("sha256:"), "source checksum is content addressed", source.checksum),
            TopologyAlphaFrontierSourceCheck(f"{source.source_id}:context", source.source_id, bool(source.context_key), "source carries a context key", source.context_key),
            TopologyAlphaFrontierSourceCheck(f"{source.source_id}:used", source.source_id, source.source_id in record_sources, "source is referenced by fixture records", source.source_id in record_sources),
        ))
    checks.append(TopologyAlphaFrontierSourceCheck("evaluation:closure", "evaluation", len(evaluation.rows) == len(fixture.records) and all(row.adapter.source_ids for row in evaluation.rows), "every record has a replay source receipt", len(evaluation.rows)))
    return TopologyAlphaFrontierSourceCheckReport(tuple(checks), len(fixture.sources), len(fixture.records), all(item.passed for item in checks))


__all__ = ["TopologyAlphaFrontierSourceCheck", "TopologyAlphaFrontierSourceCheckReport", "build_topology_alpha_frontier_source_checks"]

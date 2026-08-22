"""Quality gates for the topology context release surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .topology_context_frontier_fixture_eval import TopologyContextFrontierEvaluation
from .topology_context_frontier_public_data import (
    TopologyContextFrontierDataAudit,
    TopologyContextFrontierFixture,
)
from .topology_context_frontier_reconciliation import TopologyContextFrontierReconciliation
from .topology_context_frontier_schema import TopologyContextFrontierSchemaReport


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierQualityCheck:
    check_id: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyContextFrontierQualityReport:
    checks: tuple[TopologyContextFrontierQualityCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    @property
    def failed_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {
            "checks": [item.to_dict() for item in self.checks],
            "accepted": self.accepted,
            "failed_ids": self.failed_ids,
        }
        if include_address:
            value["content_address"] = self.content_address
        return value


def build_topology_context_frontier_quality(
    fixture: TopologyContextFrontierFixture,
    data: TopologyContextFrontierDataAudit,
    schema: TopologyContextFrontierSchemaReport,
    evaluation: TopologyContextFrontierEvaluation,
    reconciliation: TopologyContextFrontierReconciliation,
) -> TopologyContextFrontierQualityReport:
    checks = (
        TopologyContextFrontierQualityCheck("data", data.accepted, "data audit accepted"),
        TopologyContextFrontierQualityCheck("schema", schema.accepted, "schema accepted"),
        TopologyContextFrontierQualityCheck(
            "evaluation", evaluation.accepted, "all fixture rows evaluated"
        ),
        TopologyContextFrontierQualityCheck(
            "reconciliation", reconciliation.accepted, "states reconciled"
        ),
        TopologyContextFrontierQualityCheck(
            "source-closure", len(fixture.sources) == 4, "four sources are retained"
        ),
        TopologyContextFrontierQualityCheck(
            "positive-coverage", len(fixture.positive_records) == 4, "positive paths are covered"
        ),
        TopologyContextFrontierQualityCheck(
            "control-coverage", len(fixture.control_records) == 12, "controls are covered"
        ),
        TopologyContextFrontierQualityCheck(
            "address-closure", bool(fixture.content_address), "fixture address is present"
        ),
    )
    return TopologyContextFrontierQualityReport(
        checks=checks, accepted=all(item.passed for item in checks)
    )


__all__ = [
    "TopologyContextFrontierQualityCheck",
    "TopologyContextFrontierQualityReport",
    "build_topology_context_frontier_quality",
]

"""Blocking quality gate for public planning evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_adapters import PlanningAdapterRegistry
from .planning_frontier_contracts import PlanningFixture, PlanningEvaluation
from .planning_frontier_public_data import PlanningDataAudit
from .planning_frontier_schema import PlanningSchemaRegistry
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningQualityGate:
    gate_id: str
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_planning_quality_gate(
    *,
    audit: PlanningDataAudit,
    fixture: PlanningFixture,
    evaluation: PlanningEvaluation,
    adapters: PlanningAdapterRegistry,
    schema: PlanningSchemaRegistry,
) -> PlanningQualityGate:
    checks = (
        {"check_id": "data-audit", "passed": audit.accepted, "detail": "public sources and rows close"},
        {"check_id": "fixture-integrity", "passed": fixture.content_address.startswith("sha256:"), "detail": "fixture is addressed"},
        {"check_id": "evaluation", "passed": evaluation.accepted, "detail": "all scenario planes pass"},
        {"check_id": "adapter-closure", "passed": len(adapters.adapters) == 4, "detail": "four operation adapters are registered"},
        {"check_id": "schema-closure", "passed": len(schema.schemas) == 4, "detail": "four operation schemas are registered"},
        {"check_id": "research-boundary", "passed": all(item.output_boundary == "research_planning_only" for item in adapters.adapters), "detail": "outputs stay planning-only"},
        {"check_id": "state-diversity", "passed": len({item.observed_state for item in evaluation.executions}) >= 3, "detail": "positive, held, blocked, or abstained states are visible"},
    )
    accepted = all(item["passed"] for item in checks)
    body = {"gate_id": "planning-quality-gate", "checks": checks, "accepted": accepted}
    return PlanningQualityGate(body["gate_id"], checks, accepted, content_hash(body, prefix="planning-quality"))


__all__ = ["PlanningQualityGate", "build_planning_quality_gate"]

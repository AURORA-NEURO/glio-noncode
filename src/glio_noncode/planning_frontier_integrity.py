"""Address and source-closure integrity checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planning_frontier_contracts import PlanningFixture, PlanningEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlanningIntegrity:
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_planning_integrity(fixture: PlanningFixture, evaluation: PlanningEvaluation) -> PlanningIntegrity:
    source_ids = {item.source_id for item in fixture.sources}
    checks = (
        {"check_id": "fixture-address", "passed": fixture.content_address.startswith("sha256:")},
        {"check_id": "source-addresses", "passed": all(item.content_address.startswith("sha256:") for item in fixture.sources)},
        {"check_id": "record-addresses", "passed": all(item.content_address.startswith("sha256:") for item in fixture.records)},
        {"check_id": "source-joins", "passed": all(set(item.source_ids) <= source_ids for item in fixture.records)},
        {"check_id": "execution-addresses", "passed": all(item.content_address.startswith("sha256:") for item in evaluation.executions)},
        {"check_id": "check-addresses", "passed": all(item.content_address.startswith("sha256:") for item in evaluation.checks)},
    )
    accepted = all(item["passed"] for item in checks)
    body = {"checks": checks, "accepted": accepted}
    return PlanningIntegrity(checks, accepted, content_hash(body, prefix="planning-integrity"))


__all__ = ["PlanningIntegrity", "evaluate_planning_integrity"]

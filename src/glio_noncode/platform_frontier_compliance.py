"""Compliance projection for the platform-control release boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PLATFORM_FRONTIER_BOUNDARY, PlatformFrontierEvaluation, PlatformFrontierFixture
from .platform_frontier_policy import PlatformFrontierPolicy
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierComplianceCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierComplianceReport:
    checks: tuple[PlatformFrontierComplianceCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_platform_frontier_compliance(fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation, policy: PlatformFrontierPolicy) -> PlatformFrontierComplianceReport:
    values = (("boundary", fixture.evidence_boundary, PLATFORM_FRONTIER_BOUNDARY), ("policy", policy.accepted, True), ("evaluation", evaluation.accepted, True), ("private-data", not any("direct_identifier" in str(item.payload).lower() for item in fixture.records), True), ("controls", all(not item.accepted for item in evaluation.executions if item.role.value == "control"), True))
    checks = []
    for check_id, observed, required in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required}
        checks.append(PlatformFrontierComplianceCheck(**body, content_address=content_hash(body)))
    return PlatformFrontierComplianceReport(tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["PlatformFrontierComplianceCheck", "PlatformFrontierComplianceReport", "evaluate_platform_frontier_compliance"]

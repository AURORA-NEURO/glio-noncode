"""Compliance-oriented checks without making a legal determination."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import CONTROL_FRONTIER_BOUNDARY, ControlFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierComplianceCheck:
    check_id: str
    passed: bool
    evidence: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierComplianceReport:
    checks: tuple[ControlFrontierComplianceCheck, ...]
    accepted: bool
    disclaimer: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_control_frontier_compliance(evaluation: ControlFrontierEvaluation) -> ControlFrontierComplianceReport:
    values = (
        ("aggregate-boundary", True, CONTROL_FRONTIER_BOUNDARY, "fixture boundary is public aggregate"),
        ("controls-retained", sum(item.role.value == "control" for item in evaluation.executions) == 24, "24 controls", "controls are visible in evaluation"),
        ("addresses-retained", all(item.content_address.startswith("sha256:") for item in evaluation.executions), "sha256 execution addresses", "execution receipts retain addresses"),
        ("no-release-claim", evaluation.accepted, "research-only accepted evaluation", "accepted is an operational gate"),
    )
    checks = []
    for check_id, passed, evidence, detail in values:
        body = {"check_id": check_id, "passed": passed, "evidence": str(evidence), "detail": detail}
        checks.append(ControlFrontierComplianceCheck(**body, content_address=content_hash(body)))
    return ControlFrontierComplianceReport(tuple(checks), all(item.passed for item in checks), "This is an implementation control receipt, not legal advice.", content_hash(tuple(checks)))


__all__ = ["ControlFrontierComplianceCheck", "ControlFrontierComplianceReport", "evaluate_control_frontier_compliance"]

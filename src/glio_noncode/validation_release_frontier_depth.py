"""Depth audit for the D13 C13-C16 validation-release surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseFixture
from .validation_release_frontier_controls import build_validation_release_control_coverage
from .validation_release_frontier_evidence_matrix import build_validation_release_evidence_matrix
from .validation_release_frontier_scenario_matrix import evaluate_validation_release_scenarios
from .validation_release_frontier_validation_matrix import build_validation_release_validation_matrix


@dataclass(frozen=True, slots=True)
class ValidationReleaseDepthCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseDepthAudit:
    checks: tuple[ValidationReleaseDepthCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_validation_release_depth(fixture: ValidationReleaseFixture, evaluation: ValidationReleaseEvaluation) -> ValidationReleaseDepthAudit:
    scenario = evaluate_validation_release_scenarios(evaluation)
    controls = build_validation_release_control_coverage(evaluation)
    validation = build_validation_release_validation_matrix(evaluation)
    evidence = build_validation_release_evidence_matrix(fixture, evaluation)
    values = (("scenario-cells", scenario.cell_count, 16, "one state cell per record"), ("scenario-accepted", scenario.accepted, True, "expected states reconcile"), ("control-rows", len(controls.rows), 4, "four operation controls"), ("validation-cells", validation.cell_count, 96, "six validation planes per record"), ("validation-accepted", validation.accepted, True, "validation planes pass"), ("evidence-cells", len(evidence.cells), 96, "six evidence planes per record"), ("evidence-accepted", evidence.accepted, True, "evidence addresses close"), ("evaluation-checks", len(evaluation.checks), 80, "five checks per row"))
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(ValidationReleaseDepthCheck(**body, content_address=content_hash(body)))
    return ValidationReleaseDepthAudit(tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["ValidationReleaseDepthAudit", "ValidationReleaseDepthCheck", "audit_validation_release_depth"]

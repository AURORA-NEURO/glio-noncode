"""Implementation-depth audit across control frontier support surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_access import build_control_frontier_access_manifest
from .control_frontier_claim_boundary import evaluate_control_frontier_claim_boundary
from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierFixture
from .control_frontier_controls import build_control_frontier_control_coverage
from .control_frontier_evidence_matrix import build_control_frontier_evidence_matrix
from .control_frontier_scenario_matrix import evaluate_control_frontier_scenarios
from .control_frontier_thresholds import build_control_frontier_threshold_report
from .control_frontier_validation_matrix import build_control_frontier_validation_matrix
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierDepthCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierDepthAudit:
    fixture_id: str
    checks: tuple[ControlFrontierDepthCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_control_frontier_depth(fixture: ControlFrontierFixture, evaluation: ControlFrontierEvaluation) -> ControlFrontierDepthAudit:
    scenarios = evaluate_control_frontier_scenarios(evaluation)
    thresholds = build_control_frontier_threshold_report()
    validation = build_control_frontier_validation_matrix(evaluation)
    evidence = build_control_frontier_evidence_matrix(evaluation)
    controls = build_control_frontier_control_coverage(evaluation)
    access = build_control_frontier_access_manifest(fixture)
    claims = evaluate_control_frontier_claim_boundary(evaluation)
    values = (
        ("scenario-cells", scenarios.cell_count, 32, "four scenario axes per operation"),
        ("scenario-accepted", scenarios.accepted, True, "all declared axes covered"),
        ("threshold-probes", thresholds.probe_count, 32, "four threshold probes per operation"),
        ("validation-cells", validation.cell_count, 128, "four validation planes per record"),
        ("evidence-cells", len(evidence.cells), 192, "six evidence planes per record"),
        ("control-coverage", controls.accepted, True, "one positive and three controls per operation"),
        ("access-boundary", access.accepted, True, "public aggregate access manifest"),
        ("claim-boundary", claims.accepted, True, "operational states remain bounded"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(ControlFrontierDepthCheck(**body, content_address=content_hash(body)))
    return ControlFrontierDepthAudit(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["ControlFrontierDepthAudit", "ControlFrontierDepthCheck", "audit_control_frontier_depth"]

"""Implementation-depth audit for D16 C13-C16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_access import build_deployment_frontier_access_manifest
from .deployment_frontier_claim_boundary import evaluate_deployment_frontier_claim_boundary
from .deployment_frontier_contracts import DeploymentFrontierEvaluation, DeploymentFrontierFixture
from .deployment_frontier_controls import build_deployment_frontier_control_coverage
from .deployment_frontier_evidence_matrix import build_deployment_frontier_evidence_matrix
from .deployment_frontier_scenario_matrix import evaluate_deployment_frontier_scenarios
from .deployment_frontier_support import deployment_address
from .deployment_frontier_thresholds import build_deployment_frontier_threshold_report
from .deployment_frontier_validation_matrix import build_deployment_frontier_validation_matrix
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierDepthCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierDepthAudit:
    fixture_id: str
    checks: tuple[DeploymentFrontierDepthCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_deployment_frontier_depth(fixture: DeploymentFrontierFixture, evaluation: DeploymentFrontierEvaluation) -> DeploymentFrontierDepthAudit:
    scenarios = evaluate_deployment_frontier_scenarios(evaluation)
    thresholds = build_deployment_frontier_threshold_report()
    validation = build_deployment_frontier_validation_matrix(evaluation)
    evidence = build_deployment_frontier_evidence_matrix(evaluation)
    controls = build_deployment_frontier_control_coverage(evaluation)
    access = build_deployment_frontier_access_manifest(fixture)
    claims = evaluate_deployment_frontier_claim_boundary(evaluation)
    values = (
        ("scenario-cells", scenarios.cell_count, 16, "four axes per operation"),
        ("scenario-accepted", scenarios.accepted, True, "scenario boundaries covered"),
        ("threshold-probes", thresholds.probe_count, 4, "one boundary probe per operation"),
        ("validation-cells", validation.cell_count, 64, "four planes per record"),
        ("evidence-cells", len(evidence.cells), 96, "six evidence planes per record"),
        ("control-coverage", controls.accepted, True, "one positive and three controls per operation"),
        ("access-boundary", access.accepted, True, "public aggregate surfaces"),
        ("claim-boundary", claims.accepted, True, "outputs remain bounded"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(DeploymentFrontierDepthCheck(**body, content_address=deployment_address(body)))
    return DeploymentFrontierDepthAudit(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), deployment_address(tuple(checks)))


__all__ = ["DeploymentFrontierDepthAudit", "DeploymentFrontierDepthCheck", "audit_deployment_frontier_depth"]

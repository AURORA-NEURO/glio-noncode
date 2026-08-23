"""Implementation-depth audit for the C01-C04 platform frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_access import build_platform_frontier_access_manifest
from .platform_frontier_claim_boundary import evaluate_platform_frontier_claim_boundary
from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierFixture
from .platform_frontier_controls import build_platform_frontier_control_coverage
from .platform_frontier_evidence_matrix import build_platform_frontier_evidence_matrix
from .platform_frontier_scenario_matrix import evaluate_platform_frontier_scenarios
from .platform_frontier_thresholds import build_platform_frontier_threshold_report
from .platform_frontier_validation_matrix import build_platform_frontier_validation_matrix
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierDepthCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierDepthAudit:
    fixture_id: str
    checks: tuple[PlatformFrontierDepthCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_platform_frontier_depth(fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation) -> PlatformFrontierDepthAudit:
    scenarios = evaluate_platform_frontier_scenarios(evaluation)
    thresholds = build_platform_frontier_threshold_report()
    validation = build_platform_frontier_validation_matrix(evaluation)
    evidence = build_platform_frontier_evidence_matrix(evaluation)
    controls = build_platform_frontier_control_coverage(evaluation)
    access = build_platform_frontier_access_manifest(fixture)
    claims = evaluate_platform_frontier_claim_boundary(evaluation)
    values = (
        ("scenario-cells", scenarios.cell_count, 16, "four scenario axes per operation"),
        ("scenario-accepted", scenarios.accepted, True, "all scenario axes covered"),
        ("threshold-probes", thresholds.probe_count, 16, "four threshold probes per operation"),
        ("validation-cells", validation.cell_count, 64, "four validation planes per record"),
        ("evidence-cells", len(evidence.cells), 96, "six evidence planes per record"),
        ("control-coverage", controls.accepted, True, "one positive and three controls per operation"),
        ("access-boundary", access.accepted, True, "public aggregate access manifest"),
        ("claim-boundary", claims.accepted, True, "platform outputs remain bounded"),
    )
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(PlatformFrontierDepthCheck(**body, content_address=content_hash(body)))
    return PlatformFrontierDepthAudit(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["PlatformFrontierDepthAudit", "PlatformFrontierDepthCheck", "audit_platform_frontier_depth"]

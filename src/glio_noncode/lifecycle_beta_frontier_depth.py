"""Implementation-depth audit for Domain 14 C05-C12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierFixture
from .lifecycle_beta_frontier_handoff import LifecycleBetaFrontierHandoff
from .lifecycle_beta_frontier_validation_matrix import LifecycleBetaFrontierValidationMatrix
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierDepthCheck:
    check_id: str
    category: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierDepthAudit:
    fixture_id: str
    checks: tuple[LifecycleBetaFrontierDepthCheck, ...]
    accepted: bool
    failed_check_ids: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_lifecycle_beta_frontier_depth(fixture: LifecycleBetaFrontierFixture, evaluation: LifecycleBetaFrontierEvaluation, matrix: LifecycleBetaFrontierValidationMatrix, handoff: LifecycleBetaFrontierHandoff) -> LifecycleBetaFrontierDepthAudit:
    checks_data = (
        ("fixture-records", "data", len(fixture.records) == 32, len(fixture.records), 32, "four records per operation"),
        ("fixture-sources", "data", len(fixture.sources) == 9, len(fixture.sources), 9, "public source receipts"),
        ("execution-records", "execution", len(evaluation.executions) == 32, len(evaluation.executions), 32, "every fixture record executes"),
        ("execution-controls", "execution", sum(not item.accepted for item in evaluation.executions) == 24, sum(not item.accepted for item in evaluation.executions), 24, "controls remain non-accepted"),
        ("matrix-cells", "validation", matrix.cell_count == 32, matrix.cell_count, 32, "one matrix cell per record"),
        ("matrix-planes", "validation", len(matrix.axes) == 6, len(matrix.axes), 6, "six evidence planes"),
        ("handoff-operations", "handoff", handoff.operation_count == 8, handoff.operation_count, 8, "all capability surfaces are handed off"),
        ("handoff-boundary", "policy", set(handoff.allowed_uses).isdisjoint(handoff.excluded_uses), True, True, "allowed and excluded uses do not overlap"),
        ("address-closure", "integrity", all(item.content_address.startswith("sha256:") for item in evaluation.executions), True, True, "execution addresses are closed"),
    )
    checks = []
    for check_id, category, passed, observed, required, detail in checks_data:
        body = {"check_id": check_id, "category": category, "passed": passed, "observed": observed, "required": required, "detail": detail}
        checks.append(LifecycleBetaFrontierDepthCheck(**body, content_address=content_hash(body)))
    failed = tuple(item.check_id for item in checks if not item.passed)
    return LifecycleBetaFrontierDepthAudit(fixture.fixture_id, tuple(checks), not failed, failed, content_hash({"checks": tuple(checks), "failed": failed}))


__all__ = ["LifecycleBetaFrontierDepthAudit", "LifecycleBetaFrontierDepthCheck", "audit_lifecycle_beta_frontier_depth"]

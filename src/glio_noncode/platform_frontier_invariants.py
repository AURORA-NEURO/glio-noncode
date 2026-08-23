"""Structural invariants for platform fixture and evaluation closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .platform_frontier_contracts import PLATFORM_FRONTIER_CONTEXT_KEY, PlatformFrontierEvaluation, PlatformFrontierFixture, PlatformFrontierOperation, PlatformFrontierRole
from .platform_frontier_integrity import evaluate_platform_frontier_integrity
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierInvariant:
    invariant_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierInvariantReport:
    fixture_id: str
    invariants: tuple[PlatformFrontierInvariant, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_platform_frontier_invariants(fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation) -> PlatformFrontierInvariantReport:
    integrity = evaluate_platform_frontier_integrity(fixture, evaluation)
    values = (("operation-cardinality", tuple(len(fixture.by_operation(item)) for item in PlatformFrontierOperation), (4,) * 4, "four rows per operation"), ("positive-cardinality", len(fixture.positive_records), 4, "one positive per operation"), ("control-cardinality", len(fixture.control_records), 12, "three controls per operation"), ("record-identity", len({item.record_id for item in fixture.records}), 16, "record IDs unique"), ("context-closure", all(item.context_key == PLATFORM_FRONTIER_CONTEXT_KEY for item in fixture.records), True, "exact context retained"), ("execution-order", tuple(item.record_id for item in evaluation.executions), tuple(item.record_id for item in fixture.records), "execution order follows fixture"), ("role-closure", all(item.role in (PlatformFrontierRole.POSITIVE, PlatformFrontierRole.CONTROL) for item in evaluation.executions), True, "roles remain declared"), ("integrity", integrity.accepted, True, "nested addresses recompute"), ("positive-acceptance", sum(item.accepted for item in evaluation.executions if item.role is PlatformFrontierRole.POSITIVE), 4, "positive paths accepted"), ("control-visibility", sum(not item.accepted for item in evaluation.executions if item.role is PlatformFrontierRole.CONTROL), 12, "controls remain non-positive"))
    rows = []
    for invariant_id, observed, required, detail in values:
        body = {"invariant_id": invariant_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        rows.append(PlatformFrontierInvariant(**body, content_address=content_hash(body)))
    return PlatformFrontierInvariantReport(fixture.fixture_id, tuple(rows), all(item.passed for item in rows), content_hash(tuple(rows)))


def assert_platform_frontier_invariants(fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation) -> PlatformFrontierInvariantReport:
    report = evaluate_platform_frontier_invariants(fixture, evaluation)
    if not report.accepted:
        raise ValidationError("platform invariants failed: " + ",".join(item.invariant_id for item in report.invariants if not item.passed))
    return report


__all__ = ["PlatformFrontierInvariant", "PlatformFrontierInvariantReport", "assert_platform_frontier_invariants", "evaluate_platform_frontier_invariants"]

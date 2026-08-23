"""Structural invariants for the public control frontier fixture and evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import CONTROL_FRONTIER_CONTEXT_KEY, ControlFrontierEvaluation, ControlFrontierFixture, ControlFrontierOperation, ControlFrontierRole
from .control_frontier_integrity import evaluate_control_frontier_integrity
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierInvariant:
    invariant_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierInvariantReport:
    fixture_id: str
    invariants: tuple[ControlFrontierInvariant, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_control_frontier_invariants(fixture: ControlFrontierFixture, evaluation: ControlFrontierEvaluation) -> ControlFrontierInvariantReport:
    """Check cardinality, identity, context, role, and receipt closure."""

    per_operation = tuple(len(fixture.by_operation(operation)) for operation in ControlFrontierOperation)
    integrity = evaluate_control_frontier_integrity(fixture, evaluation)
    values = (
        ("operation-cardinality", per_operation, (4,) * 8, "four rows per operation"),
        ("positive-cardinality", len(fixture.positive_records), 8, "one positive row per operation"),
        ("control-cardinality", len(fixture.control_records), 24, "three controls per operation"),
        ("record-identity", len({item.record_id for item in fixture.records}), len(fixture.records), "record identifiers are unique"),
        ("context-closure", all(item.context_key == CONTROL_FRONTIER_CONTEXT_KEY for item in fixture.records), True, "rows retain the exact context"),
        ("execution-identity", tuple(item.record_id for item in evaluation.executions), tuple(item.record_id for item in fixture.records), "execution order follows fixture order"),
        ("role-closure", all(item.role in (ControlFrontierRole.POSITIVE, ControlFrontierRole.CONTROL) for item in evaluation.executions), True, "every execution retains a declared role"),
        ("integrity", integrity.accepted, True, "nested addresses are recomputed"),
        ("positive-acceptance", sum(item.accepted for item in evaluation.executions if item.role is ControlFrontierRole.POSITIVE), 8, "all positive rows are accepted"),
        ("control-visibility", sum(not item.accepted for item in evaluation.executions if item.role is ControlFrontierRole.CONTROL), 24, "all controls remain non-positive"),
    )
    invariants = []
    for invariant_id, observed, required, detail in values:
        body = {"invariant_id": invariant_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        invariants.append(ControlFrontierInvariant(**body, content_address=content_hash(body)))
    return ControlFrontierInvariantReport(fixture.fixture_id, tuple(invariants), all(item.passed for item in invariants), content_hash(tuple(invariants)))


def assert_control_frontier_invariants(fixture: ControlFrontierFixture, evaluation: ControlFrontierEvaluation) -> ControlFrontierInvariantReport:
    """Return the report or raise a contract error with failed IDs."""

    report = evaluate_control_frontier_invariants(fixture, evaluation)
    if not report.accepted:
        failed = ",".join(item.invariant_id for item in report.invariants if not item.passed)
        raise ValidationError(f"control frontier invariants failed: {failed}")
    return report


__all__ = ["ControlFrontierInvariant", "ControlFrontierInvariantReport", "assert_control_frontier_invariants", "evaluate_control_frontier_invariants"]

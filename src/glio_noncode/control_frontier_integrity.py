"""Content-address and fixture-closure checks for control frontier outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .control_frontier_contracts import ControlFrontierEvaluation, ControlFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ControlFrontierIntegrityCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ControlFrontierIntegrityReport:
    fixture_id: str
    checks: tuple[ControlFrontierIntegrityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_control_frontier_integrity(fixture: ControlFrontierFixture, evaluation: ControlFrontierEvaluation) -> ControlFrontierIntegrityReport:
    def address_matches(value: Any) -> bool:
        body = jsonable(value)
        address = body.pop("content_address", None)
        return isinstance(address, str) and address == content_hash(body)

    values = (
        ("fixture-address", address_matches(fixture), True),
        ("evaluation-address", address_matches(evaluation), True),
        ("source-addresses", all(address_matches(item) for item in fixture.sources), True),
        ("record-addresses", all(address_matches(item) for item in fixture.records), True),
        ("execution-addresses", all(address_matches(item) for item in evaluation.executions), True),
        ("check-addresses", all(address_matches(item) for item in evaluation.checks), True),
        ("unique-record-ids", len({item.record_id for item in fixture.records}) == len(fixture.records), True),
    )
    checks = []
    for check_id, observed, required in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required}
        checks.append(ControlFrontierIntegrityCheck(**body, content_address=content_hash(body)))
    return ControlFrontierIntegrityReport(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["ControlFrontierIntegrityCheck", "ControlFrontierIntegrityReport", "evaluate_control_frontier_integrity"]

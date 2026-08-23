"""Nested content-address checks for platform fixture receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .platform_frontier_contracts import PlatformFrontierEvaluation, PlatformFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class PlatformFrontierIntegrityCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class PlatformFrontierIntegrityReport:
    fixture_id: str
    checks: tuple[PlatformFrontierIntegrityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_platform_frontier_integrity(fixture: PlatformFrontierFixture, evaluation: PlatformFrontierEvaluation) -> PlatformFrontierIntegrityReport:
    def matches(value: Any) -> bool:
        body = jsonable(value)
        address = body.pop("content_address", None)
        return isinstance(address, str) and address == content_hash(body)

    values = (
        ("fixture-address", matches(fixture), True),
        ("evaluation-address", matches(evaluation), True),
        ("source-addresses", all(matches(item) for item in fixture.sources), True),
        ("record-addresses", all(matches(item) for item in fixture.records), True),
        ("execution-addresses", all(matches(item) for item in evaluation.executions), True),
        ("check-addresses", all(matches(item) for item in evaluation.checks), True),
        ("record-ids", len({item.record_id for item in fixture.records}), len(fixture.records)),
    )
    checks = []
    for check_id, observed, required in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required}
        checks.append(PlatformFrontierIntegrityCheck(**body, content_address=content_hash(body)))
    return PlatformFrontierIntegrityReport(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["PlatformFrontierIntegrityCheck", "PlatformFrontierIntegrityReport", "evaluate_platform_frontier_integrity"]

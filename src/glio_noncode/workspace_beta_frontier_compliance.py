"""Public-boundary and payload-scope checks for the beta frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable, require_non_empty
from .workspace_beta_frontier_fixture_eval import BetaFrontierEvaluation
from .workspace_beta_frontier_public_data import BetaFrontierFixture, BetaFrontierOperation


@dataclass(frozen=True, slots=True)
class BetaFrontierBoundaryCheck:
    check_id: str
    passed: bool
    severity: str
    observed: Any
    required: Any
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.severity, "severity")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class BetaFrontierBoundaryReport:
    fixture_id: str
    checks: tuple[BetaFrontierBoundaryCheck, ...]
    accepted: bool
    blocking_failures: tuple[str, ...]
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_count": self.passed_count}


def _check(index: int, passed: bool, severity: str, observed: Any, required: Any, detail: str) -> BetaFrontierBoundaryCheck:
    body = {"check_id": f"boundary-{index:03d}", "passed": passed, "severity": severity, "observed": observed, "required": required, "detail": detail}
    return BetaFrontierBoundaryCheck(**body, content_address=content_hash(body))


def _keys(value: Any) -> tuple[str, ...]:
    if isinstance(value, dict):
        result: list[str] = []
        for key, child in value.items():
            result.append(str(key))
            result.extend(_keys(child))
        return tuple(result)
    if isinstance(value, (list, tuple)):
        return tuple(key for child in value for key in _keys(child))
    return ()


def evaluate_beta_frontier_boundary(fixture: BetaFrontierFixture, evaluation: BetaFrontierEvaluation) -> BetaFrontierBoundaryReport:
    """Verify source, scope, context, and operation boundaries."""

    payload_keys = tuple(key.casefold() for record in fixture.records for key in _keys(record.payload))
    forbidden = ("patient_identifier", "direct_identifier", "medical_record", "contact_phone")
    checks = (
        _check(1, fixture.evidence_boundary == "public_aggregate_non_patient", "blocking", fixture.evidence_boundary, "public_aggregate_non_patient", "fixture boundary is public aggregate"),
        _check(2, len(fixture.sources) == 5, "blocking", len(fixture.sources), 5, "five source receipts are present"),
        _check(3, all(item.uri.startswith("https://") for item in fixture.sources), "blocking", True, True, "all source receipts use HTTPS"),
        _check(4, all(item.source_id for item in fixture.sources), "blocking", True, True, "source IDs are non-empty"),
        _check(5, all(item.context_key == fixture.context_key for item in fixture.records), "blocking", True, True, "fixture row contexts are exact"),
        _check(6, len({item.operation for item in fixture.records}) == 4, "blocking", len({item.operation for item in fixture.records}), 4, "all operation boundaries are present"),
        _check(7, all(item.operation in set(BetaFrontierOperation) for item in fixture.records), "blocking", True, True, "operations use the declared vocabulary"),
        _check(8, not any(key in payload_keys for key in forbidden), "blocking", tuple(key for key in forbidden if key in payload_keys), (), "payload does not contain direct identity keys"),
        _check(9, all(item.content_address.startswith("sha256:") for item in fixture.records), "blocking", True, True, "fixture records are addressed"),
        _check(10, all(item.content_address.startswith("sha256:") for item in evaluation.executions), "blocking", True, True, "execution records are addressed"),
        _check(11, all(item.role.value in {"positive", "control"} for item in fixture.records), "blocking", True, True, "roles use the declared vocabulary"),
        _check(12, sum(item.role.value == "positive" for item in fixture.records) == 4, "blocking", 4, 4, "one positive path per operation"),
        _check(13, sum(item.role.value == "control" for item in fixture.records) == 12, "blocking", 12, 12, "three controls per operation"),
        _check(14, all(item.output for item in evaluation.executions), "advisory", True, True, "every execution has a serializable result"),
        _check(15, all(item.issue_codes or item.role.value == "positive" for item in evaluation.executions), "advisory", True, True, "control issues remain visible"),
    )
    blocking = tuple(item.check_id for item in checks if not item.passed and item.severity == "blocking")
    body = {"fixture_id": fixture.fixture_id, "checks": checks, "accepted": not blocking, "blocking_failures": blocking}
    return BetaFrontierBoundaryReport(**body, content_address=content_hash(body))


__all__ = ["BetaFrontierBoundaryCheck", "BetaFrontierBoundaryReport", "evaluate_beta_frontier_boundary"]

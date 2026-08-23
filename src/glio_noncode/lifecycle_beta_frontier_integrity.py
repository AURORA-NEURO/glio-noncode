"""Content-address and identity integrity checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierEvaluation, LifecycleBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierIntegrityCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierIntegrityReport:
    fixture_id: str
    checks: tuple[LifecycleBetaFrontierIntegrityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_lifecycle_beta_frontier_integrity(fixture: LifecycleBetaFrontierFixture, evaluation: LifecycleBetaFrontierEvaluation) -> LifecycleBetaFrontierIntegrityReport:
    rows = (
        ("fixture-address", fixture.content_address.startswith("sha256:"), fixture.content_address, "sha256:", "fixture is addressed"),
        ("source-addresses", all(item.content_address.startswith("sha256:") for item in fixture.sources), True, True, "source receipts are addressed"),
        ("record-addresses", all(item.content_address.startswith("sha256:") for item in fixture.records), True, True, "record receipts are addressed"),
        ("execution-addresses", all(item.content_address.startswith("sha256:") for item in evaluation.executions), True, True, "execution receipts are addressed"),
        ("unique-execution-addresses", len({item.content_address for item in evaluation.executions}) == len(evaluation.executions), True, True, "execution receipts are unique"),
        ("unique-record-ids", len({item.record_id for item in fixture.records}) == len(fixture.records), len({item.record_id for item in fixture.records}), len(fixture.records), "record IDs are unique"),
    )
    checks = []
    for check_id, passed, observed, required, detail in rows:
        body = {"check_id": check_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
        checks.append(LifecycleBetaFrontierIntegrityCheck(**body, content_address=content_hash(body)))
    return LifecycleBetaFrontierIntegrityReport(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash({"checks": tuple(checks)}))


__all__ = ["LifecycleBetaFrontierIntegrityCheck", "LifecycleBetaFrontierIntegrityReport", "evaluate_lifecycle_beta_frontier_integrity"]

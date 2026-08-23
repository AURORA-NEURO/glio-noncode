"""Compliance-style checks for scope, retention, and review boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .lifecycle_beta_frontier_contracts import LifecycleBetaFrontierFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierComplianceCheck:
    check_id: str
    control_family: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class LifecycleBetaFrontierComplianceReport:
    fixture_id: str
    checks: tuple[LifecycleBetaFrontierComplianceCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def evaluate_lifecycle_beta_frontier_compliance(fixture: LifecycleBetaFrontierFixture) -> LifecycleBetaFrontierComplianceReport:
    rows = (
        ("scope", "public_boundary", fixture.evidence_boundary, "public_aggregate_non_patient", "fixture scope is non-patient"),
        ("transport", "https_receipts", all(item.uri.startswith("https://") for item in fixture.sources), True, "source receipts use HTTPS"),
        ("retention", "content_addresses", all(item.content_address.startswith("sha256:") for item in fixture.sources), True, "source receipts are immutable"),
        ("controls", "negative_controls", len(fixture.control_records), 24, "controls are retained"),
        ("context", "exact_context", all(item.context_key == fixture.context_key for item in fixture.records), True, "records share the declared context"),
    )
    checks = []
    for check_id, family, observed, required, detail in rows:
        body = {"check_id": check_id, "control_family": family, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(LifecycleBetaFrontierComplianceCheck(**body, content_address=content_hash(body)))
    return LifecycleBetaFrontierComplianceReport(fixture.fixture_id, tuple(checks), all(item.passed for item in checks), content_hash({"checks": tuple(checks)}))


__all__ = ["LifecycleBetaFrontierComplianceCheck", "LifecycleBetaFrontierComplianceReport", "evaluate_lifecycle_beta_frontier_compliance"]

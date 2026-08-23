"""Blocking quality gate over data, evaluation, adapters, schema, and policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_adapters import ValidationReleaseAdapterRegistry
from .validation_release_frontier_contracts import ValidationReleaseEvaluation
from .validation_release_frontier_public_data import ValidationReleaseDataAudit
from .validation_release_frontier_reconciliation import ValidationReleaseReconciliation
from .validation_release_frontier_schema import ValidationReleaseSchema


@dataclass(frozen=True, slots=True)
class ValidationReleaseQualityCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationReleaseQualityReport:
    checks: tuple[ValidationReleaseQualityCheck, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_validation_release_quality_gate(audit: ValidationReleaseDataAudit, evaluation: ValidationReleaseEvaluation, adapters: ValidationReleaseAdapterRegistry, schema: ValidationReleaseSchema, reconciliation: ValidationReleaseReconciliation) -> ValidationReleaseQualityReport:
    values = (("data-audit", audit.accepted, True, "public data audit passes"), ("evaluation", evaluation.accepted, True, "all row checks pass"), ("record-floor", len(evaluation.executions), 16, "fixture has the declared record floor"), ("check-floor", len(evaluation.checks), 80, "five checks cover every row"), ("adapter-floor", len(adapters.adapters), 4, "four operation adapters are registered"), ("schema-address", schema.content_address.startswith("sha256:"), True, "schema is addressed"), ("reconciliation", reconciliation.accepted, True, "expected and observed states reconcile"), ("address-closure", all(item.content_address.startswith("sha256:") for item in evaluation.executions), True, "execution outputs are addressed"))
    checks = []
    for check_id, observed, required, detail in values:
        body = {"check_id": check_id, "passed": observed == required, "observed": observed, "required": required, "detail": detail}
        checks.append(ValidationReleaseQualityCheck(**body, content_address=content_hash(body)))
    return ValidationReleaseQualityReport(tuple(checks), all(item.passed for item in checks), content_hash(tuple(checks)))


__all__ = ["ValidationReleaseQualityCheck", "ValidationReleaseQualityReport", "run_validation_release_quality_gate"]

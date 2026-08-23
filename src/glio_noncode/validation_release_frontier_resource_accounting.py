"""Resource accounting for local evaluation and export."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation


@dataclass(frozen=True, slots=True)
class ValidationReleaseResourceReport:
    rows: int
    checks: int
    estimated_output_units: int
    bounded: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def account_validation_release_resources(evaluation: ValidationReleaseEvaluation) -> ValidationReleaseResourceReport:
    output_units = sum(len(str(item.output)) for item in evaluation.executions) + sum(len(str(item.observed)) for item in evaluation.checks)
    body = {"rows": len(evaluation.executions), "checks": len(evaluation.checks), "estimated_output_units": output_units, "bounded": output_units < 100000}
    return ValidationReleaseResourceReport(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseResourceReport", "account_validation_release_resources"]

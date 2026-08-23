"""Input and output schema checks for validation-release operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseOperation
from .validation_release_frontier_support import mapping, sequence


@dataclass(frozen=True, slots=True)
class ValidationReleaseSchema:
    version: str
    required_fields: Mapping[str, tuple[str, ...]]
    output_fields: Mapping[str, tuple[str, ...]]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_validation_release_frontier_schema() -> ValidationReleaseSchema:
    required = {ValidationReleaseOperation.OFF_TARGET_RISK.value: ("target_id", "context_key", "on_target_score", "off_targets"), ValidationReleaseOperation.VALUE_OF_INFORMATION.value: ("plan_id", "context_key", "budget", "experiments"), ValidationReleaseOperation.EXPERIMENT_PACKAGE.value: ("package_id", "context_key", "experiments", "controls", "protocols"), ValidationReleaseOperation.CLAIM_UPDATE.value: ("context_key", "claims", "results")}
    outputs = {item.value: ("state", "issue_codes", "content_address") for item in ValidationReleaseOperation}
    body = {"version": "validation-release-schema-v1", "required_fields": required, "output_fields": outputs}
    return ValidationReleaseSchema(**body, content_address=content_hash(body))


def validate_validation_release_schema(payload: Mapping[str, Any], operation: ValidationReleaseOperation, schema: ValidationReleaseSchema | None = None) -> tuple[str, ...]:
    schema = schema or default_validation_release_frontier_schema()
    errors = [f"missing:{field}" for field in schema.required_fields[operation.value] if field not in payload]
    try:
        if operation in (ValidationReleaseOperation.OFF_TARGET_RISK, ValidationReleaseOperation.VALUE_OF_INFORMATION, ValidationReleaseOperation.EXPERIMENT_PACKAGE, ValidationReleaseOperation.CLAIM_UPDATE):
            if not isinstance(payload.get("context_key"), str):
                errors.append("context_key:not_text")
        if operation == ValidationReleaseOperation.OFF_TARGET_RISK and "off_targets" in payload:
            sequence(payload["off_targets"], "off_targets")
        if operation == ValidationReleaseOperation.VALUE_OF_INFORMATION and "experiments" in payload:
            sequence(payload["experiments"], "experiments")
        if operation == ValidationReleaseOperation.EXPERIMENT_PACKAGE:
            for field in ("experiments", "controls", "protocols"):
                if field in payload:
                    sequence(payload[field], field)
        if operation == ValidationReleaseOperation.CLAIM_UPDATE:
            for field in ("claims", "results"):
                if field in payload:
                    sequence(payload[field], field)
    except ValueError as exc:
        errors.append(f"shape:{exc}")
    return tuple(errors)


__all__ = ["ValidationReleaseSchema", "default_validation_release_frontier_schema", "validate_validation_release_schema"]

"""Input and output schema receipts for the four planning operations."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from .serialization import content_hash, jsonable
from .validation_design_frontier_contracts import ValidationDesignOperation
from .validation_design_frontier_support import mapping, sequence

@dataclass(frozen=True, slots=True)
class ValidationDesignSchema:
    version: str
    required_fields: Mapping[str, tuple[str, ...]]
    output_fields: Mapping[str, tuple[str, ...]]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def default_validation_design_frontier_schema() -> ValidationDesignSchema:
    required = {
        ValidationDesignOperation.GAP_ANALYSIS.value: ("target_id", "context_key", "required_evidence", "available_evidence"),
        ValidationDesignOperation.ASSAY_ELIGIBILITY.value: ("target_id", "context_key", "requested_assay", "capabilities"),
        ValidationDesignOperation.MPRA_PACKAGE.value: ("package_id", "context_key", "construct_budget", "constructs", "controls"),
        ValidationDesignOperation.STARRSEQ_PACKAGE.value: ("package_id", "context_key", "construct_budget", "constructs", "controls"),
    }
    output = {item.value: ("operation", "state", "issue_codes", "output", "content_address") for item in ValidationDesignOperation}
    body = {"version": "validation-design-schema-v1", "required_fields": required, "output_fields": output}
    return ValidationDesignSchema(**body, content_address=content_hash(body))

def validate_validation_design_schema(payload: Mapping[str, Any], operation: ValidationDesignOperation, schema: ValidationDesignSchema | None = None) -> tuple[str, ...]:
    schema = schema or default_validation_design_frontier_schema()
    errors = [f"missing:{field}" for field in schema.required_fields[operation.value] if field not in payload]
    if "context_key" in payload and not isinstance(payload.get("context_key"), str): errors.append("context_key:not_text")
    try:
        if operation == ValidationDesignOperation.GAP_ANALYSIS:
            if "required_evidence" in payload: sequence(payload["required_evidence"], "required_evidence")
            if "available_evidence" in payload: sequence(payload["available_evidence"], "available_evidence")
        elif operation == ValidationDesignOperation.ASSAY_ELIGIBILITY:
            if "capabilities" in payload: sequence(payload["capabilities"], "capabilities")
        else:
            if "constructs" in payload: sequence(payload["constructs"], "constructs")
            if "controls" in payload: sequence(payload["controls"], "controls")
    except ValueError as exc:
        errors.append(f"shape:{exc}")
    return tuple(errors)

__all__ = ["ValidationDesignSchema", "default_validation_design_frontier_schema", "validate_validation_design_schema"]

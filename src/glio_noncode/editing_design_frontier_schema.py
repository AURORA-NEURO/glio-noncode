"""Typed field schema for the four editing-design operations."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from .serialization import content_hash, jsonable
from .editing_design_frontier_contracts import EditingDesignOperation
from .editing_design_frontier_support import mapping, sequence

@dataclass(frozen=True, slots=True)
class EditingDesignSchema:
    version: str
    required_fields: Mapping[str, tuple[str, ...]]
    output_fields: Mapping[str, tuple[str, ...]]
    content_address: str
    def to_dict(self) -> dict[str, Any]: return jsonable(self)

def default_editing_design_frontier_schema() -> EditingDesignSchema:
    required = {EditingDesignOperation.CRISPR_DESIGN.value: ("design_id", "context_key", "targets", "modes", "guide_length", "max_guides", "controls", "readouts"), EditingDesignOperation.BASE_EDITING.value: ("design_id", "context_key", "targets", "editing_window", "controls", "readouts"), EditingDesignOperation.PRIME_EDITING.value: ("design_id", "context_key", "targets", "pbs_length", "rtt_length", "flank_length", "max_edit_length", "controls", "readouts"), EditingDesignOperation.ALLELE_REPORTER.value: ("design_id", "context_key", "constructs", "max_constructs", "controls", "readouts")}
    output = {item.value: ("operation", "state", "issue_codes", "output", "content_address") for item in EditingDesignOperation}
    body = {"version": "editing-design-schema-v1", "required_fields": required, "output_fields": output}
    return EditingDesignSchema(**body, content_address=content_hash(body))

def validate_editing_design_schema(payload: Mapping[str, Any], operation: EditingDesignOperation, schema: EditingDesignSchema | None = None) -> tuple[str, ...]:
    schema = schema or default_editing_design_frontier_schema(); errors = [f"missing:{field}" for field in schema.required_fields[operation.value] if field not in payload]
    if "context_key" in payload and not isinstance(payload.get("context_key"), str): errors.append("context_key:not_text")
    try:
        if operation == EditingDesignOperation.CRISPR_DESIGN:
            if "targets" in payload: sequence(payload["targets"], "targets")
            if "modes" in payload: sequence(payload["modes"], "modes")
        elif operation == EditingDesignOperation.ALLELE_REPORTER:
            if "constructs" in payload: sequence(payload["constructs"], "constructs")
        else:
            if "targets" in payload: sequence(payload["targets"], "targets")
            if operation == EditingDesignOperation.BASE_EDITING and "editing_window" in payload: sequence(payload["editing_window"], "editing_window")
    except ValueError as exc: errors.append(f"shape:{exc}")
    return tuple(errors)

__all__ = ["EditingDesignSchema", "default_editing_design_frontier_schema", "validate_editing_design_schema"]

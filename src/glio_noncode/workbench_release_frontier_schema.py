"""Schema receipts for the four workbench-release operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable
from .workbench_release_frontier_contracts import WorkbenchReleaseOperation
from .workbench_release_frontier_support import mapping, sequence


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseSchema:
    version: str
    required_fields: Mapping[str, tuple[str, ...]]
    output_fields: Mapping[str, tuple[str, ...]]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_workbench_release_frontier_schema() -> WorkbenchReleaseSchema:
    required = {WorkbenchReleaseOperation.REVIEW_FORM.value: ("form_id", "reviewer_id", "context_key", "schema", "response"), WorkbenchReleaseOperation.REPORT_EXPORT.value: ("report_id", "context_key", "format", "sections"), WorkbenchReleaseOperation.SEARCH_PALETTE.value: ("query", "context_key", "records", "commands"), WorkbenchReleaseOperation.ACCESSIBILITY.value: ("surface_id", "context_key", "surface", "required_criteria")}
    output = {operation.value: ("operation", "state", "issue_codes", "content_address") for operation in WorkbenchReleaseOperation}
    body = {"version": "workbench-release-schema-v1", "required_fields": required, "output_fields": output}
    return WorkbenchReleaseSchema(**body, content_address=content_hash(body))


def validate_workbench_release_schema(payload: Mapping[str, Any], operation: WorkbenchReleaseOperation, schema: WorkbenchReleaseSchema | None = None) -> tuple[str, ...]:
    schema = schema or default_workbench_release_frontier_schema()
    errors = [f"missing:{field}" for field in schema.required_fields[operation.value] if field not in payload]
    try:
        if "context_key" in payload and not isinstance(payload.get("context_key"), str):
            errors.append("context_key:not_text")
        if operation == WorkbenchReleaseOperation.REVIEW_FORM:
            if "schema" in payload:
                sequence(payload["schema"], "schema")
            if "response" in payload:
                mapping(payload["response"], "response")
        elif operation == WorkbenchReleaseOperation.REPORT_EXPORT and "sections" in payload:
            sequence(payload["sections"], "sections")
        elif operation == WorkbenchReleaseOperation.SEARCH_PALETTE:
            if "records" in payload:
                sequence(payload["records"], "records")
            if "commands" in payload:
                sequence(payload["commands"], "commands")
        elif operation == WorkbenchReleaseOperation.ACCESSIBILITY:
            if "surface" in payload:
                mapping(payload["surface"], "surface")
            if "required_criteria" in payload:
                sequence(payload["required_criteria"], "required_criteria")
    except ValueError as exc:
        errors.append(f"shape:{exc}")
    return tuple(errors)


__all__ = ["WorkbenchReleaseSchema", "default_workbench_release_frontier_schema", "validate_workbench_release_schema"]

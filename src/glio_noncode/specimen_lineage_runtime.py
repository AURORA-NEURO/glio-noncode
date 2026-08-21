"""Four-stage runtime for the Domain 03 C09-C12 specimen context surface."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_lineage import (
    LineageAlphaState,
    LongitudinalSpecimenLinker,
    MultiRegionLineageResolver,
    PrimaryRecurrencePhaseMapper,
    TreatmentExposureContextualizer,
)
from .specimen_lineage_public_data import SpecimenLineageOperation


class SpecimenLineagePipelineState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class SpecimenLineagePipelineRequest:
    """Runtime request containing one aggregate payload per operation."""

    pipeline_id: str
    context_key: str
    source_ids: tuple[str, ...]
    operation_payloads: Mapping[str, Mapping[str, Any]]
    parameters: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.pipeline_id, "lineage pipeline ID")
        require_non_empty(self.context_key, "lineage pipeline context")
        if not self.source_ids:
            raise ValidationError("lineage pipeline source IDs must not be empty")
        expected = {operation.value for operation in SpecimenLineageOperation}
        if set(self.operation_payloads) != expected:
            raise ValidationError("lineage pipeline must provide all four operation payloads")
        for operation, payload in self.operation_payloads.items():
            if not isinstance(payload, Mapping) or not payload:
                raise ValidationError(f"lineage pipeline {operation} payload must be non-empty")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SpecimenLineagePipelineRequest:
        operations = raw.get("operations", {})
        if not isinstance(operations, Mapping):
            raise ValidationError("lineage pipeline operations must be an object")
        payloads: dict[str, Mapping[str, Any]] = {}
        for operation in SpecimenLineageOperation:
            value = operations.get(operation.value, raw.get(operation.value, {}))
            if not isinstance(value, Mapping):
                raise ValidationError(f"lineage pipeline {operation.value} must be an object")
            payloads[operation.value] = dict(value)
        parameters = raw.get("parameters", {})
        if not isinstance(parameters, Mapping):
            raise ValidationError("lineage pipeline parameters must be an object")
        return cls(
            pipeline_id=str(raw.get("pipeline_id", "")),
            context_key=str(raw.get("context_key", "")),
            source_ids=tuple(sorted(str(item) for item in raw.get("source_ids", ()) if str(item))),
            operation_payloads=payloads,
            parameters={
                str(name): dict(value)
                for name, value in parameters.items()
                if isinstance(value, Mapping)
            },
        )


@dataclass(frozen=True, slots=True)
class SpecimenLineageStageReceipt:
    """One operation stage with conserved accepted/review/blocked counts."""

    stage: SpecimenLineageOperation
    state: SpecimenLineagePipelineState
    input_count: int
    accepted_count: int
    review_count: int
    blocked_count: int
    issue_codes: tuple[str, ...]
    result_address: str
    content_address: str

    def __post_init__(self) -> None:
        if min(self.input_count, self.accepted_count, self.review_count, self.blocked_count) < 0:
            raise ValidationError("lineage stage counts must not be negative")
        if self.accepted_count + self.review_count + self.blocked_count != self.input_count:
            raise ValidationError("lineage stage counts must be conserved")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenLineagePipelineReport:
    """Final four-stage runtime manifest."""

    pipeline_id: str
    context_key: str
    state: SpecimenLineagePipelineState
    published: bool
    stage_receipts: tuple[SpecimenLineageStageReceipt, ...]
    manifest: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_specimen_lineage_pipeline(
    request: SpecimenLineagePipelineRequest,
) -> SpecimenLineagePipelineReport:
    """Run four stages in order and publish only a sanitized manifest."""

    stage_receipts: list[SpecimenLineageStageReceipt] = []
    manifest_stages: list[dict[str, Any]] = []
    blocked = False
    review = False
    for operation in SpecimenLineageOperation:
        payload = request.operation_payloads[operation.value]
        parameters = dict(request.parameters.get(operation.value, {}))
        try:
            result, input_count, summary = _run_stage(
                operation, payload, request.context_key, parameters
            )
            result_state = result.state
            issue_codes = tuple(sorted(issue.code for issue in result.issues))
            stage_state = (
                SpecimenLineagePipelineState.ACCEPTED
                if result_state == LineageAlphaState.SUPPORTED
                else SpecimenLineagePipelineState.REVIEW
            )
            accepted_count = (
                input_count if stage_state == SpecimenLineagePipelineState.ACCEPTED else 0
            )
            review_count = input_count if stage_state == SpecimenLineagePipelineState.REVIEW else 0
            blocked_count = 0
            result_payload = {
                "operation": operation.value,
                "state": result_state.value,
                "counts": summary,
                "issue_codes": issue_codes,
            }
        except (TypeError, ValueError, ValidationError) as exc:
            input_count = _payload_count(operation, payload)
            stage_state = SpecimenLineagePipelineState.BLOCKED
            accepted_count = 0
            review_count = 0
            blocked_count = input_count
            issue_codes = ("stage_error",)
            result_payload = {
                "operation": operation.value,
                "state": "blocked",
                "counts": {"input": input_count},
                "issue_codes": issue_codes,
                "error_type": type(exc).__name__,
            }
        if stage_state == SpecimenLineagePipelineState.BLOCKED:
            blocked = True
        elif stage_state == SpecimenLineagePipelineState.REVIEW:
            review = True
        result_address = content_hash(result_payload)
        stage_body = {
            "stage": operation,
            "state": stage_state,
            "input_count": input_count,
            "accepted_count": accepted_count,
            "review_count": review_count,
            "blocked_count": blocked_count,
            "issue_codes": issue_codes,
            "result_address": result_address,
        }
        stage_receipts.append(
            SpecimenLineageStageReceipt(
                stage=operation,
                state=stage_state,
                input_count=input_count,
                accepted_count=accepted_count,
                review_count=review_count,
                blocked_count=blocked_count,
                issue_codes=issue_codes,
                result_address=result_address,
                content_address=content_hash(stage_body),
            )
        )
        manifest_stages.append(
            {
                "stage": operation.value,
                "state": stage_state.value,
                "input_count": input_count,
                "accepted_count": accepted_count,
                "review_count": review_count,
                "blocked_count": blocked_count,
                "issue_codes": issue_codes,
                "result_address": result_address,
            }
        )
    state = (
        SpecimenLineagePipelineState.BLOCKED
        if blocked
        else SpecimenLineagePipelineState.REVIEW
        if review
        else SpecimenLineagePipelineState.ACCEPTED
    )
    published = state == SpecimenLineagePipelineState.ACCEPTED
    manifest = {
        "pipeline_id": request.pipeline_id,
        "context_key": request.context_key,
        "source_ids": request.source_ids,
        "state": state.value,
        "published": published,
        "stages": tuple(manifest_stages),
    }
    return SpecimenLineagePipelineReport(
        pipeline_id=request.pipeline_id,
        context_key=request.context_key,
        state=state,
        published=published,
        stage_receipts=tuple(stage_receipts),
        manifest=manifest,
        content_address=content_hash(manifest),
    )


def _run_stage(
    operation: SpecimenLineageOperation,
    payload: Mapping[str, Any],
    context_key: str,
    parameters: Mapping[str, Any],
) -> tuple[Any, int, Mapping[str, int]]:
    if operation == SpecimenLineageOperation.REGION_LINEAGE:
        rows = _rows(payload, "records", "regions", "observations")
        result = MultiRegionLineageResolver().resolve(rows, context_key=context_key)
        summary = {
            "lineages": len(result.lineages),
            "edges": sum(len(item.edges) for item in result.lineages),
            "issues": len(result.issues),
        }
        return result, max(len(result.lineages), 1 if rows else 0), summary
    if operation == SpecimenLineageOperation.LONGITUDINAL_LINKING:
        rows = _rows(payload, "records", "specimens", "observations")
        result = LongitudinalSpecimenLinker().link(
            rows,
            context_key=context_key,
            link_singleton=bool(parameters.get("link_singleton", False)),
        )
        summary = {
            "observations": len(result.observations),
            "links": len(result.links),
            "issues": len(result.issues),
        }
        return result, max(len(result.observations), 1 if rows else 0), summary
    if operation == SpecimenLineageOperation.PHASE_MAPPING:
        rows = _rows(payload, "records", "specimens", "observations")
        result = PrimaryRecurrencePhaseMapper().map(rows, context_key=context_key)
        summary = {
            "assignments": len(result.assignments),
            "unknown": len(result.unknown_specimen_ids),
            "issues": len(result.issues),
        }
        return result, max(len(result.assignments), 1 if rows else 0), summary
    if operation == SpecimenLineageOperation.TREATMENT_CONTEXT:
        specimens = _rows(payload, "specimens", "records", "observations")
        exposures = _rows(payload, "exposures")
        result = TreatmentExposureContextualizer().contextualize(
            specimens, exposures, context_key=context_key
        )
        summary = {
            "specimens": len(result.specimens),
            "contexts": len(result.contexts),
            "issues": len(result.issues),
        }
        return result, max(len(result.specimens), 1 if specimens else 0), summary
    raise ValidationError(f"unsupported lineage pipeline operation: {operation}")


def _rows(payload: Mapping[str, Any], *keys: str) -> Sequence[Mapping[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (list, tuple)):
            return value
    raise ValidationError(f"pipeline payload requires one of {keys}")


def _payload_count(operation: SpecimenLineageOperation, payload: Mapping[str, Any]) -> int:
    keys = (
        ("specimens", "records", "observations", "regions")
        if operation != SpecimenLineageOperation.TREATMENT_CONTEXT
        else ("specimens", "records", "observations")
    )
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return max(len(value), 1)
    return 1


def specimen_lineage_pipeline_request_from_file(path: str | Path) -> SpecimenLineagePipelineRequest:
    """Load a runtime request from JSON."""

    source = Path(path)
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid lineage pipeline request: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ValidationError("lineage pipeline request root must be an object")
    return SpecimenLineagePipelineRequest.from_mapping(raw)


__all__ = [
    "SpecimenLineagePipelineReport",
    "SpecimenLineagePipelineRequest",
    "SpecimenLineagePipelineState",
    "SpecimenLineageStageReceipt",
    "run_specimen_lineage_pipeline",
    "specimen_lineage_pipeline_request_from_file",
]

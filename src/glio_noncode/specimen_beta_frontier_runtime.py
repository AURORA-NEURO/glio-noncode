"""Four-stage runtime for the specimen beta frontier."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_beta import (
    CancerCellFractionEstimator,
    MosaicismPosteriorEstimator,
    SomaticGermlineOriginClassifier,
    SpecimenBetaState,
    SubcloneAssigner,
)
from .specimen_beta_frontier_public_data import SpecimenBetaFrontierOperation


class SpecimenBetaFrontierPipelineState(StrEnum):
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierPipelineRequest:
    """Runtime request containing one aggregate payload per operation."""

    pipeline_id: str
    context_key: str
    source_ids: tuple[str, ...]
    operation_payloads: Mapping[str, Mapping[str, Any]]
    parameters: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.pipeline_id, "beta pipeline ID")
        require_non_empty(self.context_key, "beta pipeline context")
        if not self.source_ids:
            raise ValidationError("beta pipeline source IDs must not be empty")
        expected = {operation.value for operation in SpecimenBetaFrontierOperation}
        if set(self.operation_payloads) != expected:
            raise ValidationError("beta pipeline must provide all four operation payloads")
        for operation, payload in self.operation_payloads.items():
            if not payload:
                raise ValidationError(f"beta pipeline {operation} payload must not be empty")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SpecimenBetaFrontierPipelineRequest:
        operations = raw.get("operations", {})
        if not isinstance(operations, Mapping):
            raise ValidationError("beta pipeline operations must be an object")
        payloads: dict[str, Mapping[str, Any]] = {}
        for operation in SpecimenBetaFrontierOperation:
            value = operations.get(operation.value, raw.get(operation.value, {}))
            if not isinstance(value, Mapping):
                raise ValidationError(f"beta pipeline {operation.value} must be an object")
            payloads[operation.value] = dict(value)
        parameters = raw.get("parameters", {})
        if not isinstance(parameters, Mapping):
            raise ValidationError("beta pipeline parameters must be an object")
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
class SpecimenBetaFrontierStageReceipt:
    """One operation stage receipt with conserved counts."""

    stage: SpecimenBetaFrontierOperation
    state: SpecimenBetaFrontierPipelineState
    input_count: int
    accepted_count: int
    review_count: int
    blocked_count: int
    issue_codes: tuple[str, ...]
    result_address: str
    content_address: str

    def __post_init__(self) -> None:
        if min(self.input_count, self.accepted_count, self.review_count, self.blocked_count) < 0:
            raise ValidationError("beta stage counts must not be negative")
        if self.accepted_count + self.review_count + self.blocked_count != self.input_count:
            raise ValidationError("beta stage counts must be conserved")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierPipelineReport:
    """Final four-stage runtime report."""

    pipeline_id: str
    context_key: str
    state: SpecimenBetaFrontierPipelineState
    published: bool
    stage_receipts: tuple[SpecimenBetaFrontierStageReceipt, ...]
    manifest: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def run_specimen_beta_frontier_pipeline(
    request: SpecimenBetaFrontierPipelineRequest,
) -> SpecimenBetaFrontierPipelineReport:
    """Run origin, mosaicism, CCF, and subclone stages in fixed order."""

    receipts: list[SpecimenBetaFrontierStageReceipt] = []
    manifest_stages: list[dict[str, Any]] = []
    for operation in SpecimenBetaFrontierOperation:
        payload = request.operation_payloads[operation.value]
        parameters = dict(request.parameters.get(operation.value, {}))
        raw_records = payload.get("records", ())
        if not isinstance(raw_records, Sequence) or isinstance(raw_records, (str, bytes)):
            raise ValidationError(f"beta pipeline {operation.value} records must be a sequence")
        result_state, item_states, issue_codes, result_address = _run_stage(
            operation,
            tuple(raw_records),
            parameters,
        )
        input_count = len(item_states) or (1 if raw_records else 0)
        accepted_count = sum(state == SpecimenBetaState.SUPPORTED for state in item_states)
        blocked_count = (
            1 if result_state in {SpecimenBetaState.INVALID, SpecimenBetaState.OUT_OF_DOMAIN} else 0
        )
        review_count = input_count - accepted_count - blocked_count
        if input_count == 0:
            review_count = 0
        stage_state = (
            SpecimenBetaFrontierPipelineState.BLOCKED
            if blocked_count
            else SpecimenBetaFrontierPipelineState.REVIEW
            if review_count
            else SpecimenBetaFrontierPipelineState.ACCEPTED
        )
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
        receipt = SpecimenBetaFrontierStageReceipt(
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
        receipts.append(receipt)
        manifest_stages.append(
            {
                "stage": operation.value,
                "state": stage_state.value,
                "accepted_count": accepted_count,
                "review_count": review_count,
                "blocked_count": blocked_count,
                "issue_codes": issue_codes,
                "content_address": receipt.content_address,
            }
        )
        if stage_state == SpecimenBetaFrontierPipelineState.BLOCKED:
            break
    state = (
        SpecimenBetaFrontierPipelineState.BLOCKED
        if any(receipt.state == SpecimenBetaFrontierPipelineState.BLOCKED for receipt in receipts)
        else SpecimenBetaFrontierPipelineState.REVIEW
        if any(receipt.state == SpecimenBetaFrontierPipelineState.REVIEW for receipt in receipts)
        else SpecimenBetaFrontierPipelineState.ACCEPTED
    )
    manifest = {
        "pipeline_id": request.pipeline_id,
        "context_key": request.context_key,
        "source_ids": request.source_ids,
        "state": state.value,
        "stages": tuple(manifest_stages),
    }
    body = {
        "pipeline_id": request.pipeline_id,
        "context_key": request.context_key,
        "state": state,
        "published": state == SpecimenBetaFrontierPipelineState.ACCEPTED,
        "stage_receipts": receipts,
        "manifest": manifest,
    }
    return SpecimenBetaFrontierPipelineReport(
        pipeline_id=request.pipeline_id,
        context_key=request.context_key,
        state=state,
        published=state == SpecimenBetaFrontierPipelineState.ACCEPTED,
        stage_receipts=tuple(receipts),
        manifest=manifest,
        content_address=content_hash(body),
    )


def _run_stage(
    operation: SpecimenBetaFrontierOperation,
    records: tuple[Mapping[str, Any], ...],
    parameters: Mapping[str, Any],
) -> tuple[SpecimenBetaState, tuple[SpecimenBetaState, ...], tuple[str, ...], str]:
    if operation == SpecimenBetaFrontierOperation.ORIGIN:
        result = SomaticGermlineOriginClassifier().classify(records, **parameters)
        states = tuple(item.state for item in result.classifications)
        address = content_hash(
            {
                "operation": operation,
                "states": states,
                "issues": tuple(issue.code for issue in result.issues),
            }
        )
        return result.state, states, tuple(sorted(issue.code for issue in result.issues)), address
    if operation == SpecimenBetaFrontierOperation.MOSAICISM:
        result = MosaicismPosteriorEstimator().estimate(records, **parameters)
        states = tuple(item.state for item in result.estimates)
        address = content_hash(
            {
                "operation": operation,
                "states": states,
                "issues": tuple(issue.code for issue in result.issues),
            }
        )
        return result.state, states, tuple(sorted(issue.code for issue in result.issues)), address
    if operation == SpecimenBetaFrontierOperation.CANCER_CELL_FRACTION:
        result = CancerCellFractionEstimator().estimate(records, **parameters)
        states = tuple(item.state for item in result.estimates)
        address = content_hash(
            {
                "operation": operation,
                "states": states,
                "issues": tuple(issue.code for issue in result.issues),
            }
        )
        return result.state, states, tuple(sorted(issue.code for issue in result.issues)), address
    result = SubcloneAssigner().assign(records, **parameters)
    states = tuple(item.assignment_state for item in result.assignments)
    address = content_hash(
        {
            "operation": operation,
            "states": states,
            "issues": tuple(issue.code for issue in result.issues),
        }
    )
    return result.state, states, tuple(sorted(issue.code for issue in result.issues)), address


def specimen_beta_frontier_pipeline_request_from_file(
    path: str,
) -> SpecimenBetaFrontierPipelineRequest:
    """Read a runtime request from JSON."""

    from pathlib import Path

    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid beta pipeline request: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise ValidationError("beta pipeline request root must be an object")
    return SpecimenBetaFrontierPipelineRequest.from_mapping(raw)


__all__ = [
    "SpecimenBetaFrontierPipelineReport",
    "SpecimenBetaFrontierPipelineRequest",
    "SpecimenBetaFrontierPipelineState",
    "SpecimenBetaFrontierStageReceipt",
    "run_specimen_beta_frontier_pipeline",
    "specimen_beta_frontier_pipeline_request_from_file",
]

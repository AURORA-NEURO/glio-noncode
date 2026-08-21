"""Typed C01-C04 orchestration runtime for structural evidence batches."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .structural_fixture_eval import (
    StructuralExecution,
    _failed_execution,
    _run_complex,
    _run_consensus,
    _run_copy_number,
    _run_reconstruction,
)
from .structural_public_data import (
    StructuralFixtureRecord,
    StructuralFixtureState,
    StructuralOperation,
)


class StructuralPipelineState(StrEnum):
    """Aggregate state of the four-stage structural pipeline."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class StructuralPipelineRequest:
    """Validated input envelope for one C01-C04 batch."""

    request_id: str
    manifest_id: str
    context_key: str
    source_ids: tuple[str, ...]
    reconstruction: Mapping[str, Any]
    consensus: Mapping[str, Any]
    complex_resolution: Mapping[str, Any]
    copy_number: Mapping[str, Any]

    def __post_init__(self) -> None:
        for field_name in ("request_id", "manifest_id", "context_key"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("structural pipeline context key requires six fields")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("structural pipeline source IDs must be non-empty and unique")
        for operation, payload in self.operation_payloads.items():
            if not payload:
                raise ValidationError(f"structural pipeline {operation} payload must not be empty")

    @property
    def operation_payloads(self) -> dict[str, Mapping[str, Any]]:
        return {
            "reconstruction": self.reconstruction,
            "consensus": self.consensus,
            "complex_resolution": self.complex_resolution,
            "copy_number": self.copy_number,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> StructuralPipelineRequest:
        if not isinstance(raw, Mapping):
            raise ValidationError("structural pipeline request must be an object")
        source_ids_raw = raw.get("source_ids", ())
        if not isinstance(source_ids_raw, Sequence) or isinstance(source_ids_raw, (str, bytes)):
            raise ValidationError("structural pipeline source_ids must be an array")
        operations = raw.get("operations", {})
        if not isinstance(operations, Mapping):
            raise ValidationError("structural pipeline operations must be an object")
        payloads: dict[str, Mapping[str, Any]] = {}
        for name in ("reconstruction", "consensus", "complex_resolution", "copy_number"):
            value = operations.get(name, raw.get(name, {}))
            if not isinstance(value, Mapping):
                raise ValidationError(f"structural pipeline operation {name} must be an object")
            payloads[name] = dict(value)
        return cls(
            request_id=str(raw.get("request_id", "structural-pipeline-request")),
            manifest_id=str(raw.get("manifest_id", "structural-pipeline-manifest")),
            context_key=str(raw.get("context_key", "")),
            source_ids=tuple(str(item) for item in source_ids_raw),
            reconstruction=payloads["reconstruction"],
            consensus=payloads["consensus"],
            complex_resolution=payloads["complex_resolution"],
            copy_number=payloads["copy_number"],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralStageReceipt:
    """Sanitized stage accounting with no raw operation payload."""

    stage_id: str
    capability_id: str
    operation: StructuralOperation
    state: StructuralPipelineState
    input_count: int
    accepted_count: int
    review_count: int
    result_state: str
    issue_codes: tuple[str, ...]
    output_address: str
    detail: str

    def __post_init__(self) -> None:
        for field_name in ("stage_id", "capability_id", "result_state", "output_address", "detail"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if min(self.input_count, self.accepted_count, self.review_count) < 0:
            raise ValidationError("structural stage counts cannot be negative")
        if self.accepted_count + self.review_count != self.input_count:
            raise ValidationError("structural stage counts must sum to input count")
        if not self.output_address.startswith("sha256:"):
            raise ValidationError("structural stage output must be content-addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralPipelineReport:
    """Aggregate pipeline report containing a manifest receipt only."""

    request_id: str
    manifest_id: str
    context_key: str
    state: StructuralPipelineState
    stage_receipts: tuple[StructuralStageReceipt, ...]
    issues: tuple[str, ...]
    manifest: Mapping[str, Any] | None
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == StructuralPipelineState.ACCEPTED

    @property
    def published(self) -> bool:
        return self.manifest is not None and bool(self.manifest.get("content_address"))

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        result["published"] = self.published
        result["stage_count"] = len(self.stage_receipts)
        result["review_stage_count"] = sum(
            receipt.state != StructuralPipelineState.ACCEPTED for receipt in self.stage_receipts
        )
        return result


class StructuralPipeline:
    """Run C01-C04 in order and publish only a sanitized stage manifest."""

    def run(self, request: StructuralPipelineRequest) -> StructuralPipelineReport:
        executions = (
            self._run_stage(
                StructuralOperation.RECONSTRUCTION,
                request.reconstruction,
                request.context_key,
            ),
            self._run_stage(StructuralOperation.CONSENSUS, request.consensus, request.context_key),
            self._run_stage(
                StructuralOperation.COMPLEX_RESOLUTION,
                request.complex_resolution,
                request.context_key,
            ),
            self._run_stage(StructuralOperation.COPY_NUMBER, request.copy_number, request.context_key),
        )
        receipts = tuple(self._receipt(execution, request.operation_payloads[execution.operation.value]) for execution in executions)
        issues = tuple(sorted({code for execution in executions for code in execution.issue_codes}))
        all_accepted = all(execution.state == StructuralFixtureState.ACCEPTED for execution in executions)
        any_executed = any(execution.counts.get("records", execution.counts.get("observations", 0)) > 0 for execution in executions)
        state = (
            StructuralPipelineState.ACCEPTED
            if all_accepted
            else StructuralPipelineState.REVIEW
            if any_executed
            else StructuralPipelineState.BLOCKED
        )
        manifest = self._manifest(request, state, receipts) if any_executed else None
        body = {
            "request_id": request.request_id,
            "manifest_id": request.manifest_id,
            "context_key": request.context_key,
            "state": state,
            "stage_receipts": receipts,
            "issues": issues,
            "manifest": manifest,
        }
        return StructuralPipelineReport(
            request_id=request.request_id,
            manifest_id=request.manifest_id,
            context_key=request.context_key,
            state=state,
            stage_receipts=receipts,
            issues=issues,
            manifest=manifest,
            content_address=content_hash(body),
        )

    def _run_stage(
        self,
        operation: StructuralOperation,
        payload: Mapping[str, Any],
        context_key: str,
    ) -> StructuralExecution:
        record = StructuralFixtureRecord(
            record_id=f"pipeline:{operation.value}",
            operation=operation,
            expected_state=StructuralFixtureState.ACCEPTED,
            expected_result_state="pipeline",
            context_key=context_key,
            source_id=str(payload.get("source_id", "structural-pipeline-source")),
            payload=payload,
        )
        if operation == StructuralOperation.RECONSTRUCTION:
            try:
                return _run_reconstruction(record, context_key)
            except (TypeError, ValueError, ValidationError, KeyError):
                return _failed_execution(record, "validation_error", "structural reconstruction input failed validation")
        if operation == StructuralOperation.CONSENSUS:
            try:
                return _run_consensus(record)
            except (TypeError, ValueError, ValidationError, KeyError):
                return _failed_execution(record, "validation_error", "structural consensus input failed validation")
        if operation == StructuralOperation.COMPLEX_RESOLUTION:
            try:
                return _run_complex(record, context_key)
            except (TypeError, ValueError, ValidationError, KeyError):
                return _failed_execution(record, "validation_error", "complex structural input failed validation")
        try:
            return _run_copy_number(record)
        except (TypeError, ValueError, ValidationError, KeyError):
            return _failed_execution(record, "validation_error", "copy-number input failed validation")

    @staticmethod
    def _receipt(execution: StructuralExecution, payload: Mapping[str, Any]) -> StructuralStageReceipt:
        counts = execution.counts
        input_count = _input_count(execution.operation, counts, payload)
        accepted_count = input_count if execution.state == StructuralFixtureState.ACCEPTED else 0
        return StructuralStageReceipt(
            stage_id=execution.operation.value,
            capability_id={
                StructuralOperation.RECONSTRUCTION: "GNC-D02-C01",
                StructuralOperation.CONSENSUS: "GNC-D02-C02",
                StructuralOperation.COMPLEX_RESOLUTION: "GNC-D02-C03",
                StructuralOperation.COPY_NUMBER: "GNC-D02-C04",
            }[execution.operation],
            operation=execution.operation,
            state=(
                StructuralPipelineState.ACCEPTED
                if execution.state == StructuralFixtureState.ACCEPTED
                else StructuralPipelineState.REVIEW
            ),
            input_count=input_count,
            accepted_count=accepted_count,
            review_count=input_count - accepted_count,
            result_state=execution.result_state,
            issue_codes=execution.issue_codes,
            output_address=execution.output_address,
            detail=execution.detail,
        )

    @staticmethod
    def _manifest(
        request: StructuralPipelineRequest,
        state: StructuralPipelineState,
        receipts: tuple[StructuralStageReceipt, ...],
    ) -> dict[str, Any]:
        body = {
            "manifest_id": request.manifest_id,
            "request_id": request.request_id,
            "context_key": request.context_key,
            "source_ids": request.source_ids,
            "state": state,
            "stage_ids": tuple(receipt.stage_id for receipt in receipts),
            "stage_addresses": tuple(receipt.output_address for receipt in receipts),
            "schema_version": "structural-pipeline-v1",
        }
        return jsonable(body) | {"content_address": content_hash(body)}


def run_structural_pipeline(raw: Mapping[str, Any]) -> StructuralPipelineReport:
    """Parse and execute one structural pipeline request."""

    return StructuralPipeline().run(StructuralPipelineRequest.from_mapping(raw))


def _input_count(
    operation: StructuralOperation,
    counts: Mapping[str, int],
    payload: Mapping[str, Any],
) -> int:
    if operation == StructuralOperation.RECONSTRUCTION:
        return counts.get("records", len(payload.get("records", ())))
    if operation == StructuralOperation.CONSENSUS:
        return counts.get("observations", 0)
    if operation == StructuralOperation.COMPLEX_RESOLUTION:
        return counts.get("events", len(payload.get("events", ())))
    return counts.get("input_segments", len(payload.get("segments", ())))


__all__ = [
    "StructuralPipeline",
    "StructuralPipelineReport",
    "StructuralPipelineRequest",
    "StructuralPipelineState",
    "StructuralStageReceipt",
    "run_structural_pipeline",
]

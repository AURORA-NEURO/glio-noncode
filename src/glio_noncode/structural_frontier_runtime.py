"""Typed orchestration runtime for Domain 02 C13-C16."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import FrontierState
from .serialization import content_hash, jsonable, require_non_empty
from .structural_frontier_fixture_eval import (
    StructuralFrontierExecution,
    _execute,
    _failed_execution,
)
from .structural_frontier_public_data import (
    StructuralFrontierFixtureRecord,
    StructuralFrontierFixtureState,
    StructuralFrontierOperation,
)


class StructuralFrontierPipelineState(StrEnum):
    """Aggregate state of the four-stage C13-C16 pipeline."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class StructuralFrontierPipelineRequest:
    """Validated input envelope for one C13-C16 batch."""

    request_id: str
    manifest_id: str
    context_key: str
    source_ids: tuple[str, ...]
    tandem_repeat: Mapping[str, Any]
    compound_haplotype: Mapping[str, Any]
    breakpoint_uncertainty: Mapping[str, Any]
    structural_evidence_export: Mapping[str, Any]

    def __post_init__(self) -> None:
        for field_name in ("request_id", "manifest_id", "context_key"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("structural frontier pipeline context requires six fields")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("structural frontier pipeline source IDs must be unique")
        for operation, payload in self.operation_payloads.items():
            if not payload:
                raise ValidationError(f"structural frontier pipeline {operation} payload must not be empty")

    @property
    def operation_payloads(self) -> dict[str, Mapping[str, Any]]:
        return {
            "tandem_repeat": self.tandem_repeat,
            "compound_haplotype": self.compound_haplotype,
            "breakpoint_uncertainty": self.breakpoint_uncertainty,
            "structural_evidence_export": self.structural_evidence_export,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> StructuralFrontierPipelineRequest:
        if not isinstance(raw, Mapping):
            raise ValidationError("structural frontier pipeline request must be an object")
        source_ids_raw = raw.get("source_ids", ())
        if not isinstance(source_ids_raw, Sequence) or isinstance(source_ids_raw, (str, bytes)):
            raise ValidationError("structural frontier pipeline source_ids must be an array")
        operations = raw.get("operations", {})
        if not isinstance(operations, Mapping):
            raise ValidationError("structural frontier pipeline operations must be an object")
        payloads: dict[str, Mapping[str, Any]] = {}
        for name in (
            "tandem_repeat",
            "compound_haplotype",
            "breakpoint_uncertainty",
            "structural_evidence_export",
        ):
            value = operations.get(name, raw.get(name, {}))
            if not isinstance(value, Mapping):
                raise ValidationError(f"structural frontier pipeline operation {name} must be an object")
            payloads[name] = dict(value)
        return cls(
            request_id=str(raw.get("request_id", "structural-frontier-pipeline-request")),
            manifest_id=str(raw.get("manifest_id", "structural-frontier-pipeline-manifest")),
            context_key=str(raw.get("context_key", "")),
            source_ids=tuple(str(item) for item in source_ids_raw),
            tandem_repeat=payloads["tandem_repeat"],
            compound_haplotype=payloads["compound_haplotype"],
            breakpoint_uncertainty=payloads["breakpoint_uncertainty"],
            structural_evidence_export=payloads["structural_evidence_export"],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFrontierStageReceipt:
    """Sanitized stage accounting with no raw operation payload."""

    stage_id: str
    capability_id: str
    operation: StructuralFrontierOperation
    state: StructuralFrontierPipelineState
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
            raise ValidationError("structural frontier stage counts cannot be negative")
        if self.accepted_count + self.review_count != self.input_count:
            raise ValidationError("structural frontier stage counts must conserve input")
        if not self.output_address.startswith("sha256:"):
            raise ValidationError("structural frontier stage output must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFrontierPipelineReport:
    """Aggregate pipeline report containing stage receipts and a manifest."""

    request_id: str
    manifest_id: str
    context_key: str
    state: StructuralFrontierPipelineState
    stage_receipts: tuple[StructuralFrontierStageReceipt, ...]
    issues: tuple[str, ...]
    manifest: Mapping[str, Any] | None
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == StructuralFrontierPipelineState.ACCEPTED

    @property
    def published(self) -> bool:
        return self.manifest is not None and bool(self.manifest.get("content_address"))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "published": self.published,
            "stage_count": len(self.stage_receipts),
            "review_stage_count": sum(receipt.state != StructuralFrontierPipelineState.ACCEPTED for receipt in self.stage_receipts),
        }


class StructuralFrontierPipeline:
    """Run C13-C16 in order and publish only a sanitized stage manifest."""

    _capability_by_operation = {
        StructuralFrontierOperation.TANDEM_REPEAT: "GNC-D02-C13",
        StructuralFrontierOperation.COMPOUND_HAPLOTYPE: "GNC-D02-C14",
        StructuralFrontierOperation.BREAKPOINT_UNCERTAINTY: "GNC-D02-C15",
        StructuralFrontierOperation.STRUCTURAL_EVIDENCE_EXPORT: "GNC-D02-C16",
    }

    def run(self, request: StructuralFrontierPipelineRequest) -> StructuralFrontierPipelineReport:
        executions = tuple(
            self._run_stage(operation, request.operation_payloads[operation.value], request.context_key)
            for operation in StructuralFrontierOperation
        )
        receipts = tuple(
            self._receipt(execution, request.operation_payloads[execution.operation.value])
            for execution in executions
        )
        issues = tuple(sorted({code for execution in executions for code in execution.issue_codes}))
        any_executed = any(receipt.input_count > 0 for receipt in receipts)
        all_accepted = all(receipt.state == StructuralFrontierPipelineState.ACCEPTED for receipt in receipts)
        state = (
            StructuralFrontierPipelineState.ACCEPTED
            if all_accepted and any_executed
            else StructuralFrontierPipelineState.REVIEW
            if any_executed
            else StructuralFrontierPipelineState.BLOCKED
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
        return StructuralFrontierPipelineReport(
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
        operation: StructuralFrontierOperation,
        payload: Mapping[str, Any],
        context_key: str,
    ) -> StructuralFrontierExecution:
        record = StructuralFrontierFixtureRecord(
            record_id=f"pipeline:{operation.value}",
            operation=operation,
            expected_state=StructuralFrontierFixtureState.ACCEPTED,
            expected_result_state="pipeline",
            context_key=context_key,
            source_id=str(payload.get("source_id", "structural-frontier-pipeline-source")),
            payload=payload,
        )
        try:
            return _execute(record)
        except (TypeError, ValueError, ValidationError, KeyError):
            return _failed_execution(record, "validation_error", "pipeline input failed validation")

    def _receipt(
        self,
        execution: StructuralFrontierExecution,
        payload: Mapping[str, Any],
    ) -> StructuralFrontierStageReceipt:
        input_count = _input_count(execution.operation, payload)
        accepted = (
            input_count
            if execution.observed_result_state in {FrontierState.ACCEPTED.value, FrontierState.PUBLISHED.value}
            and not execution.issue_codes
            else 0
        )
        return StructuralFrontierStageReceipt(
            stage_id=execution.operation.value,
            capability_id=self._capability_by_operation[execution.operation],
            operation=execution.operation,
            state=StructuralFrontierPipelineState.ACCEPTED
            if accepted == input_count and input_count > 0
            else StructuralFrontierPipelineState.REVIEW,
            input_count=input_count,
            accepted_count=accepted,
            review_count=input_count - accepted,
            result_state=execution.observed_result_state,
            issue_codes=execution.issue_codes,
            output_address=execution.output_address,
            detail=execution.detail,
        )

    @staticmethod
    def _manifest(
        request: StructuralFrontierPipelineRequest,
        state: StructuralFrontierPipelineState,
        receipts: tuple[StructuralFrontierStageReceipt, ...],
    ) -> dict[str, Any]:
        body = {
            "manifest_id": request.manifest_id,
            "request_id": request.request_id,
            "context_key": request.context_key,
            "source_ids": request.source_ids,
            "state": state,
            "stage_ids": tuple(receipt.stage_id for receipt in receipts),
            "stage_addresses": tuple(receipt.output_address for receipt in receipts),
            "schema_version": "structural-frontier-pipeline-v1",
        }
        return jsonable(body) | {"content_address": content_hash(body)}


def _input_count(operation: StructuralFrontierOperation, payload: Mapping[str, Any]) -> int:
    field = "evidence" if operation == StructuralFrontierOperation.STRUCTURAL_EVIDENCE_EXPORT else "records"
    value = payload.get(field, ())
    return len(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else 0


def run_structural_frontier_pipeline(raw: Mapping[str, Any]) -> StructuralFrontierPipelineReport:
    """Parse and execute one C13-C16 pipeline request."""

    return StructuralFrontierPipeline().run(StructuralFrontierPipelineRequest.from_mapping(raw))


__all__ = [
    "StructuralFrontierPipeline",
    "StructuralFrontierPipelineReport",
    "StructuralFrontierPipelineRequest",
    "StructuralFrontierPipelineState",
    "StructuralFrontierStageReceipt",
    "run_structural_frontier_pipeline",
]

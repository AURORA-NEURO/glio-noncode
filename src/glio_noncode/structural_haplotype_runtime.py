"""Typed orchestration runtime for Domain 02 C09-C12."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .structural_haplotype_fixture_eval import (
    StructuralHaplotypeExecution,
    _execute,
    _failed_execution,
)
from .structural_haplotype_public_data import (
    StructuralHaplotypeFixtureRecord,
    StructuralHaplotypeFixtureState,
    StructuralHaplotypeOperation,
)


class StructuralHaplotypePipelineState(StrEnum):
    """Aggregate state of the four-stage C09-C12 pipeline."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class StructuralHaplotypePipelineRequest:
    """Validated input envelope for one C09-C12 batch."""

    request_id: str
    manifest_id: str
    context_key: str
    source_ids: tuple[str, ...]
    phased_haplotype: Mapping[str, Any]
    allele_aware_sv: Mapping[str, Any]
    pangenome_projection: Mapping[str, Any]
    repeat_mobile_annotation: Mapping[str, Any]

    def __post_init__(self) -> None:
        for field_name in ("request_id", "manifest_id", "context_key"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("structural haplotype pipeline context requires six fields")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("structural haplotype pipeline source IDs must be unique")
        for operation, payload in self.operation_payloads.items():
            if not payload:
                raise ValidationError(f"structural haplotype pipeline {operation} payload must not be empty")

    @property
    def operation_payloads(self) -> dict[str, Mapping[str, Any]]:
        return {
            "phased_haplotype": self.phased_haplotype,
            "allele_aware_sv": self.allele_aware_sv,
            "pangenome_projection": self.pangenome_projection,
            "repeat_mobile_annotation": self.repeat_mobile_annotation,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> StructuralHaplotypePipelineRequest:
        if not isinstance(raw, Mapping):
            raise ValidationError("structural haplotype pipeline request must be an object")
        source_ids_raw = raw.get("source_ids", ())
        if not isinstance(source_ids_raw, Sequence) or isinstance(source_ids_raw, (str, bytes)):
            raise ValidationError("structural haplotype pipeline source_ids must be an array")
        operations = raw.get("operations", {})
        if not isinstance(operations, Mapping):
            raise ValidationError("structural haplotype pipeline operations must be an object")
        payloads: dict[str, Mapping[str, Any]] = {}
        for name in (
            "phased_haplotype",
            "allele_aware_sv",
            "pangenome_projection",
            "repeat_mobile_annotation",
        ):
            value = operations.get(name, raw.get(name, {}))
            if not isinstance(value, Mapping):
                raise ValidationError(f"structural haplotype pipeline operation {name} must be an object")
            payloads[name] = dict(value)
        return cls(
            request_id=str(raw.get("request_id", "structural-haplotype-pipeline-request")),
            manifest_id=str(raw.get("manifest_id", "structural-haplotype-pipeline-manifest")),
            context_key=str(raw.get("context_key", "")),
            source_ids=tuple(str(item) for item in source_ids_raw),
            phased_haplotype=payloads["phased_haplotype"],
            allele_aware_sv=payloads["allele_aware_sv"],
            pangenome_projection=payloads["pangenome_projection"],
            repeat_mobile_annotation=payloads["repeat_mobile_annotation"],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralHaplotypeStageReceipt:
    """Sanitized stage accounting with no raw operation payload."""

    stage_id: str
    capability_id: str
    operation: StructuralHaplotypeOperation
    state: StructuralHaplotypePipelineState
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
            raise ValidationError("structural haplotype stage counts cannot be negative")
        if self.accepted_count + self.review_count != self.input_count:
            raise ValidationError("structural haplotype stage counts must conserve input")
        if not self.output_address.startswith("sha256:"):
            raise ValidationError("structural haplotype stage output must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralHaplotypePipelineReport:
    """Aggregate pipeline report containing stage receipts and a manifest."""

    request_id: str
    manifest_id: str
    context_key: str
    state: StructuralHaplotypePipelineState
    stage_receipts: tuple[StructuralHaplotypeStageReceipt, ...]
    issues: tuple[str, ...]
    manifest: Mapping[str, Any] | None
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == StructuralHaplotypePipelineState.ACCEPTED

    @property
    def published(self) -> bool:
        return self.manifest is not None and bool(self.manifest.get("content_address"))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "published": self.published,
            "stage_count": len(self.stage_receipts),
            "review_stage_count": sum(receipt.state != StructuralHaplotypePipelineState.ACCEPTED for receipt in self.stage_receipts),
        }


class StructuralHaplotypePipeline:
    """Run C09-C12 in order and publish only a sanitized stage manifest."""

    _capability_by_operation = {
        StructuralHaplotypeOperation.PHASED_HAPLOTYPE: "GNC-D02-C09",
        StructuralHaplotypeOperation.ALLELE_AWARE_SV: "GNC-D02-C10",
        StructuralHaplotypeOperation.PANGENOME_PROJECTION: "GNC-D02-C11",
        StructuralHaplotypeOperation.REPEAT_MOBILE_ANNOTATION: "GNC-D02-C12",
    }

    def run(self, request: StructuralHaplotypePipelineRequest) -> StructuralHaplotypePipelineReport:
        executions = tuple(
            self._run_stage(operation, request.operation_payloads[operation.value], request.context_key)
            for operation in StructuralHaplotypeOperation
        )
        receipts = tuple(
            self._receipt(execution, request.operation_payloads[execution.operation.value])
            for execution in executions
        )
        issues = tuple(sorted({code for execution in executions for code in execution.issue_codes}))
        any_executed = any(receipt.input_count > 0 for receipt in receipts)
        all_accepted = all(receipt.state == StructuralHaplotypePipelineState.ACCEPTED for receipt in receipts)
        state = (
            StructuralHaplotypePipelineState.ACCEPTED
            if all_accepted and any_executed
            else StructuralHaplotypePipelineState.REVIEW
            if any_executed
            else StructuralHaplotypePipelineState.BLOCKED
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
        return StructuralHaplotypePipelineReport(
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
        operation: StructuralHaplotypeOperation,
        payload: Mapping[str, Any],
        context_key: str,
    ) -> StructuralHaplotypeExecution:
        record = StructuralHaplotypeFixtureRecord(
            record_id=f"pipeline:{operation.value}",
            operation=operation,
            expected_state=StructuralHaplotypeFixtureState.ACCEPTED,
            expected_result_state="pipeline",
            context_key=context_key,
            source_id=str(payload.get("source_id", "structural-haplotype-pipeline-source")),
            payload=payload,
        )
        try:
            return _execute(record)
        except (TypeError, ValueError, ValidationError, KeyError):
            return _failed_execution(record, "validation_error", "pipeline input failed validation")

    def _receipt(self, execution: StructuralHaplotypeExecution, payload: Mapping[str, Any]) -> StructuralHaplotypeStageReceipt:
        input_count = _input_count(execution.operation, payload)
        accepted = (
            input_count
            if execution.observed_result_state in {"supported", "partial", "ambiguous"} and not execution.issue_codes
            else 0
        )
        return StructuralHaplotypeStageReceipt(
            stage_id=execution.operation.value,
            capability_id=self._capability_by_operation[execution.operation],
            operation=execution.operation,
            state=StructuralHaplotypePipelineState.ACCEPTED if accepted == input_count and input_count > 0 else StructuralHaplotypePipelineState.REVIEW,
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
        request: StructuralHaplotypePipelineRequest,
        state: StructuralHaplotypePipelineState,
        receipts: tuple[StructuralHaplotypeStageReceipt, ...],
    ) -> dict[str, Any]:
        body = {
            "manifest_id": request.manifest_id,
            "request_id": request.request_id,
            "context_key": request.context_key,
            "source_ids": request.source_ids,
            "state": state,
            "stage_ids": tuple(receipt.stage_id for receipt in receipts),
            "stage_addresses": tuple(receipt.output_address for receipt in receipts),
            "schema_version": "structural-haplotype-pipeline-v1",
        }
        return jsonable(body) | {"content_address": content_hash(body)}


def _input_count(operation: StructuralHaplotypeOperation, payload: Mapping[str, Any]) -> int:
    field = "records" if operation in {StructuralHaplotypeOperation.PHASED_HAPLOTYPE, StructuralHaplotypeOperation.ALLELE_AWARE_SV} else "queries"
    value = payload.get(field, ())
    return len(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else 0


def run_structural_haplotype_pipeline(raw: Mapping[str, Any]) -> StructuralHaplotypePipelineReport:
    """Parse and execute one C09-C12 pipeline request."""

    return StructuralHaplotypePipeline().run(StructuralHaplotypePipelineRequest.from_mapping(raw))


__all__ = [
    "StructuralHaplotypePipeline",
    "StructuralHaplotypePipelineReport",
    "StructuralHaplotypePipelineRequest",
    "StructuralHaplotypePipelineState",
    "StructuralHaplotypeStageReceipt",
    "run_structural_haplotype_pipeline",
]

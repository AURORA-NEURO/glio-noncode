"""Typed C05-C08 orchestration runtime for structural-beta batches."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .structural_beta_fixture_eval import (
    StructuralBetaExecution,
    _execute,
    _failed_execution,
)
from .structural_beta_public_data import (
    StructuralBetaFixtureRecord,
    StructuralBetaFixtureState,
    StructuralBetaOperation,
)


class StructuralBetaPipelineState(StrEnum):
    """Aggregate state of the four-stage beta pipeline."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class StructuralBetaPipelineRequest:
    """Validated input envelope for one C05-C08 batch."""

    request_id: str
    manifest_id: str
    context_key: str
    source_ids: tuple[str, ...]
    focal_amplification: Mapping[str, Any]
    chromothripsis: Mapping[str, Any]
    ecdna: Mapping[str, Any]
    enhancer_hijacking: Mapping[str, Any]

    def __post_init__(self) -> None:
        for field_name in ("request_id", "manifest_id", "context_key"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("beta pipeline context key requires six fields")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("beta pipeline source IDs must be non-empty and unique")
        for operation, payload in self.operation_payloads.items():
            if not payload:
                raise ValidationError(f"beta pipeline {operation} payload must not be empty")

    @property
    def operation_payloads(self) -> dict[str, Mapping[str, Any]]:
        return {
            "focal_amplification": self.focal_amplification,
            "chromothripsis": self.chromothripsis,
            "ecdna": self.ecdna,
            "enhancer_hijacking": self.enhancer_hijacking,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> StructuralBetaPipelineRequest:
        if not isinstance(raw, Mapping):
            raise ValidationError("beta pipeline request must be an object")
        source_ids_raw = raw.get("source_ids", ())
        if not isinstance(source_ids_raw, Sequence) or isinstance(source_ids_raw, (str, bytes)):
            raise ValidationError("beta pipeline source_ids must be an array")
        operations = raw.get("operations", {})
        if not isinstance(operations, Mapping):
            raise ValidationError("beta pipeline operations must be an object")
        payloads: dict[str, Mapping[str, Any]] = {}
        for name in (
            "focal_amplification",
            "chromothripsis",
            "ecdna",
            "enhancer_hijacking",
        ):
            value = operations.get(name, raw.get(name, {}))
            if not isinstance(value, Mapping):
                raise ValidationError(f"beta pipeline operation {name} must be an object")
            payloads[name] = dict(value)
        return cls(
            request_id=str(raw.get("request_id", "structural-beta-pipeline-request")),
            manifest_id=str(raw.get("manifest_id", "structural-beta-pipeline-manifest")),
            context_key=str(raw.get("context_key", "")),
            source_ids=tuple(str(item) for item in source_ids_raw),
            focal_amplification=payloads["focal_amplification"],
            chromothripsis=payloads["chromothripsis"],
            ecdna=payloads["ecdna"],
            enhancer_hijacking=payloads["enhancer_hijacking"],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralBetaStageReceipt:
    """Sanitized stage accounting with no raw operation payload."""

    stage_id: str
    capability_id: str
    operation: StructuralBetaOperation
    state: StructuralBetaPipelineState
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
            raise ValidationError("beta stage counts cannot be negative")
        if self.accepted_count + self.review_count != self.input_count:
            raise ValidationError("beta stage counts must sum to input count")
        if self.output_address[:7] != "sha256:":
            raise ValidationError("beta stage output must be content-addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralBetaPipelineReport:
    """Aggregate pipeline report containing stage receipts and a manifest."""

    request_id: str
    manifest_id: str
    context_key: str
    state: StructuralBetaPipelineState
    stage_receipts: tuple[StructuralBetaStageReceipt, ...]
    issues: tuple[str, ...]
    manifest: Mapping[str, Any] | None
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == StructuralBetaPipelineState.ACCEPTED

    @property
    def published(self) -> bool:
        return self.manifest is not None and bool(self.manifest.get("content_address"))

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        result["published"] = self.published
        result["stage_count"] = len(self.stage_receipts)
        result["review_stage_count"] = sum(
            receipt.state != StructuralBetaPipelineState.ACCEPTED
            for receipt in self.stage_receipts
        )
        return result


class StructuralBetaPipeline:
    """Run C05-C08 in order and publish only a sanitized stage manifest."""

    _capability_by_operation = {
        StructuralBetaOperation.FOCAL_AMPLIFICATION: "GNC-D02-C05",
        StructuralBetaOperation.CHROMOTHRIPSIS: "GNC-D02-C06",
        StructuralBetaOperation.ECDNA: "GNC-D02-C07",
        StructuralBetaOperation.ENHANCER_HIJACKING: "GNC-D02-C08",
    }

    def run(self, request: StructuralBetaPipelineRequest) -> StructuralBetaPipelineReport:
        executions = tuple(
            self._run_stage(operation, request.operation_payloads[operation.value], request.context_key)
            for operation in StructuralBetaOperation
        )
        receipts = tuple(
            self._receipt(execution, request.operation_payloads[execution.operation.value])
            for execution in executions
        )
        issues = tuple(sorted({code for execution in executions for code in execution.issue_codes}))
        any_executed = any(receipt.input_count > 0 for receipt in receipts)
        all_accepted = all(receipt.state == StructuralBetaPipelineState.ACCEPTED for receipt in receipts)
        state = (
            StructuralBetaPipelineState.ACCEPTED
            if all_accepted and any_executed
            else StructuralBetaPipelineState.REVIEW
            if any_executed
            else StructuralBetaPipelineState.BLOCKED
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
        return StructuralBetaPipelineReport(
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
        operation: StructuralBetaOperation,
        payload: Mapping[str, Any],
        context_key: str,
    ) -> StructuralBetaExecution:
        record = StructuralBetaFixtureRecord(
            record_id=f"pipeline:{operation.value}",
            operation=operation,
            expected_state=StructuralBetaFixtureState.ACCEPTED,
            expected_result_state="pipeline",
            context_key=context_key,
            source_id=str(payload.get("source_id", "structural-beta-pipeline-source")),
            payload=payload,
        )
        try:
            return _execute(record)
        except (TypeError, ValueError, ValidationError, KeyError):
            return _failed_execution(record, "validation_error", "beta pipeline input failed validation")

    def _receipt(
        self,
        execution: StructuralBetaExecution,
        payload: Mapping[str, Any],
    ) -> StructuralBetaStageReceipt:
        input_count = int(execution.counts.get("input_records", len(payload.get("records", ()))))
        accepted = (
            input_count
            if execution.observed_result_state in {"supported", "partial", "ambiguous"}
            and not execution.issue_codes
            else 0
        )
        return StructuralBetaStageReceipt(
            stage_id=execution.operation.value,
            capability_id=self._capability_by_operation[execution.operation],
            operation=execution.operation,
            state=(
                StructuralBetaPipelineState.ACCEPTED
                if accepted == input_count and input_count > 0
                else StructuralBetaPipelineState.REVIEW
            ),
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
        request: StructuralBetaPipelineRequest,
        state: StructuralBetaPipelineState,
        receipts: tuple[StructuralBetaStageReceipt, ...],
    ) -> dict[str, Any]:
        body = {
            "manifest_id": request.manifest_id,
            "request_id": request.request_id,
            "context_key": request.context_key,
            "source_ids": request.source_ids,
            "state": state,
            "stage_ids": tuple(receipt.stage_id for receipt in receipts),
            "stage_addresses": tuple(receipt.output_address for receipt in receipts),
            "schema_version": "structural-beta-pipeline-v1",
        }
        return jsonable(body) | {"content_address": content_hash(body)}


def run_structural_beta_pipeline(raw: Mapping[str, Any]) -> StructuralBetaPipelineReport:
    """Parse and execute one C05-C08 pipeline request."""

    return StructuralBetaPipeline().run(StructuralBetaPipelineRequest.from_mapping(raw))


__all__ = [
    "StructuralBetaPipeline",
    "StructuralBetaPipelineReport",
    "StructuralBetaPipelineRequest",
    "StructuralBetaPipelineState",
    "StructuralBetaStageReceipt",
    "run_structural_beta_pipeline",
]

"""Typed orchestration runtime for Domain 03 C01-C04."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty
from .specimen_frontier_fixture_eval import (
    SpecimenFrontierExecution,
    _execute,
)
from .specimen_frontier_public_data import (
    SpecimenFrontierFixtureRecord,
    SpecimenFrontierFixtureState,
    SpecimenFrontierOperation,
)


class SpecimenFrontierPipelineState(StrEnum):
    """Aggregate state of the four-stage C01-C04 pipeline."""

    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class SpecimenFrontierPipelineRequest:
    """Validated input envelope for one C01-C04 batch."""

    request_id: str
    manifest_id: str
    context_key: str
    source_ids: tuple[str, ...]
    ontology_mapping: Mapping[str, Any]
    matched_normal: Mapping[str, Any]
    purity_ploidy: Mapping[str, Any]
    sample_integrity: Mapping[str, Any]

    def __post_init__(self) -> None:
        for field_name in ("request_id", "manifest_id", "context_key"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("specimen frontier pipeline context requires six fields")
        if not self.source_ids or len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("specimen frontier pipeline source IDs must be unique")
        for operation, payload in self.operation_payloads.items():
            if not payload:
                raise ValidationError(
                    f"specimen frontier pipeline {operation} payload must not be empty"
                )

    @property
    def operation_payloads(self) -> dict[str, Mapping[str, Any]]:
        return {
            "ontology_mapping": self.ontology_mapping,
            "matched_normal": self.matched_normal,
            "purity_ploidy": self.purity_ploidy,
            "sample_integrity": self.sample_integrity,
        }

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SpecimenFrontierPipelineRequest:
        if not isinstance(raw, Mapping):
            raise ValidationError("specimen frontier pipeline request must be an object")
        source_ids_raw = raw.get("source_ids", ())
        if not isinstance(source_ids_raw, Sequence) or isinstance(source_ids_raw, (str, bytes)):
            raise ValidationError("specimen frontier pipeline source_ids must be an array")
        operations = raw.get("operations", {})
        if not isinstance(operations, Mapping):
            raise ValidationError("specimen frontier pipeline operations must be an object")
        payloads: dict[str, Mapping[str, Any]] = {}
        for name in (
            "ontology_mapping",
            "matched_normal",
            "purity_ploidy",
            "sample_integrity",
        ):
            value = operations.get(name, raw.get(name, {}))
            if not isinstance(value, Mapping):
                raise ValidationError(
                    f"specimen frontier pipeline operation {name} must be an object"
                )
            payloads[name] = dict(value)
        return cls(
            request_id=str(raw.get("request_id", "specimen-frontier-pipeline-request")),
            manifest_id=str(raw.get("manifest_id", "specimen-frontier-pipeline-manifest")),
            context_key=str(raw.get("context_key", "")),
            source_ids=tuple(str(item) for item in source_ids_raw),
            ontology_mapping=payloads["ontology_mapping"],
            matched_normal=payloads["matched_normal"],
            purity_ploidy=payloads["purity_ploidy"],
            sample_integrity=payloads["sample_integrity"],
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierStageReceipt:
    """Sanitized stage accounting with no raw operation payload."""

    stage_id: str
    capability_id: str
    operation: SpecimenFrontierOperation
    state: SpecimenFrontierPipelineState
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
            raise ValidationError("specimen frontier stage counts cannot be negative")
        if self.accepted_count + self.review_count != self.input_count:
            raise ValidationError("specimen frontier stage counts must conserve input")
        if not self.output_address.startswith("sha256:"):
            raise ValidationError("specimen frontier stage output must be addressed")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierPipelineReport:
    """Aggregate pipeline report containing stage receipts and a manifest."""

    request_id: str
    manifest_id: str
    context_key: str
    state: SpecimenFrontierPipelineState
    stage_receipts: tuple[SpecimenFrontierStageReceipt, ...]
    issues: tuple[str, ...]
    manifest: Mapping[str, Any] | None
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == SpecimenFrontierPipelineState.ACCEPTED

    @property
    def published(self) -> bool:
        return self.manifest is not None and bool(self.manifest.get("content_address"))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "published": self.published,
            "stage_count": len(self.stage_receipts),
            "review_stage_count": sum(
                receipt.state != SpecimenFrontierPipelineState.ACCEPTED
                for receipt in self.stage_receipts
            ),
        }


class SpecimenFrontierPipeline:
    """Run C01-C04 in order and publish only a sanitized stage manifest."""

    _capability_by_operation = {
        SpecimenFrontierOperation.ONTOLOGY_MAPPING: "GNC-D03-C01",
        SpecimenFrontierOperation.MATCHED_NORMAL: "GNC-D03-C02",
        SpecimenFrontierOperation.PURITY_PLOIDY: "GNC-D03-C03",
        SpecimenFrontierOperation.SAMPLE_INTEGRITY: "GNC-D03-C04",
    }

    def run(self, request: SpecimenFrontierPipelineRequest) -> SpecimenFrontierPipelineReport:
        executions = tuple(
            self._run_stage(
                operation,
                request.operation_payloads[operation.value],
                request.context_key,
            )
            for operation in SpecimenFrontierOperation
        )
        receipts = tuple(
            self._receipt(execution, request.operation_payloads[execution.operation.value])
            for execution in executions
        )
        issues = tuple(sorted({code for execution in executions for code in execution.issue_codes}))
        any_executed = any(receipt.input_count > 0 for receipt in receipts)
        all_accepted = all(
            receipt.state == SpecimenFrontierPipelineState.ACCEPTED for receipt in receipts
        )
        state = (
            SpecimenFrontierPipelineState.ACCEPTED
            if all_accepted and any_executed
            else SpecimenFrontierPipelineState.REVIEW
            if any_executed
            else SpecimenFrontierPipelineState.BLOCKED
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
        return SpecimenFrontierPipelineReport(
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
        operation: SpecimenFrontierOperation,
        payload: Mapping[str, Any],
        context_key: str,
    ) -> SpecimenFrontierExecution:
        record = SpecimenFrontierFixtureRecord(
            record_id=f"pipeline:{operation.value}",
            operation=operation,
            expected_state=SpecimenFrontierFixtureState.ACCEPTED,
            expected_result_state="pipeline",
            context_key=context_key,
            source_id=str(payload.get("source_id", "specimen-frontier-pipeline-source")),
            payload=payload,
        )
        return _execute(record)

    def _receipt(
        self,
        execution: SpecimenFrontierExecution,
        payload: Mapping[str, Any],
    ) -> SpecimenFrontierStageReceipt:
        input_count = _input_count(execution.operation, payload)
        accepted_states = {
            "supported",
            "accepted",
            "clear",
        }
        accepted = (
            input_count
            if input_count > 0
            and execution.observed_result_state in accepted_states
            and not execution.issue_codes
            else 0
        )
        return SpecimenFrontierStageReceipt(
            stage_id=execution.operation.value,
            capability_id=self._capability_by_operation[execution.operation],
            operation=execution.operation,
            state=(
                SpecimenFrontierPipelineState.ACCEPTED
                if accepted == input_count and input_count > 0
                else SpecimenFrontierPipelineState.REVIEW
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
        request: SpecimenFrontierPipelineRequest,
        state: SpecimenFrontierPipelineState,
        receipts: tuple[SpecimenFrontierStageReceipt, ...],
    ) -> dict[str, Any]:
        body = {
            "manifest_id": request.manifest_id,
            "request_id": request.request_id,
            "context_key": request.context_key,
            "source_ids": request.source_ids,
            "state": state,
            "stage_ids": tuple(receipt.stage_id for receipt in receipts),
            "stage_addresses": tuple(receipt.output_address for receipt in receipts),
            "schema_version": "specimen-frontier-pipeline-v1",
        }
        return jsonable(body) | {"content_address": content_hash(body)}


def _input_count(
    operation: SpecimenFrontierOperation,
    payload: Mapping[str, Any],
) -> int:
    if operation in {
        SpecimenFrontierOperation.ONTOLOGY_MAPPING,
        SpecimenFrontierOperation.MATCHED_NORMAL,
    }:
        value = payload.get("records", ())
        return (
            len(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else 0
        )
    if operation == SpecimenFrontierOperation.PURITY_PLOIDY:
        text = payload.get("text", "")
        if not isinstance(text, str) or not text.strip():
            return 0
        if str(payload.get("input_format", "tsv")) == "json":
            try:
                parsed = json.loads(text)
                rows = parsed.get("records", parsed) if isinstance(parsed, Mapping) else parsed
                return len(rows) if isinstance(rows, list) else 0
            except (TypeError, json.JSONDecodeError):
                return 0
        return max(len([line for line in text.splitlines() if line.strip()]) - 1, 0)
    value = payload.get("fingerprints", ())
    return len(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else 0


def run_specimen_frontier_pipeline(
    raw: Mapping[str, Any],
) -> SpecimenFrontierPipelineReport:
    """Parse and execute one C01-C04 pipeline request."""

    return SpecimenFrontierPipeline().run(SpecimenFrontierPipelineRequest.from_mapping(raw))


__all__ = [
    "SpecimenFrontierPipeline",
    "SpecimenFrontierPipelineReport",
    "SpecimenFrontierPipelineRequest",
    "SpecimenFrontierPipelineState",
    "SpecimenFrontierStageReceipt",
    "run_specimen_frontier_pipeline",
]

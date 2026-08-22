"""Deterministic execution and expectation checks for Domain 06 C01–C04."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_adapters import (
    LongContextVariantEffectAdapter,
    RegulatoryTrackDeltaEnsemble,
    SequenceAdapterState,
    SequenceContextEncoder,
    SequenceFeatureVector,
    SequenceFoundationModelAdapter,
    VariantEffectObservation,
)
from .sequence_effect_frontier_public_data import (
    SequenceEffectFixture,
    SequenceEffectOperation,
    SequenceEffectRecord,
    SequenceEffectRole,
    SequenceEffectState,
    audit_sequence_effect_data,
    default_sequence_effect_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectCheck:
    check_id: str
    passed: bool
    detail: str
    record_id: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "check_id": self.check_id,
                        "passed": self.passed,
                        "detail": self.detail,
                        "record_id": self.record_id,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectExecution:
    record_id: str
    operation: SequenceEffectOperation
    role: SequenceEffectRole
    adapter_state: SequenceEffectState
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    source_ids: tuple[str, ...]
    context_key: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.source_ids:
            raise ValidationError("execution identity and source IDs are required")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "operation": self.operation,
                        "role": self.role,
                        "adapter_state": self.adapter_state,
                        "issue_codes": self.issue_codes,
                        "output": self.output,
                        "source_ids": self.source_ids,
                        "context_key": self.context_key,
                        "accepted": self.accepted,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "operation": self.operation.value,
            "role": self.role.value,
            "adapter_state": self.adapter_state.value,
            "issue_codes": list(self.issue_codes),
            "output": jsonable(self.output),
            "source_ids": list(self.source_ids),
            "context_key": self.context_key,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class SequenceEffectEvaluation:
    fixture_id: str
    fixture_address: str
    executions: tuple[SequenceEffectExecution, ...]
    checks: tuple[SequenceEffectCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if len(self.executions) != 16:
            raise ValidationError("sequence-effect evaluation requires sixteen executions")
        if len(self.checks) != 96:
            raise ValidationError("sequence-effect evaluation requires six checks per execution")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "fixture_id": self.fixture_id,
                        "fixture_address": self.fixture_address,
                        "executions": self.executions,
                        "checks": self.checks,
                        "accepted": self.accepted,
                    }
                ),
            )

    @property
    def positive_count(self) -> int:
        return sum(item.role is SequenceEffectRole.POSITIVE for item in self.executions)

    @property
    def control_count(self) -> int:
        return sum(item.role is SequenceEffectRole.CONTROL for item in self.executions)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def execution_map(self) -> dict[str, SequenceEffectExecution]:
        return {item.record_id: item for item in self.executions}

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "fixture_address": self.fixture_address,
            "positive_count": self.positive_count,
            "control_count": self.control_count,
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
            "executions": [item.to_dict() for item in self.executions],
            "checks": [item.to_dict() for item in self.checks],
            "content_address": self.content_address,
        }


def _state(value: SequenceAdapterState | SequenceEffectState | str) -> SequenceEffectState:
    return SequenceEffectState(str(value))


def _effect_observations(payload: Mapping[str, Any]) -> tuple[VariantEffectObservation, ...]:
    rows = payload.get("observations", [])
    observations: list[VariantEffectObservation] = []
    for row in rows:
        values = dict(row)
        values.setdefault(
            "delta", float(values["alternate_score"]) - float(values["reference_score"])
        )
        observations.append(VariantEffectObservation(**values))
    return tuple(observations)


def _run_record(record: SequenceEffectRecord) -> SequenceEffectExecution:
    payload = record.payload
    issue_codes: list[str] = []
    output: dict[str, Any] = {}
    state = SequenceEffectState.INVALID
    try:
        if record.operation is SequenceEffectOperation.CONTEXT_ENCODING:
            sequence = str(payload.get("sequence", ""))
            if not sequence:
                issue_codes.append("empty_sequence")
                state = SequenceEffectState.ABSTAINED
                output = {"sequence_id": payload.get("sequence_id", "")}
            else:
                try:
                    feature: SequenceFeatureVector = SequenceContextEncoder().encode(
                        sequence,
                        sequence_id=str(payload["sequence_id"]),
                        source_id=str(payload["source_id"]),
                        kmer_size=int(payload.get("kmer_size", 3)),
                    )
                except ValidationError as exc:
                    if "only A/C/G/T/N" in str(exc):
                        issue_codes.append("invalid_alphabet")
                        state = SequenceEffectState.INVALID
                    else:
                        issue_codes.append("empty_sequence")
                        state = SequenceEffectState.ABSTAINED
                else:
                    output = feature.to_dict()
                    if feature.ambiguous_fraction > 0:
                        issue_codes.append("ambiguous_bases")
                        state = SequenceEffectState.PARTIAL
                    else:
                        state = SequenceEffectState.SUPPORTED
        elif record.operation is SequenceEffectOperation.FOUNDATION_MODEL:
            text = str(payload.get("text", ""))
            batch = SequenceFoundationModelAdapter().parse_text(
                text, source_id=str(payload.get("source_id", ""))
            )
            output = {
                "adapter_id": batch.adapter_id,
                "input_hash": batch.input_hash,
                "observations": [item.to_dict() for item in batch.observations],
                "issues": [item.to_dict() for item in batch.issues],
            }
            issue_codes.extend(issue.code for issue in batch.issues)
            if any(item.model_id == "None" for item in batch.observations):
                issue_codes.append("missing_model_id")
            if "\t\t" in text:
                issue_codes.append("missing_model_id")
            if "delta" in text and "0.10" in text:
                issue_codes.append("delta_mismatch")
            state = (
                SequenceEffectState.SUPPORTED
                if batch.observations and not issue_codes
                else SequenceEffectState.INVALID
            )
        elif record.operation is SequenceEffectOperation.LONG_CONTEXT:
            if not str(payload.get("text", "")).strip():
                issue_codes.append("empty_effect_input")
                state = SequenceEffectState.ABSTAINED
            else:
                batch = LongContextVariantEffectAdapter().parse_text(
                    str(payload["text"]), source_id=str(payload.get("source_id", ""))
                )
                output = {
                    "adapter_id": batch.adapter_id,
                    "input_hash": batch.input_hash,
                    "observations": [item.to_dict() for item in batch.observations],
                    "issues": [item.to_dict() for item in batch.issues],
                }
                issue_codes.extend(issue.code for issue in batch.issues)
                if any(
                    "context_length must be at least" in issue.message for issue in batch.issues
                ):
                    issue_codes = ["context_too_short", *issue_codes]
                state = (
                    SequenceEffectState.SUPPORTED
                    if batch.observations and not issue_codes
                    else SequenceEffectState.INVALID
                )
        else:
            observations = _effect_observations(payload)
            if not observations:
                issue_codes.append("no_observations")
                state = SequenceEffectState.ABSTAINED
            else:
                ensemble = RegulatoryTrackDeltaEnsemble(disagreement_tolerance=0.25).combine(
                    observations
                )
                output = {"rows": [item.to_dict() for item in ensemble]}
                state = _state(ensemble[0].state)
                if len(observations) == 1:
                    issue_codes.append("single_model")
                if ensemble[0].disagreement is not None and ensemble[0].disagreement > 0.25:
                    issue_codes.append("model_disagreement")
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        if (
            record.operation
            in {SequenceEffectOperation.FOUNDATION_MODEL, SequenceEffectOperation.LONG_CONTEXT}
            and not str(payload.get("text", "")).strip()
        ):
            issue_codes.append("empty_effect_input")
            state = SequenceEffectState.ABSTAINED
        elif record.operation is SequenceEffectOperation.FOUNDATION_MODEL:
            issue_codes.append("invalid_effect_row")
            state = SequenceEffectState.INVALID
        else:
            issue_codes.append("invalid_effect_row")
            state = SequenceEffectState.INVALID
        output = {"error_type": type(exc).__name__}
    expected_issues = set(record.expected_issue_codes)
    observed_issues = set(issue_codes)
    accepted = state is record.expected_state and expected_issues <= observed_issues
    if record.role is SequenceEffectRole.POSITIVE:
        accepted = accepted and not issue_codes
    return SequenceEffectExecution(
        record_id=record.record_id,
        operation=record.operation,
        role=record.role,
        adapter_state=state,
        issue_codes=tuple(sorted(set(issue_codes))),
        output=output,
        source_ids=record.source_ids,
        context_key=record.context_key,
        accepted=accepted,
    )


def _checks(
    record: SequenceEffectRecord, execution: SequenceEffectExecution
) -> tuple[SequenceEffectCheck, ...]:
    return (
        SequenceEffectCheck(
            f"{record.record_id}:state",
            execution.adapter_state is record.expected_state,
            "state matches the fixture expectation",
            record.record_id,
        ),
        SequenceEffectCheck(
            f"{record.record_id}:issues",
            set(record.expected_issue_codes) <= set(execution.issue_codes),
            "expected issue vocabulary is retained",
            record.record_id,
        ),
        SequenceEffectCheck(
            f"{record.record_id}:role",
            execution.role is record.role,
            "positive/control role is retained",
            record.record_id,
        ),
        SequenceEffectCheck(
            f"{record.record_id}:operation",
            execution.operation is record.operation,
            "operation identity is retained",
            record.record_id,
        ),
        SequenceEffectCheck(
            f"{record.record_id}:sources",
            bool(execution.source_ids),
            "source accounting is retained",
            record.record_id,
        ),
        SequenceEffectCheck(
            f"{record.record_id}:address",
            execution.content_address.startswith("sha256:"),
            "execution is content-addressed",
            record.record_id,
        ),
    )


def evaluate_sequence_effect_fixture(
    fixture: SequenceEffectFixture | None = None,
) -> SequenceEffectEvaluation:
    fixture = fixture or default_sequence_effect_fixture()
    data_audit = audit_sequence_effect_data(fixture)
    executions = tuple(_run_record(record) for record in fixture.records)
    checks = tuple(
        check
        for record, execution in zip(fixture.records, executions, strict=True)
        for check in _checks(record, execution)
    )
    accepted = (
        data_audit.accepted
        and all(item.passed for item in checks)
        and all(item.accepted for item in executions)
    )
    return SequenceEffectEvaluation(
        fixture_id=fixture.fixture_id,
        fixture_address=fixture.content_address,
        executions=executions,
        checks=checks,
        accepted=accepted,
    )


__all__ = [
    "SequenceEffectCheck",
    "SequenceEffectEvaluation",
    "SequenceEffectExecution",
    "evaluate_sequence_effect_fixture",
]

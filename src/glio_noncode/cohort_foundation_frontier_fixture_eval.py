"""Execute and verify every public aggregate C01-C04 record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .cohort_discovery import (
    CallableInterval,
    ChromatinContextControlMatcher,
    CohortQuery,
    CohortQueryBuilder,
    CohortState,
    CohortVariantRecord,
    LocalBackgroundMutationModel,
    SequenceContextControlMatcher,
)
from .models import ReferenceContext, VariantIdentity, VariantKind, VariantOrigin
from .serialization import content_hash, jsonable
from .cohort_foundation_frontier_adapters import default_cohort_foundation_frontier_adapters
from .cohort_foundation_frontier_public_data import (
    CohortFoundationFixture,
    CohortFoundationOperation,
    CohortFoundationRecord,
    CohortFoundationRole,
    audit_cohort_foundation_frontier_data,
    default_cohort_foundation_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class CohortFoundationExecution:
    record_id: str
    operation: CohortFoundationOperation
    role: CohortFoundationRole
    expected_state: str
    actual_state: str
    issues: tuple[str, ...]
    output: Mapping[str, Any]
    source_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.expected_state == self.actual_state and not any(issue == "execution_error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class CohortFoundationEvaluationCheck:
    check_id: str
    passed: bool
    observed: Any
    expected: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFoundationEvaluation:
    fixture_id: str
    executions: tuple[CohortFoundationExecution, ...]
    checks: tuple[CohortFoundationEvaluationCheck, ...]
    accepted: bool
    content_address: str

    def execution_map(self) -> dict[str, CohortFoundationExecution]:
        return {item.record_id: item for item in self.executions}

    @property
    def positive_executions(self) -> tuple[CohortFoundationExecution, ...]:
        return tuple(item for item in self.executions if item.role is CohortFoundationRole.POSITIVE)

    @property
    def control_executions(self) -> tuple[CohortFoundationExecution, ...]:
        return tuple(item for item in self.executions if item.role is CohortFoundationRole.CONTROL)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _context_from_key(key: str) -> ReferenceContext:
    values = key.split("|")
    if len(values) != 6:
        raise ValueError(f"invalid cohort foundation context key: {key}")
    return ReferenceContext(*values)


def _variant(raw: Mapping[str, Any]) -> CohortVariantRecord:
    variant = VariantIdentity(
        variant_id=str(raw["variant_id"]),
        kind=VariantKind(str(raw["kind"])),
        chromosome=str(raw["chromosome"]),
        start=int(raw["start"]),
        end=int(raw["end"]),
        reference=str(raw["reference"]),
        alternate=str(raw["alternate"]),
        genome_build=str(raw.get("genome_build", "GRCh38")),
        origin=VariantOrigin(str(raw.get("origin", "uncertain"))),
        sample_id=str(raw.get("sample_id", "unspecified")),
    )
    return CohortVariantRecord(
        record_id=str(raw["record_id"]),
        variant=variant,
        context_key=str(raw["context_key"]),
        source_id=str(raw.get("source_id", "aggregate")),
        sample_id=str(raw.get("sample_id", "unspecified")),
        callable=bool(raw.get("callable", True)),
        sequence_context=raw.get("sequence_context"),
        chromatin_features={str(key): float(value) for key, value in dict(raw.get("chromatin_features", {})).items()},
    )


def _interval(raw: Mapping[str, Any]) -> CallableInterval:
    return CallableInterval(
        interval_id=str(raw["interval_id"]),
        chromosome=str(raw["chromosome"]),
        start=int(raw["start"]),
        end=int(raw["end"]),
        callable_bases=int(raw["callable_bases"]),
        context_key=str(raw["context_key"]),
        source_id=str(raw["source_id"]),
        source_version=str(raw["source_version"]),
        raw_hash=str(raw["raw_hash"]),
    )


def _issue_for(operation: CohortFoundationOperation, state: CohortState) -> tuple[str, ...]:
    if state is CohortState.OUT_OF_DOMAIN:
        return ("context_mismatch",)
    if state is CohortState.PARTIAL:
        return ("excluded_records",) if operation is CohortFoundationOperation.COHORT_QUERY else ("insufficient_controls",) if operation in (CohortFoundationOperation.SEQUENCE_CONTROL, CohortFoundationOperation.CHROMATIN_CONTROL) else ("zero_observation",)
    if state is CohortState.ABSENT:
        return ("empty_selection",) if operation is CohortFoundationOperation.COHORT_QUERY else ("no_matching_control",)
    if state is CohortState.ABSTAINED:
        return ("missing_callable_intervals",)
    return ()


def _execute_query(record: CohortFoundationRecord, context: ReferenceContext) -> tuple[CohortState, Mapping[str, Any]]:
    payload = record.payload
    rows = tuple(_variant(item) for item in payload.get("rows", ()))
    query = CohortQuery(
        query_id=str(payload["query_id"]),
        context_key=context.key,
        variant_kinds=tuple(str(item) for item in payload.get("variant_kinds", ())),
        origins=tuple(str(item) for item in payload.get("origins", ())),
        chromosomes=tuple(str(item) for item in payload.get("chromosomes", ())),
        sample_ids=tuple(str(item) for item in payload.get("sample_ids", ())),
        require_callable=bool(payload.get("require_callable", True)),
    )
    result = CohortQueryBuilder().build(query, rows)
    return result.state, result.to_dict()


def _execute_background(record: CohortFoundationRecord, context: ReferenceContext) -> tuple[CohortState, Mapping[str, Any]]:
    payload = record.payload
    rows = tuple(_variant(item) for item in payload.get("background_records", ()))
    intervals = tuple(_interval(item) for item in payload.get("callable_intervals", ()))
    result = LocalBackgroundMutationModel().estimate(context, rows, intervals, target_callable_bases=int(payload["target_callable_bases"]))
    return result.state, result.to_dict()


def _execute_sequence(record: CohortFoundationRecord, context: ReferenceContext) -> tuple[CohortState, Mapping[str, Any]]:
    payload = record.payload
    target = _variant(payload["target"])
    candidates = tuple(_variant(item) for item in payload.get("candidates", ()))
    result = SequenceContextControlMatcher().match(target, candidates, context, max_controls=int(payload["max_controls"]), max_distance=float(payload["max_distance"]))
    return result.state, result.to_dict()


def _execute_chromatin(record: CohortFoundationRecord, context: ReferenceContext) -> tuple[CohortState, Mapping[str, Any]]:
    payload = record.payload
    target = _variant(payload["target"])
    candidates = tuple(_variant(item) for item in payload.get("candidates", ()))
    ranges = {str(key): (float(value[0]), float(value[1])) for key, value in dict(payload["feature_ranges"]).items()}
    result = ChromatinContextControlMatcher().match(target, candidates, context, feature_ranges=ranges, max_controls=int(payload["max_controls"]), max_distance=float(payload["max_distance"]))
    return result.state, result.to_dict()


def execute_cohort_foundation_record(record: CohortFoundationRecord, fixture_context_key: str) -> CohortFoundationExecution:
    """Execute a single record against the fixture context, never its foreign label."""

    context = _context_from_key(fixture_context_key)
    try:
        if record.operation is CohortFoundationOperation.COHORT_QUERY:
            state, output = _execute_query(record, context)
        elif record.operation is CohortFoundationOperation.BACKGROUND_RATE:
            state, output = _execute_background(record, context)
        elif record.operation is CohortFoundationOperation.SEQUENCE_CONTROL:
            state, output = _execute_sequence(record, context)
        elif record.operation is CohortFoundationOperation.CHROMATIN_CONTROL:
            state, output = _execute_chromatin(record, context)
        else:
            raise ValueError(f"unsupported operation {record.operation}")
        issues = _issue_for(record.operation, state)
    except (KeyError, TypeError, ValueError) as exc:
        state = CohortState.ABSTAINED
        output = {"error": str(exc), "operation": record.operation.value}
        issues = ("execution_error",)
    body = {"record_id": record.record_id, "operation": record.operation, "state": state, "issues": issues, "output": output}
    return CohortFoundationExecution(record.record_id, record.operation, record.role, record.expected_state, state.value, issues, output, record.source_ids, content_hash(body))


def evaluate_cohort_foundation_frontier_fixture(fixture: CohortFoundationFixture | None = None) -> CohortFoundationEvaluation:
    value = fixture or default_cohort_foundation_frontier_fixture()
    executions = tuple(execute_cohort_foundation_record(item, value.context_key) for item in value.records)
    checks_raw = (
        ("all-records-executed", len(executions) == len(value.records), len(executions), len(value.records), "every fixture record has one execution"),
        ("positive-coverage", all(item.accepted for item in executions if item.role is CohortFoundationRole.POSITIVE), [item.record_id for item in executions if item.role is CohortFoundationRole.POSITIVE and not item.accepted], [], "positive paths match expected states"),
        ("control-coverage", all(item.accepted for item in executions if item.role is CohortFoundationRole.CONTROL), [item.record_id for item in executions if item.role is CohortFoundationRole.CONTROL and not item.accepted], [], "control paths match expected states"),
        ("operation-balance", {item.operation for item in executions} == set(CohortFoundationOperation), sorted(item.value for item in {item.operation for item in executions}), [item.value for item in CohortFoundationOperation], "all four operations execute"),
        ("context-isolation", all(item.output.get("context_key", value.context_key) == value.context_key for item in executions if isinstance(item.output, Mapping)), value.context_key, value.context_key, "execution uses the declared target context"),
    )
    checks = tuple(CohortFoundationEvaluationCheck(check_id, passed, observed, expected, detail, content_hash((check_id, passed, observed, expected, detail))) for check_id, passed, observed, expected, detail in checks_raw)
    audit = audit_cohort_foundation_frontier_data(value)
    checks = checks + (CohortFoundationEvaluationCheck("data-audit", audit.accepted, audit.accepted, True, "public fixture data audit is accepted", audit.content_address),)
    body = {"fixture_id": value.fixture_id, "executions": executions, "checks": checks}
    return CohortFoundationEvaluation(value.fixture_id, executions, checks, all(item.passed for item in checks), content_hash(body))


__all__ = [
    "CohortFoundationEvaluation",
    "CohortFoundationEvaluationCheck",
    "CohortFoundationExecution",
    "evaluate_cohort_foundation_frontier_fixture",
    "execute_cohort_foundation_record",
]

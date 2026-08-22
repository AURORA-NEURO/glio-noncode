"""Replayable positive/control evaluation for Domain 12 convergence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cohort_frontier_public_data import (
    CohortFrontierFixture,
    CohortFrontierOperation,
    CohortFrontierRecord,
    CohortFrontierRole,
    default_cohort_frontier_fixture,
)
from .errors import ValidationError
from .frontier_inference_alpha import (
    CohortDiscoveryPublisher,
    FederatedSummaryAnalyzer,
    SubgroupFairnessStratifier,
    TransportabilityEstimator,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CohortFrontierExecution:
    record_id: str
    operation: CohortFrontierOperation
    role: CohortFrontierRole
    context_key: str
    state: str
    issue_codes: tuple[str, ...]
    output: dict[str, Any]
    error: str | None
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record_id")
        require_non_empty(self.context_key, "context_key")
        require_non_empty(self.state, "state")

    @property
    def accepted(self) -> bool:
        return self.state in {"supported", "published"} and not self.error

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class CohortFrontierEvaluationCheck:
    check_id: str
    record_id: str
    check_kind: str
    passed: bool
    expected: Any
    observed: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CohortFrontierEvaluation:
    fixture_id: str
    fixture_version: str
    context_key: str
    executions: tuple[CohortFrontierExecution, ...]
    checks: tuple[CohortFrontierEvaluationCheck, ...]
    positive_record_ids: tuple[str, ...]
    control_record_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def execution_map(self) -> dict[str, CohortFrontierExecution]:
        return {item.record_id: item for item in self.executions}

    def by_operation(self, operation: CohortFrontierOperation) -> tuple[CohortFrontierExecution, ...]:
        return tuple(item for item in self.executions if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted, "passed_checks": self.passed_checks, "failed_check_ids": list(self.failed_check_ids)}


def _execute(record: CohortFrontierRecord) -> CohortFrontierExecution:
    rows = record.payload.get("input_records")
    issues: list[str] = []
    output: dict[str, Any] = {}
    error: str | None = None
    state = "invalid"
    try:
        if not isinstance(rows, list):
            raise ValidationError("input_records must be a list")
        if record.operation is CohortFrontierOperation.SUBGROUP_FAIRNESS:
            if not rows:
                issues.append("empty_fairness_input")
            else:
                report = SubgroupFairnessStratifier().stratify(rows, context_key=record.context_key, maximum_parity_gap=float(record.payload.get("maximum_parity_gap", 0.2)))
                output = report.to_dict()
                if report.review_ids:
                    issues.append("parity_gap_high")
                state = "review" if issues else "supported"
        elif record.operation is CohortFrontierOperation.TRANSPORTABILITY:
            if not rows:
                issues.append("empty_transportability_input")
            else:
                report = TransportabilityEstimator().estimate(rows, context_key=record.context_key, minimum_overlap=float(record.payload.get("minimum_overlap", 0.75)), maximum_shift=float(record.payload.get("maximum_shift", 0.25)))
                output = report.to_dict()
                issues.extend(sorted({issue.code for item in report.estimates for issue in item.issues}))
                state = "review" if issues else "supported"
        elif record.operation is CohortFrontierOperation.FEDERATED_SUMMARY:
            if not rows:
                issues.append("empty_federated_input")
            else:
                report = FederatedSummaryAnalyzer().analyze(rows, context_key=record.context_key, privacy_floor=int(record.payload.get("privacy_floor", 5)))
                output = report.to_dict()
                issues.extend(sorted({issue.code for item in report.summaries for issue in item.issues}))
                state = "review" if issues else "supported"
        elif record.operation is CohortFrontierOperation.COHORT_DISCOVERY:
            if not rows:
                issues.append("empty_cohort_discovery_input")
            else:
                bundle = CohortDiscoveryPublisher().publish(rows, bundle_id=str(record.payload.get("bundle_id", "")), context_key=record.context_key, analysis_ids=tuple(record.payload.get("analysis_ids", ())))
                output = bundle.to_dict()
                state = "published"
        else:
            raise ValidationError("unsupported cohort frontier operation")
    except (TypeError, ValueError, KeyError, ValidationError) as exc:
        error = str(exc)
        issues.append({CohortFrontierOperation.SUBGROUP_FAIRNESS: "invalid_fairness_input", CohortFrontierOperation.TRANSPORTABILITY: "invalid_transportability_input", CohortFrontierOperation.FEDERATED_SUMMARY: "invalid_federated_input", CohortFrontierOperation.COHORT_DISCOVERY: "invalid_cohort_discovery_input"}[record.operation])
        state = "invalid"
    body = {"record_id": record.record_id, "operation": record.operation, "role": record.role, "context_key": record.context_key, "state": state, "issue_codes": tuple(sorted(set(issues))), "output": output, "error": error}
    return CohortFrontierExecution(**body, content_address=content_hash(body))


def execute_cohort_frontier_record(record: CohortFrontierRecord) -> CohortFrontierExecution:
    return _execute(record)


def _check(record: CohortFrontierRecord, execution: CohortFrontierExecution, kind: str, passed: bool, expected: Any, observed: Any, detail: str) -> CohortFrontierEvaluationCheck:
    body = {"check_id": f"{record.record_id}:{kind}", "record_id": record.record_id, "check_kind": kind, "passed": passed, "expected": expected, "observed": observed, "detail": detail}
    return CohortFrontierEvaluationCheck(**body, content_address=content_hash(body))


def _global_check(kind: str, passed: bool, detail: str) -> CohortFrontierEvaluationCheck:
    body = {"check_id": f"global:{kind}", "record_id": "global", "check_kind": kind, "passed": passed, "expected": True, "observed": passed, "detail": detail}
    return CohortFrontierEvaluationCheck(**body, content_address=content_hash(body))


def evaluate_cohort_frontier_fixture(fixture: CohortFrontierFixture | None = None) -> CohortFrontierEvaluation:
    fixture = fixture or default_cohort_frontier_fixture()
    executions: list[CohortFrontierExecution] = []
    checks: list[CohortFrontierEvaluationCheck] = []
    source_ids = {item.source_id for item in fixture.sources}
    for record in fixture.records:
        execution = _execute(record)
        executions.append(execution)
        checks.extend((_check(record, execution, "state", execution.state == record.expected_state, record.expected_state, execution.state, "state matches expectation"), _check(record, execution, "issues", execution.issue_codes == tuple(sorted(record.expected_issue_codes)), tuple(sorted(record.expected_issue_codes)), execution.issue_codes, "issues match expectation"), _check(record, execution, "operation", execution.operation is record.operation, record.operation.value, execution.operation.value, "operation dispatch is stable"), _check(record, execution, "context", execution.context_key == fixture.context_key, fixture.context_key, execution.context_key, "context is retained"), _check(record, execution, "sources", set(record.source_ids) <= source_ids, True, set(record.source_ids) <= source_ids, "source references resolve"), _check(record, execution, "address", bool(execution.content_address), True, bool(execution.content_address), "execution is addressed"), _check(record, execution, "role", (record.role is CohortFrontierRole.POSITIVE) == execution.accepted, record.role.value, execution.accepted, "positive and control semantics remain distinct")))
    positives = tuple(item.record_id for item in fixture.positive_records)
    controls = tuple(item.record_id for item in fixture.control_records)
    checks.extend((_global_check("fixture_id", bool(fixture.fixture_id), "fixture identity exists"), _global_check("fixture_version", fixture.fixture_version.startswith("2026.08."), "fixture version is pinned"), _global_check("context_key", bool(fixture.context_key), "context exists"), _global_check("boundary", fixture.evidence_boundary == "public_aggregate_non_patient", "public boundary exists"), _global_check("execution_count", len(executions) == len(fixture.records), "all records execute"), _global_check("positive_count", len(positives) == 4, "four positive paths"), _global_check("control_count", len(controls) == 12, "twelve controls"), _global_check("operation_count", len({item.operation for item in executions}) == 4, "four operations")))
    body = {"fixture_id": fixture.fixture_id, "fixture_version": fixture.fixture_version, "context_key": fixture.context_key, "executions": tuple(executions), "checks": tuple(checks), "positive_record_ids": positives, "control_record_ids": controls}
    return CohortFrontierEvaluation(**body, content_address=content_hash(body))


__all__ = ["CohortFrontierEvaluation", "CohortFrontierEvaluationCheck", "CohortFrontierExecution", "evaluate_cohort_frontier_fixture", "execute_cohort_frontier_record"]

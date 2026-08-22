"""Replayable positive/control evaluation for causal frontier operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_frontier_public_data import (
    CausalFrontierFixture,
    CausalFrontierOperation,
    CausalFrontierRecord,
    CausalFrontierRole,
    default_causal_frontier_fixture,
)
from .errors import ValidationError
from .frontier_inference_alpha import (
    CausalDossierPublisher,
    PosteriorDecompositionEngine,
    RegulatoryDriverHypothesisPosterior,
    SelectivePredictionAndAbstention,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class CausalFrontierExecution:
    record_id: str
    operation: CausalFrontierOperation
    role: CausalFrontierRole
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
class CausalFrontierEvaluationCheck:
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
class CausalFrontierEvaluation:
    fixture_id: str
    fixture_version: str
    context_key: str
    executions: tuple[CausalFrontierExecution, ...]
    checks: tuple[CausalFrontierEvaluationCheck, ...]
    positive_record_ids: tuple[str, ...]
    control_record_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    @property
    def passed_checks(self) -> int:
        return sum(1 for item in self.checks if item.passed)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def execution_map(self) -> dict[str, CausalFrontierExecution]:
        return {item.record_id: item for item in self.executions}

    def by_operation(self, operation: CausalFrontierOperation) -> tuple[CausalFrontierExecution, ...]:
        return tuple(item for item in self.executions if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "passed_checks": self.passed_checks,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _execute(record: CausalFrontierRecord) -> CausalFrontierExecution:
    rows = record.payload.get("input_records")
    issue_codes: list[str] = []
    error: str | None = None
    output: dict[str, Any] = {}
    state = "invalid"
    try:
        if not isinstance(rows, list):
            raise ValidationError("input_records must be a list")
        if record.operation is CausalFrontierOperation.POSTERIOR_DECOMPOSITION:
            if not rows:
                issue_codes.append("empty_posterior_input")
            else:
                report = PosteriorDecompositionEngine().decompose(rows, context_key=record.context_key)
                output = report.to_dict()
                if not report.components or all(item.raw_posterior <= 0 for item in report.components):
                    issue_codes.append("zero_posterior_mass")
                state = "partial" if issue_codes else "supported"
        elif record.operation is CausalFrontierOperation.DRIVER_POSTERIOR:
            if not rows:
                issue_codes.append("empty_driver_input")
            else:
                report = RegulatoryDriverHypothesisPosterior().infer(
                    rows,
                    context_key=record.context_key,
                    minimum_support=float(record.payload.get("minimum_support", 0.2)),
                )
                output = report.to_dict()
                if any(item.state.value == "review" for item in report.posteriors):
                    issue_codes.append("low_driver_support")
                state = "partial" if issue_codes else "supported"
        elif record.operation is CausalFrontierOperation.SELECTIVE_PREDICTION:
            if not rows:
                issue_codes.append("empty_prediction_input")
            else:
                report = SelectivePredictionAndAbstention().evaluate(
                    rows,
                    context_key=record.context_key,
                    minimum_score=float(record.payload.get("minimum_score", 0.6)),
                    maximum_uncertainty=float(record.payload.get("maximum_uncertainty", 0.25)),
                )
                output = report.to_dict()
                issue_codes.extend(sorted({issue.code for item in report.predictions for issue in item.issues}))
                state = "partial" if issue_codes else "supported"
        elif record.operation is CausalFrontierOperation.DOSSIER_PUBLICATION:
            if not rows:
                issue_codes.append("empty_dossier_input")
            else:
                bundle = CausalDossierPublisher().publish(
                    dossier_id=str(record.payload.get("dossier_id", "")),
                    context_key=record.context_key,
                    hypothesis_ids=tuple(record.payload.get("hypothesis_ids", ())),
                    evidence_addresses=tuple(record.payload.get("evidence_addresses", ())),
                    top_hypothesis_id=str(record.payload.get("top_hypothesis_id", "")),
                )
                output = bundle.to_dict()
                state = "published"
        else:
            raise ValidationError("unsupported causal frontier operation")
    except (TypeError, ValueError, KeyError, ValidationError) as exc:
        error = str(exc)
        issue_codes.append(
            {
                CausalFrontierOperation.POSTERIOR_DECOMPOSITION: "invalid_posterior_input",
                CausalFrontierOperation.DRIVER_POSTERIOR: "invalid_driver_input",
                CausalFrontierOperation.SELECTIVE_PREDICTION: "invalid_prediction_input",
                CausalFrontierOperation.DOSSIER_PUBLICATION: "invalid_dossier_input",
            }[record.operation]
        )
        state = "invalid"
    body = {
        "record_id": record.record_id,
        "operation": record.operation,
        "role": record.role,
        "context_key": record.context_key,
        "state": state,
        "issue_codes": tuple(sorted(set(issue_codes))),
        "output": output,
        "error": error,
    }
    return CausalFrontierExecution(**body, content_address=content_hash(body))


def execute_causal_frontier_record(record: CausalFrontierRecord) -> CausalFrontierExecution:
    """Execute one record through its declared, bounded operation adapter."""

    return _execute(record)


def _check(record: CausalFrontierRecord, execution: CausalFrontierExecution, kind: str, passed: bool, expected: Any, observed: Any, detail: str) -> CausalFrontierEvaluationCheck:
    body = {
        "check_id": f"{record.record_id}:{kind}",
        "record_id": record.record_id,
        "check_kind": kind,
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }
    return CausalFrontierEvaluationCheck(**body, content_address=content_hash(body))


def _global_check(check_kind: str, passed: bool, detail: str) -> CausalFrontierEvaluationCheck:
    body = {
        "check_id": f"global:{check_kind}",
        "record_id": "global",
        "check_kind": check_kind,
        "passed": passed,
        "expected": True,
        "observed": passed,
        "detail": detail,
    }
    return CausalFrontierEvaluationCheck(**body, content_address=content_hash(body))


def evaluate_causal_frontier_fixture(fixture: CausalFrontierFixture | None = None) -> CausalFrontierEvaluation:
    fixture = fixture or default_causal_frontier_fixture()
    executions: list[CausalFrontierExecution] = []
    checks: list[CausalFrontierEvaluationCheck] = []
    source_ids = {source.source_id for source in fixture.sources}
    for record in fixture.records:
        execution = _execute(record)
        executions.append(execution)
        checks.extend(
            (
                _check(record, execution, "state", execution.state == record.expected_state, record.expected_state, execution.state, "state matches fixture expectation"),
                _check(record, execution, "issues", execution.issue_codes == tuple(sorted(record.expected_issue_codes)), tuple(sorted(record.expected_issue_codes)), execution.issue_codes, "issue vocabulary matches fixture expectation"),
                _check(record, execution, "operation", execution.operation is record.operation, record.operation.value, execution.operation.value, "operation dispatch is stable"),
                _check(record, execution, "context", execution.context_key == fixture.context_key, fixture.context_key, execution.context_key, "context is retained"),
                _check(record, execution, "sources", set(record.source_ids) <= source_ids, True, set(record.source_ids) <= source_ids, "source receipts resolve"),
                _check(record, execution, "address", bool(execution.content_address), True, bool(execution.content_address), "execution has a content address"),
                _check(record, execution, "role", (record.role is CausalFrontierRole.POSITIVE) == execution.accepted, record.role.value, execution.accepted, "positive and control semantics remain separated"),
            )
        )
    positives = tuple(item.record_id for item in fixture.positive_records)
    controls = tuple(item.record_id for item in fixture.control_records)
    checks.extend(
        (
            _global_check("fixture_id", bool(fixture.fixture_id), "fixture identity is present"),
            _global_check("fixture_version", fixture.fixture_version.startswith("2026.08."), "fixture version is pinned"),
            _global_check("context_key", bool(fixture.context_key), "fixture context is present"),
            _global_check("boundary", fixture.evidence_boundary == "public_aggregate_non_patient", "public boundary is explicit"),
            _global_check("execution_count", len(executions) == len(fixture.records), "every record executed"),
            _global_check("positive_count", len(positives) == 4, "positive coverage is complete"),
            _global_check("control_count", len(controls) == 12, "control coverage is complete"),
            _global_check("operation_count", len({item.operation for item in executions}) == 4, "all operations executed"),
        )
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "executions": executions,
        "checks": checks,
        "positive_record_ids": positives,
        "control_record_ids": controls,
    }
    return CausalFrontierEvaluation(**body, content_address=content_hash(body))


__all__ = [
    "CausalFrontierEvaluation",
    "CausalFrontierEvaluationCheck",
    "CausalFrontierExecution",
    "evaluate_causal_frontier_fixture",
    "execute_causal_frontier_record",
]

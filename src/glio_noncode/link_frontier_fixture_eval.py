"""Deterministic positive/control evaluation for the Domain 10 link frontier."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .frontier_inference_alpha import (
    LinkCalibrationAndAbstention,
    LinkEvidenceDependenceCorrector,
    LinkEvidencePublisher,
    TargetGeneRanker,
)
from .link_frontier_public_data import (
    LinkFrontierFixture,
    LinkFrontierOperation,
    LinkFrontierRecord,
    LinkFrontierRole,
    default_link_frontier_fixture,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class LinkFrontierExecution:
    record_id: str
    operation: LinkFrontierOperation
    role: LinkFrontierRole
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
class LinkFrontierEvaluationCheck:
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
class LinkFrontierEvaluation:
    fixture_id: str
    fixture_version: str
    context_key: str
    executions: tuple[LinkFrontierExecution, ...]
    checks: tuple[LinkFrontierEvaluationCheck, ...]
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

    def execution_map(self) -> dict[str, LinkFrontierExecution]:
        return {item.record_id: item for item in self.executions}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "passed_checks": self.passed_checks,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _execute(record: LinkFrontierRecord) -> LinkFrontierExecution:
    rows = record.payload.get("input_records")
    issue_codes: list[str] = []
    error: str | None = None
    output: dict[str, Any] = {}
    state = "invalid"
    try:
        if not isinstance(rows, list):
            raise ValidationError("input_records must be a list")
        if record.operation is LinkFrontierOperation.DEPENDENCE_CORRECTION:
            if not rows:
                issue_codes.append("empty_dependence_input")
            else:
                report = LinkEvidenceDependenceCorrector().correct(rows, context_key=record.context_key)
                output = report.to_dict()
                zero = tuple(item.link_id for item in report.links if item.corrected_support <= 0)
                if zero:
                    issue_codes.append("zero_corrected_support")
                state = "partial" if issue_codes else "supported"
        elif record.operation is LinkFrontierOperation.TARGET_GENE_RANKING:
            if not rows:
                issue_codes.append("empty_rank_input")
            else:
                report = TargetGeneRanker().rank(rows, context_key=record.context_key)
                output = report.to_dict()
                if any(item.total_score <= 0 for item in report.ranks):
                    issue_codes.append("zero_rank_support")
                state = "partial" if issue_codes else "supported"
        elif record.operation is LinkFrontierOperation.CALIBRATION_ABSTENTION:
            if not rows:
                issue_codes.append("empty_calibration_input")
            else:
                report = LinkCalibrationAndAbstention().evaluate(
                    rows,
                    context_key=record.context_key,
                    maximum_uncertainty=float(record.payload.get("maximum_uncertainty", 0.25)),
                    maximum_calibration_error=float(record.payload.get("maximum_calibration_error", 0.30)),
                )
                output = report.to_dict()
                issue_codes.extend(
                    sorted({issue.code for item in report.decisions for issue in item.issues})
                )
                state = "partial" if issue_codes else "supported"
        elif record.operation is LinkFrontierOperation.EVIDENCE_PUBLICATION:
            if not rows:
                issue_codes.append("empty_publication_input")
            else:
                bundle_id = str(record.payload.get("bundle_id", ""))
                bundle = LinkEvidencePublisher().publish(
                    rows,
                    bundle_id=bundle_id,
                    context_key=record.context_key,
                )
                output = bundle.to_dict()
                state = "published"
        else:
            raise ValidationError("unsupported link frontier operation")
    except (TypeError, ValueError, KeyError, ValidationError) as exc:
        error = str(exc)
        if record.operation is LinkFrontierOperation.EVIDENCE_PUBLICATION and "context" in error.lower():
            issue_codes.append("publication_context_mismatch")
        elif record.operation is LinkFrontierOperation.TARGET_GENE_RANKING:
            issue_codes.append("invalid_rank_input")
        elif record.operation is LinkFrontierOperation.DEPENDENCE_CORRECTION:
            issue_codes.append("invalid_dependence_input")
        elif record.operation is LinkFrontierOperation.CALIBRATION_ABSTENTION:
            issue_codes.append("invalid_calibration_input")
        else:
            issue_codes.append("invalid_publication_input")
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
    return LinkFrontierExecution(**body, content_address=content_hash(body))


def execute_link_frontier_record(record: LinkFrontierRecord) -> LinkFrontierExecution:
    """Execute one fixture record through its declared link operation."""

    return _execute(record)


def _check(
    record: LinkFrontierRecord,
    execution: LinkFrontierExecution,
    kind: str,
    passed: bool,
    expected: Any,
    observed: Any,
    detail: str,
) -> LinkFrontierEvaluationCheck:
    body = {
        "check_id": f"{record.record_id}:{kind}",
        "record_id": record.record_id,
        "check_kind": kind,
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }
    return LinkFrontierEvaluationCheck(**body, content_address=content_hash(body))


def evaluate_link_frontier_fixture(
    fixture: LinkFrontierFixture | None = None,
) -> LinkFrontierEvaluation:
    fixture = fixture or default_link_frontier_fixture()
    executions: list[LinkFrontierExecution] = []
    checks: list[LinkFrontierEvaluationCheck] = []
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
                _check(record, execution, "role", (record.role is LinkFrontierRole.POSITIVE) == execution.accepted, record.role.value, execution.accepted, "positive and control semantics remain separated"),
            )
        )
    positive_ids = tuple(item.record_id for item in fixture.positive_records)
    control_ids = tuple(item.record_id for item in fixture.control_records)
    global_checks = [
        _global_check("fixture_id", bool(fixture.fixture_id), "fixture identity is present"),
        _global_check("fixture_version", fixture.fixture_version.startswith("2026.08."), "fixture version is pinned"),
        _global_check("context_key", bool(fixture.context_key), "fixture context is present"),
        _global_check("boundary", fixture.evidence_boundary == "public_aggregate_non_patient", "public boundary is explicit"),
        _global_check("execution_count", len(executions) == len(fixture.records), "every record executed"),
        _global_check("positive_count", len(positive_ids) == 4, "positive coverage is complete"),
        _global_check("control_count", len(control_ids) == 12, "control coverage is complete"),
        _global_check("operation_count", len({item.operation for item in executions}) == 4, "all four operations executed"),
    ]
    checks.extend(global_checks)
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "executions": executions,
        "checks": checks,
        "positive_record_ids": positive_ids,
        "control_record_ids": control_ids,
    }
    return LinkFrontierEvaluation(**body, content_address=content_hash(body))


def _global_check(check_kind: str, passed: bool, detail: str) -> LinkFrontierEvaluationCheck:
    body = {
        "check_id": f"global:{check_kind}",
        "record_id": "global",
        "check_kind": check_kind,
        "passed": passed,
        "expected": True,
        "observed": passed,
        "detail": detail,
    }
    return LinkFrontierEvaluationCheck(**body, content_address=content_hash(body))


__all__ = [
    "LinkFrontierEvaluation",
    "LinkFrontierEvaluationCheck",
    "LinkFrontierExecution",
    "evaluate_link_frontier_fixture",
    "execute_link_frontier_record",
]

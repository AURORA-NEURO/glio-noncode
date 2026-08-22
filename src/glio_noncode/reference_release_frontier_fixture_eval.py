"""Execution and expected-state accounting for the C13-C16 fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import (
    AnnotationDriftDetector,
    ReferenceReleaseGate,
    ReproducibleReferenceBundleBuilder,
    SourceProvenanceChecker,
)
from .reference_release_frontier_public_data import (
    REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY,
    ReferenceReleaseFixture,
    ReferenceReleaseOperation,
    ReferenceReleaseRecord,
    ReferenceReleaseRole,
    default_reference_release_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ReferenceReleaseExecution:
    """One deterministic adapter receipt with sanitized output."""

    record_id: str
    operation: ReferenceReleaseOperation
    role: ReferenceReleaseRole
    state: str
    accepted: bool
    issue_codes: tuple[str, ...]
    output: dict[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseEvaluationCheck:
    """One expected-versus-observed receipt assertion."""

    check_id: str
    record_id: str | None
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseEvaluation:
    """Complete positive/control evaluation and stable execution indexes."""

    fixture_id: str
    executions: tuple[ReferenceReleaseExecution, ...]
    checks: tuple[ReferenceReleaseEvaluationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    @property
    def positive_count(self) -> int:
        return sum(item.role is ReferenceReleaseRole.POSITIVE for item in self.executions)

    @property
    def control_count(self) -> int:
        return sum(item.role is ReferenceReleaseRole.CONTROL for item in self.executions)

    def execution_map(self) -> dict[str, ReferenceReleaseExecution]:
        return {item.record_id: item for item in self.executions}

    def by_operation(
        self, operation: ReferenceReleaseOperation
    ) -> tuple[ReferenceReleaseExecution, ...]:
        return tuple(item for item in self.executions if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_checks": self.passed_checks,
            "failed_check_ids": list(self.failed_check_ids),
            "positive_count": self.positive_count,
            "control_count": self.control_count,
        }


def _execution(
    record: ReferenceReleaseRecord,
    state: str,
    output: dict[str, Any],
    issue_codes: tuple[str, ...],
) -> ReferenceReleaseExecution:
    issue_codes = tuple(sorted(set(issue_codes)))
    body = {
        "record_id": record.record_id,
        "operation": record.operation,
        "role": record.role,
        "state": state,
        "accepted": state in {"accepted", "published"},
        "issue_codes": issue_codes,
        "output": output,
    }
    return ReferenceReleaseExecution(**body, content_address=content_hash(body))


def _provenance(record: ReferenceReleaseRecord, context_key: str) -> ReferenceReleaseExecution:
    payload = record.payload
    report = SourceProvenanceChecker().check(
        payload.get("records", ()),
        context_key=context_key,
        require_checksum_match=bool(payload.get("require_checksum_match", True)),
    )
    issues = tuple(sorted({issue.code for item in report.checks for issue in item.issues}))
    state = "accepted" if not report.review_ids else "review"
    output = {
        "state": state,
        "check_count": len(report.checks),
        "compatible_ids": report.compatible_ids,
        "review_ids": report.review_ids,
        "checksum_matches": tuple(item.checksum_matches for item in report.checks),
        "issue_codes": issues,
        "report_address": report.content_address,
    }
    return _execution(record, state, output, issues)


def _drift(record: ReferenceReleaseRecord, context_key: str) -> ReferenceReleaseExecution:
    payload = record.payload
    report = AnnotationDriftDetector().compare(
        payload.get("previous", ()),
        payload.get("current", ()),
        context_key=context_key,
        identity_field=str(payload.get("identity_field", "annotation_id")),
        ignored_fields=tuple(payload.get("ignored_fields", ("retrieved_at", "source_uri"))),
        drift_threshold=float(payload.get("drift_threshold", 0.2)),
    )
    output = {
        "state": "drift" if report.drifted_ids else "accepted",
        "finding_count": len(report.findings),
        "drifted_ids": report.drifted_ids,
        "stable_ids": report.stable_ids,
        "changed_fields": tuple(
            {
                "annotation_id": item.annotation_id,
                "fields": item.changed_fields,
                "score": item.change_score,
            }
            for item in report.findings
        ),
        "report_address": report.content_address,
    }
    return _execution(record, output["state"], output, ())


def _bundle_error_code(error: str) -> str:
    lowered = error.casefold()
    if "context" in lowered:
        return "bundle_context_mismatch"
    if "available" in lowered:
        return "bundle_unavailable"
    if "reference_id" in lowered:
        return "bundle_missing_reference_id"
    if "schema_hash" in lowered:
        return "bundle_schema_missing"
    return "bundle_validation_error"


def _bundle(record: ReferenceReleaseRecord, context_key: str) -> ReferenceReleaseExecution:
    payload = record.payload
    try:
        bundle = ReproducibleReferenceBundleBuilder().build(
            payload.get("records", ()),
            bundle_id=str(payload.get("bundle_id", f"bundle:{record.record_id}")),
            context_key=context_key,
            schema_hash=str(payload.get("schema_hash", "")),
            require_available=bool(payload.get("require_available", True)),
        )
    except (TypeError, ValueError, ValidationError, KeyError) as exc:
        code = _bundle_error_code(str(exc))
        return _execution(
            record,
            "blocked",
            {"state": "blocked", "error_type": type(exc).__name__, "error_code": code},
            (code,),
        )
    output = {
        "state": bundle.state.value,
        "bundle_id": bundle.bundle_id,
        "reference_ids": bundle.reference_ids,
        "record_count": len(bundle.records),
        "schema_hash": bundle.schema_hash,
        "bundle_address": bundle.bundle_address,
    }
    return _execution(record, bundle.state.value, output, ())


def _gate(record: ReferenceReleaseRecord, context_key: str) -> ReferenceReleaseExecution:
    payload = record.payload
    decision = ReferenceReleaseGate().evaluate(
        release_id=str(payload.get("release_id", f"release:{record.record_id}")),
        context_key=context_key,
        bundle_address=str(payload.get("bundle_address", "")),
        checks=payload.get("checks", {}),
        required_checks=tuple(
            payload.get("required_checks", ("checksum", "schema", "license", "context", "source"))
        ),
    )
    issues = tuple(sorted({issue.code for issue in decision.issues}))
    output = {
        "state": decision.state.value,
        "release_id": decision.release_id,
        "bundle_address": decision.bundle_address,
        "checks": decision.checks,
        "failed_checks": decision.failed_checks,
        "issue_codes": issues,
    }
    return _execution(record, decision.state.value, output, issues)


def execute_reference_release_record(
    record: ReferenceReleaseRecord,
    *,
    context_key: str = REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY,
) -> ReferenceReleaseExecution:
    """Execute one record against the bounded reference-release primitives."""

    try:
        if record.operation is ReferenceReleaseOperation.PROVENANCE_CHECK:
            return _provenance(record, context_key)
        if record.operation is ReferenceReleaseOperation.ANNOTATION_DRIFT:
            return _drift(record, context_key)
        if record.operation is ReferenceReleaseOperation.REFERENCE_BUNDLE:
            return _bundle(record, context_key)
        if record.operation is ReferenceReleaseOperation.RELEASE_GATE:
            return _gate(record, context_key)
    except (TypeError, ValueError, ValidationError, KeyError) as exc:
        return _execution(
            record,
            "blocked",
            {"state": "blocked", "error_type": type(exc).__name__},
            ("invalid_surface_input",),
        )
    raise ValueError(f"unsupported reference release operation: {record.operation}")


def _check(
    index: int, record_id: str | None, passed: bool, observed: Any, required: Any, detail: str
) -> ReferenceReleaseEvaluationCheck:
    body = {
        "check_id": f"release-check-{index:03d}",
        "record_id": record_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceReleaseEvaluationCheck(**body, content_address=content_hash(body))


def evaluate_reference_release_fixture(
    fixture: ReferenceReleaseFixture | None = None,
) -> ReferenceReleaseEvaluation:
    """Execute all 16 records and compare state, issues, and addresses."""

    fixture = fixture or default_reference_release_fixture()
    executions: list[ReferenceReleaseExecution] = []
    checks: list[ReferenceReleaseEvaluationCheck] = []
    index = 1
    for record in fixture.records:
        result = execute_reference_release_record(record, context_key=fixture.context_key)
        executions.append(result)
        checks.append(
            _check(
                index,
                record.record_id,
                result.state == record.expected_state,
                result.state,
                record.expected_state,
                "surface state matches fixture expectation",
            )
        )
        index += 1
        checks.append(
            _check(
                index,
                record.record_id,
                result.issue_codes == tuple(sorted(record.expected_issue_codes)),
                result.issue_codes,
                tuple(sorted(record.expected_issue_codes)),
                "issue vocabulary matches fixture expectation",
            )
        )
        index += 1
        checks.append(
            _check(
                index,
                record.record_id,
                result.content_address.startswith("sha256:"),
                result.content_address,
                "sha256:",
                "execution receipt is content addressed",
            )
        )
        index += 1
    accepted = all(item.passed for item in checks)
    body = {
        "fixture_id": fixture.fixture_id,
        "executions": tuple(executions),
        "checks": tuple(checks),
        "accepted": accepted,
    }
    return ReferenceReleaseEvaluation(**body, content_address=content_hash(body))


__all__ = [
    "ReferenceReleaseEvaluation",
    "ReferenceReleaseEvaluationCheck",
    "ReferenceReleaseExecution",
    "evaluate_reference_release_fixture",
    "execute_reference_release_record",
]

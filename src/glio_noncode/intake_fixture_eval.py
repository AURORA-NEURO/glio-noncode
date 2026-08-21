"""Executable public-fixture evidence for Domain 01 intake operations.

The fixture evaluator runs each positive envelope through the existing intake
adapter and then runs every negative control through the same path.  It does
not infer consent, repair malformed rows, or silently downgrade a blocked
bundle.  Instead, each operation result is wrapped with a stable state and a
trace receipt so a review can compare the declared expectation with the
observed behavior.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import GlioError, ValidationError
from .frontier_data_alpha import (
    ConsentPolicyAttacher,
    DataCompletenessScorer,
    InputAnomalyQuarantine,
    IntakeBundleExporter,
)
from .intake_public_data import (
    INTAKE_FIXTURE_SCHEMA_VERSION,
    IntakeDataState,
    IntakeFixtureCatalog,
    IntakeFixtureControl,
    IntakeFixtureRecord,
    IntakeRecordKind,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class IntakeOperationFailure:
    """Safe review receipt for an operation that rejects its input envelope."""

    state: str
    error_code: str
    operation: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeFixtureCheck:
    """One expected state, trace, issue, or boundary assertion."""

    check_id: str
    expected: Any
    observed: Any
    passed: bool
    detail: str
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.check_id, "check_id")
        require_non_empty(self.detail, "detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeFixtureEvaluationReport:
    """Complete operation and review-boundary result for a fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    data_report: Mapping[str, Any]
    positive_reports: Mapping[str, Mapping[str, Any]]
    negative_reports: Mapping[str, Mapping[str, Any]]
    checks: tuple[IntakeFixtureCheck, ...]
    passed_check_ids: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    evidence_boundary: str
    state: IntakeDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == IntakeDataState.ACCEPTED and not self.failed_check_ids

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["check_count"] = len(self.checks)
        result["passed_count"] = len(self.passed_check_ids)
        result["failed_count"] = len(self.failed_check_ids)
        return result


class IntakeFixtureEvaluator:
    """Run four Domain 01 intake adapters against one checked-in fixture."""

    _expected_kinds = set(IntakeRecordKind)

    def load_file(self, path: str | Path) -> Mapping[str, Any]:
        fixture_path = Path(path)
        try:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValidationError(f"unable to read intake fixture: {fixture_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"intake fixture is not valid JSON: {fixture_path}") from exc
        if not isinstance(raw, Mapping):
            raise ValidationError("intake fixture must be an object")
        self.validate_fixture(raw)
        return raw

    def validate_fixture(self, raw: Mapping[str, Any]) -> IntakeFixtureCatalog:
        catalog = IntakeFixtureCatalog.from_fixture(raw)
        if catalog.fixture_version != INTAKE_FIXTURE_SCHEMA_VERSION:
            raise ValidationError(
                f"fixture_version must be {INTAKE_FIXTURE_SCHEMA_VERSION}, "
                f"received {catalog.fixture_version}"
            )
        if not catalog.records:
            raise ValidationError("intake fixture must declare positive records")
        observed_kinds = {record.kind for record in catalog.records}
        missing_kinds = self._expected_kinds - observed_kinds
        if missing_kinds:
            raise ValidationError(
                "intake fixture is missing record kinds: "
                + ", ".join(sorted(kind.value for kind in missing_kinds))
            )
        if len(catalog.records) != len(self._expected_kinds):
            raise ValidationError(
                "intake fixture must contain exactly one positive record per capability"
            )
        if not catalog.controls:
            raise ValidationError("intake fixture must declare negative controls")
        operations = {record.operation for record in catalog.records}
        if len(operations) != len(catalog.records):
            raise ValidationError("intake positive records must use distinct operations")
        return catalog

    def evaluate_file(self, path: str | Path) -> IntakeFixtureEvaluationReport:
        return self.evaluate(self.load_file(path))

    def evaluate(self, raw: Mapping[str, Any]) -> IntakeFixtureEvaluationReport:
        catalog = self.validate_fixture(raw)
        data_report = catalog.audit()
        context = _context_mapping(raw.get("context"))
        context_key = catalog.context_key
        checks: list[IntakeFixtureCheck] = []
        positive_reports: dict[str, Mapping[str, Any]] = {}
        negative_reports: dict[str, Mapping[str, Any]] = {}
        self._append_check(
            checks,
            "data-boundary:intake-catalog",
            True,
            data_report.accepted,
            "public policy and aggregate records have exact context and source receipts",
            data_report.to_dict(),
        )
        for record in catalog.records:
            output = self._run_record(record, context, context_key)
            serialized = self._receipt(record, output)
            positive_reports[record.record_id] = serialized
            observed = _state_value(serialized)
            self._append_check(
                checks,
                f"positive:{record.record_id}",
                record.expected_state,
                observed,
                "intake operation returned the declared positive state",
                serialized,
            )
            self._append_check(
                checks,
                f"trace:{record.record_id}",
                True,
                record.public_identifier in json.dumps(serialized, sort_keys=True),
                "public identifier remains traceable in the operation receipt",
                serialized,
            )
            self._append_check(
                checks,
                f"address:{record.record_id}",
                True,
                _has_address(serialized),
                "intake operation output is content-addressed",
                serialized,
            )
        for control in catalog.controls:
            output = self._run_record(control.as_record(), context, context_key)
            serialized = self._receipt(control, output)
            negative_reports[control.control_id] = serialized
            observed = _state_value(serialized)
            self._append_check(
                checks,
                f"negative:{control.control_id}",
                control.expected_state,
                observed,
                "negative control retains its declared review or blocking state",
                serialized,
            )
            issue_codes = _issue_codes(serialized)
            self._append_check(
                checks,
                f"negative-issues:{control.control_id}",
                True,
                all(code in issue_codes for code in control.required_issue_codes),
                "negative control exposes every required structured reason code",
                {"issue_codes": issue_codes, "result": serialized},
            )
        expected_negative_count = int(
            raw.get("expected_negative_control_count", len(catalog.controls))
        )
        self._append_check(
            checks,
            "negative-control-floor",
            expected_negative_count,
            len(negative_reports),
            "all declared intake review controls were executed",
            negative_reports,
        )
        repeated = self._run_record(catalog.records[0], context, context_key)
        first_address = _content_address(positive_reports[catalog.records[0].record_id])
        second_address = _content_address(self._receipt(catalog.records[0], repeated))
        self._append_check(
            checks,
            "deterministic:intake-first-record",
            True,
            first_address == second_address,
            "repeated operation evaluation produces one stable receipt address",
            {"first": first_address, "second": second_address},
        )
        serialized_all = json.dumps(
            {"positive": positive_reports, "negative": negative_reports}, sort_keys=True
        ).casefold()
        restricted_fragments = (
            "patient_id",
            "medical_record",
            "mrn",
            "email",
            "password",
            "secret",
            "private_key",
        )
        self._append_check(
            checks,
            "output-boundary:intake",
            False,
            any(fragment in serialized_all for fragment in restricted_fragments),
            "operation receipts do not expose restricted fixture fields",
            {"restricted_output": serialized_all},
        )
        self._append_check(
            checks,
            "operation-kind-floor:intake",
            sorted(kind.value for kind in self._expected_kinds),
            sorted(record.kind.value for record in catalog.records),
            "each C13-C16 operation has one positive fixture record",
            {"kinds": tuple(sorted(record.kind.value for record in catalog.records))},
        )
        passed_ids = tuple(check.check_id for check in checks if check.passed)
        failed_ids = tuple(check.check_id for check in checks if not check.passed)
        state = IntakeDataState.ACCEPTED if not failed_ids else IntakeDataState.REVIEW
        boundary = require_non_empty(
            str(catalog.provenance.get("evidence_boundary", "")),
            "provenance.evidence_boundary",
        )
        body = {
            "fixture_id": catalog.fixture_id,
            "fixture_version": catalog.fixture_version,
            "context_key": context_key,
            "source_ids": tuple(sorted(source.source_id for source in catalog.sources)),
            "data_report": data_report,
            "positive_reports": positive_reports,
            "negative_reports": negative_reports,
            "checks": checks,
        }
        return IntakeFixtureEvaluationReport(
            catalog.fixture_id,
            catalog.fixture_version,
            context_key,
            tuple(sorted(source.source_id for source in catalog.sources)),
            data_report.to_dict(),
            positive_reports,
            negative_reports,
            tuple(checks),
            passed_ids,
            failed_ids,
            boundary,
            state,
            content_hash(body),
        )

    def run_record(
        self,
        record: IntakeFixtureRecord,
        context: Mapping[str, str],
        context_key: str,
    ) -> Any:
        """Run one validated record for scenario and integration inspection."""

        return self._run_record(record, context, context_key)

    @staticmethod
    def _append_check(
        checks: list[IntakeFixtureCheck],
        check_id: str,
        expected: Any,
        observed: Any,
        detail: str,
        receipt: Any,
    ) -> None:
        passed = bool(observed) == expected if isinstance(expected, bool) else observed == expected
        checks.append(
            IntakeFixtureCheck(
                check_id,
                expected,
                observed,
                passed,
                detail,
                _content_address(receipt),
            )
        )

    def _receipt(
        self,
        envelope: IntakeFixtureRecord | IntakeFixtureControl,
        output: Any,
    ) -> dict[str, Any]:
        serialized = _serialize_output(output)
        return {
            "record_id": envelope.record_id
            if isinstance(envelope, IntakeFixtureRecord)
            else f"negative:{envelope.control_id}",
            "kind": envelope.kind.value,
            "operation": envelope.operation,
            "public_identifier": envelope.public_identifier,
            "state": _state_value(output),
            "operation_output": serialized,
            "content_address": _content_address(serialized),
        }

    def _run_record(
        self,
        record: IntakeFixtureRecord,
        context: Mapping[str, str],
        context_key: str,
    ) -> Any:
        """Dispatch a record to the exact existing adapter contract."""

        payload = record.payload
        try:
            if record.kind == IntakeRecordKind.CONSENT:
                return ConsentPolicyAttacher().attach(
                    _rows(payload.get("records", ()), "records"),
                    context_key=context_key,
                    policy_id=str(payload.get("policy_id", "")),
                    policy_version=str(payload.get("policy_version", "")),
                    purpose=str(payload.get("purpose", "")),
                    permitted_uses=tuple(str(item) for item in payload.get("permitted_uses", ())),
                    source_id=record.source_id,
                )
            if record.kind == IntakeRecordKind.ANOMALY:
                return InputAnomalyQuarantine().inspect(
                    _rows(payload.get("records", ()), "records"),
                    context_key=context_key,
                    source_id=record.source_id,
                    allowed_bases=str(payload.get("allowed_bases", "ACGTN")),
                )
            if record.kind == IntakeRecordKind.COMPLETENESS:
                weights = payload.get("weights", {})
                if not isinstance(weights, Mapping):
                    raise ValidationError("completeness weights must be an object")
                return DataCompletenessScorer().score(
                    _rows(payload.get("records", ()), "records"),
                    context_key=context_key,
                    required_fields=tuple(
                        str(item) for item in payload.get("required_fields", ())
                    ),
                    weights={str(key): float(value) for key, value in weights.items()},
                    minimum_score=float(payload.get("minimum_score", 0.8)),
                    source_id=record.source_id,
                )
            if record.kind == IntakeRecordKind.BUNDLE:
                source_ids = tuple(str(item) for item in payload.get("source_ids", ()))
                return IntakeBundleExporter().export(
                    _rows(payload.get("records", ()), "records"),
                    bundle_id=str(payload.get("bundle_id", "")),
                    context_key=context_key,
                    source_ids=source_ids,
                    require_accepted=bool(payload.get("require_accepted", True)),
                )
            raise ValidationError(f"unsupported intake record kind: {record.kind.value}")
        except (GlioError, TypeError, ValueError) as exc:
            error_code = getattr(exc, "code", "validation_error")
            return IntakeOperationFailure(
                state="review",
                error_code=str(error_code),
                operation=record.operation,
                detail="operation input was rejected by its declared contract",
                content_address=content_hash(
                    {
                        "operation": record.operation,
                        "error_code": str(error_code),
                        "state": "review",
                    }
                ),
            )


def _rows(value: Any, field: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValidationError(f"{field} must be an array")
    rows: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise ValidationError(f"{field}[{index}] must be an object")
        rows.append(item)
    return tuple(rows)


def _serialize_output(output: Any) -> dict[str, Any]:
    if hasattr(output, "to_dict"):
        value = output.to_dict()
    elif isinstance(output, Mapping):
        value = dict(output)
    else:
        value = {"value": output}
    if not isinstance(value, Mapping):
        return {"value": jsonable(value)}
    return jsonable(dict(value))


def _state_value(value: Any) -> str:
    if isinstance(value, Mapping):
        if isinstance(value.get("state"), str):
            return value["state"]
        if isinstance(value.get("state"), Mapping):
            return _state_value(value["state"])
        operation_output = value.get("operation_output")
        if operation_output is not None:
            return _state_value(operation_output)
        if value.get("blocked_record_ids"):
            return "blocked"
        if value.get("quarantined_record_ids"):
            return "quarantined"
        if value.get("review_record_ids"):
            return "review"
        if value.get("accepted_record_ids"):
            return "accepted"
        if value.get("record_count") is not None and value.get("content_address"):
            return "published"
    state = getattr(value, "state", None)
    if state is not None:
        return str(getattr(state, "value", state))
    if getattr(value, "blocked_record_ids", ()):
        return "blocked"
    if getattr(value, "quarantined_record_ids", ()):
        return "quarantined"
    if getattr(value, "review_record_ids", ()):
        return "review"
    if getattr(value, "accepted_record_ids", ()):
        return "accepted"
    if getattr(value, "content_address", None) and getattr(value, "record_count", None) is not None:
        return "published"
    return "review"


def _issue_codes(value: Any) -> tuple[str, ...]:
    codes: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {"code", "error_code"} and isinstance(child, str):
                codes.append(child)
            else:
                codes.extend(_issue_codes(child))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            codes.extend(_issue_codes(child))
    return tuple(sorted(set(codes)))


def _has_address(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            (isinstance(key, str) and "address" in key and isinstance(child, str) and child.startswith("sha256:"))
            or _has_address(child)
            for key, child in value.items()
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_has_address(child) for child in value)
    return False


def _content_address(value: Any) -> str:
    return content_hash(jsonable(value))


def _context_mapping(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise ValidationError("intake fixture context must be an object")
    fields = (
        "genome_build",
        "disease_class",
        "age_group",
        "cell_state",
        "territory",
        "treatment_phase",
    )
    return {
        field: require_non_empty(str(value.get(field, "")), f"context.{field}")
        for field in fields
    }


def evaluate_intake_fixture(path: str | Path) -> IntakeFixtureEvaluationReport:
    """Run the checked-in public aggregate intake fixture."""

    return IntakeFixtureEvaluator().evaluate_file(path)


__all__ = [
    "IntakeFixtureCheck",
    "IntakeFixtureEvaluationReport",
    "IntakeFixtureEvaluator",
    "IntakeOperationFailure",
    "evaluate_intake_fixture",
]

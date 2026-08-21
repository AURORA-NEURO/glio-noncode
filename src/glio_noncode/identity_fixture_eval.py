"""Executable public-aggregate evidence for Domain 01 identity operations.

The evaluator exercises the existing identity beta adapters through one
fixture. It checks supported results, reviewable partial results, explicit
out-of-domain handling, validation abstention, deterministic receipts, and
the absence of restricted output fields independently of the unit tests for
the individual adapters.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .identity_beta import (
    BatchSampleIdentityChecker,
    ChainOfCustodyCapture,
    DuplicateAliasReconciler,
    VariantEquivalenceResolver,
)
from .identity_public_data import (
    IDENTITY_FIXTURE_SCHEMA_VERSION,
    IdentityDataState,
    IdentityFixtureCatalog,
    IdentityFixtureControl,
    IdentityFixtureRecord,
    IdentityRecordKind,
)
from .serialization import content_hash, jsonable, require_non_empty


@dataclass(frozen=True, slots=True)
class IdentityOperationFailure:
    """Serializable validation abstention for a malformed review control."""

    state: str
    error_code: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IdentityFixtureCheck:
    """One expected state, signal, or output-boundary assertion."""

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
class IdentityFixtureEvaluationReport:
    """Complete operation and review-boundary result for one fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    data_report: Mapping[str, Any]
    positive_reports: Mapping[str, Mapping[str, Any]]
    negative_reports: Mapping[str, Mapping[str, Any]]
    checks: tuple[IdentityFixtureCheck, ...]
    passed_check_ids: tuple[str, ...]
    failed_check_ids: tuple[str, ...]
    evidence_boundary: str
    state: IdentityDataState
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == IdentityDataState.ACCEPTED and not self.failed_check_ids

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["passed"] = self.passed
        result["check_count"] = len(self.checks)
        result["passed_count"] = len(self.passed_check_ids)
        result["failed_count"] = len(self.failed_check_ids)
        return result


class IdentityFixtureEvaluator:
    """Run four public identity operation families through one fixture."""

    _expected_kinds = {
        IdentityRecordKind.EQUIVALENCE,
        IdentityRecordKind.RECONCILIATION,
        IdentityRecordKind.SAMPLE,
        IdentityRecordKind.CUSTODY,
    }

    def load_file(self, path: str | Path) -> Mapping[str, Any]:
        fixture_path = Path(path)
        try:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"identity fixture is not valid JSON: {fixture_path}") from exc
        if not isinstance(raw, Mapping):
            raise ValidationError("identity fixture must be an object")
        self.validate_fixture(raw)
        return raw

    def validate_fixture(self, raw: Mapping[str, Any]) -> IdentityFixtureCatalog:
        catalog = IdentityFixtureCatalog.from_fixture(raw)
        if catalog.fixture_version != IDENTITY_FIXTURE_SCHEMA_VERSION:
            raise ValidationError(
                f"fixture_version must be {IDENTITY_FIXTURE_SCHEMA_VERSION}, "
                f"received {catalog.fixture_version}"
            )
        if not catalog.records:
            raise ValidationError("identity fixture must declare positive records")
        observed_kinds = {record.kind for record in catalog.records}
        missing_kinds = self._expected_kinds - observed_kinds
        if missing_kinds:
            raise ValidationError(
                "identity fixture is missing record kinds: "
                + ", ".join(sorted(kind.value for kind in missing_kinds))
            )
        if not catalog.controls:
            raise ValidationError("identity fixture must declare negative controls")
        return catalog

    def evaluate_file(self, path: str | Path) -> IdentityFixtureEvaluationReport:
        raw = self.load_file(path)
        return self.evaluate(raw)

    def evaluate(self, raw: Mapping[str, Any]) -> IdentityFixtureEvaluationReport:
        catalog = self.validate_fixture(raw)
        data_report = catalog.audit()
        context_key = catalog.context_key
        checks: list[IdentityFixtureCheck] = []
        positive_reports: dict[str, Mapping[str, Any]] = {}
        negative_reports: dict[str, Mapping[str, Any]] = {}
        self._append_check(
            checks,
            "data-boundary:identity-catalog",
            True,
            data_report.accepted,
            (
                "public aggregate identity records have source receipts, exact context, "
                "and no restricted paths"
            ),
            data_report.to_dict(),
        )
        for record in catalog.records:
            output = self.run_record(record, context_key)
            serialized = _serialize_output(output)
            positive_reports[record.record_id] = serialized
            observed = _state_value(output)
            self._append_check(
                checks,
                f"positive:{record.record_id}",
                record.expected_state,
                observed,
                f"{record.kind.value} operation returned the declared fixture state",
                serialized,
            )
            self._append_check(
                checks,
                f"trace:{record.record_id}",
                True,
                record.public_identifier in json.dumps(record.payload, sort_keys=True),
                "public aggregate identifier is traceable in the operation input envelope",
                {"public_identifier": record.public_identifier, "payload": record.payload},
            )
            self._append_check(
                checks,
                f"address:{record.record_id}",
                True,
                _has_address(serialized),
                "operation output is content-addressed",
                serialized,
            )
            self._append_check(
                checks,
                f"signals:{record.record_id}",
                True,
                _signals_match(record.expected_signals, serialized),
                "positive operation exposes all declared structural signals",
                {"expected": record.expected_signals, "observed": _observed_signals(serialized)},
            )
        for control in catalog.controls:
            output = self.run_control(control, context_key)
            serialized = _serialize_output(output)
            negative_reports[control.control_id] = serialized
            self._append_check(
                checks,
                f"negative:{control.control_id}",
                control.expected_state,
                _state_value(output),
                "negative control retains its declared review or abstention state",
                serialized,
            )
            self._append_check(
                checks,
                f"negative-signals:{control.control_id}",
                True,
                _signals_match(control.expected_signals, serialized),
                "negative control exposes its required structured signal set",
                {"expected": control.expected_signals, "observed": _observed_signals(serialized)},
            )
        self._append_check(
            checks,
            "positive-record-floor",
            len(catalog.records),
            len(positive_reports),
            "all declared identity operation records were executed",
            positive_reports,
        )
        expected_negative_count = int(
            raw.get("expected_negative_control_count", len(catalog.controls))
        )
        self._append_check(
            checks,
            "negative-control-floor",
            expected_negative_count,
            len(negative_reports),
            "all declared identity review controls were executed",
            negative_reports,
        )
        first_record = catalog.records[0]
        repeated = self.run_record(first_record, context_key)
        first_address = _content_address(positive_reports[first_record.record_id])
        second_address = _content_address(_serialize_output(repeated))
        self._append_check(
            checks,
            "deterministic:identity-first-record",
            True,
            first_address == second_address,
            "repeated evaluation produces one operation content address",
            {"first": first_address, "second": second_address},
        )
        serialized_all = json.dumps(
            {"positive": positive_reports, "negative": negative_reports}, sort_keys=True
        ).casefold()
        self._append_check(
            checks,
            "output-boundary:identity",
            False,
            any(
                fragment in serialized_all
                for fragment in ("patient_id", "medical_record", "mrn", "password", "secret")
            ),
            "operation receipts do not expose restricted fixture fields",
            {"restricted_output": serialized_all},
        )
        passed_ids = tuple(check.check_id for check in checks if check.passed)
        failed_ids = tuple(check.check_id for check in checks if not check.passed)
        state = IdentityDataState.ACCEPTED if not failed_ids else IdentityDataState.REVIEW
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
        return IdentityFixtureEvaluationReport(
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

    def run_record(self, record: IdentityFixtureRecord, context_key: str) -> Any:
        """Run one positive record for independent scenario inspection."""

        return self._run_record(record, context_key)

    def run_control(self, control: IdentityFixtureControl, context_key: str) -> Any:
        """Run one control and convert validation failures into abstentions."""

        record = IdentityFixtureRecord(
            record_id=f"negative:{control.control_id}",
            kind=control.kind,
            operation=control.operation,
            source_id=control.source_id,
            context_key=control.context_key,
            payload=control.payload,
            public_identifier=control.public_identifier,
            expected_state=control.expected_state,
            expected_signals=control.expected_signals,
        )
        try:
            return self._run_record(record, context_key)
        except ValidationError as exc:
            detail = str(exc)
            return IdentityOperationFailure(
                state="abstained",
                error_code="validation_error",
                detail=detail,
                content_address=content_hash(
                    {"state": "abstained", "error_code": "validation_error", "detail": detail}
                ),
            )

    @staticmethod
    def _append_check(
        checks: list[IdentityFixtureCheck],
        check_id: str,
        expected: Any,
        observed: Any,
        detail: str,
        receipt: Any,
    ) -> None:
        if isinstance(expected, bool):
            passed = bool(observed) == expected
        else:
            passed = observed == expected
        checks.append(
            IdentityFixtureCheck(
                check_id,
                expected,
                observed,
                passed,
                detail,
                content_hash(receipt),
            )
        )

    @staticmethod
    def _run_record(record: IdentityFixtureRecord, context_key: str) -> Any:
        payload = dict(record.payload)
        if record.kind == IdentityRecordKind.EQUIVALENCE:
            records = payload.get("records", payload.get("variants", ()))
            if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
                raise ValidationError(f"{record.record_id} equivalence records must be an array")
            return VariantEquivalenceResolver().resolve(
                records,
                str(payload.get("query", "")),
                genome_build=(
                    str(payload["genome_build"])
                    if payload.get("genome_build") is not None
                    else None
                ),
                context_key=(
                    str(payload["context_key"])
                    if payload.get("context_key") is not None
                    else context_key
                ),
            )
        if record.kind == IdentityRecordKind.RECONCILIATION:
            records = payload.get("records", payload.get("variants", ()))
            if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
                raise ValidationError(
                    f"{record.record_id} reconciliation records must be an array"
                )
            return DuplicateAliasReconciler().reconcile(records)
        if record.kind == IdentityRecordKind.SAMPLE:
            observations = payload.get("observations", payload.get("records", ()))
            if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)):
                raise ValidationError(f"{record.record_id} observations must be an array")
            return BatchSampleIdentityChecker().check(
                observations,
                require_batch=bool(payload.get("require_batch", True)),
                require_sample=bool(payload.get("require_sample", True)),
                require_subject=bool(payload.get("require_subject", False)),
            )
        if record.kind == IdentityRecordKind.CUSTODY:
            events = payload.get("events", payload.get("records", ()))
            if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
                raise ValidationError(f"{record.record_id} custody events must be an array")
            return ChainOfCustodyCapture().capture(events)
        raise ValidationError(f"unsupported identity record kind: {record.kind}")


def _state_value(value: Any) -> str:
    if isinstance(value, Mapping):
        state = value.get("state", "invalid")
        return str(getattr(state, "value", state))
    state = getattr(value, "state", "invalid")
    return str(getattr(state, "value", state))


def _serialize_output(value: Any) -> dict[str, Any]:
    if not hasattr(value, "to_dict"):
        raise ValidationError("identity operation did not return a serializable report")
    result = value.to_dict()
    if not isinstance(result, Mapping):
        raise ValidationError("identity operation report must serialize to an object")
    return dict(result)


def _has_address(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key == "content_address" and isinstance(child, str) and child.startswith("sha256:"):
                return True
            if _has_address(child):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_has_address(child) for child in value)
    return False


def _content_address(value: Mapping[str, Any]) -> str | None:
    address = value.get("content_address")
    return address if isinstance(address, str) else None


def _observed_signals(value: Any) -> tuple[str, ...]:
    signals: set[str] = set()
    state = _state_value(value)
    if state != "invalid":
        signals.add(state)
    _collect_signal_values(value, signals)
    return tuple(sorted(signals))


def _signals_match(expected: Sequence[str], value: Any) -> bool:
    observed = set(_observed_signals(value))
    return all(signal in observed for signal in expected)


def _collect_signal_values(value: Any, signals: set[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if key in {"code", "error_code"} and isinstance(child, str):
                signals.add(child)
            if key in {
                "duplicate_record_ids",
                "ambiguous_aliases",
                "missing_observation_ids",
                "ungrouped_record_ids",
            } and child:
                signals.add(key)
            _collect_signal_values(child, signals)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for child in value:
            _collect_signal_values(child, signals)


def evaluate_identity_fixture(path: str | Path) -> IdentityFixtureEvaluationReport:
    """Convenience function for one public aggregate identity fixture."""

    return IdentityFixtureEvaluator().evaluate_file(path)


__all__ = [
    "IdentityFixtureCheck",
    "IdentityFixtureEvaluationReport",
    "IdentityFixtureEvaluator",
    "IdentityOperationFailure",
    "evaluate_identity_fixture",
]

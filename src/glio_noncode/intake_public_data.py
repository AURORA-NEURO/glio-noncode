"""Public-data boundary for the Domain 01 intake evidence fixture.

The intake adapters operate on rows, policies, and manifests rather than on a
single scientific object.  This module gives those inputs one explicit data
boundary: every row has a source receipt, an exact six-field context, and a
declared public scope.  The catalog is intentionally independent from the
four operation implementations so that a green operation test cannot hide a
fixture with missing provenance or restricted fields.

The fixture format supports two source classes.  Public policy documents may
describe permitted-use rules, while public aggregate scientific records may
provide the traceable identifiers used in the intake examples.  Neither class
permits patient-level data.  Negative controls are validation controls and are
retained as reviewable rows instead of being dropped during parsing.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

INTAKE_FIXTURE_SCHEMA_VERSION = "intake-evidence-v1"


class IntakeRecordKind(StrEnum):
    """The four Domain 01 intake capabilities covered by the fixture."""

    CONSENT = "consent"
    ANOMALY = "anomaly"
    COMPLETENESS = "completeness"
    BUNDLE = "bundle"


class IntakeDataState(StrEnum):
    """Data-boundary state for an intake fixture."""

    ACCEPTED = "accepted"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class IntakeSourceReceipt:
    """Traceable public source declaration for one intake input family."""

    source_id: str
    source_url: str
    source_version: str
    context_key: str
    public_aggregate: bool
    patient_level_data: bool
    license: str
    source_kind: str

    def __post_init__(self) -> None:
        for field_name in (
            "source_id",
            "source_url",
            "source_version",
            "context_key",
            "license",
            "source_kind",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not self.source_url.startswith("https://"):
            raise ValidationError("intake source_url must use https")
        if not isinstance(self.public_aggregate, bool):
            raise ValidationError("intake public_aggregate must be boolean")
        if not isinstance(self.patient_level_data, bool):
            raise ValidationError("intake patient_level_data must be boolean")
        if self.source_kind not in {"public_policy", "public_aggregate", "validation_control"}:
            raise ValidationError("intake source_kind is unsupported")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> IntakeSourceReceipt:
        """Build a receipt without accepting implicit private-data defaults."""

        if not isinstance(raw, Mapping):
            raise ValidationError("intake source receipt must be an object")
        return cls(
            str(raw.get("source_id", "")),
            str(raw.get("source_url", "")),
            str(raw.get("source_version", "")),
            str(raw.get("context_key", "")),
            raw.get("public_aggregate", False),
            raw.get("patient_level_data", True),
            str(raw.get("license", "")),
            str(raw.get("source_kind", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeFixtureRecord:
    """One positive public record retained with its operation payload."""

    record_id: str
    kind: IntakeRecordKind
    operation: str
    source_id: str
    context_key: str
    payload: Mapping[str, Any]
    public_identifier: str
    expected_state: str = "accepted"

    def __post_init__(self) -> None:
        for field_name in (
            "record_id",
            "operation",
            "source_id",
            "context_key",
            "public_identifier",
            "expected_state",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not isinstance(self.payload, Mapping):
            raise ValidationError("intake record payload must be an object")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        fallback_context_key: str,
    ) -> IntakeFixtureRecord:
        if not isinstance(raw, Mapping):
            raise ValidationError("intake fixture record must be an object")
        try:
            kind = IntakeRecordKind(str(raw.get("kind", "")))
        except ValueError as exc:
            raise ValidationError("intake record kind is unsupported") from exc
        payload = raw.get("payload", {})
        if not isinstance(payload, Mapping):
            raise ValidationError("intake record payload must be an object")
        return cls(
            str(raw.get("record_id", raw.get("id", ""))),
            kind,
            str(raw.get("operation", "")),
            str(raw.get("source_id", "")),
            str(raw.get("context_key", fallback_context_key)),
            payload,
            str(raw.get("public_identifier", raw.get("record_id", ""))),
            str(raw.get("expected_state", "accepted")),
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeFixtureControl:
    """One negative control expected to remain visible as a review state."""

    control_id: str
    kind: IntakeRecordKind
    operation: str
    source_id: str
    context_key: str
    payload: Mapping[str, Any]
    public_identifier: str
    expected_state: str
    required_issue_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "control_id",
            "operation",
            "source_id",
            "context_key",
            "public_identifier",
            "expected_state",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not isinstance(self.payload, Mapping):
            raise ValidationError("intake control payload must be an object")
        if len(self.required_issue_codes) != len(set(self.required_issue_codes)):
            raise ValidationError("intake control issue codes must be unique")

    @classmethod
    def from_mapping(
        cls,
        raw: Mapping[str, Any],
        *,
        fallback_context_key: str,
    ) -> IntakeFixtureControl:
        if not isinstance(raw, Mapping):
            raise ValidationError("intake negative control must be an object")
        try:
            kind = IntakeRecordKind(str(raw.get("kind", "")))
        except ValueError as exc:
            raise ValidationError("intake control kind is unsupported") from exc
        payload = raw.get("payload", {})
        if not isinstance(payload, Mapping):
            raise ValidationError("intake control payload must be an object")
        return cls(
            str(raw.get("control_id", "")),
            kind,
            str(raw.get("operation", kind.value)),
            str(raw.get("source_id", "")),
            str(raw.get("context_key", fallback_context_key)),
            payload,
            str(raw.get("public_identifier", raw.get("control_id", ""))),
            str(raw.get("expected_state", "review")),
            tuple(str(item) for item in raw.get("required_issue_codes", ())),
        )

    def as_record(self) -> IntakeFixtureRecord:
        """Project a control into the same operation envelope as a positive row."""

        return IntakeFixtureRecord(
            record_id=f"negative:{self.control_id}",
            kind=self.kind,
            operation=self.operation,
            source_id=self.source_id,
            context_key=self.context_key,
            payload=self.payload,
            public_identifier=self.public_identifier,
            expected_state=self.expected_state,
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeDataIssue:
    """Addressable fixture issue that never includes a sensitive value."""

    code: str
    path: str
    detail: str

    def __post_init__(self) -> None:
        require_non_empty(self.code, "issue code")
        require_non_empty(self.path, "issue path")
        require_non_empty(self.detail, "issue detail")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeDataAuditReport:
    """Full provenance and field-boundary audit for one fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_ids: tuple[str, ...]
    record_count: int
    control_count: int
    counts_by_kind: Mapping[str, int]
    duplicate_source_ids: tuple[str, ...]
    duplicate_record_ids: tuple[str, ...]
    duplicate_control_ids: tuple[str, ...]
    context_mismatch_ids: tuple[str, ...]
    unknown_source_ids: tuple[str, ...]
    sensitive_paths: tuple[str, ...]
    patient_scope_paths: tuple[str, ...]
    issues: tuple[IntakeDataIssue, ...]
    state: IntakeDataState
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == IntakeDataState.ACCEPTED and not self.issues

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        return result


class IntakeFixtureCatalog:
    """Parse and audit public policy/aggregate intake records and controls."""

    _sensitive_fragments = (
        "patient",
        "participant",
        "donor",
        "medical_record",
        "medicalrecord",
        "mrn",
        "email",
        "phone",
        "password",
        "token",
        "secret",
        "private",
    )

    def __init__(
        self,
        *,
        fixture_id: str,
        fixture_version: str,
        context_key: str,
        sources: Sequence[IntakeSourceReceipt],
        records: Sequence[IntakeFixtureRecord],
        controls: Sequence[IntakeFixtureControl],
        provenance: Mapping[str, Any],
        initial_issues: Sequence[IntakeDataIssue] = (),
    ) -> None:
        self.fixture_id = require_non_empty(fixture_id, "fixture_id")
        self.fixture_version = require_non_empty(fixture_version, "fixture_version")
        self.context_key = require_non_empty(context_key, "context_key")
        self.sources = tuple(sources)
        self.records = tuple(records)
        self.controls = tuple(controls)
        self.provenance = dict(provenance)
        self.initial_issues = tuple(initial_issues)

    @classmethod
    def from_file(cls, path: str | Path) -> IntakeFixtureCatalog:
        fixture_path = Path(path)
        try:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ValidationError(f"unable to read intake fixture: {fixture_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"intake fixture is not valid JSON: {fixture_path}") from exc
        if not isinstance(raw, Mapping):
            raise ValidationError("intake fixture must be an object")
        return cls.from_fixture(raw)

    @classmethod
    def from_fixture(cls, raw: Mapping[str, Any]) -> IntakeFixtureCatalog:
        if not isinstance(raw, Mapping):
            raise ValidationError("intake fixture must be an object")
        context_key = _context_key(raw.get("context"))
        provenance = raw.get("provenance", {})
        if not isinstance(provenance, Mapping):
            raise ValidationError("intake fixture provenance must be an object")
        source_values = raw.get("source_receipts", ())
        if not isinstance(source_values, Sequence) or isinstance(source_values, (str, bytes)):
            raise ValidationError("intake source_receipts must be an array")
        sources = tuple(IntakeSourceReceipt.from_mapping(item) for item in source_values)
        record_values = raw.get("records", ())
        if not isinstance(record_values, Sequence) or isinstance(record_values, (str, bytes)):
            raise ValidationError("intake records must be an array")
        records = tuple(
            IntakeFixtureRecord.from_mapping(item, fallback_context_key=context_key)
            for item in record_values
        )
        control_values = raw.get("negative_controls", ())
        if not isinstance(control_values, Sequence) or isinstance(control_values, (str, bytes)):
            raise ValidationError("intake negative_controls must be an array")
        controls = tuple(
            IntakeFixtureControl.from_mapping(item, fallback_context_key=context_key)
            for item in control_values
        )
        initial: list[IntakeDataIssue] = []
        fixture_id = str(raw.get("fixture_id", ""))
        version = str(raw.get("fixture_version", ""))
        if not fixture_id.strip():
            initial.append(
                IntakeDataIssue("missing_fixture_id", "fixture_id", "fixture ID is required")
            )
            fixture_id = "invalid-intake-fixture"
        if not version.strip():
            initial.append(
                IntakeDataIssue(
                    "missing_fixture_version",
                    "fixture_version",
                    "fixture version is required",
                )
            )
            version = "missing"
        return cls(
            fixture_id=fixture_id,
            fixture_version=version,
            context_key=context_key,
            sources=sources,
            records=records,
            controls=controls,
            provenance=provenance,
            initial_issues=initial,
        )

    def record(self, record_id: str) -> IntakeFixtureRecord | None:
        """Return a positive record by its stable fixture ID."""

        for record in self.records:
            if record.record_id == record_id:
                return record
        return None

    def control(self, control_id: str) -> IntakeFixtureControl | None:
        """Return a negative control by its stable control ID."""

        for control in self.controls:
            if control.control_id == control_id:
                return control
        return None

    def audit(self) -> IntakeDataAuditReport:
        issues = list(self.initial_issues)
        source_ids = tuple(source.source_id for source in self.sources)
        source_id_set = set(source_ids)
        if self.fixture_version != INTAKE_FIXTURE_SCHEMA_VERSION:
            issues.append(
                IntakeDataIssue(
                    "fixture_version_mismatch",
                    "fixture_version",
                    f"expected {INTAKE_FIXTURE_SCHEMA_VERSION}",
                )
            )
        if not self.sources:
            issues.append(
                IntakeDataIssue(
                    "missing_source_receipts",
                    "source_receipts",
                    "at least one public source receipt is required",
                )
            )
        for index, source in enumerate(self.sources):
            prefix = f"source_receipts[{index}]"
            if not source.public_aggregate:
                issues.append(
                    IntakeDataIssue(
                        "source_not_public",
                        prefix,
                        "intake evidence requires a public policy or aggregate source",
                    )
                )
            if source.patient_level_data:
                issues.append(
                    IntakeDataIssue(
                        "source_patient_scope",
                        prefix,
                        "patient-level source declarations are not allowed",
                    )
                )
            if source.context_key != self.context_key:
                issues.append(
                    IntakeDataIssue(
                        "source_context_mismatch",
                        prefix,
                        "source receipt context differs from fixture context",
                    )
                )
        duplicate_sources = tuple(
            sorted(source_id for source_id, count in Counter(source_ids).items() if count > 1)
        )
        for source_id in duplicate_sources:
            issues.append(
                IntakeDataIssue(
                    "duplicate_source_id",
                    "source_receipts",
                    f"source ID {source_id} occurs more than once",
                )
            )
        record_ids = tuple(record.record_id for record in self.records)
        control_ids = tuple(control.control_id for control in self.controls)
        duplicate_records = tuple(
            sorted(record_id for record_id, count in Counter(record_ids).items() if count > 1)
        )
        duplicate_controls = tuple(
            sorted(control_id for control_id, count in Counter(control_ids).items() if count > 1)
        )
        for record_id in duplicate_records:
            issues.append(
                IntakeDataIssue(
                    "duplicate_record_id",
                    "records",
                    f"record ID {record_id} occurs more than once",
                )
            )
        for control_id in duplicate_controls:
            issues.append(
                IntakeDataIssue(
                    "duplicate_control_id",
                    "negative_controls",
                    f"control ID {control_id} occurs more than once",
                )
            )
        collisions = set(record_ids) & set(control_ids)
        for collision in sorted(collisions):
            issues.append(
                IntakeDataIssue(
                    "record_control_id_collision",
                    "fixture",
                    f"record and control identity collide for {collision}",
                )
            )
        context_mismatches: list[str] = []
        unknown_sources: list[str] = []
        sensitive_paths: list[str] = []
        patient_scope_paths: list[str] = []

        def inspect_envelope(
            envelope: IntakeFixtureRecord | IntakeFixtureControl,
            prefix: str,
        ) -> None:
            if envelope.context_key != self.context_key:
                context_mismatches.append(envelope.record_id if isinstance(envelope, IntakeFixtureRecord) else envelope.control_id)
                issues.append(
                    IntakeDataIssue(
                        "record_context_mismatch",
                        prefix,
                        "operation envelope context differs from fixture context",
                    )
                )
            if envelope.source_id not in source_id_set:
                unknown_sources.append(envelope.source_id)
                issues.append(
                    IntakeDataIssue(
                        "unknown_record_source",
                        f"{prefix}.source_id",
                        f"source ID {envelope.source_id} has no receipt",
                    )
                )
            for path, key in _walk_keys(envelope.payload, f"{prefix}.payload"):
                lowered = key.casefold()
                if any(fragment in lowered for fragment in self._sensitive_fragments):
                    sensitive_paths.append(path)
                    issues.append(
                        IntakeDataIssue(
                            "sensitive_record_path",
                            path,
                            "public intake fixture contains a restricted field name",
                        )
                    )
                if "patient" in lowered or "participant" in lowered or "donor" in lowered:
                    patient_scope_paths.append(path)

        for index, record in enumerate(self.records):
            inspect_envelope(record, f"records[{index}]")
        for index, control in enumerate(self.controls):
            inspect_envelope(control, f"negative_controls[{index}]")
            if control.expected_state == "accepted":
                issues.append(
                    IntakeDataIssue(
                        "control_expected_acceptance",
                        f"negative_controls[{index}].expected_state",
                        "negative controls must declare a review-compatible state",
                    )
                )
        if self.provenance.get("patient_level_data") is not False:
            issues.append(
                IntakeDataIssue(
                    "fixture_patient_scope",
                    "provenance.patient_level_data",
                    "fixture must explicitly declare patient_level_data=false",
                )
            )
        if self.provenance.get("data_scope") not in {"public_aggregate", "public_policy_and_aggregate"}:
            issues.append(
                IntakeDataIssue(
                    "invalid_data_scope",
                    "provenance.data_scope",
                    "fixture must declare public_policy_and_aggregate or public_aggregate",
                )
            )
        if not str(self.provenance.get("evidence_boundary", "")).strip():
            issues.append(
                IntakeDataIssue(
                    "missing_evidence_boundary",
                    "provenance.evidence_boundary",
                    "fixture must state what the evidence does not claim",
                )
            )
        expected_record_count = self.provenance.get("expected_record_count")
        if expected_record_count is not None and expected_record_count != len(self.records):
            issues.append(
                IntakeDataIssue(
                    "record_count_mismatch",
                    "provenance.expected_record_count",
                    "declared positive record count differs from parsed records",
                )
            )
        expected_control_count = self.provenance.get("expected_control_count")
        if expected_control_count is not None and expected_control_count != len(self.controls):
            issues.append(
                IntakeDataIssue(
                    "control_count_mismatch",
                    "provenance.expected_control_count",
                    "declared control count differs from parsed controls",
                )
            )
        counts = Counter(record.kind.value for record in self.records)
        body = {
            "fixture_id": self.fixture_id,
            "fixture_version": self.fixture_version,
            "context_key": self.context_key,
            "source_ids": source_ids,
            "records": self.records,
            "controls": self.controls,
            "issues": issues,
        }
        state = IntakeDataState.ACCEPTED if not issues else IntakeDataState.REVIEW
        return IntakeDataAuditReport(
            self.fixture_id,
            self.fixture_version,
            self.context_key,
            tuple(sorted(source_ids)),
            len(self.records),
            len(self.controls),
            dict(sorted(counts.items())),
            duplicate_sources,
            duplicate_records,
            duplicate_controls,
            tuple(sorted(set(context_mismatches))),
            tuple(sorted(set(unknown_sources))),
            tuple(sorted(set(sensitive_paths))),
            tuple(sorted(set(patient_scope_paths))),
            tuple(issues),
            state,
            content_hash(body),
        )


def _context_key(value: Any) -> str:
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
    values = tuple(
        require_non_empty(str(value.get(field, "")), f"context.{field}") for field in fields
    )
    return "|".join(values)


def _walk_keys(value: Any, prefix: str) -> tuple[tuple[str, str], ...]:
    found: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            found.append((path, str(key)))
            found.extend(_walk_keys(child, path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(_walk_keys(child, f"{prefix}[{index}]"))
    return tuple(found)


def audit_intake_fixture(path: str | Path) -> IntakeDataAuditReport:
    """Audit one checked-in public intake fixture."""

    return IntakeFixtureCatalog.from_file(path).audit()


__all__ = [
    "INTAKE_FIXTURE_SCHEMA_VERSION",
    "IntakeDataAuditReport",
    "IntakeDataIssue",
    "IntakeDataState",
    "IntakeFixtureCatalog",
    "IntakeFixtureControl",
    "IntakeFixtureRecord",
    "IntakeRecordKind",
    "IntakeSourceReceipt",
    "audit_intake_fixture",
]

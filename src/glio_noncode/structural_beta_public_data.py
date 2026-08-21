"""Public aggregate fixture contracts for Domain 02 C05-C08.

The scientific-beta detectors already expose bounded operations.  This module
adds the release boundary around those operations: public source receipts,
exact context identity, positive records, review controls, and a strict
aggregate-only payload policy.  The fixture is intentionally a compact
mechanics set.  It exercises the detector branches without pretending to be a
complete callset or a biological truth set.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

STRUCTURAL_BETA_FIXTURE_SCHEMA_VERSION = "structural-beta-evidence-v1"
STRUCTURAL_BETA_OPERATION_FLOOR = 4
STRUCTURAL_BETA_CONTROL_FLOOR = 8


class StructuralBetaOperation(StrEnum):
    """The four scientific-beta operations covered by this evidence gate."""

    FOCAL_AMPLIFICATION = "focal_amplification"
    CHROMOTHRIPSIS = "chromothripsis"
    ECDNA = "ecdna"
    ENHANCER_HIJACKING = "enhancer_hijacking"


class StructuralBetaFixtureState(StrEnum):
    """Fixture assertion state, separate from detector result state."""

    ACCEPTED = "accepted"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class StructuralBetaSourceReceipt:
    """Public aggregate source receipt used to frame a fixture record."""

    source_id: str
    title: str
    url: str
    version: str
    license: str
    data_scope: str
    patient_level: bool = False
    retrieved_at: str = "2026-08-21"
    notes: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "source_id",
            "title",
            "url",
            "version",
            "license",
            "data_scope",
            "retrieved_at",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not self.url.startswith(("https://", "http://")):
            raise ValidationError("beta source url must use an explicit web scheme")
        if self.patient_level:
            raise ValidationError("beta fixture sources must be aggregate")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralBetaFixtureRecord:
    """One positive detector case or review control."""

    record_id: str
    operation: StructuralBetaOperation
    expected_state: StructuralBetaFixtureState
    expected_result_state: str
    context_key: str
    source_id: str
    payload: Mapping[str, Any]
    required_issue_codes: tuple[str, ...] = ()
    expected_counts: Mapping[str, int] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "record_id",
            "expected_result_state",
            "context_key",
            "source_id",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not self.payload:
            raise ValidationError("beta fixture payload must not be empty")
        if self.context_key.count("|") != 5:
            raise ValidationError("beta fixture context key requires six fields")
        for key, value in self.expected_counts.items():
            if not str(key).strip() or int(value) < 0:
                raise ValidationError("beta expected counts must be named and non-negative")
        if len(self.required_issue_codes) != len(set(self.required_issue_codes)):
            raise ValidationError("beta required issue codes must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralBetaFixtureCatalog:
    """Complete aggregate fixture catalog for C05-C08."""

    fixture_id: str
    schema_version: str
    context_key: str
    provenance: str
    patient_level: bool
    sources: tuple[StructuralBetaSourceReceipt, ...]
    positives: tuple[StructuralBetaFixtureRecord, ...]
    controls: tuple[StructuralBetaFixtureRecord, ...]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("fixture_id", "schema_version", "context_key", "provenance"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.schema_version != STRUCTURAL_BETA_FIXTURE_SCHEMA_VERSION:
            raise ValidationError("unsupported beta fixture schema version")
        if self.context_key.count("|") != 5:
            raise ValidationError("beta fixture context key requires six fields")
        if self.patient_level:
            raise ValidationError("beta fixture must be aggregate, not patient-level")
        if not self.sources:
            raise ValidationError("beta fixture requires public source receipts")
        if not self.positives:
            raise ValidationError("beta fixture requires positive records")
        if not self.controls:
            raise ValidationError("beta fixture requires review controls")

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(sorted(source.source_id for source in self.sources))

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(sorted({item.operation.value for item in self.positives + self.controls}))

    @property
    def record_ids(self) -> tuple[str, ...]:
        return tuple(item.record_id for item in self.positives + self.controls)

    @property
    def content_address(self) -> str:
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> StructuralBetaFixtureCatalog:
        """Parse and validate one JSON-compatible fixture mapping."""

        if not isinstance(raw, Mapping):
            raise ValidationError("beta fixture must be an object")
        sources = tuple(
            StructuralBetaSourceReceipt(
                source_id=str(item.get("source_id", "")),
                title=str(item.get("title", "")),
                url=str(item.get("url", "")),
                version=str(item.get("version", "")),
                license=str(item.get("license", "")),
                data_scope=str(item.get("data_scope", "")),
                patient_level=bool(item.get("patient_level", False)),
                retrieved_at=str(item.get("retrieved_at", "2026-08-21")),
                notes=str(item.get("notes", "")),
            )
            for item in _object_array(raw.get("sources", ()), "sources")
        )
        return cls(
            fixture_id=str(raw.get("fixture_id", "")),
            schema_version=str(raw.get("schema_version", "")),
            context_key=str(raw.get("context_key", "")),
            provenance=str(raw.get("provenance", "")),
            patient_level=bool(raw.get("patient_level", False)),
            sources=sources,
            positives=_records(raw.get("positives", ()), StructuralBetaFixtureState.ACCEPTED),
            controls=_records(raw.get("controls", ()), StructuralBetaFixtureState.REVIEW),
            notes=tuple(str(item) for item in _array(raw.get("notes", ()), "notes")),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> StructuralBetaFixtureCatalog:
        file_path = Path(path)
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValidationError(f"beta fixture file not found: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid beta fixture JSON: {exc}") from exc
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class StructuralBetaDataAuditReport:
    """Audit result for public scope, identity, context, and operation floors."""

    fixture_id: str
    context_key: str
    state: StructuralBetaFixtureState
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    positive_count: int
    control_count: int
    operation_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == StructuralBetaFixtureState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        return result


def audit_structural_beta_fixture(
    catalog: StructuralBetaFixtureCatalog,
) -> StructuralBetaDataAuditReport:
    """Audit a catalog without running any detector."""

    issues: set[str] = set()
    source_ids = set(catalog.source_ids)
    record_ids = list(catalog.record_ids)
    if len(source_ids) != len(catalog.sources):
        issues.add("duplicate_source_id")
    if len(record_ids) != len(set(record_ids)):
        issues.add("duplicate_record_id")
    if len(catalog.positives) < STRUCTURAL_BETA_OPERATION_FLOOR:
        issues.add("positive_floor")
    if len(catalog.controls) < STRUCTURAL_BETA_CONTROL_FLOOR:
        issues.add("control_floor")
    if set(catalog.operation_ids) != {item.value for item in StructuralBetaOperation}:
        issues.add("operation_floor")
    for source in catalog.sources:
        if source.patient_level:
            issues.add("patient_level_source")
        scope = source.data_scope.casefold()
        if "public" not in scope and "aggregate" not in scope:
            issues.add("source_scope_not_public_aggregate")
    for record in catalog.positives + catalog.controls:
        if record.context_key != catalog.context_key:
            issues.add("record_context_mismatch")
        if record.source_id not in source_ids:
            issues.add("record_source_missing")
        if _sensitive_paths(record.payload):
            issues.add("sensitive_payload_path")
        if record.expected_state == StructuralBetaFixtureState.ACCEPTED and record in catalog.controls:
            issues.add("control_state_mismatch")
        if record.expected_state == StructuralBetaFixtureState.REVIEW and record in catalog.positives:
            issues.add("positive_state_mismatch")
    state = StructuralBetaFixtureState.ACCEPTED if not issues else StructuralBetaFixtureState.REVIEW
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "state": state,
        "issues": tuple(sorted(issues)),
        "source_ids": tuple(sorted(source_ids)),
        "positive_count": len(catalog.positives),
        "control_count": len(catalog.controls),
        "operation_ids": catalog.operation_ids,
        "record_ids": tuple(sorted(record_ids)),
    }
    return StructuralBetaDataAuditReport(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        state=state,
        issue_codes=tuple(sorted(issues)),
        source_ids=tuple(sorted(source_ids)),
        positive_count=len(catalog.positives),
        control_count=len(catalog.controls),
        operation_ids=catalog.operation_ids,
        record_ids=tuple(sorted(record_ids)),
        content_address=content_hash(body),
    )


def _array(value: Any, field_name: str) -> tuple[Any, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValidationError(f"{field_name} must be an array")
    return tuple(value)


def _object_array(value: Any, field_name: str) -> tuple[Mapping[str, Any], ...]:
    rows = _array(value, field_name)
    if not all(isinstance(item, Mapping) for item in rows):
        raise ValidationError(f"{field_name} must contain objects")
    return tuple(item for item in rows if isinstance(item, Mapping))


def _records(
    value: Any,
    default_state: StructuralBetaFixtureState,
) -> tuple[StructuralBetaFixtureRecord, ...]:
    rows = _object_array(value, "fixture records")
    records: list[StructuralBetaFixtureRecord] = []
    for item in rows:
        try:
            operation = StructuralBetaOperation(str(item.get("operation", "")))
            state = StructuralBetaFixtureState(
                str(item.get("expected_state", default_state.value))
            )
        except ValueError as exc:
            raise ValidationError(f"invalid beta fixture state or operation: {exc}") from exc
        expected_counts_raw = item.get("expected_counts", {})
        if not isinstance(expected_counts_raw, Mapping):
            raise ValidationError("beta expected_counts must be an object")
        payload = item.get("payload", {})
        if not isinstance(payload, Mapping):
            raise ValidationError("beta fixture payload must be an object")
        records.append(
            StructuralBetaFixtureRecord(
                record_id=str(item.get("record_id", "")),
                operation=operation,
                expected_state=state,
                expected_result_state=str(item.get("expected_result_state", "")),
                context_key=str(item.get("context_key", "")),
                source_id=str(item.get("source_id", "")),
                payload=dict(payload),
                required_issue_codes=tuple(
                    str(code)
                    for code in _array(item.get("required_issue_codes", ()), "required_issue_codes")
                ),
                expected_counts={str(key): int(value) for key, value in expected_counts_raw.items()},
                description=str(item.get("description", "")),
            )
        )
    return tuple(records)


def _sensitive_paths(value: Any, path: str = "payload") -> tuple[str, ...]:
    forbidden = {
        "patient_id",
        "subject_id",
        "donor_id",
        "participant_id",
        "medical_record_number",
        "email",
        "phone",
        "address",
        "date_of_birth",
        "full_name",
    }
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).casefold() in forbidden:
                found.append(child_path)
            found.extend(_sensitive_paths(child, child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(_sensitive_paths(child, f"{path}[{index}]"))
    return tuple(found)


__all__ = [
    "STRUCTURAL_BETA_CONTROL_FLOOR",
    "STRUCTURAL_BETA_FIXTURE_SCHEMA_VERSION",
    "STRUCTURAL_BETA_OPERATION_FLOOR",
    "StructuralBetaDataAuditReport",
    "StructuralBetaFixtureCatalog",
    "StructuralBetaFixtureRecord",
    "StructuralBetaFixtureState",
    "StructuralBetaOperation",
    "StructuralBetaSourceReceipt",
    "audit_structural_beta_fixture",
]

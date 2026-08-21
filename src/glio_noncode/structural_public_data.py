"""Public aggregate source and data-boundary controls for Domain 02.

The structural adapters operate on typed observations, but a release-quality
fixture needs more than a few in-memory calls.  This module defines the
versioned source receipt, positive operation records, review controls, and
audit report used by the structural evidence gate.  Payloads are deliberately
aggregate and de-identified.  The source receipt describes where the public
summary came from; it does not claim that the small fixture is a complete copy
of that source.
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

STRUCTURAL_FIXTURE_SCHEMA_VERSION = "structural-evidence-v1"
STRUCTURAL_OPERATION_FLOOR = 4
STRUCTURAL_CONTROL_FLOOR = 8


class StructuralOperation(StrEnum):
    """The four operations covered by the Domain 02 C01-C04 gate."""

    RECONSTRUCTION = "reconstruction"
    CONSENSUS = "consensus"
    COMPLEX_RESOLUTION = "complex_resolution"
    COPY_NUMBER = "copy_number"


class StructuralFixtureState(StrEnum):
    """Fixture-level state, separate from a domain result state."""

    ACCEPTED = "accepted"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class StructuralSourceReceipt:
    """A public source receipt with scope and version declarations."""

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
            raise ValidationError("source url must use an explicit web scheme")
        if self.patient_level:
            raise ValidationError("structural fixture sources must be aggregate")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFixtureRecord:
    """One executable positive record or review control."""

    record_id: str
    operation: StructuralOperation
    expected_state: StructuralFixtureState
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
            "context_key",
            "source_id",
            "expected_result_state",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if not self.payload:
            raise ValidationError("structural fixture payload must not be empty")
        for key, value in self.expected_counts.items():
            if not str(key).strip() or int(value) < 0:
                raise ValidationError("expected structural counts must be named and non-negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFixtureCatalog:
    """Complete public aggregate fixture catalog."""

    fixture_id: str
    schema_version: str
    context_key: str
    provenance: str
    patient_level: bool
    sources: tuple[StructuralSourceReceipt, ...]
    positives: tuple[StructuralFixtureRecord, ...]
    controls: tuple[StructuralFixtureRecord, ...]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("fixture_id", "schema_version", "context_key", "provenance"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.schema_version != STRUCTURAL_FIXTURE_SCHEMA_VERSION:
            raise ValidationError("unsupported structural fixture schema version")
        if self.patient_level:
            raise ValidationError("structural fixture must be aggregate, not patient-level")
        if not self.sources:
            raise ValidationError("structural fixture requires source receipts")
        if not self.positives:
            raise ValidationError("structural fixture requires positive records")
        if not self.controls:
            raise ValidationError("structural fixture requires review controls")

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(sorted(source.source_id for source in self.sources))

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(sorted({record.operation.value for record in self.positives + self.controls}))

    @property
    def record_ids(self) -> tuple[str, ...]:
        return tuple(record.record_id for record in self.positives + self.controls)

    @property
    def content_address(self) -> str:
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> StructuralFixtureCatalog:
        if not isinstance(raw, Mapping):
            raise ValidationError("structural fixture must be an object")
        sources = tuple(
            StructuralSourceReceipt(
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
            positives=_records(raw.get("positives", ()), StructuralFixtureState.ACCEPTED),
            controls=_records(raw.get("controls", ()), StructuralFixtureState.REVIEW),
            notes=tuple(str(item) for item in _array(raw.get("notes", ()), "notes")),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> StructuralFixtureCatalog:
        file_path = Path(path)
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid structural fixture JSON: {exc}") from exc
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class StructuralDataAuditReport:
    """Audit result for source, scope, identity, and payload boundaries."""

    fixture_id: str
    context_key: str
    state: StructuralFixtureState
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    positive_count: int
    control_count: int
    operation_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == StructuralFixtureState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        result = jsonable(self)
        result["accepted"] = self.accepted
        return result


def audit_structural_fixture(catalog: StructuralFixtureCatalog) -> StructuralDataAuditReport:
    """Validate a loaded catalog without executing scientific operations."""

    issues: set[str] = set()
    source_ids = set(catalog.source_ids)
    record_ids = list(catalog.record_ids)
    if len(source_ids) != len(catalog.sources):
        issues.add("duplicate_source_id")
    if len(record_ids) != len(set(record_ids)):
        issues.add("duplicate_record_id")
    if catalog.context_key.count("|") != 5:
        issues.add("invalid_context_key")
    if len(catalog.positives) < STRUCTURAL_OPERATION_FLOOR:
        issues.add("positive_floor")
    if len(catalog.controls) < STRUCTURAL_CONTROL_FLOOR:
        issues.add("control_floor")
    if set(catalog.operation_ids) != {item.value for item in StructuralOperation}:
        issues.add("operation_floor")
    for source in catalog.sources:
        if source.patient_level:
            issues.add("patient_level_source")
        if "public" not in source.data_scope.lower() and "aggregate" not in source.data_scope.lower():
            issues.add("source_scope_not_public_aggregate")
    for record in catalog.positives + catalog.controls:
        if record.context_key != catalog.context_key:
            issues.add("record_context_mismatch")
        if record.source_id not in source_ids:
            issues.add("record_source_missing")
        if _sensitive_paths(record.payload):
            issues.add("sensitive_payload_path")
        if record.expected_state == StructuralFixtureState.ACCEPTED and record in catalog.controls:
            issues.add("control_state_mismatch")
        if record.expected_state == StructuralFixtureState.REVIEW and record in catalog.positives:
            issues.add("positive_state_mismatch")
    state = StructuralFixtureState.ACCEPTED if not issues else StructuralFixtureState.REVIEW
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
    return StructuralDataAuditReport(
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


def _records(value: Any, default_state: StructuralFixtureState) -> tuple[StructuralFixtureRecord, ...]:
    rows = _object_array(value, "fixture records")
    records: list[StructuralFixtureRecord] = []
    for item in rows:
        raw_state = str(item.get("expected_state", default_state.value))
        try:
            state = StructuralFixtureState(raw_state)
            operation = StructuralOperation(str(item.get("operation", "")))
        except ValueError as exc:
            raise ValidationError(f"invalid structural fixture state or operation: {exc}") from exc
        expected_counts_raw = item.get("expected_counts", {})
        if not isinstance(expected_counts_raw, Mapping):
            raise ValidationError("expected_counts must be an object")
        payload = item.get("payload", {})
        if not isinstance(payload, Mapping):
            raise ValidationError("fixture payload must be an object")
        records.append(
            StructuralFixtureRecord(
                record_id=str(item.get("record_id", "")),
                operation=operation,
                expected_state=state,
                expected_result_state=str(item.get("expected_result_state", "")),
                context_key=str(item.get("context_key", "")),
                source_id=str(item.get("source_id", "")),
                payload=dict(payload),
                required_issue_codes=tuple(
                    str(code) for code in _array(item.get("required_issue_codes", ()), "required_issue_codes")
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
            if str(key).lower() in forbidden:
                found.append(child_path)
            found.extend(_sensitive_paths(child, child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(_sensitive_paths(child, f"{path}[{index}]"))
    return tuple(found)


__all__ = [
    "STRUCTURAL_CONTROL_FLOOR",
    "STRUCTURAL_FIXTURE_SCHEMA_VERSION",
    "STRUCTURAL_OPERATION_FLOOR",
    "StructuralDataAuditReport",
    "StructuralFixtureCatalog",
    "StructuralFixtureRecord",
    "StructuralFixtureState",
    "StructuralOperation",
    "StructuralSourceReceipt",
    "audit_structural_fixture",
]

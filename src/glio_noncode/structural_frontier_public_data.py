"""Public aggregate boundary for Domain 02 C13-C16.

The four frontier structural adapters already expose bounded calculations in
``frontier_data_alpha``. This module gives that family a strict, deterministic
fixture contract: public source receipts, one exact context, positive records,
review controls, and an aggregate-only payload policy.
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

STRUCTURAL_FRONTIER_FIXTURE_SCHEMA_VERSION = "structural-frontier-evidence-v1"
STRUCTURAL_FRONTIER_OPERATION_FLOOR = 4
STRUCTURAL_FRONTIER_CONTROL_FLOOR = 8


class StructuralFrontierOperation(StrEnum):
    """The four Domain 02 frontier operations covered by this family."""

    TANDEM_REPEAT = "tandem_repeat"
    COMPOUND_HAPLOTYPE = "compound_haplotype"
    BREAKPOINT_UNCERTAINTY = "breakpoint_uncertainty"
    STRUCTURAL_EVIDENCE_EXPORT = "structural_evidence_export"


class StructuralFrontierFixtureState(StrEnum):
    """Fixture assertion state, independent from detector result state."""

    ACCEPTED = "accepted"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class StructuralFrontierSourceReceipt:
    """Receipt for one public aggregate source used by a fixture record."""

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
            raise ValidationError("structural frontier source URL must use a web scheme")
        if self.patient_level:
            raise ValidationError("structural frontier sources must be aggregate")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFrontierFixtureRecord:
    """One positive operation case or review control."""

    record_id: str
    operation: StructuralFrontierOperation
    expected_state: StructuralFrontierFixtureState
    expected_result_state: str
    context_key: str
    source_id: str
    payload: Mapping[str, Any]
    required_issue_codes: tuple[str, ...] = ()
    expected_counts: Mapping[str, int] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        for field_name in ("record_id", "expected_result_state", "context_key", "source_id"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.context_key.count("|") != 5:
            raise ValidationError("structural frontier context key requires six fields")
        if not self.payload:
            raise ValidationError("structural frontier fixture payload must not be empty")
        if len(self.required_issue_codes) != len(set(self.required_issue_codes)):
            raise ValidationError("required issue codes must be unique")
        for key, value in self.expected_counts.items():
            if not str(key).strip() or int(value) < 0:
                raise ValidationError("expected counts must be named and non-negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StructuralFrontierFixtureCatalog:
    """Complete public aggregate catalog for C13-C16."""

    fixture_id: str
    schema_version: str
    context_key: str
    provenance: str
    patient_level: bool
    sources: tuple[StructuralFrontierSourceReceipt, ...]
    positives: tuple[StructuralFrontierFixtureRecord, ...]
    controls: tuple[StructuralFrontierFixtureRecord, ...]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("fixture_id", "schema_version", "context_key", "provenance"):
            require_non_empty(str(getattr(self, field_name)), field_name)
        if self.schema_version != STRUCTURAL_FRONTIER_FIXTURE_SCHEMA_VERSION:
            raise ValidationError("unsupported structural frontier fixture schema version")
        if self.context_key.count("|") != 5:
            raise ValidationError("structural frontier context key requires six fields")
        if self.patient_level:
            raise ValidationError("structural frontier fixture must be aggregate")
        if not self.sources:
            raise ValidationError("structural frontier fixture requires source receipts")
        if not self.positives:
            raise ValidationError("structural frontier fixture requires positive records")
        if not self.controls:
            raise ValidationError("structural frontier fixture requires review controls")

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
    def from_mapping(cls, raw: Mapping[str, Any]) -> StructuralFrontierFixtureCatalog:
        if not isinstance(raw, Mapping):
            raise ValidationError("structural frontier fixture must be an object")
        sources = tuple(
            StructuralFrontierSourceReceipt(
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
            positives=_records(raw.get("positives", ()), StructuralFrontierFixtureState.ACCEPTED),
            controls=_records(raw.get("controls", ()), StructuralFrontierFixtureState.REVIEW),
            notes=tuple(str(item) for item in _array(raw.get("notes", ()), "notes")),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> StructuralFrontierFixtureCatalog:
        file_path = Path(path)
        try:
            raw = json.loads(file_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValidationError(f"structural frontier fixture file not found: {file_path}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"invalid structural frontier fixture JSON: {exc}") from exc
        return cls.from_mapping(raw)


@dataclass(frozen=True, slots=True)
class StructuralFrontierDataAuditReport:
    """Audit result for source scope, identity, context, and operation floors."""

    fixture_id: str
    context_key: str
    state: StructuralFrontierFixtureState
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    positive_count: int
    control_count: int
    operation_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == StructuralFrontierFixtureState.ACCEPTED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def audit_structural_frontier_fixture(
    catalog: StructuralFrontierFixtureCatalog,
) -> StructuralFrontierDataAuditReport:
    """Audit a catalog without executing any frontier adapter."""

    issues: set[str] = set()
    source_ids = set(catalog.source_ids)
    record_ids = list(catalog.record_ids)
    if len(source_ids) != len(catalog.sources):
        issues.add("duplicate_source_id")
    if len(record_ids) != len(set(record_ids)):
        issues.add("duplicate_record_id")
    if len(catalog.positives) < STRUCTURAL_FRONTIER_OPERATION_FLOOR:
        issues.add("positive_floor")
    if len(catalog.controls) < STRUCTURAL_FRONTIER_CONTROL_FLOOR:
        issues.add("control_floor")
    if set(catalog.operation_ids) != {item.value for item in StructuralFrontierOperation}:
        issues.add("operation_floor")
    for source in catalog.sources:
        scope = source.data_scope.casefold()
        if "public" not in scope and "aggregate" not in scope:
            issues.add("source_scope_not_public_aggregate")
    for record in catalog.positives + catalog.controls:
        if record.context_key != catalog.context_key:
            issues.add("record_context_mismatch")
        if record.source_id not in source_ids:
            issues.add("record_source_missing")
        if _contains_sensitive_key(record.payload):
            issues.add("sensitive_payload_key")
    state = StructuralFrontierFixtureState.ACCEPTED if not issues else StructuralFrontierFixtureState.REVIEW
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "state": state,
        "issue_codes": tuple(sorted(issues)),
        "source_ids": catalog.source_ids,
        "positive_count": len(catalog.positives),
        "control_count": len(catalog.controls),
        "operation_ids": catalog.operation_ids,
        "record_ids": tuple(sorted(record_ids)),
    }
    return StructuralFrontierDataAuditReport(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        state=state,
        issue_codes=tuple(sorted(issues)),
        source_ids=catalog.source_ids,
        positive_count=len(catalog.positives),
        control_count=len(catalog.controls),
        operation_ids=catalog.operation_ids,
        record_ids=tuple(sorted(record_ids)),
        content_address=content_hash(body),
    )


def _records(value: Any, state: StructuralFrontierFixtureState) -> tuple[StructuralFrontierFixtureRecord, ...]:
    return tuple(
        StructuralFrontierFixtureRecord(
            record_id=str(item.get("record_id", "")),
            operation=StructuralFrontierOperation(str(item.get("operation", ""))),
            expected_state=state,
            expected_result_state=str(item.get("expected_result_state", "")),
            context_key=str(item.get("context_key", "")),
            source_id=str(item.get("source_id", "")),
            payload=item.get("payload", {}),
            required_issue_codes=tuple(str(code) for code in _array(item.get("required_issue_codes", ()), "required_issue_codes")),
            expected_counts={str(key): int(count) for key, count in _mapping(item.get("expected_counts", {}), "expected_counts").items()},
            description=str(item.get("description", "")),
        )
        for item in _object_array(value, "records")
    )


def _array(value: Any, label: str) -> tuple[Any, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValidationError(f"{label} must be an array")
    return tuple(value)


def _object_array(value: Any, label: str) -> tuple[Mapping[str, Any], ...]:
    items = _array(value, label)
    if any(not isinstance(item, Mapping) for item in items):
        raise ValidationError(f"{label} must contain objects")
    return tuple(items)


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    return value


def _contains_sensitive_key(value: Any) -> bool:
    sensitive = {
        "patient_id",
        "subject_id",
        "medical_record_number",
        "sample_patient_id",
        "participant_id",
    }
    if isinstance(value, Mapping):
        return any(str(key).casefold() in sensitive or _contains_sensitive_key(item) for key, item in value.items())
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return any(_contains_sensitive_key(item) for item in value)
    return False


__all__ = [
    "STRUCTURAL_FRONTIER_CONTROL_FLOOR",
    "STRUCTURAL_FRONTIER_FIXTURE_SCHEMA_VERSION",
    "STRUCTURAL_FRONTIER_OPERATION_FLOOR",
    "StructuralFrontierDataAuditReport",
    "StructuralFrontierFixtureCatalog",
    "StructuralFrontierFixtureRecord",
    "StructuralFrontierFixtureState",
    "StructuralFrontierOperation",
    "StructuralFrontierSourceReceipt",
    "audit_structural_frontier_fixture",
]

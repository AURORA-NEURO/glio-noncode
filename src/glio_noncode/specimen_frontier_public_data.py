"""Public aggregate boundary for Domain 03 C01-C04.

The existing specimen adapters preserve declared sample relationships and
measurement anomalies. This module adds a strict fixture contract around that
behavior: source receipts, one exact context, positive records, review
controls, deterministic identifiers, and an aggregate-only payload policy.
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

SPECIMEN_FRONTIER_FIXTURE_SCHEMA_VERSION = "specimen-frontier-evidence-v1"
SPECIMEN_FRONTIER_OPERATION_FLOOR = 4
SPECIMEN_FRONTIER_CONTROL_FLOOR = 8
SPECIMEN_FRONTIER_CONTEXT_DIMENSION_FLOOR = 6
SPECIMEN_FRONTIER_SENSITIVE_KEYS = frozenset(
    {
        "patient_id",
        "subject_id",
        "medical_record_number",
        "sample_patient_id",
        "participant_id",
    }
)


class SpecimenFrontierOperation(StrEnum):
    """The four Domain 03 specimen operations covered by this family."""

    ONTOLOGY_MAPPING = "ontology_mapping"
    MATCHED_NORMAL = "matched_normal"
    PURITY_PLOIDY = "purity_ploidy"
    SAMPLE_INTEGRITY = "sample_integrity"


class SpecimenFrontierFixtureState(StrEnum):
    """Expected fixture state, independent from adapter result state."""

    ACCEPTED = "accepted"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class SpecimenFrontierSourceReceipt:
    """One public aggregate metadata source used to shape the fixture."""

    source_id: str
    label: str
    url: str
    release: str
    aggregate_only: bool = True
    patient_level: bool = False
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("source_id", "label", "url", "release"):
            require_non_empty(str(getattr(self, name)), f"source receipt {name}")
        if not self.url.startswith(("https://", "http://")):
            raise ValidationError("specimen frontier source URL must be absolute")
        if self.patient_level or not self.aggregate_only:
            raise ValidationError("specimen frontier sources must be aggregate-only")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierFixtureRecord:
    """One positive operation case or review control."""

    record_id: str
    operation: SpecimenFrontierOperation
    source_id: str
    context_key: str
    expected_state: SpecimenFrontierFixtureState
    expected_result_state: str
    payload: Mapping[str, Any]
    parameters: Mapping[str, Any] = field(default_factory=dict)
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "source_id", "context_key", "expected_result_state"):
            require_non_empty(str(getattr(self, name)), f"specimen frontier record {name}")
        if not isinstance(self.payload, Mapping):
            raise ValidationError("specimen frontier record payload must be a mapping")
        if not self.content_address:
            body = {
                "record_id": self.record_id,
                "operation": self.operation,
                "source_id": self.source_id,
                "context_key": self.context_key,
                "expected_state": self.expected_state,
                "expected_result_state": self.expected_result_state,
                "payload": self.payload,
                "parameters": self.parameters,
            }
            object.__setattr__(self, "content_address", content_hash(body))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierFixtureCatalog:
    """Complete public aggregate catalog for Domain 03 C01-C04."""

    fixture_id: str
    context_key: str
    sources: tuple[SpecimenFrontierSourceReceipt, ...]
    positives: tuple[SpecimenFrontierFixtureRecord, ...]
    controls: tuple[SpecimenFrontierFixtureRecord, ...]
    schema_version: str = SPECIMEN_FRONTIER_FIXTURE_SCHEMA_VERSION
    aggregate_only: bool = True
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "specimen frontier fixture_id")
        require_non_empty(self.context_key, "specimen frontier context_key")
        if self.schema_version != SPECIMEN_FRONTIER_FIXTURE_SCHEMA_VERSION:
            raise ValidationError("unsupported specimen frontier fixture schema")
        if not self.aggregate_only:
            raise ValidationError("specimen frontier fixture must be aggregate-only")
        if not self.content_address:
            body = {
                "fixture_id": self.fixture_id,
                "context_key": self.context_key,
                "schema_version": self.schema_version,
                "aggregate_only": self.aggregate_only,
                "sources": self.sources,
                "positives": self.positives,
                "controls": self.controls,
            }
            object.__setattr__(self, "content_address", content_hash(body))

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(sorted(source.source_id for source in self.sources))

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(sorted({record.operation.value for record in self.positives + self.controls}))

    @property
    def record_ids(self) -> tuple[str, ...]:
        return tuple(sorted(record.record_id for record in self.positives + self.controls))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> SpecimenFrontierFixtureCatalog:
        sources = tuple(
            SpecimenFrontierSourceReceipt(
                source_id=str(item["source_id"]),
                label=str(item["label"]),
                url=str(item["url"]),
                release=str(item.get("release", "unspecified")),
                aggregate_only=bool(item.get("aggregate_only", True)),
                patient_level=bool(item.get("patient_level", False)),
                attributes=dict(item.get("attributes", {})),
            )
            for item in payload.get("sources", ())
        )
        context_key = str(payload.get("context_key", ""))

        def records(key: str) -> tuple[SpecimenFrontierFixtureRecord, ...]:
            result: list[SpecimenFrontierFixtureRecord] = []
            for item in payload.get(key, ()):
                result.append(
                    SpecimenFrontierFixtureRecord(
                        record_id=str(item["record_id"]),
                        operation=SpecimenFrontierOperation(str(item["operation"])),
                        source_id=str(item["source_id"]),
                        context_key=str(item.get("context_key", context_key)),
                        expected_state=SpecimenFrontierFixtureState(str(item["expected_state"])),
                        expected_result_state=str(item["expected_result_state"]),
                        payload=dict(item.get("payload", {})),
                        parameters=dict(item.get("parameters", {})),
                        content_address=str(item.get("content_address", "")),
                    )
                )
            return tuple(result)

        return cls(
            fixture_id=str(payload.get("fixture_id", "")),
            context_key=context_key,
            sources=sources,
            positives=records("positives"),
            controls=records("controls"),
            schema_version=str(payload.get("schema_version", "")),
            aggregate_only=bool(payload.get("aggregate_only", True)),
            content_address=str(payload.get("content_address", "")),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> SpecimenFrontierFixtureCatalog:
        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"invalid specimen frontier fixture: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise ValidationError("specimen frontier fixture root must be an object")
        return cls.from_mapping(payload)


@dataclass(frozen=True, slots=True)
class SpecimenFrontierDataAuditReport:
    """Audit result for source scope, identity, context, and operation floors."""

    fixture_id: str
    context_key: str
    state: SpecimenFrontierFixtureState
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    positive_count: int
    control_count: int
    operation_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == SpecimenFrontierFixtureState.ACCEPTED and not self.issue_codes

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def _sensitive_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).strip().lower()
            if normalized in SPECIMEN_FRONTIER_SENSITIVE_KEYS:
                found.add(normalized)
            found.update(_sensitive_keys(nested))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            found.update(_sensitive_keys(nested))
    return found


def audit_specimen_frontier_fixture(
    catalog: SpecimenFrontierFixtureCatalog,
) -> SpecimenFrontierDataAuditReport:
    """Audit a catalog without executing specimen adapters."""

    issues: set[str] = set()
    records = catalog.positives + catalog.controls
    source_ids = catalog.source_ids
    record_ids = catalog.record_ids
    if len(source_ids) != len(set(source_ids)):
        issues.add("duplicate_source_id")
    if len(record_ids) != len(set(record_ids)):
        issues.add("duplicate_record_id")
    if len(catalog.positives) < SPECIMEN_FRONTIER_OPERATION_FLOOR:
        issues.add("positive_floor")
    if len(catalog.controls) < SPECIMEN_FRONTIER_CONTROL_FLOOR:
        issues.add("control_floor")
    if set(catalog.operation_ids) != {item.value for item in SpecimenFrontierOperation}:
        issues.add("operation_coverage")
    if len(catalog.context_key.split("|")) != SPECIMEN_FRONTIER_CONTEXT_DIMENSION_FLOOR:
        issues.add("context_dimension_count")
    if not catalog.aggregate_only or any(not source.aggregate_only for source in catalog.sources):
        issues.add("non_aggregate_scope")
    if any(source.patient_level for source in catalog.sources):
        issues.add("patient_level_source")
    if _sensitive_keys(catalog.to_dict()):
        issues.add("sensitive_payload")
    declared_sources = set(source_ids)
    for record in records:
        if record.context_key != catalog.context_key:
            issues.add("context_mismatch")
        if record.source_id not in declared_sources:
            issues.add("undeclared_source")
        if len(record.context_key.split("|")) != SPECIMEN_FRONTIER_CONTEXT_DIMENSION_FLOOR:
            issues.add("record_context_dimension_count")
        if _sensitive_keys(record.payload):
            issues.add("sensitive_record_payload")
        if record.content_address != content_hash(
            {
                "record_id": record.record_id,
                "operation": record.operation,
                "source_id": record.source_id,
                "context_key": record.context_key,
                "expected_state": record.expected_state,
                "expected_result_state": record.expected_result_state,
                "payload": record.payload,
                "parameters": record.parameters,
            }
        ):
            issues.add("record_address_mismatch")
    state = (
        SpecimenFrontierFixtureState.ACCEPTED if not issues else SpecimenFrontierFixtureState.REVIEW
    )
    body = {
        "fixture_id": catalog.fixture_id,
        "context_key": catalog.context_key,
        "state": state,
        "issue_codes": tuple(sorted(issues)),
        "source_ids": source_ids,
        "positive_count": len(catalog.positives),
        "control_count": len(catalog.controls),
        "operation_ids": catalog.operation_ids,
        "record_ids": record_ids,
    }
    return SpecimenFrontierDataAuditReport(
        fixture_id=catalog.fixture_id,
        context_key=catalog.context_key,
        state=state,
        issue_codes=tuple(sorted(issues)),
        source_ids=source_ids,
        positive_count=len(catalog.positives),
        control_count=len(catalog.controls),
        operation_ids=catalog.operation_ids,
        record_ids=record_ids,
        content_address=content_hash(body),
    )


__all__ = [
    "SPECIMEN_FRONTIER_CONTEXT_DIMENSION_FLOOR",
    "SPECIMEN_FRONTIER_CONTROL_FLOOR",
    "SPECIMEN_FRONTIER_FIXTURE_SCHEMA_VERSION",
    "SPECIMEN_FRONTIER_OPERATION_FLOOR",
    "SPECIMEN_FRONTIER_SENSITIVE_KEYS",
    "SpecimenFrontierDataAuditReport",
    "SpecimenFrontierFixtureCatalog",
    "SpecimenFrontierFixtureRecord",
    "SpecimenFrontierFixtureState",
    "SpecimenFrontierOperation",
    "SpecimenFrontierSourceReceipt",
    "audit_specimen_frontier_fixture",
]

"""Aggregate evidence boundary for specimen-origin and clonality adapters.

The four beta adapters operate on declared variant observations. This module
keeps their public evidence contract separate from the adapter implementation:
source receipts, exact context, positive cases, review controls, content
addresses, and a recursive aggregate-only boundary are all verified before
execution.
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

SPECIMEN_BETA_FRONTIER_FIXTURE_SCHEMA_VERSION = "specimen-beta-frontier-evidence-v1"
SPECIMEN_BETA_FRONTIER_OPERATION_FLOOR = 4
SPECIMEN_BETA_FRONTIER_CONTROL_FLOOR = 8
SPECIMEN_BETA_FRONTIER_CONTEXT_DIMENSION_FLOOR = 6
SPECIMEN_BETA_FRONTIER_SENSITIVE_KEYS = frozenset(
    {
        "patient_id",
        "subject_id",
        "medical_record_number",
        "sample_patient_id",
        "participant_id",
        "case_uuid",
        "individual_id",
    }
)


class SpecimenBetaFrontierOperation(StrEnum):
    """Adapter operations covered by the C05-C08 evidence plane."""

    ORIGIN = "origin"
    MOSAICISM = "mosaicism"
    CANCER_CELL_FRACTION = "cancer_cell_fraction"
    SUBCLONE = "subclone"


class SpecimenBetaFrontierFixtureState(StrEnum):
    """Fixture role, independent from the adapter result state."""

    ACCEPTED = "accepted"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierSourceReceipt:
    """Public documentation receipt used to shape an aggregate fixture."""

    source_id: str
    label: str
    url: str
    release: str
    scope: str
    aggregate_only: bool = True
    patient_level: bool = False
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("source_id", "label", "url", "release", "scope"):
            require_non_empty(str(getattr(self, name)), f"beta source receipt {name}")
        if not self.url.startswith(("https://", "http://")):
            raise ValidationError("beta source URL must be absolute")
        if self.patient_level or not self.aggregate_only:
            raise ValidationError("beta sources must be aggregate-only")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierFixtureRecord:
    """One positive operation record or negative-control record."""

    record_id: str
    operation: SpecimenBetaFrontierOperation
    source_ids: tuple[str, ...]
    context_key: str
    expected_fixture_state: SpecimenBetaFrontierFixtureState
    expected_result_state: str
    payload: Mapping[str, Any]
    parameters: Mapping[str, Any] = field(default_factory=dict)
    expected_issue_codes: tuple[str, ...] = ()
    expected_counts: Mapping[str, int] = field(default_factory=dict)
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "expected_result_state"):
            require_non_empty(str(getattr(self, name)), f"beta fixture record {name}")
        if not self.source_ids:
            raise ValidationError("beta fixture record requires source IDs")
        if not isinstance(self.payload, Mapping):
            raise ValidationError("beta fixture payload must be an object")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self._address_body()))

    def _address_body(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "operation": self.operation,
            "source_ids": self.source_ids,
            "context_key": self.context_key,
            "expected_fixture_state": self.expected_fixture_state,
            "expected_result_state": self.expected_result_state,
            "payload": self.payload,
            "parameters": self.parameters,
            "expected_issue_codes": self.expected_issue_codes,
            "expected_counts": self.expected_counts,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierFixtureCatalog:
    """Complete aggregate catalog for C05-C08."""

    fixture_id: str
    context_key: str
    sources: tuple[SpecimenBetaFrontierSourceReceipt, ...]
    positives: tuple[SpecimenBetaFrontierFixtureRecord, ...]
    controls: tuple[SpecimenBetaFrontierFixtureRecord, ...]
    schema_version: str = SPECIMEN_BETA_FRONTIER_FIXTURE_SCHEMA_VERSION
    aggregate_only: bool = True
    content_address: str = ""

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "beta fixture ID")
        require_non_empty(self.context_key, "beta context key")
        if self.schema_version != SPECIMEN_BETA_FRONTIER_FIXTURE_SCHEMA_VERSION:
            raise ValidationError("unsupported beta fixture schema")
        if not self.aggregate_only:
            raise ValidationError("beta fixture must be aggregate-only")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self._address_body()))

    def _address_body(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "context_key": self.context_key,
            "schema_version": self.schema_version,
            "aggregate_only": self.aggregate_only,
            "sources": self.sources,
            "positives": self.positives,
            "controls": self.controls,
        }

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(sorted(source.source_id for source in self.sources))

    @property
    def records(self) -> tuple[SpecimenBetaFrontierFixtureRecord, ...]:
        return self.positives + self.controls

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(sorted({record.operation.value for record in self.records}))

    @property
    def record_ids(self) -> tuple[str, ...]:
        return tuple(sorted(record.record_id for record in self.records))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> SpecimenBetaFrontierFixtureCatalog:
        sources = tuple(
            SpecimenBetaFrontierSourceReceipt(
                source_id=str(item["source_id"]),
                label=str(item["label"]),
                url=str(item["url"]),
                release=str(item.get("release", "unspecified")),
                scope=str(item.get("scope", "aggregate documentation")),
                aggregate_only=bool(item.get("aggregate_only", True)),
                patient_level=bool(item.get("patient_level", False)),
                attributes=dict(item.get("attributes", {})),
            )
            for item in payload.get("sources", ())
        )
        context_key = str(payload.get("context_key", ""))

        def records(key: str) -> tuple[SpecimenBetaFrontierFixtureRecord, ...]:
            result: list[SpecimenBetaFrontierFixtureRecord] = []
            for item in payload.get(key, ()):
                source_ids = tuple(
                    str(value)
                    for value in item.get("source_ids", (item.get("source_id", ""),))
                    if str(value)
                )
                result.append(
                    SpecimenBetaFrontierFixtureRecord(
                        record_id=str(item["record_id"]),
                        operation=SpecimenBetaFrontierOperation(str(item["operation"])),
                        source_ids=source_ids,
                        context_key=str(item.get("context_key", context_key)),
                        expected_fixture_state=SpecimenBetaFrontierFixtureState(
                            str(item["expected_fixture_state"])
                        ),
                        expected_result_state=str(item["expected_result_state"]),
                        payload=dict(item.get("payload", {})),
                        parameters=dict(item.get("parameters", {})),
                        expected_issue_codes=tuple(
                            sorted(str(value) for value in item.get("expected_issue_codes", ()))
                        ),
                        expected_counts={
                            str(name): int(value)
                            for name, value in dict(item.get("expected_counts", {})).items()
                        },
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
    def from_file(cls, path: str | Path) -> SpecimenBetaFrontierFixtureCatalog:
        source = Path(path)
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"invalid beta fixture: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise ValidationError("beta fixture root must be an object")
        return cls.from_mapping(payload)


@dataclass(frozen=True, slots=True)
class SpecimenBetaFrontierDataAuditReport:
    """Source, identity, context, and scope audit result."""

    fixture_id: str
    context_key: str
    state: SpecimenBetaFrontierFixtureState
    issue_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    positive_count: int
    control_count: int
    operation_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state == SpecimenBetaFrontierFixtureState.ACCEPTED and not self.issue_codes

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def _sensitive_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).strip().lower()
            if normalized in SPECIMEN_BETA_FRONTIER_SENSITIVE_KEYS:
                found.add(normalized)
            found.update(_sensitive_keys(nested))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            found.update(_sensitive_keys(nested))
    return found


def audit_specimen_beta_frontier_fixture(
    catalog: SpecimenBetaFrontierFixtureCatalog,
) -> SpecimenBetaFrontierDataAuditReport:
    """Audit a catalog without executing any adapter."""

    issues: set[str] = set()
    records = catalog.records
    source_ids = catalog.source_ids
    record_ids = catalog.record_ids
    expected_operations = {item.value for item in SpecimenBetaFrontierOperation}
    if len(source_ids) != len(set(source_ids)):
        issues.add("duplicate_source_id")
    if len(record_ids) != len(set(record_ids)):
        issues.add("duplicate_record_id")
    if len(catalog.positives) < SPECIMEN_BETA_FRONTIER_OPERATION_FLOOR:
        issues.add("positive_floor")
    if len(catalog.controls) < SPECIMEN_BETA_FRONTIER_CONTROL_FLOOR:
        issues.add("control_floor")
    if set(catalog.operation_ids) != expected_operations:
        issues.add("operation_coverage")
    if len(catalog.context_key.split("|")) != SPECIMEN_BETA_FRONTIER_CONTEXT_DIMENSION_FLOOR:
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
        if not set(record.source_ids).issubset(declared_sources):
            issues.add("undeclared_source")
        if len(record.context_key.split("|")) != SPECIMEN_BETA_FRONTIER_CONTEXT_DIMENSION_FLOOR:
            issues.add("record_context_dimension_count")
        if _sensitive_keys(record.payload):
            issues.add("sensitive_record_payload")
        if record.content_address != content_hash(record._address_body()):
            issues.add("record_address_mismatch")
    state = (
        SpecimenBetaFrontierFixtureState.ACCEPTED
        if not issues
        else SpecimenBetaFrontierFixtureState.REVIEW
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
    return SpecimenBetaFrontierDataAuditReport(
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
    "SPECIMEN_BETA_FRONTIER_CONTEXT_DIMENSION_FLOOR",
    "SPECIMEN_BETA_FRONTIER_CONTROL_FLOOR",
    "SPECIMEN_BETA_FRONTIER_FIXTURE_SCHEMA_VERSION",
    "SPECIMEN_BETA_FRONTIER_OPERATION_FLOOR",
    "SPECIMEN_BETA_FRONTIER_SENSITIVE_KEYS",
    "SpecimenBetaFrontierDataAuditReport",
    "SpecimenBetaFrontierFixtureCatalog",
    "SpecimenBetaFrontierFixtureRecord",
    "SpecimenBetaFrontierFixtureState",
    "SpecimenBetaFrontierOperation",
    "SpecimenBetaFrontierSourceReceipt",
    "audit_specimen_beta_frontier_fixture",
]

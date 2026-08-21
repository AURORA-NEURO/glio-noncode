"""Public aggregate fixture and source boundary for Domain 03 C13-C16.

The older frontier adapters provide the bounded operations. This module gives
those operations a release-facing public-data contract: an exact context, a
small source manifest, explicit positive and review records, deterministic
record addresses, and a data audit that rejects patient-level payloads.

The fixture is intentionally aggregate and synthetic. Public sources supply
the vocabulary and scope for the fields; they are not copied into the fixture
as patient records. The resulting catalog is suitable for deterministic
software verification while remaining separate from clinical validation.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .frontier_data_alpha import FrontierState
from .serialization import content_hash, jsonable, require_non_empty

SPECIMEN_PREANALYTIC_FIXTURE_VERSION = "specimen-preanalytic-public-aggregate-v1"
EXPECTED_CONTEXT_KEY = (
    "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
)
EXPECTED_POSITIVE_COUNT = 4
EXPECTED_CONTROL_COUNT = 8


class SpecimenPreanalyticOperation(StrEnum):
    """The four Domain 03 C13-C16 operations covered by the fixture."""

    PREANALYTIC_QUALITY = "preanalytic_quality"
    ASSAY_LINEAGE = "assay_lineage"
    IDENTITY_ADJUDICATION = "identity_adjudication"
    CONTEXT_ENVELOPE = "context_envelope"


class SpecimenPreanalyticRole(StrEnum):
    """Fixture role used to keep positive and review controls explicit."""

    POSITIVE = "positive"
    CONTROL = "control"


_FORBIDDEN_KEYS = frozenset(
    {
        "patient_id",
        "subject_id",
        "medical_record_number",
        "sample_patient_id",
        "participant_id",
        "case_uuid",
        "individual_id",
        "person_id",
        "direct_identifier",
        "name",
        "address",
        "phone",
        "email",
    }
)


def _text(value: Any, field: str) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _required(value: Any, field: str) -> str:
    return require_non_empty(_text(value, field), field)


def _text_tuple(value: Any, field: str) -> tuple[str, ...]:
    if isinstance(value, str):
        value = (value,)
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        raise ValidationError(f"{field} must be a list")
    values = tuple(_required(item, field) for item in value)
    if not values:
        raise ValidationError(f"{field} must not be empty")
    return values


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _forbidden_keys(value: Any) -> tuple[str, ...]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower()
            if normalized in _FORBIDDEN_KEYS:
                found.add(normalized)
            found.update(_forbidden_keys(nested))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            found.update(_forbidden_keys(nested))
    return tuple(sorted(found))


def _context_is_well_formed(context_key: str) -> bool:
    parts = context_key.split("|")
    return len(parts) == 6 and all(part.strip() for part in parts)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticSourceReceipt:
    """A public source declaration used for field vocabulary and scope."""

    source_id: str
    title: str
    uri: str
    scope: str
    patient_level: bool
    accessed_on: str
    content_address: str

    def __post_init__(self) -> None:
        for field in ("source_id", "title", "uri", "scope", "accessed_on"):
            require_non_empty(str(getattr(self, field)), f"source receipt {field}")
        if not self.uri.startswith("https://"):
            raise ValidationError("source receipt URI must use HTTPS")
        if self.patient_level:
            raise ValidationError("public source receipt must not be patient-level")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("source receipt must be content-addressed")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SpecimenPreanalyticSourceReceipt:
        row = _mapping(raw, "source receipt")
        body = {
            "source_id": _required(row.get("source_id"), "source_id"),
            "title": _required(row.get("title"), "title"),
            "uri": _required(row.get("uri"), "uri"),
            "scope": _required(row.get("scope"), "scope"),
            "patient_level": row.get("patient_level", False),
            "accessed_on": _required(row.get("accessed_on"), "accessed_on"),
        }
        if not isinstance(body["patient_level"], bool):
            raise ValidationError("source receipt patient_level must be boolean")
        return cls(**body, content_address=content_hash(body))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticRecord:
    """One aggregate operation input and its declared expected state."""

    record_id: str
    operation: SpecimenPreanalyticOperation
    role: SpecimenPreanalyticRole
    expected_state: FrontierState
    context_key: str
    source_ids: tuple[str, ...]
    expected_issue_codes: tuple[str, ...]
    payload: Mapping[str, Any]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.record_id, "record ID")
        require_non_empty(self.context_key, "record context")
        if not _context_is_well_formed(self.context_key):
            raise ValidationError("record context must have six non-empty components")
        if not self.source_ids:
            raise ValidationError("record source IDs must not be empty")
        if not isinstance(self.payload, Mapping):
            raise ValidationError("record payload must be an object")
        forbidden = _forbidden_keys(self.payload)
        if forbidden:
            raise ValidationError(f"record payload has forbidden keys: {', '.join(forbidden)}")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("record must be content-addressed")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SpecimenPreanalyticRecord:
        row = _mapping(raw, "fixture record")
        record_id = _required(row.get("record_id"), "record_id")
        operation = SpecimenPreanalyticOperation(_required(row.get("operation"), "operation"))
        role = SpecimenPreanalyticRole(_required(row.get("role"), "role"))
        expected_state = FrontierState(_required(row.get("expected_state"), "expected_state"))
        context_key = _required(row.get("context_key"), "context_key")
        source_ids = _text_tuple(row.get("source_ids"), "source_ids")
        issue_value = row.get("expected_issue_codes", ())
        if isinstance(issue_value, str):
            issue_value = (issue_value,)
        if not isinstance(issue_value, Sequence):
            raise ValidationError("expected_issue_codes must be a list")
        expected_issue_codes = tuple(str(item).strip() for item in issue_value if str(item).strip())
        payload = dict(_mapping(row.get("payload"), "payload"))
        body = {
            "record_id": record_id,
            "operation": operation.value,
            "role": role.value,
            "expected_state": expected_state.value,
            "context_key": context_key,
            "source_ids": source_ids,
            "expected_issue_codes": expected_issue_codes,
            "payload": payload,
        }
        return cls(
            record_id=record_id,
            operation=operation,
            role=role,
            expected_state=expected_state,
            context_key=context_key,
            source_ids=source_ids,
            expected_issue_codes=expected_issue_codes,
            payload=payload,
            content_address=content_hash(body),
        )

    def address_body(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "operation": self.operation.value,
            "role": self.role.value,
            "expected_state": self.expected_state.value,
            "context_key": self.context_key,
            "source_ids": self.source_ids,
            "expected_issue_codes": self.expected_issue_codes,
            "payload": self.payload,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticFixtureCatalog:
    """Typed public aggregate catalog for the C13-C16 evidence plane."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_receipts: tuple[SpecimenPreanalyticSourceReceipt, ...]
    records: tuple[SpecimenPreanalyticRecord, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.fixture_id, "fixture ID")
        require_non_empty(self.fixture_version, "fixture version")
        require_non_empty(self.context_key, "fixture context")
        if not _context_is_well_formed(self.context_key):
            raise ValidationError("fixture context must have six non-empty components")
        if not self.source_receipts:
            raise ValidationError("fixture requires source receipts")
        if not self.records:
            raise ValidationError("fixture requires records")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("fixture must be content-addressed")

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(sorted(receipt.source_id for receipt in self.source_receipts))

    @property
    def record_ids(self) -> tuple[str, ...]:
        return tuple(record.record_id for record in self.records)

    @property
    def operation_ids(self) -> tuple[str, ...]:
        return tuple(sorted({record.operation.value for record in self.records}))

    @property
    def positives(self) -> tuple[SpecimenPreanalyticRecord, ...]:
        return tuple(
            record for record in self.records if record.role == SpecimenPreanalyticRole.POSITIVE
        )

    @property
    def controls(self) -> tuple[SpecimenPreanalyticRecord, ...]:
        return tuple(
            record for record in self.records if record.role == SpecimenPreanalyticRole.CONTROL
        )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> SpecimenPreanalyticFixtureCatalog:
        root = _mapping(raw, "fixture")
        fixture_id = _required(root.get("fixture_id"), "fixture_id")
        fixture_version = _required(root.get("fixture_version"), "fixture_version")
        context_key = _required(root.get("context_key"), "context_key")
        sources_raw = root.get("source_receipts")
        records_raw = root.get("records")
        if not isinstance(sources_raw, Sequence) or isinstance(
            sources_raw, (str, bytes, bytearray)
        ):
            raise ValidationError("source_receipts must be a list")
        if not isinstance(records_raw, Sequence) or isinstance(
            records_raw, (str, bytes, bytearray)
        ):
            raise ValidationError("records must be a list")
        sources = tuple(SpecimenPreanalyticSourceReceipt.from_mapping(item) for item in sources_raw)
        records = tuple(SpecimenPreanalyticRecord.from_mapping(item) for item in records_raw)
        body = {
            "fixture_id": fixture_id,
            "fixture_version": fixture_version,
            "context_key": context_key,
            "source_receipts": sources,
            "records": records,
        }
        return cls(fixture_id, fixture_version, context_key, sources, records, content_hash(body))

    @classmethod
    def from_file(cls, path: str | Path) -> SpecimenPreanalyticFixtureCatalog:
        source = Path(path)
        return cls.from_mapping(json.loads(source.read_text(encoding="utf-8")))

    def address_body(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "fixture_version": self.fixture_version,
            "context_key": self.context_key,
            "source_receipts": self.source_receipts,
            "records": self.records,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticDataCheck:
    """One explicit public-data boundary assertion."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SpecimenPreanalyticDataAudit:
    """Data-boundary report for the public aggregate catalog."""

    fixture_id: str
    state: str
    checks: tuple[SpecimenPreanalyticDataCheck, ...]
    content_address: str

    @property
    def passed(self) -> bool:
        return self.state == "accepted" and all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed": self.passed,
            "failed_check_ids": self.failed_check_ids,
        }


def audit_specimen_preanalytic_data(
    catalog: SpecimenPreanalyticFixtureCatalog,
) -> SpecimenPreanalyticDataAudit:
    """Audit identity, source, context, role, operation, and privacy boundaries."""

    checks: list[SpecimenPreanalyticDataCheck] = []
    source_ids = catalog.source_ids
    record_ids = catalog.record_ids
    expected_operations = tuple(item.value for item in SpecimenPreanalyticOperation)

    def add(check_id: str, passed: bool, observed: Any, expected: Any, message: str) -> None:
        checks.append(
            SpecimenPreanalyticDataCheck(check_id, bool(passed), observed, expected, message)
        )

    add(
        "fixture-version",
        catalog.fixture_version == SPECIMEN_PREANALYTIC_FIXTURE_VERSION,
        catalog.fixture_version,
        SPECIMEN_PREANALYTIC_FIXTURE_VERSION,
        "fixture version is locked",
    )
    add(
        "context-shape",
        _context_is_well_formed(catalog.context_key),
        catalog.context_key,
        "six non-empty context fields",
        "context key is complete",
    )
    add(
        "context-exact",
        catalog.context_key == EXPECTED_CONTEXT_KEY,
        catalog.context_key,
        EXPECTED_CONTEXT_KEY,
        "fixture context is exact",
    )
    add(
        "source-floor",
        len(catalog.source_receipts) >= 4,
        len(catalog.source_receipts),
        ">=4",
        "public source receipt floor",
    )
    add(
        "source-identity",
        len(set(source_ids)) == len(source_ids),
        source_ids,
        "unique source IDs",
        "source IDs are unique",
    )
    add(
        "source-public",
        all(not receipt.patient_level for receipt in catalog.source_receipts),
        True,
        False,
        "source receipts are aggregate",
    )
    add(
        "source-addresses",
        all(receipt.content_address.startswith("sha256:") for receipt in catalog.source_receipts),
        True,
        True,
        "source receipts are addressed",
    )
    add(
        "source-uris",
        all(receipt.uri.startswith("https://") for receipt in catalog.source_receipts),
        True,
        True,
        "source URIs use HTTPS",
    )
    add(
        "record-floor",
        len(catalog.records) == EXPECTED_POSITIVE_COUNT + EXPECTED_CONTROL_COUNT,
        len(catalog.records),
        12,
        "fixture record count is locked",
    )
    add(
        "record-identity",
        len(set(record_ids)) == len(record_ids),
        record_ids,
        "unique record IDs",
        "record IDs are unique",
    )
    add(
        "record-addresses",
        all(record.content_address.startswith("sha256:") for record in catalog.records),
        True,
        True,
        "record addresses exist",
    )
    add(
        "record-context",
        all(record.context_key == catalog.context_key for record in catalog.records),
        True,
        True,
        "record contexts match",
    )
    add(
        "record-sources",
        all(set(record.source_ids).issubset(set(source_ids)) for record in catalog.records),
        True,
        True,
        "record source IDs are declared",
    )
    add(
        "positive-floor",
        len(catalog.positives) == EXPECTED_POSITIVE_COUNT,
        len(catalog.positives),
        EXPECTED_POSITIVE_COUNT,
        "positive record floor",
    )
    add(
        "control-floor",
        len(catalog.controls) == EXPECTED_CONTROL_COUNT,
        len(catalog.controls),
        EXPECTED_CONTROL_COUNT,
        "review control floor",
    )
    add(
        "role-partition",
        len(catalog.positives) + len(catalog.controls) == len(catalog.records),
        len(catalog.positives) + len(catalog.controls),
        len(catalog.records),
        "roles partition records",
    )
    add(
        "operation-coverage",
        set(catalog.operation_ids) == set(expected_operations),
        catalog.operation_ids,
        expected_operations,
        "all four operation IDs are covered",
    )
    add(
        "operation-balance",
        all(
            any(record.operation.value == operation for record in catalog.records)
            for operation in expected_operations
        ),
        True,
        True,
        "each operation has a record",
    )
    add(
        "payload-boundary",
        not any(_forbidden_keys(record.payload) for record in catalog.records),
        True,
        True,
        "payloads contain no direct identifiers",
    )
    add(
        "payload-mappings",
        all(isinstance(record.payload, Mapping) for record in catalog.records),
        True,
        True,
        "payloads are objects",
    )
    add(
        "fixture-address",
        catalog.content_address == content_hash(catalog.address_body()),
        catalog.content_address,
        "sha256:<recomputed>",
        "fixture address is deterministic",
    )
    add(
        "source-coverage",
        all(record.source_ids for record in catalog.records),
        True,
        True,
        "every record retains provenance",
    )
    add(
        "expected-state-roles",
        all(
            record.expected_state in {FrontierState.ACCEPTED, FrontierState.PUBLISHED}
            if record.role == SpecimenPreanalyticRole.POSITIVE
            else record.expected_state == FrontierState.REVIEW
            for record in catalog.records
        ),
        True,
        "positive accepted/published; controls review",
        "role states are conservative",
    )
    state = "accepted" if all(check.passed for check in checks) else "review"
    body = {"fixture_id": catalog.fixture_id, "state": state, "checks": checks}
    return SpecimenPreanalyticDataAudit(
        catalog.fixture_id, state, tuple(checks), content_hash(body)
    )


__all__ = [
    "EXPECTED_CONTEXT_KEY",
    "EXPECTED_CONTROL_COUNT",
    "EXPECTED_POSITIVE_COUNT",
    "SPECIMEN_PREANALYTIC_FIXTURE_VERSION",
    "SpecimenPreanalyticDataAudit",
    "SpecimenPreanalyticDataCheck",
    "SpecimenPreanalyticFixtureCatalog",
    "SpecimenPreanalyticOperation",
    "SpecimenPreanalyticRecord",
    "SpecimenPreanalyticRole",
    "SpecimenPreanalyticSourceReceipt",
    "audit_specimen_preanalytic_data",
]

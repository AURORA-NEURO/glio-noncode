"""Public aggregate fixture and source boundary for Domain 04 C01-C04.

The reference-coordinate plane is deliberately separated from the older
coordinate adapters.  The adapters perform bounded registry, liftover, and
pangenome operations; this module defines the release-facing data boundary
that makes those operations reproducible.  It accepts public source receipts,
aggregate coordinate examples, and explicit controls.  It never treats a
coordinate conversion as proof of sequence equivalence or clinical meaning.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .reference_extensions import ReferenceExtensionState
from .serialization import content_hash, jsonable, require_non_empty

REFERENCE_COORDINATE_FIXTURE_VERSION = "reference-coordinate-public-aggregate-v1"
REFERENCE_COORDINATE_CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline"
REFERENCE_COORDINATE_POSITIVE_COUNT = 4
REFERENCE_COORDINATE_CONTROL_COUNT = 12
REFERENCE_COORDINATE_SOURCE_COUNT = 6


class ReferenceCoordinateOperation(StrEnum):
    """The four Domain 04 coordinate operations covered by the fixture."""

    REFERENCE_REGISTRY = "reference_registry"
    LIFTOVER_CHAIN = "liftover_chain"
    LIFTOVER_AMBIGUITY = "liftover_ambiguity"
    PANGENOME_COORDINATE = "pangenome_coordinate"


class ReferenceCoordinateRole(StrEnum):
    """Fixture role that separates release paths from review controls."""

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
        "access_token",
        "refresh_token",
        "api_key",
        "private_key",
        "secret",
    }
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _required(value: Any, field: str) -> str:
    return require_non_empty(_text(value), field)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _text_tuple(value: Any, field: str) -> tuple[str, ...]:
    if isinstance(value, str):
        value = (value,)
    if not isinstance(value, Sequence) or isinstance(value, (bytes, bytearray)):
        raise ValidationError(f"{field} must be a list")
    result = tuple(_required(item, field) for item in value)
    if not result:
        raise ValidationError(f"{field} must not be empty")
    return result


def _context_is_well_formed(context_key: str) -> bool:
    parts = context_key.split("|")
    return len(parts) == 6 and all(part.strip() for part in parts)


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


def _payload_shape(record: ReferenceCoordinateRecord) -> bool:
    """Check only the outer operation shape; adapters own semantic checks."""

    payload = record.payload
    if record.operation == ReferenceCoordinateOperation.REFERENCE_REGISTRY:
        return bool(_text(payload.get("query")))
    if record.operation == ReferenceCoordinateOperation.LIFTOVER_CHAIN:
        return all(
            _text(payload.get(field))
            for field in ("chain_text", "source_assembly", "target_assembly", "variant")
        )
    if record.operation == ReferenceCoordinateOperation.LIFTOVER_AMBIGUITY:
        interval = payload.get("query_interval")
        return (
            isinstance(payload.get("segments"), Sequence)
            and not isinstance(payload.get("segments"), (str, bytes, bytearray))
            and isinstance(interval, Mapping)
        )
    if record.operation == ReferenceCoordinateOperation.PANGENOME_COORDINATE:
        interval = payload.get("query_interval")
        return (
            isinstance(payload.get("paths"), Sequence)
            and not isinstance(payload.get("paths"), (str, bytes, bytearray))
            and isinstance(interval, Mapping)
        )
    return False


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateSourceReceipt:
    """A public source declaration for vocabulary, scope, or provenance."""

    source_id: str
    title: str
    uri: str
    scope: str
    patient_level: bool
    accessed_on: str
    content_address: str
    license_note: str = "public documentation or public aggregate data"

    def __post_init__(self) -> None:
        for field in ("source_id", "title", "uri", "scope", "accessed_on", "license_note"):
            require_non_empty(str(getattr(self, field)), f"source receipt {field}")
        if not self.uri.startswith("https://"):
            raise ValidationError("source receipt URI must use HTTPS")
        if self.patient_level:
            raise ValidationError("reference source receipt must not be patient-level")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("source receipt must be content-addressed")

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ReferenceCoordinateSourceReceipt:
        row = _mapping(raw, "source receipt")
        body = {
            "source_id": _required(row.get("source_id"), "source_id"),
            "title": _required(row.get("title"), "title"),
            "uri": _required(row.get("uri"), "uri"),
            "scope": _required(row.get("scope"), "scope"),
            "patient_level": row.get("patient_level", False),
            "accessed_on": _required(row.get("accessed_on"), "accessed_on"),
            "license_note": _required(
                row.get("license_note", "public documentation or public aggregate data"),
                "license_note",
            ),
        }
        if not isinstance(body["patient_level"], bool):
            raise ValidationError("source receipt patient_level must be boolean")
        return cls(**body, content_address=content_hash(body))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateRecord:
    """One aggregate operation input and its declared expected state."""

    record_id: str
    operation: ReferenceCoordinateOperation
    role: ReferenceCoordinateRole
    expected_state: ReferenceExtensionState
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
    def from_mapping(cls, raw: Mapping[str, Any]) -> ReferenceCoordinateRecord:
        row = _mapping(raw, "coordinate fixture record")
        record_id = _required(row.get("record_id"), "record_id")
        operation = ReferenceCoordinateOperation(_required(row.get("operation"), "operation"))
        role = ReferenceCoordinateRole(_required(row.get("role"), "role"))
        expected_state = ReferenceExtensionState(
            _required(row.get("expected_state"), "expected_state")
        )
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
class ReferenceCoordinateFixtureCatalog:
    """Typed public aggregate catalog for Domain 04 C01-C04."""

    fixture_id: str
    fixture_version: str
    context_key: str
    source_receipts: tuple[ReferenceCoordinateSourceReceipt, ...]
    records: tuple[ReferenceCoordinateRecord, ...]
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
    def positives(self) -> tuple[ReferenceCoordinateRecord, ...]:
        return tuple(
            record for record in self.records if record.role == ReferenceCoordinateRole.POSITIVE
        )

    @property
    def controls(self) -> tuple[ReferenceCoordinateRecord, ...]:
        return tuple(
            record for record in self.records if record.role == ReferenceCoordinateRole.CONTROL
        )

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> ReferenceCoordinateFixtureCatalog:
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
        sources = tuple(ReferenceCoordinateSourceReceipt.from_mapping(item) for item in sources_raw)
        records = tuple(ReferenceCoordinateRecord.from_mapping(item) for item in records_raw)
        body = {
            "fixture_id": fixture_id,
            "fixture_version": fixture_version,
            "context_key": context_key,
            "source_receipts": sources,
            "records": records,
        }
        return cls(fixture_id, fixture_version, context_key, sources, records, content_hash(body))

    @classmethod
    def from_file(cls, path: str | Path) -> ReferenceCoordinateFixtureCatalog:
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
class ReferenceCoordinateDataCheck:
    """One explicit public-data boundary assertion."""

    check_id: str
    passed: bool
    observed: Any
    expected: Any
    message: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceCoordinateDataAudit:
    """Data-boundary report for the reference-coordinate fixture."""

    fixture_id: str
    state: str
    checks: tuple[ReferenceCoordinateDataCheck, ...]
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


def audit_reference_coordinate_data(
    catalog: ReferenceCoordinateFixtureCatalog,
) -> ReferenceCoordinateDataAudit:
    """Audit identity, source, context, operation, and privacy boundaries."""

    checks: list[ReferenceCoordinateDataCheck] = []
    source_ids = catalog.source_ids
    record_ids = catalog.record_ids
    expected_operations = tuple(item.value for item in ReferenceCoordinateOperation)

    def add(check_id: str, passed: bool, observed: Any, expected: Any, message: str) -> None:
        checks.append(
            ReferenceCoordinateDataCheck(check_id, bool(passed), observed, expected, message)
        )

    add(
        "fixture-version",
        catalog.fixture_version == REFERENCE_COORDINATE_FIXTURE_VERSION,
        catalog.fixture_version,
        REFERENCE_COORDINATE_FIXTURE_VERSION,
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
        catalog.context_key == REFERENCE_COORDINATE_CONTEXT_KEY,
        catalog.context_key,
        REFERENCE_COORDINATE_CONTEXT_KEY,
        "fixture context is exact",
    )
    add(
        "source-floor",
        len(catalog.source_receipts) == REFERENCE_COORDINATE_SOURCE_COUNT,
        len(catalog.source_receipts),
        REFERENCE_COORDINATE_SOURCE_COUNT,
        "source receipt count is locked",
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
        all(not receipt.patient_level for receipt in catalog.source_receipts),
        True,
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
        "source-scopes",
        all(receipt.scope.strip() for receipt in catalog.source_receipts),
        True,
        True,
        "source scopes are declared",
    )
    add(
        "record-floor",
        len(catalog.records)
        == REFERENCE_COORDINATE_POSITIVE_COUNT + REFERENCE_COORDINATE_CONTROL_COUNT,
        len(catalog.records),
        REFERENCE_COORDINATE_POSITIVE_COUNT + REFERENCE_COORDINATE_CONTROL_COUNT,
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
        len(catalog.positives) == REFERENCE_COORDINATE_POSITIVE_COUNT,
        len(catalog.positives),
        REFERENCE_COORDINATE_POSITIVE_COUNT,
        "positive record floor",
    )
    add(
        "control-floor",
        len(catalog.controls) == REFERENCE_COORDINATE_CONTROL_COUNT,
        len(catalog.controls),
        REFERENCE_COORDINATE_CONTROL_COUNT,
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
        "payloads contain no direct identifiers or secrets",
    )
    add(
        "payload-mappings",
        all(isinstance(record.payload, Mapping) for record in catalog.records),
        True,
        True,
        "payloads are objects",
    )
    add(
        "payload-shapes",
        all(_payload_shape(record) for record in catalog.records),
        True,
        True,
        "operation payload outer shapes are present",
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
            record.expected_state == ReferenceExtensionState.SUPPORTED
            if record.role == ReferenceCoordinateRole.POSITIVE
            else record.expected_state != ReferenceExtensionState.SUPPORTED
            for record in catalog.records
        ),
        True,
        "positive supported; controls non-supported",
        "role states are conservative",
    )
    add(
        "expected-issues",
        all(
            record.role == ReferenceCoordinateRole.POSITIVE or bool(record.expected_issue_codes)
            for record in catalog.records
        ),
        True,
        True,
        "controls name their expected issue codes",
    )
    state = "accepted" if all(check.passed for check in checks) else "review"
    body = {"fixture_id": catalog.fixture_id, "state": state, "checks": checks}
    return ReferenceCoordinateDataAudit(
        catalog.fixture_id, state, tuple(checks), content_hash(body)
    )


__all__ = [
    "REFERENCE_COORDINATE_CONTEXT_KEY",
    "REFERENCE_COORDINATE_CONTROL_COUNT",
    "REFERENCE_COORDINATE_FIXTURE_VERSION",
    "REFERENCE_COORDINATE_POSITIVE_COUNT",
    "REFERENCE_COORDINATE_SOURCE_COUNT",
    "ReferenceCoordinateDataAudit",
    "ReferenceCoordinateDataCheck",
    "ReferenceCoordinateFixtureCatalog",
    "ReferenceCoordinateOperation",
    "ReferenceCoordinateRecord",
    "ReferenceCoordinateRole",
    "ReferenceCoordinateSourceReceipt",
    "audit_reference_coordinate_data",
]

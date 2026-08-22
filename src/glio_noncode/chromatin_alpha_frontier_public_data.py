"""Closed public aggregate fixture for Domain 07 C09-C12.

The fixture makes four chromatin-alpha operations executable on the same
declared context: interval segmentation, reference/alternate signal deltas,
bounded epigenomic mixture estimates, and transparent batch/composition
correction.  Positive rows and controls are retained together so every
uncertain, malformed, or foreign-context path remains observable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .chromatin_frontier_public_data import default_chromatin_frontier_fixture
from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

CHROMATIN_ALPHA_FRONTIER_FIXTURE_VERSION = "2026.08.d07-c09-c12.v1"
CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor|unknown"
CHROMATIN_ALPHA_FRONTIER_BOUNDARY = "public_aggregate_non_patient"
CHROMATIN_ALPHA_FRONTIER_POSITIVE_COUNT = 4
CHROMATIN_ALPHA_FRONTIER_CONTROL_COUNT = 12
CHROMATIN_ALPHA_FRONTIER_SOURCE_COUNT = 5


class ChromatinAlphaFrontierOperation(StrEnum):
    SEGMENTATION = "chromatin_segmentation"
    ALLELE_SPECIFIC = "allele_specific_chromatin"
    PURITY = "epigenomic_purity"
    COMPOSITION_CORRECTION = "batch_composition_correction"


class ChromatinAlphaFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierSourceReceipt:
    source_id: str
    title: str
    uri: str
    source_kind: str
    release: str
    scope: str
    context_key: str
    public_aggregate: bool = True
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "title",
            "uri",
            "source_kind",
            "release",
            "scope",
            "context_key",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("source receipts require HTTPS")
        if self.context_key != CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY:
            raise ValidationError("source context is outside the tranche")
        if not self.public_aggregate:
            raise ValidationError("source receipt must be aggregate")
        if not self.content_address:
            object.__setattr__(
                self, "content_address", content_hash(self.to_dict(include_address=False))
            )

    def to_dict(self, *, include_address: bool = True) -> dict[str, Any]:
        result = {
            "source_id": self.source_id,
            "title": self.title,
            "uri": self.uri,
            "source_kind": self.source_kind,
            "release": self.release,
            "scope": self.scope,
            "context_key": self.context_key,
            "public_aggregate": self.public_aggregate,
        }
        if include_address:
            result["content_address"] = self.content_address
        return result


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierRecord:
    record_id: str
    operation: ChromatinAlphaFrontierOperation
    role: ChromatinAlphaFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "expected_state", "description"):
            require_non_empty(str(getattr(self, name)), name)
        if self.context_key != CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY:
            raise ValidationError("record context is outside the tranche")
        if not self.source_ids or not self.payload:
            raise ValidationError("record requires source IDs and payload")
        if not isinstance(self.operation, ChromatinAlphaFrontierOperation):
            raise ValidationError("record operation must be declared")
        if not isinstance(self.role, ChromatinAlphaFrontierRole):
            raise ValidationError("record role must be declared")
        forbidden = {
            "patient",
            "subject",
            "sample_id",
            "donor_id",
            "participant_id",
            "individual_id",
        }
        if set(str(key).lower() for key in self.payload) & forbidden:
            raise ValidationError("subject-level keys are not permitted")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "operation": self.operation,
                        "role": self.role,
                        "context_key": self.context_key,
                        "source_ids": self.source_ids,
                        "payload": self.payload,
                        "expected_state": self.expected_state,
                        "expected_issue_codes": self.expected_issue_codes,
                        "description": self.description,
                    }
                ),
            )

    def to_dict(self, *, include_payload: bool = True) -> dict[str, Any]:
        result = {
            "record_id": self.record_id,
            "operation": self.operation.value,
            "role": self.role.value,
            "context_key": self.context_key,
            "source_ids": list(self.source_ids),
            "expected_state": self.expected_state,
            "expected_issue_codes": list(self.expected_issue_codes),
            "description": self.description,
            "content_address": self.content_address,
        }
        if include_payload:
            result["payload"] = jsonable(self.payload)
        return result


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[ChromatinAlphaFrontierSourceReceipt, ...]
    records: tuple[ChromatinAlphaFrontierRecord, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if self.fixture_version != CHROMATIN_ALPHA_FRONTIER_FIXTURE_VERSION:
            raise ValidationError("unsupported chromatin alpha frontier version")
        if self.context_key != CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY:
            raise ValidationError("fixture context does not match the tranche")
        if self.evidence_boundary != CHROMATIN_ALPHA_FRONTIER_BOUNDARY:
            raise ValidationError("fixture boundary must be public aggregate")
        if len(self.sources) != CHROMATIN_ALPHA_FRONTIER_SOURCE_COUNT:
            raise ValidationError("fixture requires five source receipts")
        if (
            len(self.records)
            != CHROMATIN_ALPHA_FRONTIER_POSITIVE_COUNT + CHROMATIN_ALPHA_FRONTIER_CONTROL_COUNT
        ):
            raise ValidationError("fixture requires four positive and twelve control records")
        if len(self.positive_records) != CHROMATIN_ALPHA_FRONTIER_POSITIVE_COUNT:
            raise ValidationError("positive record count is not four")
        if len(self.control_records) != CHROMATIN_ALPHA_FRONTIER_CONTROL_COUNT:
            raise ValidationError("control record count is not twelve")
        source_ids = {source.source_id for source in self.sources}
        if any(set(record.source_ids) - source_ids for record in self.records):
            raise ValidationError("record references an undeclared source")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(self.to_dict(include_payload=True, include_address=False)),
            )

    @property
    def positive_records(self) -> tuple[ChromatinAlphaFrontierRecord, ...]:
        return tuple(
            record for record in self.records if record.role is ChromatinAlphaFrontierRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[ChromatinAlphaFrontierRecord, ...]:
        return tuple(
            record for record in self.records if record.role is ChromatinAlphaFrontierRole.CONTROL
        )

    def operation_records(
        self, operation: ChromatinAlphaFrontierOperation
    ) -> tuple[ChromatinAlphaFrontierRecord, ...]:
        return tuple(record for record in self.records if record.operation is operation)

    def record_map(self) -> dict[str, ChromatinAlphaFrontierRecord]:
        return {record.record_id: record for record in self.records}

    def source_map(self) -> dict[str, ChromatinAlphaFrontierSourceReceipt]:
        return {source.source_id: source for source in self.sources}

    def to_dict(
        self, *, include_payload: bool = False, include_address: bool = True
    ) -> dict[str, Any]:
        result = {
            "fixture_id": self.fixture_id,
            "fixture_version": self.fixture_version,
            "context_key": self.context_key,
            "evidence_boundary": self.evidence_boundary,
            "sources": [source.to_dict() for source in self.sources],
            "records": [record.to_dict(include_payload=include_payload) for record in self.records],
        }
        if include_address:
            result["content_address"] = self.content_address
        return result


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierDataCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.check_id or not self.detail:
            raise ValidationError("data check is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierDataAudit:
    fixture_id: str
    checks: tuple[ChromatinAlphaFrontierDataCheck, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.checks:
            raise ValidationError("data audit requires fixture and checks")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"failed_check_ids": list(self.failed_check_ids)}


@dataclass(frozen=True, slots=True)
class ChromatinAlphaFrontierCatalog:
    fixture_id: str
    context_key: str
    operation_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    issue_codes: tuple[str, ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.fixture_id or not self.operation_ids or not self.record_ids:
            raise ValidationError("catalog is incomplete")
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _source_from_base(source: Any) -> ChromatinAlphaFrontierSourceReceipt:
    return ChromatinAlphaFrontierSourceReceipt(
        source_id=source.source_id,
        title=source.title,
        uri=source.uri,
        source_kind=source.source_kind,
        release=source.release,
        scope=source.scope,
        context_key=CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY,
    )


def default_chromatin_alpha_frontier_fixture() -> ChromatinAlphaFrontierFixture:
    """Build the checked-in aggregate rows from public source-shaped records."""

    base = default_chromatin_frontier_fixture()
    sources = tuple(_source_from_base(source) for source in base.sources)
    prefix_map = {
        "C13": "C09",
        "C14": "C10",
        "C15": "C11",
        "C16": "C12",
    }
    records = tuple(
        ChromatinAlphaFrontierRecord(
            record_id=next(
                record.record_id.replace(old, new)
                for old, new in prefix_map.items()
                if old in record.record_id
            ),
            operation=ChromatinAlphaFrontierOperation(record.operation.value),
            role=ChromatinAlphaFrontierRole(record.role.value),
            context_key=CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY,
            source_ids=record.source_ids,
            payload=dict(record.payload),
            expected_state=record.expected_state,
            expected_issue_codes=record.expected_issue_codes,
            description=record.description,
        )
        for record in base.records
    )
    return ChromatinAlphaFrontierFixture(
        fixture_id="chromatin-alpha-frontier-public-aggregate",
        fixture_version=CHROMATIN_ALPHA_FRONTIER_FIXTURE_VERSION,
        context_key=CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY,
        evidence_boundary=CHROMATIN_ALPHA_FRONTIER_BOUNDARY,
        sources=sources,
        records=records,
    )


def audit_chromatin_alpha_frontier_data(
    fixture: ChromatinAlphaFrontierFixture,
) -> ChromatinAlphaFrontierDataAudit:
    source_ids = {source.source_id for source in fixture.sources}
    checks = (
        ChromatinAlphaFrontierDataCheck(
            "fixture_version",
            fixture.fixture_version == CHROMATIN_ALPHA_FRONTIER_FIXTURE_VERSION,
            "fixture version is supported",
        ),
        ChromatinAlphaFrontierDataCheck(
            "fixture_context",
            fixture.context_key == CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY,
            "fixture context is exact",
        ),
        ChromatinAlphaFrontierDataCheck(
            "fixture_boundary",
            fixture.evidence_boundary == CHROMATIN_ALPHA_FRONTIER_BOUNDARY,
            "aggregate boundary is explicit",
        ),
        ChromatinAlphaFrontierDataCheck(
            "source_count", len(fixture.sources) == 5, "five source receipts are retained"
        ),
        ChromatinAlphaFrontierDataCheck(
            "source_https",
            all(source.uri.startswith("https://") for source in fixture.sources),
            "source URIs use HTTPS",
        ),
        ChromatinAlphaFrontierDataCheck(
            "source_addresses",
            all(source.content_address.startswith("sha256:") for source in fixture.sources),
            "source receipts are addressed",
        ),
        ChromatinAlphaFrontierDataCheck(
            "record_count", len(fixture.records) == 16, "sixteen records are retained"
        ),
        ChromatinAlphaFrontierDataCheck(
            "positive_count",
            len(fixture.positive_records) == 4,
            "four positive records are retained",
        ),
        ChromatinAlphaFrontierDataCheck(
            "control_count",
            len(fixture.control_records) == 12,
            "twelve control records are retained",
        ),
        ChromatinAlphaFrontierDataCheck(
            "operation_balance",
            all(
                len(fixture.operation_records(operation)) == 4
                for operation in ChromatinAlphaFrontierOperation
            ),
            "each operation has one positive and three controls",
        ),
        ChromatinAlphaFrontierDataCheck(
            "source_references",
            all(not (set(record.source_ids) - source_ids) for record in fixture.records),
            "every record source is declared",
        ),
        ChromatinAlphaFrontierDataCheck(
            "record_context",
            all(record.context_key == fixture.context_key for record in fixture.records),
            "record context is locked",
        ),
        ChromatinAlphaFrontierDataCheck(
            "record_addresses",
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "record receipts are addressed",
        ),
        ChromatinAlphaFrontierDataCheck(
            "record_descriptions",
            all(record.description for record in fixture.records),
            "record descriptions are retained",
        ),
        ChromatinAlphaFrontierDataCheck(
            "payload_objects",
            all(isinstance(record.payload, Mapping) for record in fixture.records),
            "payloads are objects",
        ),
    )
    return ChromatinAlphaFrontierDataAudit(
        fixture.fixture_id, checks, all(check.passed for check in checks)
    )


def build_chromatin_alpha_frontier_catalog(
    fixture: ChromatinAlphaFrontierFixture,
) -> ChromatinAlphaFrontierCatalog:
    issue_codes = tuple(
        sorted({code for record in fixture.records for code in record.expected_issue_codes})
    )
    return ChromatinAlphaFrontierCatalog(
        fixture_id=fixture.fixture_id,
        context_key=fixture.context_key,
        operation_ids=tuple(operation.value for operation in ChromatinAlphaFrontierOperation),
        source_ids=tuple(source.source_id for source in fixture.sources),
        record_ids=tuple(record.record_id for record in fixture.records),
        issue_codes=issue_codes,
    )


__all__ = [
    "CHROMATIN_ALPHA_FRONTIER_BOUNDARY",
    "CHROMATIN_ALPHA_FRONTIER_CONTEXT_KEY",
    "CHROMATIN_ALPHA_FRONTIER_CONTROL_COUNT",
    "CHROMATIN_ALPHA_FRONTIER_FIXTURE_VERSION",
    "CHROMATIN_ALPHA_FRONTIER_POSITIVE_COUNT",
    "CHROMATIN_ALPHA_FRONTIER_SOURCE_COUNT",
    "ChromatinAlphaFrontierCatalog",
    "ChromatinAlphaFrontierDataAudit",
    "ChromatinAlphaFrontierDataCheck",
    "ChromatinAlphaFrontierFixture",
    "ChromatinAlphaFrontierOperation",
    "ChromatinAlphaFrontierRecord",
    "ChromatinAlphaFrontierRole",
    "ChromatinAlphaFrontierSourceReceipt",
    "audit_chromatin_alpha_frontier_data",
    "build_chromatin_alpha_frontier_catalog",
    "default_chromatin_alpha_frontier_fixture",
]

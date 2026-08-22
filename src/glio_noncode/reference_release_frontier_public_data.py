"""Public aggregate data for the Domain 04 C13-C16 release frontier.

The fixture in this module is a small, deterministic representation of public
reference-release work.  It keeps source receipts and release metadata while
excluding downloaded reference bytes and subject-level observations.  Every
operation has one accepted example and three controls for each of the four
operations.  Controls are deliberately expected to remain visible: a review
state is evidence about a release boundary, not a reason to invent a value.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

REFERENCE_RELEASE_FRONTIER_FIXTURE_VERSION = "2026.08.d04-c13-c16.v1"
REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY = (
    "GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline"
)
REFERENCE_RELEASE_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
REFERENCE_RELEASE_FRONTIER_POSITIVE_COUNT = 4
REFERENCE_RELEASE_FRONTIER_CONTROL_COUNT = 12
REFERENCE_RELEASE_FRONTIER_SOURCE_COUNT = 5


class ReferenceReleaseOperation(StrEnum):
    """The four executable C13-C16 reference governance operations."""

    PROVENANCE_CHECK = "source_provenance_check"
    ANNOTATION_DRIFT = "annotation_drift_detection"
    REFERENCE_BUNDLE = "reproducible_reference_bundle"
    RELEASE_GATE = "reference_release_gate"


class ReferenceReleaseRole(StrEnum):
    """Fixture role used to separate accepted paths from controls."""

    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class ReferenceReleaseSourceReceipt:
    """A public source identity, scope, and release receipt."""

    source_id: str
    title: str
    uri: str
    source_kind: str
    release: str
    accessed_on: str
    license: str
    scope: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "title",
            "uri",
            "source_kind",
            "release",
            "accessed_on",
            "license",
            "scope",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith(("https://", "http://")):
            raise ValidationError("source URI must be HTTP(S)")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseRecord:
    """One executable operation payload with an expected receipt outcome."""

    record_id: str
    operation: ReferenceReleaseOperation
    role: ReferenceReleaseRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: dict[str, Any]
    expected_state: str
    expected_issue_codes: tuple[str, ...]
    description: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "record_id",
            "context_key",
            "expected_state",
            "description",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValidationError("release record requires source IDs")
        if not self.payload:
            raise ValidationError("release record payload must not be empty")
        if not isinstance(self.operation, ReferenceReleaseOperation):
            raise ValidationError("release operation must be a declared enum")
        if not isinstance(self.role, ReferenceReleaseRole):
            raise ValidationError("release role must be a declared enum")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseFixture:
    """Versioned, aggregate-only fixture for C13-C16."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[ReferenceReleaseSourceReceipt, ...]
    records: tuple[ReferenceReleaseRecord, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "fixture_id",
            "fixture_version",
            "context_key",
            "evidence_boundary",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.evidence_boundary != REFERENCE_RELEASE_FRONTIER_EVIDENCE_BOUNDARY:
            raise ValidationError("fixture evidence boundary is not supported")
        if not self.sources or not self.records:
            raise ValidationError("release fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[ReferenceReleaseRecord, ...]:
        return tuple(
            record for record in self.records if record.role is ReferenceReleaseRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[ReferenceReleaseRecord, ...]:
        return tuple(
            record for record in self.records if record.role is ReferenceReleaseRole.CONTROL
        )

    def source_map(self) -> dict[str, ReferenceReleaseSourceReceipt]:
        return {source.source_id: source for source in self.sources}

    def record_map(self) -> dict[str, ReferenceReleaseRecord]:
        return {record.record_id: record for record in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseFixtureCatalog:
    """Indexed fixture view used by evaluators and release checks."""

    fixture: ReferenceReleaseFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[ReferenceReleaseOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("catalog source IDs must be unique")
        if len(self.record_ids) != len(set(self.record_ids)):
            raise ValidationError("catalog record IDs must be unique")
        if not self.operations:
            raise ValidationError("catalog requires operation coverage")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseDataCheck:
    """One deterministic fixture or source closure assertion."""

    check_id: str
    passed: bool
    detail: str
    observed: Any
    expected: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseDataAudit:
    """Closure report for counts, operations, addresses, and source scope."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[ReferenceReleaseDataCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _address(value: Any) -> str:
    return content_hash(value)


def _source(
    source_id: str,
    title: str,
    uri: str,
    source_kind: str,
    release: str,
    license: str,
    scope: str,
) -> ReferenceReleaseSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "source_kind": source_kind,
        "release": release,
        "accessed_on": "2026-08-22",
        "license": license,
        "scope": scope,
    }
    return ReferenceReleaseSourceReceipt(**body, content_address=_address(body))


def _record(
    record_id: str,
    operation: ReferenceReleaseOperation,
    role: ReferenceReleaseRole,
    payload: dict[str, Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
) -> ReferenceReleaseRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "description": description,
    }
    return ReferenceReleaseRecord(**body, content_address=_address(body))


def _provenance_row(
    source_id: str, *, context_key: str | None = None, **overrides: Any
) -> dict[str, Any]:
    row = {
        "source_id": source_id,
        "source_uri": f"https://example.org/reference/{source_id}",
        "declared_checksum": f"sha256:{source_id}-declared",
        "observed_checksum": f"sha256:{source_id}-declared",
        "license_id": "CC-BY-4.0",
        "context_key": context_key or REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY,
    }
    row.update(overrides)
    return row


def _annotation_pair(
    annotation_id: str = "anno-1", *, changed: bool = False, new: bool = False
) -> tuple[dict[str, Any], dict[str, Any]]:
    previous = {
        "annotation_id": annotation_id,
        "gene_id": "EGFR",
        "assembly": "GRCh38",
        "class": "enhancer",
        "score": 0.84,
        "source_uri": "https://example.org/annotation/v1",
        "retrieved_at": "2026-08-01",
    }
    current = dict(previous)
    current["retrieved_at"] = "2026-08-22"
    if changed:
        current["score"] = 0.21
        current["class"] = "promoter"
    if new:
        current["annotation_id"] = "anno-new"
    return previous, current


def _reference_rows(
    *, context_key: str | None = None, unavailable: bool = False, missing_id: bool = False
) -> list[dict[str, Any]]:
    row = {
        "reference_id": "refseq-grch38",
        "status": "unavailable" if unavailable else "available",
        "context_key": context_key or REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY,
        "source_id": "ncbi-refseq",
        "uri": "https://ftp.ncbi.nlm.nih.gov/refseq/",
        "checksum": "sha256:refseq-grch38",
    }
    if missing_id:
        row.pop("reference_id")
    return [
        row,
        {
            "reference_id": "ucsc-grch38",
            "status": "available",
            "context_key": context_key or REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY,
            "source_id": "ucsc-genome-browser",
            "uri": "https://genome.ucsc.edu/goldenPath/help/",
            "checksum": "sha256:ucsc-grch38",
        },
    ]


def _release_checks(*, failed: tuple[str, ...] = ()) -> dict[str, bool]:
    checks = {key: True for key in ("checksum", "schema", "license", "context", "source")}
    for key in failed:
        checks[key] = False
    return checks


def _sources() -> tuple[ReferenceReleaseSourceReceipt, ...]:
    return (
        _source(
            "hgnc",
            "HGNC gene nomenclature",
            "https://www.genenames.org/download/custom/",
            "gene_catalog",
            "2026-01",
            "CC-BY-4.0",
            "declared symbols and aliases",
        ),
        _source(
            "ensembl",
            "Ensembl data resources",
            "https://www.ensembl.org/info/data/ftp/index.html",
            "annotation_catalog",
            "release-114",
            "Ensembl-terms",
            "reference annotation metadata",
        ),
        _source(
            "ncbi-refseq",
            "NCBI RefSeq resources",
            "https://ftp.ncbi.nlm.nih.gov/refseq/",
            "reference_sequence",
            "GRCh38-2026",
            "NCBI-terms",
            "reference sequence release identity",
        ),
        _source(
            "ucsc-genome-browser",
            "UCSC Genome Browser documentation",
            "https://genome.ucsc.edu/goldenPath/help/",
            "assembly_documentation",
            "GRCh38",
            "UCSC-terms",
            "assembly and track documentation",
        ),
        _source(
            "gnomad",
            "gnomAD public data portal",
            "https://gnomad.broadinstitute.org/data",
            "population_reference",
            "v4.1",
            "gnomAD-terms",
            "aggregate population reference metadata",
        ),
    )


def _records() -> tuple[ReferenceReleaseRecord, ...]:
    records: list[ReferenceReleaseRecord] = []
    records.extend(
        (
            _record(
                "C13-POS-001",
                ReferenceReleaseOperation.PROVENANCE_CHECK,
                ReferenceReleaseRole.POSITIVE,
                {"records": [_provenance_row("hgnc")]},
                "accepted",
                (),
                ("hgnc",),
                "matched URI, checksum, license, and exact context",
            ),
            _record(
                "C13-CTRL-001",
                ReferenceReleaseOperation.PROVENANCE_CHECK,
                ReferenceReleaseRole.CONTROL,
                {"records": [_provenance_row("ensembl", source_uri="")]},
                "review",
                ("missing_source_uri",),
                ("ensembl",),
                "missing URI remains a review receipt",
            ),
            _record(
                "C13-CTRL-002",
                ReferenceReleaseOperation.PROVENANCE_CHECK,
                ReferenceReleaseRole.CONTROL,
                {"records": [_provenance_row("ncbi-refseq", observed_checksum="sha256:other")]},
                "review",
                ("checksum_unverified",),
                ("ncbi-refseq",),
                "checksum mismatch remains visible",
            ),
            _record(
                "C13-CTRL-003",
                ReferenceReleaseOperation.PROVENANCE_CHECK,
                ReferenceReleaseRole.CONTROL,
                {"records": [_provenance_row("ucsc-genome-browser", license_id="")]},
                "review",
                ("missing_license",),
                ("ucsc-genome-browser",),
                "missing license is never treated as permission",
            ),
        )
    )
    previous, current = _annotation_pair()
    changed_previous, changed_current = _annotation_pair(changed=True)
    new_previous, new_current = _annotation_pair(new=True)
    ignored_previous, ignored_current = _annotation_pair()
    records.extend(
        (
            _record(
                "C14-POS-001",
                ReferenceReleaseOperation.ANNOTATION_DRIFT,
                ReferenceReleaseRole.POSITIVE,
                {
                    "previous": [previous],
                    "current": [current],
                    "ignored_fields": ["retrieved_at", "source_uri"],
                },
                "accepted",
                (),
                ("ensembl",),
                "retrieval-only changes are ignored and remain stable",
            ),
            _record(
                "C14-CTRL-001",
                ReferenceReleaseOperation.ANNOTATION_DRIFT,
                ReferenceReleaseRole.CONTROL,
                {
                    "previous": [changed_previous],
                    "current": [changed_current],
                    "ignored_fields": ["retrieved_at", "source_uri"],
                    "drift_threshold": 0.2,
                },
                "drift",
                (),
                ("ensembl",),
                "two substantive annotation fields exceed the drift threshold",
            ),
            _record(
                "C14-CTRL-002",
                ReferenceReleaseOperation.ANNOTATION_DRIFT,
                ReferenceReleaseRole.CONTROL,
                {
                    "previous": [new_previous],
                    "current": [new_current],
                    "ignored_fields": ["retrieved_at", "source_uri"],
                },
                "drift",
                (),
                ("ensembl",),
                "new annotation identity is classified as drift",
            ),
            _record(
                "C14-CTRL-003",
                ReferenceReleaseOperation.ANNOTATION_DRIFT,
                ReferenceReleaseRole.CONTROL,
                {
                    "previous": [ignored_previous],
                    "current": [ignored_current],
                    "ignored_fields": ["retrieved_at", "source_uri"],
                },
                "accepted",
                (),
                ("hgnc",),
                "a control proves ignored receipt fields do not create drift",
            ),
        )
    )
    records.extend(
        (
            _record(
                "C15-POS-001",
                ReferenceReleaseOperation.REFERENCE_BUNDLE,
                ReferenceReleaseRole.POSITIVE,
                {
                    "records": _reference_rows(),
                    "bundle_id": "bundle-positive",
                    "schema_hash": "sha256:schema-v1",
                },
                "published",
                (),
                ("ncbi-refseq", "ucsc-genome-browser"),
                "available exact-context rows are sorted into a reproducible bundle",
            ),
            _record(
                "C15-CTRL-001",
                ReferenceReleaseOperation.REFERENCE_BUNDLE,
                ReferenceReleaseRole.CONTROL,
                {
                    "records": _reference_rows(context_key="GRCh37|wrong|context"),
                    "bundle_id": "bundle-context",
                    "schema_hash": "sha256:schema-v1",
                },
                "blocked",
                ("bundle_context_mismatch",),
                ("ncbi-refseq", "ucsc-genome-browser"),
                "foreign context is blocked before publication",
            ),
            _record(
                "C15-CTRL-002",
                ReferenceReleaseOperation.REFERENCE_BUNDLE,
                ReferenceReleaseRole.CONTROL,
                {
                    "records": _reference_rows(unavailable=True),
                    "bundle_id": "bundle-unavailable",
                    "schema_hash": "sha256:schema-v1",
                },
                "blocked",
                ("bundle_unavailable",),
                ("ncbi-refseq", "ucsc-genome-browser"),
                "unavailable reference rows cannot enter a release bundle",
            ),
            _record(
                "C15-CTRL-003",
                ReferenceReleaseOperation.REFERENCE_BUNDLE,
                ReferenceReleaseRole.CONTROL,
                {
                    "records": _reference_rows(missing_id=True),
                    "bundle_id": "bundle-missing-id",
                    "schema_hash": "sha256:schema-v1",
                },
                "blocked",
                ("bundle_missing_reference_id",),
                ("ncbi-refseq", "ucsc-genome-browser"),
                "missing reference identity is rejected",
            ),
        )
    )
    records.extend(
        (
            _record(
                "C16-POS-001",
                ReferenceReleaseOperation.RELEASE_GATE,
                ReferenceReleaseRole.POSITIVE,
                {
                    "release_id": "release-positive",
                    "bundle_address": "sha256:bundle-positive",
                    "checks": _release_checks(),
                },
                "published",
                (),
                ("ncbi-refseq", "ucsc-genome-browser", "ensembl"),
                "all required release checks pass",
            ),
            _record(
                "C16-CTRL-001",
                ReferenceReleaseOperation.RELEASE_GATE,
                ReferenceReleaseRole.CONTROL,
                {
                    "release_id": "release-checksum",
                    "bundle_address": "sha256:bundle-checksum",
                    "checks": _release_checks(failed=("checksum",)),
                },
                "blocked",
                ("release_check_failed",),
                ("ncbi-refseq",),
                "checksum failure blocks release",
            ),
            _record(
                "C16-CTRL-002",
                ReferenceReleaseOperation.RELEASE_GATE,
                ReferenceReleaseRole.CONTROL,
                {
                    "release_id": "release-context",
                    "bundle_address": "sha256:bundle-context",
                    "checks": _release_checks(failed=("context",)),
                },
                "blocked",
                ("release_check_failed",),
                ("ucsc-genome-browser",),
                "context failure blocks release",
            ),
            _record(
                "C16-CTRL-003",
                ReferenceReleaseOperation.RELEASE_GATE,
                ReferenceReleaseRole.CONTROL,
                {
                    "release_id": "release-multiple",
                    "bundle_address": "sha256:bundle-multiple",
                    "checks": _release_checks(failed=("license", "source")),
                },
                "blocked",
                ("release_check_failed",),
                ("hgnc", "ensembl"),
                "multiple failed checks remain separately listed",
            ),
        )
    )
    if len(records) != 16:
        raise ValidationError(f"release fixture requires 16 records, found {len(records)}")
    return tuple(records)


def default_reference_release_fixture() -> ReferenceReleaseFixture:
    """Return the checked-in public aggregate fixture."""

    body = {
        "fixture_id": "reference-release-frontier-public-aggregate",
        "fixture_version": REFERENCE_RELEASE_FRONTIER_FIXTURE_VERSION,
        "context_key": REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": REFERENCE_RELEASE_FRONTIER_EVIDENCE_BOUNDARY,
        "sources": _sources(),
        "records": _records(),
    }
    return ReferenceReleaseFixture(**body, content_address=_address(body))


def build_reference_release_catalog(
    fixture: ReferenceReleaseFixture | None = None,
) -> ReferenceReleaseFixtureCatalog:
    """Build an ordered source and operation index from the fixture."""

    fixture = fixture or default_reference_release_fixture()
    body = {
        "fixture_id": fixture.fixture_id,
        "source_ids": tuple(source.source_id for source in fixture.sources),
        "record_ids": tuple(record.record_id for record in fixture.records),
        "operations": tuple(sorted({record.operation for record in fixture.records}, key=str)),
    }
    return ReferenceReleaseFixtureCatalog(
        fixture,
        body["source_ids"],
        body["record_ids"],
        body["operations"],
        _address(body),
    )


def _data_check(
    index: int, passed: bool, detail: str, observed: Any, expected: Any
) -> ReferenceReleaseDataCheck:
    body = {
        "check_id": f"release-data-{index:03d}",
        "passed": passed,
        "detail": detail,
        "observed": observed,
        "expected": expected,
    }
    return ReferenceReleaseDataCheck(**body, content_address=_address(body))


def audit_reference_release_data(
    fixture: ReferenceReleaseFixture | None = None,
) -> ReferenceReleaseDataAudit:
    """Audit source closure, role balance, operation balance, and boundaries."""

    fixture = fixture or default_reference_release_fixture()
    source_ids = {source.source_id for source in fixture.sources}
    record_ids = [record.record_id for record in fixture.records]
    checks: list[ReferenceReleaseDataCheck] = []
    checks.append(
        _data_check(
            1,
            len(fixture.sources) == REFERENCE_RELEASE_FRONTIER_SOURCE_COUNT,
            "source count",
            len(fixture.sources),
            REFERENCE_RELEASE_FRONTIER_SOURCE_COUNT,
        )
    )
    checks.append(
        _data_check(2, len(fixture.records) == 16, "record count", len(fixture.records), 16)
    )
    checks.append(
        _data_check(
            3,
            len(fixture.positive_records) == REFERENCE_RELEASE_FRONTIER_POSITIVE_COUNT,
            "positive count",
            len(fixture.positive_records),
            REFERENCE_RELEASE_FRONTIER_POSITIVE_COUNT,
        )
    )
    checks.append(
        _data_check(
            4,
            len(fixture.control_records) == REFERENCE_RELEASE_FRONTIER_CONTROL_COUNT,
            "control count",
            len(fixture.control_records),
            REFERENCE_RELEASE_FRONTIER_CONTROL_COUNT,
        )
    )
    checks.append(
        _data_check(
            5,
            len(record_ids) == len(set(record_ids)),
            "record IDs unique",
            len(record_ids),
            len(set(record_ids)),
        )
    )
    checks.append(
        _data_check(
            6,
            fixture.context_key == REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY,
            "fixture context",
            fixture.context_key,
            REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY,
        )
    )
    checks.append(
        _data_check(
            7,
            fixture.evidence_boundary == REFERENCE_RELEASE_FRONTIER_EVIDENCE_BOUNDARY,
            "evidence boundary",
            fixture.evidence_boundary,
            REFERENCE_RELEASE_FRONTIER_EVIDENCE_BOUNDARY,
        )
    )
    checks.append(
        _data_check(
            8,
            {record.operation for record in fixture.records} == set(ReferenceReleaseOperation),
            "operation closure",
            tuple(sorted({record.operation.value for record in fixture.records})),
            tuple(item.value for item in ReferenceReleaseOperation),
        )
    )
    for offset, operation in enumerate(ReferenceReleaseOperation, start=9):
        values = tuple(record for record in fixture.records if record.operation is operation)
        checks.append(
            _data_check(offset, len(values) == 4, f"{operation.value} balance", len(values), 4)
        )
    checks.append(
        _data_check(
            13,
            all(set(record.source_ids) <= source_ids for record in fixture.records),
            "source closure",
            sorted(
                {source_id for record in fixture.records for source_id in record.source_ids}
                - source_ids
            ),
            [],
        )
    )
    checks.append(
        _data_check(
            14,
            all(record.context_key == fixture.context_key for record in fixture.records),
            "record context closure",
            sorted({record.context_key for record in fixture.records}),
            [fixture.context_key],
        )
    )
    checks.append(
        _data_check(
            15,
            all(source.content_address.startswith("sha256:") for source in fixture.sources),
            "source addresses",
            all(source.content_address.startswith("sha256:") for source in fixture.sources),
            True,
        )
    )
    checks.append(
        _data_check(
            16,
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            "record addresses",
            all(record.content_address.startswith("sha256:") for record in fixture.records),
            True,
        )
    )
    checks.append(
        _data_check(
            17,
            all(source.uri.startswith("https://") for source in fixture.sources),
            "public URI closure",
            all(source.uri.startswith("https://") for source in fixture.sources),
            True,
        )
    )
    checks.append(
        _data_check(
            18,
            all(record.payload for record in fixture.records),
            "payload closure",
            all(bool(record.payload) for record in fixture.records),
            True,
        )
    )
    checks.append(
        _data_check(
            19,
            all(record.source_ids for record in fixture.records),
            "receipt closure",
            all(bool(record.source_ids) for record in fixture.records),
            True,
        )
    )
    checks.append(
        _data_check(
            20,
            len({source.license for source in fixture.sources}) >= 4,
            "license diversity",
            len({source.license for source in fixture.sources}),
            ">=4",
        )
    )
    checks.append(
        _data_check(
            21,
            all(record.role in set(ReferenceReleaseRole) for record in fixture.records),
            "role vocabulary",
            True,
            True,
        )
    )
    checks.append(
        _data_check(
            22,
            all(record.expected_state for record in fixture.records),
            "expected state closure",
            True,
            True,
        )
    )
    checks.append(
        _data_check(
            23,
            all(record.description for record in fixture.records),
            "description closure",
            True,
            True,
        )
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "checks": tuple(checks),
    }
    return ReferenceReleaseDataAudit(**body, content_address=_address(body))


def load_reference_release_fixture(
    source: str | Path | Mapping[str, Any] | None = None,
) -> ReferenceReleaseFixture:
    """Load a JSON fixture or descriptor, preserving explicit enum types."""

    if source is None:
        return default_reference_release_fixture()
    if isinstance(source, Mapping):
        payload = dict(source)
    else:
        payload = json.loads(Path(source).read_text(encoding="utf-8"))
    if payload.get("fixture") == "default_reference_release_fixture":
        return default_reference_release_fixture()
    sources: list[ReferenceReleaseSourceReceipt] = []
    for raw in payload["sources"]:
        sources.append(ReferenceReleaseSourceReceipt(**dict(raw)))
    records: list[ReferenceReleaseRecord] = []
    for raw in payload["records"]:
        item = dict(raw)
        item["operation"] = ReferenceReleaseOperation(item["operation"])
        item["role"] = ReferenceReleaseRole(item["role"])
        item["source_ids"] = tuple(item["source_ids"])
        item["expected_issue_codes"] = tuple(item.get("expected_issue_codes", ()))
        records.append(ReferenceReleaseRecord(**item))
    body = {
        key: payload[key]
        for key in ("fixture_id", "fixture_version", "context_key", "evidence_boundary")
    }
    return ReferenceReleaseFixture(
        **body,
        sources=tuple(sources),
        records=tuple(records),
        content_address=str(
            payload.get(
                "content_address", _address({**body, "sources": sources, "records": records})
            )
        ),
    )


__all__ = [
    "REFERENCE_RELEASE_FRONTIER_CONTEXT_KEY",
    "REFERENCE_RELEASE_FRONTIER_CONTROL_COUNT",
    "REFERENCE_RELEASE_FRONTIER_EVIDENCE_BOUNDARY",
    "REFERENCE_RELEASE_FRONTIER_FIXTURE_VERSION",
    "REFERENCE_RELEASE_FRONTIER_POSITIVE_COUNT",
    "REFERENCE_RELEASE_FRONTIER_SOURCE_COUNT",
    "ReferenceReleaseDataAudit",
    "ReferenceReleaseDataCheck",
    "ReferenceReleaseFixture",
    "ReferenceReleaseFixtureCatalog",
    "ReferenceReleaseOperation",
    "ReferenceReleaseRecord",
    "ReferenceReleaseRole",
    "ReferenceReleaseSourceReceipt",
    "audit_reference_release_data",
    "build_reference_release_catalog",
    "default_reference_release_fixture",
    "load_reference_release_fixture",
]

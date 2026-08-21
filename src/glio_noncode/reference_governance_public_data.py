"""Public aggregate fixtures for Domain 04 C09–C12.

The four operations in this module exercise the existing reference adapters
against compact, deterministic records shaped like public source extracts.
The records are intentionally aggregate and synthetic: they preserve source
identity, release labels, and review controls without copying a downloaded
release or any subject-level data into the repository.

Each control is expected to remain visible as a non-supported state.  A
checksum mismatch, missing permission, ambiguous alias, population conflict,
or assembly mismatch is evidence for review rather than a reason to select a
fallback value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

REFERENCE_GOVERNANCE_FIXTURE_VERSION = "2026.08.c09-c12.v1"
REFERENCE_GOVERNANCE_CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline"
REFERENCE_GOVERNANCE_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
REFERENCE_GOVERNANCE_POSITIVE_COUNT = 4
REFERENCE_GOVERNANCE_CONTROL_COUNT = 12
REFERENCE_GOVERNANCE_SOURCE_COUNT = 5


class ReferenceGovernanceOperation(StrEnum):
    """Executable operation family covered by this aggregate fixture."""

    GENE_ALIAS = "gene_alias_version_resolution"
    POPULATION_FREQUENCY = "population_frequency_adaptation"
    REFERENCE_SNAPSHOT = "reference_snapshot_manifest"
    LICENSE_RESTRICTION = "license_use_restriction"


class ReferenceGovernanceRole(StrEnum):
    """Fixture role separating publishable positives from review controls."""

    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceSourceReceipt:
    """A public source identity and scope receipt."""

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
            raise ValidationError("source receipt URI must be an HTTP(S) URI")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceRecord:
    """One executable payload with an expected adapter state."""

    record_id: str
    operation: ReferenceGovernanceOperation
    role: ReferenceGovernanceRole
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
            raise ValidationError("governance record requires source IDs")
        if not self.payload:
            raise ValidationError("governance record payload must not be empty")
        if not isinstance(self.operation, ReferenceGovernanceOperation):
            raise ValidationError("governance operation must be a declared enum")
        if not isinstance(self.role, ReferenceGovernanceRole):
            raise ValidationError("governance role must be a declared enum")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceFixture:
    """Versioned public aggregate fixture for C09–C12."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[ReferenceGovernanceSourceReceipt, ...]
    records: tuple[ReferenceGovernanceRecord, ...]
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
        if self.evidence_boundary != REFERENCE_GOVERNANCE_EVIDENCE_BOUNDARY:
            raise ValidationError("fixture evidence boundary is not supported")
        if not self.sources or not self.records:
            raise ValidationError("governance fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[ReferenceGovernanceRecord, ...]:
        return tuple(
            record for record in self.records if record.role is ReferenceGovernanceRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[ReferenceGovernanceRecord, ...]:
        return tuple(
            record for record in self.records if record.role is ReferenceGovernanceRole.CONTROL
        )

    def source_map(self) -> dict[str, ReferenceGovernanceSourceReceipt]:
        return {source.source_id: source for source in self.sources}

    def record_map(self) -> dict[str, ReferenceGovernanceRecord]:
        return {record.record_id: record for record in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceFixtureCatalog:
    """Indexed fixture view used by evaluators and release checks."""

    fixture: ReferenceGovernanceFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[ReferenceGovernanceOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("governance catalog source IDs must be unique")
        if len(self.record_ids) != len(set(self.record_ids)):
            raise ValidationError("governance catalog record IDs must be unique")
        if not self.operations:
            raise ValidationError("governance catalog requires operation coverage")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceDataCheck:
    """One deterministic source or payload-boundary check."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceGovernanceDataAudit:
    """Audit result for source closure, balance, and aggregate scope."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[ReferenceGovernanceDataCheck, ...]
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


def _address(body: Any) -> str:
    return content_hash(body)


def _source(
    source_id: str,
    title: str,
    uri: str,
    source_kind: str,
    release: str,
    license: str,
    scope: str,
) -> ReferenceGovernanceSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "source_kind": source_kind,
        "release": release,
        "accessed_on": "2026-08-21",
        "license": license,
        "scope": scope,
    }
    return ReferenceGovernanceSourceReceipt(**body, content_address=_address(body))


def _record(
    record_id: str,
    operation: ReferenceGovernanceOperation,
    role: ReferenceGovernanceRole,
    payload: dict[str, Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
) -> ReferenceGovernanceRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": REFERENCE_GOVERNANCE_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "description": description,
    }
    return ReferenceGovernanceRecord(**body, content_address=_address(body))


def default_reference_governance_fixture() -> ReferenceGovernanceFixture:
    """Return the checked-in C09–C12 public aggregate fixture."""

    sources = (
        _source(
            "hgnc-downloads",
            "HGNC data downloads",
            "https://www.genenames.org/download/",
            "public-download-index",
            "current HGNC public file boundary",
            "CC0 1.0",
            "declared gene identifiers, symbols, aliases, and versioned records",
        ),
        _source(
            "hgnc-home",
            "HGNC homepage and data policy",
            "https://hgnc.genenames.org/",
            "data-authority",
            "current HGNC public documentation",
            "CC0 1.0",
            "gene nomenclature authority and public release context",
        ),
        _source(
            "ncbi-refseq",
            "NCBI RefSeq",
            "https://www.ncbi.nlm.nih.gov/refseq/",
            "reference-catalog",
            "current public RefSeq boundary",
            "NCBI public data terms",
            "reference sequence identity, assembly, and release context",
        ),
        _source(
            "spdx-license-list",
            "SPDX License List",
            "https://spdx.org/licenses/",
            "license-registry",
            "current SPDX identifier list",
            "SPDX license list terms",
            "canonical license identifiers and use-restriction vocabulary",
        ),
        _source(
            "spdx-mit",
            "SPDX MIT license identifier",
            "https://spdx.org/licenses/MIT",
            "license-text",
            "MIT identifier page",
            "MIT License",
            "canonical MIT permission and attribution boundary",
        ),
    )
    records = (
        _record(
            "C09-POS-001",
            ReferenceGovernanceOperation.GENE_ALIAS,
            ReferenceGovernanceRole.POSITIVE,
            {
                "queries": [{"query_id": "gene-positive", "query": "GLIO-1"}],
                "records": [
                    {
                        "gene_id": "HGNC:1234",
                        "symbol": "GLIO1",
                        "aliases": ["GLIO-1", "GLIO1P"],
                        "version": "2",
                        "assembly": "GRCh38",
                        "source_id": "fixture-hgnc",
                        "source_version": "2026.08",
                    }
                ],
                "assembly": "GRCh38",
            },
            "supported",
            (),
            ("hgnc-downloads", "hgnc-home"),
            "declared HGNC alias resolves to one versioned gene record",
        ),
        _record(
            "C09-CTRL-001",
            ReferenceGovernanceOperation.GENE_ALIAS,
            ReferenceGovernanceRole.CONTROL,
            {
                "queries": [{"query_id": "gene-ambiguous", "query": "GLIO2"}],
                "records": [
                    {
                        "gene_id": "HGNC:1235",
                        "symbol": "GLIO2",
                        "aliases": ["GLIO2"],
                        "version": "1",
                        "assembly": "GRCh38",
                        "source_id": "fixture-hgnc",
                        "source_version": "2026.08",
                    },
                    {
                        "gene_id": "HGNC:1236",
                        "symbol": "GLIO2",
                        "aliases": ["GLIO2"],
                        "version": "2",
                        "assembly": "GRCh38",
                        "source_id": "fixture-hgnc",
                        "source_version": "2026.08",
                    },
                ],
                "assembly": "GRCh38",
            },
            "ambiguous",
            ("gene_match_ambiguous",),
            ("hgnc-downloads",),
            "shared symbol remains ambiguous across two declared records",
        ),
        _record(
            "C09-CTRL-002",
            ReferenceGovernanceOperation.GENE_ALIAS,
            ReferenceGovernanceRole.CONTROL,
            {
                "queries": [{"query_id": "gene-unknown", "query": "UNLISTED-ALIAS"}],
                "records": [
                    {
                        "gene_id": "HGNC:1237",
                        "symbol": "GLIO3",
                        "aliases": ["GLIO3-OLD"],
                        "version": "1",
                        "assembly": "GRCh38",
                        "source_id": "fixture-hgnc",
                        "source_version": "2026.08",
                    }
                ],
                "assembly": "GRCh38",
            },
            "partial",
            ("gene_not_resolved",),
            ("hgnc-downloads",),
            "unknown alias abstains without free-text identity inference",
        ),
        _record(
            "C09-CTRL-003",
            ReferenceGovernanceOperation.GENE_ALIAS,
            ReferenceGovernanceRole.CONTROL,
            {
                "queries": [{"query_id": "gene-build", "query": "GLIO4"}],
                "records": [
                    {
                        "gene_id": "HGNC:1238",
                        "symbol": "GLIO4",
                        "aliases": ["GLIO4"],
                        "version": "1",
                        "assembly": "GRCh37",
                        "source_id": "fixture-hgnc",
                        "source_version": "2025.12",
                    }
                ],
                "assembly": "GRCh38",
            },
            "out_of_domain",
            ("gene_not_resolved",),
            ("hgnc-downloads", "ncbi-refseq"),
            "a record from another assembly is excluded from the requested context",
        ),
        _record(
            "C10-POS-001",
            ReferenceGovernanceOperation.POPULATION_FREQUENCY,
            ReferenceGovernanceRole.POSITIVE,
            {
                "records": [
                    {
                        "variant_id": "7:100:A:T",
                        "population_id": "NFE",
                        "AC": 4,
                        "AN": 100,
                        "nhomalt": 0,
                        "assembly": "GRCh38",
                        "ancestry": "European",
                        "source_id": "fixture-frequency",
                        "source_version": "2026.08",
                    }
                ],
                "genome_build": "GRCh38",
                "variant_id": "7:100:A:T",
            },
            "supported",
            (),
            ("ncbi-refseq",),
            "allele frequency is derived from declared AC and AN for one population",
        ),
        _record(
            "C10-CTRL-001",
            ReferenceGovernanceOperation.POPULATION_FREQUENCY,
            ReferenceGovernanceRole.CONTROL,
            {
                "records": [
                    {
                        "variant_id": "7:101:C:G",
                        "population_id": "NFE",
                        "AF": 0.10,
                        "AC": 10,
                        "AN": 100,
                        "assembly": "GRCh38",
                        "source_id": "fixture-frequency",
                        "source_version": "2026.08",
                    },
                    {
                        "variant_id": "7:101:C:G",
                        "population_id": "NFE",
                        "AF": 0.20,
                        "AC": 20,
                        "AN": 100,
                        "assembly": "GRCh38",
                        "source_id": "fixture-frequency",
                        "source_version": "2026.08",
                    },
                ],
                "genome_build": "GRCh38",
                "variant_id": "7:101:C:G",
            },
            "contradictory",
            (),
            ("ncbi-refseq",),
            "two observations disagree for the same variant and population",
        ),
        _record(
            "C10-CTRL-002",
            ReferenceGovernanceOperation.POPULATION_FREQUENCY,
            ReferenceGovernanceRole.CONTROL,
            {
                "records": [
                    {
                        "variant_id": "7:102:G:A",
                        "population_id": "AMR",
                        "AC": None,
                        "AN": None,
                        "assembly": "GRCh38",
                        "source_id": "fixture-frequency",
                        "source_version": "2026.08",
                    }
                ],
                "genome_build": "GRCh38",
                "variant_id": "7:102:G:A",
            },
            "partial",
            (),
            ("ncbi-refseq",),
            "missing counts remain missing and do not become zero frequency",
        ),
        _record(
            "C10-CTRL-003",
            ReferenceGovernanceOperation.POPULATION_FREQUENCY,
            ReferenceGovernanceRole.CONTROL,
            {
                "records": [
                    {
                        "variant_id": "7:103:T:C",
                        "population_id": "SAS",
                        "AF": 0.03,
                        "assembly": "GRCh37",
                        "source_id": "fixture-frequency",
                        "source_version": "2025.12",
                    }
                ],
                "genome_build": "GRCh38",
                "variant_id": "7:103:T:C",
            },
            "out_of_domain",
            ("genome_build_mismatch",),
            ("ncbi-refseq",),
            "frequency from a different assembly is outside the requested context",
        ),
        _record(
            "C11-POS-001",
            ReferenceGovernanceOperation.REFERENCE_SNAPSHOT,
            ReferenceGovernanceRole.POSITIVE,
            {
                "snapshot_id": "grch38-fixture-2026-08",
                "assembly": "GRCh38",
                "source_id": "fixture-refseq",
                "source_version": "2026.08",
                "resources": [
                    {
                        "resource_id": "refseq-gene-index",
                        "kind": "gene-index",
                        "uri": "https://example.invalid/refseq-gene-index",
                        "sha256": "a" * 64,
                        "size_bytes": 1200,
                        "license_id": "CC0-1.0",
                    },
                    {
                        "resource_id": "refseq-transcript-index",
                        "kind": "transcript-index",
                        "uri": "https://example.invalid/refseq-transcript-index",
                        "sha256": "b" * 64,
                        "size_bytes": 2200,
                        "license_id": "CC0-1.0",
                    },
                ],
            },
            "supported",
            (),
            ("ncbi-refseq",),
            "sorted reference resources form a content-addressed snapshot manifest",
        ),
        _record(
            "C11-CTRL-001",
            ReferenceGovernanceOperation.REFERENCE_SNAPSHOT,
            ReferenceGovernanceRole.CONTROL,
            {
                "snapshot_id": "grch38-fixture-hash-drift",
                "assembly": "GRCh38",
                "source_id": "fixture-refseq",
                "source_version": "2026.08",
                "expected_manifest_hash": "sha256:deadbeef",
                "resources": [
                    {
                        "resource_id": "refseq-gene-index",
                        "kind": "gene-index",
                        "uri": "https://example.invalid/refseq-gene-index",
                        "sha256": "c" * 64,
                        "size_bytes": 1200,
                        "license_id": "CC0-1.0",
                    }
                ],
            },
            "contradictory",
            ("manifest_hash_mismatch",),
            ("ncbi-refseq",),
            "declared expected hash mismatch blocks snapshot acceptance",
        ),
        _record(
            "C11-CTRL-002",
            ReferenceGovernanceOperation.REFERENCE_SNAPSHOT,
            ReferenceGovernanceRole.CONTROL,
            {
                "snapshot_id": "grch38-fixture-duplicate",
                "assembly": "GRCh38",
                "source_id": "fixture-refseq",
                "source_version": "2026.08",
                "resources": [
                    {
                        "resource_id": "duplicate-resource",
                        "kind": "gene-index",
                        "uri": "https://example.invalid/a",
                        "sha256": "d" * 64,
                        "size_bytes": 100,
                    },
                    {
                        "resource_id": "duplicate-resource",
                        "kind": "transcript-index",
                        "uri": "https://example.invalid/b",
                        "sha256": "e" * 64,
                        "size_bytes": 200,
                    },
                ],
            },
            "contradictory",
            ("invalid_reference_resource",),
            ("ncbi-refseq",),
            "duplicate resource identity is quarantined rather than overwritten",
        ),
        _record(
            "C11-CTRL-003",
            ReferenceGovernanceOperation.REFERENCE_SNAPSHOT,
            ReferenceGovernanceRole.CONTROL,
            {
                "snapshot_id": "grch37-fixture-version",
                "assembly": "GRCh37",
                "source_id": "fixture-refseq",
                "source_version": "2025.12",
                "resources": [
                    {
                        "resource_id": "refseq-old-index",
                        "kind": "gene-index",
                        "uri": "https://example.invalid/refseq-old-index",
                        "sha256": "f" * 64,
                        "size_bytes": 900,
                    }
                ],
            },
            "out_of_domain",
            (),
            ("ncbi-refseq",),
            "a complete older snapshot remains valid but is outside current context",
        ),
        _record(
            "C12-POS-001",
            ReferenceGovernanceOperation.LICENSE_RESTRICTION,
            ReferenceGovernanceRole.POSITIVE,
            {
                "resources": [{"resource_id": "hgnc-public-table"}],
                "restrictions": [
                    {
                        "resource_id": "hgnc-public-table",
                        "license_id": "CC0-1.0",
                        "allowed_uses": ["research", "redistribution"],
                        "prohibited_uses": [],
                        "redistribution_allowed": True,
                        "commercial_allowed": True,
                        "source_id": "fixture-license",
                        "source_version": "2026.08",
                    }
                ],
                "requested_use": "research",
            },
            "supported",
            (),
            ("spdx-license-list",),
            "declared research use satisfies a public permission record",
        ),
        _record(
            "C12-CTRL-001",
            ReferenceGovernanceOperation.LICENSE_RESTRICTION,
            ReferenceGovernanceRole.CONTROL,
            {
                "resources": [{"resource_id": "restricted-table"}],
                "restrictions": [],
                "requested_use": "research",
            },
            "partial",
            (),
            ("spdx-license-list",),
            "missing permission record blocks use instead of granting it",
        ),
        _record(
            "C12-CTRL-002",
            ReferenceGovernanceOperation.LICENSE_RESTRICTION,
            ReferenceGovernanceRole.CONTROL,
            {
                "resources": [{"resource_id": "time-limited-table"}],
                "restrictions": [
                    {
                        "resource_id": "time-limited-table",
                        "license_id": "License-X",
                        "allowed_uses": ["research"],
                        "prohibited_uses": [],
                        "redistribution_allowed": False,
                        "commercial_allowed": False,
                        "expires_on": "2026-01-01",
                        "source_id": "fixture-license",
                        "source_version": "2025.12",
                    }
                ],
                "requested_use": "research",
                "as_of": "2026-08-21",
            },
            "partial",
            (),
            ("spdx-license-list",),
            "expired permission record is rejected for the requested date",
        ),
        _record(
            "C12-CTRL-003",
            ReferenceGovernanceOperation.LICENSE_RESTRICTION,
            ReferenceGovernanceRole.CONTROL,
            {
                "resources": [{"resource_id": "conflicted-table"}],
                "restrictions": [
                    {
                        "resource_id": "conflicted-table",
                        "license_id": "License-A",
                        "allowed_uses": ["research"],
                        "prohibited_uses": [],
                        "redistribution_allowed": True,
                        "commercial_allowed": False,
                        "source_id": "fixture-license-a",
                        "source_version": "2026.08",
                    },
                    {
                        "resource_id": "conflicted-table",
                        "license_id": "License-B",
                        "allowed_uses": [],
                        "prohibited_uses": ["research"],
                        "redistribution_allowed": False,
                        "commercial_allowed": False,
                        "source_id": "fixture-license-b",
                        "source_version": "2026.08",
                    },
                ],
                "requested_use": "research",
            },
            "contradictory",
            ("conflicting_license_restrictions",),
            ("spdx-license-list", "spdx-mit"),
            "disagreeing permission records require review",
        ),
    )
    body = {
        "fixture_id": "reference-governance-public-aggregate",
        "fixture_version": REFERENCE_GOVERNANCE_FIXTURE_VERSION,
        "context_key": REFERENCE_GOVERNANCE_CONTEXT_KEY,
        "evidence_boundary": REFERENCE_GOVERNANCE_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return ReferenceGovernanceFixture(**body, content_address=_address(body))


def build_reference_governance_catalog(
    fixture: ReferenceGovernanceFixture | None = None,
) -> ReferenceGovernanceFixtureCatalog:
    """Build a deterministic source and record index."""

    selected = fixture or default_reference_governance_fixture()
    source_ids = tuple(source.source_id for source in selected.sources)
    record_ids = tuple(record.record_id for record in selected.records)
    operations = tuple(dict.fromkeys(record.operation for record in selected.records))
    if len(source_ids) != len(set(source_ids)):
        raise ValidationError("fixture contains duplicate source IDs")
    if len(record_ids) != len(set(record_ids)):
        raise ValidationError("fixture contains duplicate record IDs")
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "source_ids": source_ids,
        "record_ids": record_ids,
        "operations": operations,
    }
    return ReferenceGovernanceFixtureCatalog(
        selected, source_ids, record_ids, operations, _address(body)
    )


def audit_reference_governance_data(
    fixture: ReferenceGovernanceFixture | None = None,
) -> ReferenceGovernanceDataAudit:
    """Audit source closure, context identity, balance, and aggregate scope."""

    selected = fixture or default_reference_governance_fixture()
    catalog = build_reference_governance_catalog(selected)
    checks: list[ReferenceGovernanceDataCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(ReferenceGovernanceDataCheck(check_id, passed, detail, _address(body)))

    add(
        "fixture-id",
        selected.fixture_id == "reference-governance-public-aggregate",
        "fixture identity is stable",
    )
    add(
        "fixture-version",
        selected.fixture_version == REFERENCE_GOVERNANCE_FIXTURE_VERSION,
        "fixture version is declared",
    )
    add(
        "fixture-context",
        selected.context_key == REFERENCE_GOVERNANCE_CONTEXT_KEY,
        "one exact context key covers all records",
    )
    add(
        "evidence-boundary",
        selected.evidence_boundary == REFERENCE_GOVERNANCE_EVIDENCE_BOUNDARY,
        "fixture is aggregate and non-patient",
    )
    add(
        "source-count",
        len(selected.sources) == REFERENCE_GOVERNANCE_SOURCE_COUNT,
        "all declared public source receipts are present",
    )
    add(
        "source-ids",
        len(catalog.source_ids) == len(set(catalog.source_ids)),
        "source identities are unique",
    )
    add(
        "record-count",
        len(selected.records)
        == REFERENCE_GOVERNANCE_POSITIVE_COUNT + REFERENCE_GOVERNANCE_CONTROL_COUNT,
        "fixture record count is balanced",
    )
    add(
        "record-ids",
        len(catalog.record_ids) == len(set(catalog.record_ids)),
        "record identities are unique",
    )
    add(
        "positive-count",
        len(selected.positive_records) == REFERENCE_GOVERNANCE_POSITIVE_COUNT,
        "four positive records are present",
    )
    add(
        "control-count",
        len(selected.control_records) == REFERENCE_GOVERNANCE_CONTROL_COUNT,
        "twelve control records are present",
    )
    add(
        "operation-count",
        len(catalog.operations) == 4,
        "all four C09-C12 operations are represented",
    )
    add(
        "operation-balance",
        all(
            sum(record.operation is operation for record in selected.records) == 4
            for operation in ReferenceGovernanceOperation
        ),
        "each operation has one positive and three controls",
    )
    add(
        "positive-state",
        all(record.expected_state == "supported" for record in selected.positive_records),
        "positive records expect supported states",
    )
    add(
        "control-state",
        all(record.expected_state != "supported" for record in selected.control_records),
        "controls do not expect silent support",
    )
    add(
        "context-closure",
        all(record.context_key == selected.context_key for record in selected.records),
        "record contexts close over fixture context",
    )
    source_set = set(catalog.source_ids)
    add(
        "source-closure",
        all(set(record.source_ids) <= source_set for record in selected.records),
        "every record references a declared source",
    )
    add(
        "payload-closure",
        all(isinstance(record.payload, dict) and record.payload for record in selected.records),
        "every record has an executable object payload",
    )
    add(
        "record-addresses",
        all(
            record.content_address
            == _address(
                {key: value for key, value in record.to_dict().items() if key != "content_address"}
            )
            for record in selected.records
        ),
        "record content addresses verify",
    )
    add(
        "source-addresses",
        all(
            source.content_address
            == _address(
                {key: value for key, value in source.to_dict().items() if key != "content_address"}
            )
            for source in selected.sources
        ),
        "source receipt addresses verify",
    )
    add(
        "fixture-address",
        selected.content_address
        == _address(
            {key: value for key, value in selected.to_dict().items() if key != "content_address"}
        ),
        "fixture content address verifies",
    )
    add(
        "no-subject-fields",
        all(
            not {"subject_id", "patient_id", "sample_id"} & set(record.payload)
            for record in selected.records
        ),
        "fixture payloads contain no subject-level identifiers",
    )
    add(
        "source-uri-scope",
        all(source.uri.startswith("https://") for source in selected.sources),
        "source receipts point to HTTPS public boundaries",
    )
    add(
        "catalog-address",
        catalog.content_address
        == _address(
            {
                "fixture_id": selected.fixture_id,
                "fixture_version": selected.fixture_version,
                "source_ids": catalog.source_ids,
                "record_ids": catalog.record_ids,
                "operations": catalog.operations,
            }
        ),
        "catalog content address verifies",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "evidence_boundary": selected.evidence_boundary,
        "checks": checks,
    }
    return ReferenceGovernanceDataAudit(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        selected.evidence_boundary,
        tuple(checks),
        _address(body),
    )


def load_reference_governance_fixture(payload: dict[str, Any]) -> ReferenceGovernanceFixture:
    """Load the built-in fixture by descriptor or a fully serialized object."""

    if not isinstance(payload, dict):
        raise ValidationError("governance fixture descriptor must be an object")
    if payload.get("fixture") == "default_reference_governance_fixture":
        return default_reference_governance_fixture()
    if payload.get("fixture_id") == "reference-governance-public-aggregate":
        return default_reference_governance_fixture()
    raise ValidationError("unsupported governance fixture descriptor")


__all__ = [
    "REFERENCE_GOVERNANCE_CONTEXT_KEY",
    "REFERENCE_GOVERNANCE_CONTROL_COUNT",
    "REFERENCE_GOVERNANCE_EVIDENCE_BOUNDARY",
    "REFERENCE_GOVERNANCE_FIXTURE_VERSION",
    "REFERENCE_GOVERNANCE_POSITIVE_COUNT",
    "REFERENCE_GOVERNANCE_SOURCE_COUNT",
    "ReferenceGovernanceDataAudit",
    "ReferenceGovernanceDataCheck",
    "ReferenceGovernanceFixture",
    "ReferenceGovernanceFixtureCatalog",
    "ReferenceGovernanceOperation",
    "ReferenceGovernanceRecord",
    "ReferenceGovernanceRole",
    "ReferenceGovernanceSourceReceipt",
    "audit_reference_governance_data",
    "build_reference_governance_catalog",
    "default_reference_governance_fixture",
    "load_reference_governance_fixture",
]

"""Public aggregate fixture for Domain 05 C01–C04 regulatory atlas work.

The fixture is shaped like a small ENCODE SCREEN/cCRE release boundary. It
uses official public source receipts and compact aggregate records; it does
not vendor a downloaded BED archive or any subject-level observation. Every
profile has one supported record and three explicit controls so that absence,
context mismatch, malformed rows, and overlap ambiguity remain executable.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

REGULATORY_ATLAS_FIXTURE_VERSION = "2026.08.d05-c01-c04.v1"
REGULATORY_ATLAS_CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|stem_like|unknown|unknown"
REGULATORY_ATLAS_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
REGULATORY_ATLAS_POSITIVE_COUNT = 4
REGULATORY_ATLAS_CONTROL_COUNT = 12
REGULATORY_ATLAS_SOURCE_COUNT = 5


class RegulatoryAtlasOperation(StrEnum):
    """Executable operation family covered by this fixture."""

    CCRE_PARSE = "ccre_track_parse"
    BRAIN_CELL_PROFILE = "brain_cell_type_profile"
    ADULT_GLIO_PROFILE = "adult_glioma_profile"
    PEDIATRIC_GLIO_PROFILE = "pediatric_glioma_profile"


class RegulatoryAtlasRole(StrEnum):
    """Fixture role separating supported evidence from review controls."""

    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasSourceReceipt:
    """Public source identity, release, license, and scope receipt."""

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
            raise ValidationError("regulatory source URI must be HTTP(S)")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasRecord:
    """One executable cCRE parse or profile query payload."""

    record_id: str
    operation: RegulatoryAtlasOperation
    role: RegulatoryAtlasRole
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
            raise ValidationError("regulatory atlas record requires sources")
        if not self.payload:
            raise ValidationError("regulatory atlas payload must not be empty")
        if not isinstance(self.operation, RegulatoryAtlasOperation):
            raise ValidationError("regulatory atlas operation must be declared")
        if not isinstance(self.role, RegulatoryAtlasRole):
            raise ValidationError("regulatory atlas role must be declared")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasFixture:
    """Versioned public aggregate fixture for C01–C04."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[RegulatoryAtlasSourceReceipt, ...]
    records: tuple[RegulatoryAtlasRecord, ...]
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
        if self.evidence_boundary != REGULATORY_ATLAS_EVIDENCE_BOUNDARY:
            raise ValidationError("regulatory atlas evidence boundary is unsupported")
        if not self.sources or not self.records:
            raise ValidationError("regulatory atlas fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[RegulatoryAtlasRecord, ...]:
        return tuple(
            record for record in self.records if record.role is RegulatoryAtlasRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[RegulatoryAtlasRecord, ...]:
        return tuple(
            record for record in self.records if record.role is RegulatoryAtlasRole.CONTROL
        )

    def source_map(self) -> dict[str, RegulatoryAtlasSourceReceipt]:
        return {source.source_id: source for source in self.sources}

    def record_map(self) -> dict[str, RegulatoryAtlasRecord]:
        return {record.record_id: record for record in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasFixtureCatalog:
    """Indexed source, record, and operation view."""

    fixture: RegulatoryAtlasFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[RegulatoryAtlasOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("regulatory source IDs must be unique")
        if len(self.record_ids) != len(set(self.record_ids)):
            raise ValidationError("regulatory record IDs must be unique")
        if set(self.operations) != set(RegulatoryAtlasOperation):
            raise ValidationError("regulatory catalog must cover all operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasDataCheck:
    """One public-data boundary check."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasDataAudit:
    """Audit of source closure, context, balance, and aggregate scope."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[RegulatoryAtlasDataCheck, ...]
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
) -> RegulatoryAtlasSourceReceipt:
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
    return RegulatoryAtlasSourceReceipt(**body, content_address=_address(body))


def _record(
    record_id: str,
    operation: RegulatoryAtlasOperation,
    role: RegulatoryAtlasRole,
    payload: dict[str, Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
) -> RegulatoryAtlasRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": REGULATORY_ATLAS_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "description": description,
    }
    return RegulatoryAtlasRecord(**body, content_address=_address(body))


def _ccre_tsv(*rows: str) -> str:
    return (
        "chrom\tstart\tend\tccre_id\tprofile\tregistry_class\tscore\tcell_state\t"
        "disease_class\tage_group\tversion\n" + "\n".join(rows) + "\n"
    )


def _context(
    *,
    genome_build: str = "GRCh38",
    disease_class: str = "diffuse_glioma",
    age_group: str = "adult",
    cell_state: str = "stem_like",
    territory: str = "unknown",
    treatment_phase: str = "unknown",
) -> dict[str, Any]:
    return {
        "genome_build": genome_build,
        "disease_class": disease_class,
        "age_group": age_group,
        "cell_state": cell_state,
        "territory": territory,
        "treatment_phase": treatment_phase,
    }


def default_regulatory_atlas_fixture() -> RegulatoryAtlasFixture:
    """Return the C01–C04 public aggregate fixture."""

    sources = (
        _source(
            "encode-screen-about",
            "SCREEN cCRE registry overview",
            "https://screen.encodeproject.org/index/about",
            "registry-documentation",
            "current SCREEN public documentation",
            "ENCODE data policy",
            "cCRE registry definition, classification, and context-free catalog scope",
        ),
        _source(
            "encode-ccre-file",
            "ENCODE released GRCh38 cCRE file",
            "https://www.encodeproject.org/files/ENCFF272QXW/",
            "released-bed-file",
            "ENCODE v4 cCRE file ENCFF272QXW",
            "ENCODE data policy",
            "GRCh38 cCRE file metadata, checksum, assembly, and release boundary",
        ),
        _source(
            "encode-ccre-pipeline",
            "ENCODE candidate Cis-Regulatory Elements v2 pipeline",
            "https://www.encodeproject.org/pipelines/ENCPL751FOQ/",
            "processing-pipeline",
            "released cCRE pipeline v2",
            "ENCODE data policy",
            "cCRE integration of representative DHS and supporting histone or CTCF signals",
        ),
        _source(
            "encode-annotations",
            "ENCODE annotations catalog",
            "https://www.encodeproject.org/data/annotations/",
            "annotation-catalog",
            "current ENCODE annotation boundary",
            "ENCODE data policy",
            "public annotation accession and release metadata",
        ),
        _source(
            "encode-portal",
            "ENCODE Project portal",
            "https://www.encodeproject.org/",
            "data-portal",
            "current ENCODE public portal",
            "ENCODE data policy",
            "public data access and experiment metadata boundary",
        ),
    )
    records = (
        _record(
            "C01-POS-001",
            RegulatoryAtlasOperation.CCRE_PARSE,
            RegulatoryAtlasRole.POSITIVE,
            {
                "input_format": "tsv",
                "source_id": "fixture-encode-ccre",
                "profile": "encode_screen_ccre",
                "input_text": _ccre_tsv(
                    "chr7\t99\t120\tEH38E123\tencode_screen_ccre\tPLS\t0.91\tstem_like\tdiffuse_glioma\tadult\tENCODE-v4"
                ),
            },
            "supported",
            (),
            ("encode-screen-about", "encode-ccre-file", "encode-ccre-pipeline"),
            "valid GRCh38-shaped SCREEN record parses with BED-to-closed conversion",
        ),
        _record(
            "C01-CTRL-001",
            RegulatoryAtlasOperation.CCRE_PARSE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "tsv",
                "source_id": "fixture-encode-ccre",
                "profile": "encode_screen_ccre",
                "input_text": _ccre_tsv(
                    "chr7\tbad\t120\tBAD-COORD\tencode_screen_ccre\tPLS\t0.8\tstem_like\tdiffuse_glioma\tadult\tENCODE-v4"
                ),
            },
            "partial",
            ("invalid_ccre_row",),
            ("encode-ccre-file",),
            "malformed BED coordinate is quarantined",
        ),
        _record(
            "C01-CTRL-002",
            RegulatoryAtlasOperation.CCRE_PARSE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "tsv",
                "source_id": "fixture-encode-ccre",
                "profile": "encode_screen_ccre",
                "input_text": _ccre_tsv(
                    "chr7\t99\t120\tBAD-SCORE\tencode_screen_ccre\tPLS\t101\tstem_like\tdiffuse_glioma\tadult\tENCODE-v4"
                ),
            },
            "partial",
            ("invalid_ccre_row",),
            ("encode-ccre-file",),
            "out-of-range score is quarantined rather than clipped",
        ),
        _record(
            "C01-CTRL-003",
            RegulatoryAtlasOperation.CCRE_PARSE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-encode-ccre",
                "profile": "encode_screen_ccre",
                "input_text": '{"records": [}',
            },
            "abstained",
            ("invalid_ccre_json",),
            ("encode-portal",),
            "invalid JSON input abstains before atlas querying",
        ),
        _record(
            "C02-POS-001",
            RegulatoryAtlasOperation.BRAIN_CELL_PROFILE,
            RegulatoryAtlasRole.POSITIVE,
            {
                "input_format": "json",
                "source_id": "fixture-brain",
                "profile": "brain_cell_type_ccre",
                "input_text": '{"records": [{"chrom": "7", "start": 99, "end": 120, "id": "BRAIN-001", "profile": "brain_cell_type_ccre", "cell_state": "astrocyte", "disease_class": "brain", "age_group": "adult", "version": "ENCODE-v4"}]}',
                "query": {"chromosome": "chr7", "start": 100, "end": 120},
                "context": _context(disease_class="brain", cell_state="astrocyte"),
            },
            "supported",
            (),
            ("encode-screen-about", "encode-ccre-file"),
            "brain-cell profile query matches one context-compatible cCRE",
        ),
        _record(
            "C02-CTRL-001",
            RegulatoryAtlasOperation.BRAIN_CELL_PROFILE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-brain",
                "profile": "brain_cell_type_ccre",
                "input_text": '{"records": [{"chrom": "7", "start": 99, "end": 120, "id": "BRAIN-002", "profile": "brain_cell_type_ccre", "cell_state": "astrocyte", "disease_class": "brain", "age_group": "adult", "version": "ENCODE-v4"}]}',
                "query": {"chromosome": "chr7", "start": 100, "end": 120},
                "context": _context(disease_class="diffuse_glioma", cell_state="stem_like"),
            },
            "out_of_domain",
            (),
            ("encode-screen-about",),
            "overlapping brain record does not transport into glioma stem-like context",
        ),
        _record(
            "C02-CTRL-002",
            RegulatoryAtlasOperation.BRAIN_CELL_PROFILE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-brain",
                "profile": "brain_cell_type_ccre",
                "input_text": '{"records": [{"chrom": "7", "start": 99, "end": 120, "id": "BRAIN-003", "profile": "brain_cell_type_ccre", "cell_state": "astrocyte", "disease_class": "brain", "age_group": "adult", "version": "ENCODE-v4"}]}',
                "query": {"chromosome": "chr8", "start": 100, "end": 120},
                "context": _context(disease_class="brain", cell_state="astrocyte"),
            },
            "absent",
            (),
            ("encode-screen-about",),
            "compatible brain record outside requested interval is absent, not negative",
        ),
        _record(
            "C02-CTRL-003",
            RegulatoryAtlasOperation.BRAIN_CELL_PROFILE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-brain",
                "profile": "brain_cell_type_ccre",
                "input_text": '{"records": [{"chrom": "7", "start": 99, "end": 120, "id": "BRAIN-A", "profile": "brain_cell_type_ccre", "cell_state": "astrocyte", "disease_class": "brain", "age_group": "adult"}, {"chrom": "7", "start": 99, "end": 120, "id": "BRAIN-B", "profile": "brain_cell_type_ccre", "cell_state": "astrocyte", "disease_class": "brain", "age_group": "adult"}]}',
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(disease_class="brain", cell_state="astrocyte"),
            },
            "ambiguous",
            (),
            ("encode-screen-about",),
            "two compatible brain cCREs remain ambiguous",
        ),
        _record(
            "C03-POS-001",
            RegulatoryAtlasOperation.ADULT_GLIO_PROFILE,
            RegulatoryAtlasRole.POSITIVE,
            {
                "input_format": "tsv",
                "source_id": "fixture-adult-glio",
                "profile": "adult_glioma_regulatory",
                "input_text": _ccre_tsv(
                    "7\t99\t120\tADULT-001\tadult_glioma_regulatory\tpELS\t0.75\tstem_like\tdiffuse_glioma\tadult\tENCODE-v4"
                ),
                "query": {"chromosome": "chr7", "start": 100, "end": 120},
                "context": _context(),
            },
            "supported",
            (),
            ("encode-ccre-file", "encode-annotations"),
            "adult diffuse glioma profile matches one stem-like cCRE",
        ),
        _record(
            "C03-CTRL-001",
            RegulatoryAtlasOperation.ADULT_GLIO_PROFILE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "tsv",
                "source_id": "fixture-adult-glio",
                "profile": "adult_glioma_regulatory",
                "input_text": _ccre_tsv(
                    "7\t99\t120\tADULT-002\tadult_glioma_regulatory\tpELS\t0.75\tstem_like\tdiffuse_glioma\tpediatric\tENCODE-v4"
                ),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(),
            },
            "out_of_domain",
            (),
            ("encode-annotations",),
            "adult profile with pediatric age metadata is outside context",
        ),
        _record(
            "C03-CTRL-002",
            RegulatoryAtlasOperation.ADULT_GLIO_PROFILE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "tsv",
                "source_id": "fixture-adult-glio",
                "profile": "adult_glioma_regulatory",
                "input_text": _ccre_tsv(
                    "7\t99\t120\tADULT-003\tadult_glioma_regulatory\tpELS\t0.75\tstem_like\tdiffuse_glioma\tadult\tENCODE-v4"
                ),
                "query": {"chromosome": "8", "start": 100, "end": 120},
                "context": _context(),
            },
            "absent",
            (),
            ("encode-annotations",),
            "adult profile has no compatible overlap on another chromosome",
        ),
        _record(
            "C03-CTRL-003",
            RegulatoryAtlasOperation.ADULT_GLIO_PROFILE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-adult-glio",
                "profile": "adult_glioma_regulatory",
                "input_text": '{"records": [{"chrom": "7", "start": 99, "end": 120, "id": "ADULT-A", "profile": "adult_glioma_regulatory", "cell_state": "stem_like", "disease_class": "diffuse_glioma", "age_group": "adult"}, {"chrom": "7", "start": 99, "end": 120, "id": "ADULT-B", "profile": "adult_glioma_regulatory", "cell_state": "stem_like", "disease_class": "diffuse_glioma", "age_group": "adult"}]}',
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(),
            },
            "ambiguous",
            (),
            ("encode-annotations",),
            "two adult glioma records cannot be silently collapsed",
        ),
        _record(
            "C04-POS-001",
            RegulatoryAtlasOperation.PEDIATRIC_GLIO_PROFILE,
            RegulatoryAtlasRole.POSITIVE,
            {
                "input_format": "json",
                "source_id": "fixture-pediatric-glio",
                "profile": "pediatric_glioma_regulatory",
                "input_text": '{"records": [{"chrom": "7", "start": 99, "end": 120, "id": "PED-001", "profile": "pediatric_glioma_regulatory", "cell_state": "stem_like", "disease_class": "diffuse_glioma", "age_group": "pediatric", "version": "ENCODE-v4"}]}',
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(age_group="pediatric"),
            },
            "supported",
            (),
            ("encode-screen-about", "encode-annotations"),
            "pediatric glioma profile matches only a pediatric context",
        ),
        _record(
            "C04-CTRL-001",
            RegulatoryAtlasOperation.PEDIATRIC_GLIO_PROFILE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-pediatric-glio",
                "profile": "pediatric_glioma_regulatory",
                "input_text": '{"records": [{"chrom": "7", "start": 99, "end": 120, "id": "PED-002", "profile": "pediatric_glioma_regulatory", "cell_state": "stem_like", "disease_class": "diffuse_glioma", "age_group": "pediatric"}]}',
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(age_group="adult"),
            },
            "out_of_domain",
            (),
            ("encode-annotations",),
            "pediatric record does not transport into an adult context",
        ),
        _record(
            "C04-CTRL-002",
            RegulatoryAtlasOperation.PEDIATRIC_GLIO_PROFILE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-pediatric-glio",
                "profile": "pediatric_glioma_regulatory",
                "input_text": '{"records": [{"chrom": "7", "start": 99, "end": 120, "id": "PED-003", "profile": "pediatric_glioma_regulatory", "cell_state": "stem_like", "disease_class": "diffuse_glioma", "age_group": "pediatric"}]}',
                "query": {"chromosome": "8", "start": 100, "end": 120},
                "context": _context(age_group="pediatric"),
            },
            "absent",
            (),
            ("encode-annotations",),
            "pediatric profile is absent outside the declared interval",
        ),
        _record(
            "C04-CTRL-003",
            RegulatoryAtlasOperation.PEDIATRIC_GLIO_PROFILE,
            RegulatoryAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-pediatric-glio",
                "profile": "pediatric_glioma_regulatory",
                "input_text": '{"records": [{"chrom": "7", "start": 99, "end": 120, "id": "PED-A", "profile": "pediatric_glioma_regulatory", "cell_state": "stem_like", "disease_class": "diffuse_glioma", "age_group": "pediatric"}, {"chrom": "7", "start": 99, "end": 120, "id": "PED-B", "profile": "pediatric_glioma_regulatory", "cell_state": "stem_like", "disease_class": "diffuse_glioma", "age_group": "pediatric"}]}',
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(age_group="pediatric"),
            },
            "ambiguous",
            (),
            ("encode-annotations",),
            "two pediatric records preserve interval ambiguity",
        ),
    )
    body = {
        "fixture_id": "regulatory-atlas-public-aggregate",
        "fixture_version": REGULATORY_ATLAS_FIXTURE_VERSION,
        "context_key": REGULATORY_ATLAS_CONTEXT_KEY,
        "evidence_boundary": REGULATORY_ATLAS_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return RegulatoryAtlasFixture(**body, content_address=_address(body))


def build_regulatory_atlas_catalog(
    fixture: RegulatoryAtlasFixture | None = None,
) -> RegulatoryAtlasFixtureCatalog:
    """Build a deterministic indexed fixture view."""

    selected = fixture or default_regulatory_atlas_fixture()
    source_ids = tuple(source.source_id for source in selected.sources)
    record_ids = tuple(record.record_id for record in selected.records)
    operations = tuple(dict.fromkeys(record.operation for record in selected.records))
    if len(source_ids) != len(set(source_ids)):
        raise ValidationError("regulatory fixture has duplicate source IDs")
    if len(record_ids) != len(set(record_ids)):
        raise ValidationError("regulatory fixture has duplicate record IDs")
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "source_ids": source_ids,
        "record_ids": record_ids,
        "operations": operations,
    }
    return RegulatoryAtlasFixtureCatalog(
        selected, source_ids, record_ids, operations, _address(body)
    )


def audit_regulatory_atlas_data(
    fixture: RegulatoryAtlasFixture | None = None,
) -> RegulatoryAtlasDataAudit:
    """Audit public source closure, exact context, balance, and scope."""

    selected = fixture or default_regulatory_atlas_fixture()
    catalog = build_regulatory_atlas_catalog(selected)
    checks: list[RegulatoryAtlasDataCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(RegulatoryAtlasDataCheck(check_id, passed, detail, _address(body)))

    add(
        "fixture-id",
        selected.fixture_id == "regulatory-atlas-public-aggregate",
        "fixture identity is stable",
    )
    add(
        "fixture-version",
        selected.fixture_version == REGULATORY_ATLAS_FIXTURE_VERSION,
        "fixture version is declared",
    )
    add(
        "fixture-context",
        selected.context_key == REGULATORY_ATLAS_CONTEXT_KEY,
        "all records use one exact atlas context",
    )
    add(
        "evidence-boundary",
        selected.evidence_boundary == REGULATORY_ATLAS_EVIDENCE_BOUNDARY,
        "fixture is public aggregate and non-patient",
    )
    add(
        "source-count",
        len(selected.sources) == REGULATORY_ATLAS_SOURCE_COUNT,
        "five public source receipts are present",
    )
    add(
        "source-ids",
        len(catalog.source_ids) == len(set(catalog.source_ids)),
        "source identities are unique",
    )
    add("record-count", len(selected.records) == 16, "sixteen executable records are present")
    add(
        "record-ids",
        len(catalog.record_ids) == len(set(catalog.record_ids)),
        "record identities are unique",
    )
    add(
        "positive-count",
        len(selected.positive_records) == REGULATORY_ATLAS_POSITIVE_COUNT,
        "one positive exists per profile",
    )
    add(
        "control-count",
        len(selected.control_records) == REGULATORY_ATLAS_CONTROL_COUNT,
        "three controls exist per profile",
    )
    add(
        "operation-count", len(catalog.operations) == 4, "all four atlas operations are represented"
    )
    add(
        "operation-balance",
        all(
            sum(record.operation is operation for record in selected.records) == 4
            for operation in RegulatoryAtlasOperation
        ),
        "every operation has one positive and three controls",
    )
    add(
        "positive-state",
        all(record.expected_state == "supported" for record in selected.positive_records),
        "positive records expect support",
    )
    add(
        "control-state",
        all(record.expected_state != "supported" for record in selected.control_records),
        "controls do not expect silent support",
    )
    add(
        "context-closure",
        all(record.context_key == selected.context_key for record in selected.records),
        "record context keys close over fixture context",
    )
    source_set = set(catalog.source_ids)
    add(
        "source-closure",
        all(set(record.source_ids) <= source_set for record in selected.records),
        "every record references declared sources",
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
        "record addresses verify",
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
        "source addresses verify",
    )
    add(
        "fixture-address",
        selected.content_address
        == _address(
            {key: value for key, value in selected.to_dict().items() if key != "content_address"}
        ),
        "fixture address verifies",
    )
    add(
        "no-subject-fields",
        all(
            not {"subject_id", "patient_id", "sample_id"} & set(record.payload)
            for record in selected.records
        ),
        "payloads contain no subject-level fields",
    )
    add(
        "https-sources",
        all(source.uri.startswith("https://") for source in selected.sources),
        "public source receipts use HTTPS",
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
        "catalog address verifies",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "evidence_boundary": selected.evidence_boundary,
        "checks": checks,
    }
    return RegulatoryAtlasDataAudit(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        selected.evidence_boundary,
        tuple(checks),
        _address(body),
    )


def load_regulatory_atlas_fixture(payload: dict[str, Any]) -> RegulatoryAtlasFixture:
    """Load the built-in fixture from an explicit descriptor."""

    if not isinstance(payload, dict):
        raise ValidationError("regulatory atlas descriptor must be an object")
    if payload.get("fixture") == "default_regulatory_atlas_fixture":
        return default_regulatory_atlas_fixture()
    if payload.get("fixture_id") == "regulatory-atlas-public-aggregate":
        return default_regulatory_atlas_fixture()
    raise ValidationError("unsupported regulatory atlas fixture descriptor")


__all__ = [
    "REGULATORY_ATLAS_CONTEXT_KEY",
    "REGULATORY_ATLAS_CONTROL_COUNT",
    "REGULATORY_ATLAS_EVIDENCE_BOUNDARY",
    "REGULATORY_ATLAS_FIXTURE_VERSION",
    "REGULATORY_ATLAS_POSITIVE_COUNT",
    "REGULATORY_ATLAS_SOURCE_COUNT",
    "RegulatoryAtlasDataAudit",
    "RegulatoryAtlasDataCheck",
    "RegulatoryAtlasFixture",
    "RegulatoryAtlasFixtureCatalog",
    "RegulatoryAtlasOperation",
    "RegulatoryAtlasRecord",
    "RegulatoryAtlasRole",
    "RegulatoryAtlasSourceReceipt",
    "audit_regulatory_atlas_data",
    "build_regulatory_atlas_catalog",
    "default_regulatory_atlas_fixture",
    "load_regulatory_atlas_fixture",
]

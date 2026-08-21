"""Public aggregate fixture for Domain 05 C05–C08.

The fixture exercises molecular-state separation and histone-track
harmonization through the existing atlas-beta adapters. It stores compact
aggregate rows shaped from public ENCODE/NCI data contracts. It does not vendor
subject-level data, claim that synthetic rows occur in a source release, or
turn a state-specific overlap into a mechanistic or clinical conclusion.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

MOLECULAR_ATLAS_FIXTURE_VERSION = "2026.08.d05-c05-c08.v1"
MOLECULAR_ATLAS_CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|stem_like|unknown|unknown"
MOLECULAR_ATLAS_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
MOLECULAR_ATLAS_POSITIVE_COUNT = 4
MOLECULAR_ATLAS_CONTROL_COUNT = 12
MOLECULAR_ATLAS_SOURCE_COUNT = 5


class MolecularAtlasOperation(StrEnum):
    """Executable operation families for C05–C08."""

    IDH_MUTANT_PROFILE = "idh_mutant_state_profile"
    IDH_WILDTYPE_PROFILE = "idh_wildtype_state_profile"
    H3K27_ALTERED_PROFILE = "h3k27_altered_state_profile"
    HISTONE_HARMONIZATION = "histone_mark_harmonization"


class MolecularAtlasRole(StrEnum):
    """Positive path versus an explicit review control."""

    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class MolecularAtlasSourceReceipt:
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
        if not self.uri.startswith("https://"):
            raise ValidationError("molecular atlas source URI must use HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasRecord:
    """One executable state-atlas or histone harmonization payload."""

    record_id: str
    operation: MolecularAtlasOperation
    role: MolecularAtlasRole
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
            raise ValidationError("molecular atlas record requires sources")
        if not self.payload:
            raise ValidationError("molecular atlas payload must not be empty")
        if not isinstance(self.operation, MolecularAtlasOperation):
            raise ValidationError("molecular atlas operation must be declared")
        if not isinstance(self.role, MolecularAtlasRole):
            raise ValidationError("molecular atlas role must be declared")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasFixture:
    """Versioned public aggregate fixture for C05–C08."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[MolecularAtlasSourceReceipt, ...]
    records: tuple[MolecularAtlasRecord, ...]
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
        if self.evidence_boundary != MOLECULAR_ATLAS_EVIDENCE_BOUNDARY:
            raise ValidationError("molecular atlas evidence boundary is unsupported")
        if not self.sources or not self.records:
            raise ValidationError("molecular atlas fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[MolecularAtlasRecord, ...]:
        return tuple(
            record for record in self.records if record.role is MolecularAtlasRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[MolecularAtlasRecord, ...]:
        return tuple(record for record in self.records if record.role is MolecularAtlasRole.CONTROL)

    def source_map(self) -> dict[str, MolecularAtlasSourceReceipt]:
        return {source.source_id: source for source in self.sources}

    def record_map(self) -> dict[str, MolecularAtlasRecord]:
        return {record.record_id: record for record in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasFixtureCatalog:
    """Indexed source, record, and operation view."""

    fixture: MolecularAtlasFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[MolecularAtlasOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("molecular atlas source IDs must be unique")
        if len(self.record_ids) != len(set(self.record_ids)):
            raise ValidationError("molecular atlas record IDs must be unique")
        if set(self.operations) != set(MolecularAtlasOperation):
            raise ValidationError("molecular atlas catalog must cover all operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasDataCheck:
    """One public-data boundary check."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasDataAudit:
    """Audit of source closure, context, balance, and aggregate scope."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[MolecularAtlasDataCheck, ...]
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
) -> MolecularAtlasSourceReceipt:
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
    return MolecularAtlasSourceReceipt(**body, content_address=_address(body))


def _record(
    record_id: str,
    operation: MolecularAtlasOperation,
    role: MolecularAtlasRole,
    payload: dict[str, Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
    *,
    context_key: str = MOLECULAR_ATLAS_CONTEXT_KEY,
) -> MolecularAtlasRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": context_key,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "description": description,
    }
    return MolecularAtlasRecord(**body, content_address=_address(body))


def _context(
    *,
    molecular_class: str = "diffuse_glioma",
    age_group: str = "adult",
    cell_state: str = "stem_like",
    territory: str = "unknown",
) -> dict[str, str]:
    return {
        "genome_build": "GRCh38",
        "disease_class": molecular_class,
        "age_group": age_group,
        "cell_state": cell_state,
        "territory": territory,
        "treatment_phase": "unknown",
    }


def _state_rows(
    state: str,
    element_id: str,
    *,
    context_key: str = MOLECULAR_ATLAS_CONTEXT_KEY,
    count: int = 1,
    chromosome: str = "7",
) -> str:
    rows = [
        {
            "element_id": f"{element_id}{suffix}",
            "chrom": chromosome,
            "start": 99,
            "end": 120,
            "molecular_state": state,
            "context_key": context_key,
            "assay": "ATAC-seq",
            "activity_score": 0.72,
            "cell_state": "stem_like",
            "source_version": "ENCODE-v4",
        }
        for suffix in ("" if count == 1 else "-A", "-B")
    ][:count]
    return json.dumps({"records": rows}, sort_keys=True)


def _histone_tsv(rows: tuple[str, ...]) -> str:
    return (
        "\n".join(
            (
                "chrom\tstart\tend\tmark\tsignal\treplicate_id\tcaller_id\tcontext_key\tversion",
                *rows,
            )
        )
        + "\n"
    )


def default_molecular_atlas_fixture() -> MolecularAtlasFixture:
    """Return the deterministic C05–C08 public aggregate fixture."""

    sources = (
        _source(
            "encode-histone-overview",
            "ENCODE histone ChIP-seq standards and processing overview",
            "https://www.encodeproject.org/chip-seq/histone/",
            "official_assay_standard",
            "released-overview",
            "ENCODE public portal terms",
            "histone assay, replicate, signal, and peak-processing boundary",
        ),
        _source(
            "encode-histone-pipeline",
            "ENCODE released histone ChIP-seq pipeline",
            "https://www.encodeproject.org/pipelines/ENCPL272XAE/",
            "official_pipeline_receipt",
            "released",
            "ENCODE public portal terms",
            "histone ChIP-seq processing and replicate-aware output boundary",
        ),
        _source(
            "nci-adult-glioma",
            "NCI adult central nervous system tumor treatment reference",
            "https://www.cancer.gov/types/brain/hp/adult-brain-treatment-pdq",
            "official_disease_reference",
            "current-public-page",
            "US government public information",
            "adult glioma molecular-class context boundary",
        ),
        _source(
            "nci-pediatric-glioma",
            "NCI childhood cancer genomics reference",
            "https://www.cancer.gov/research/areas/childhood/childhood-cancer-data-initiative",
            "official_disease_reference",
            "current-public-page",
            "US government public information",
            "pediatric molecular-class context boundary",
        ),
        _source(
            "gdc-lgg-publication",
            "NCI Genomic Data Commons lower-grade glioma study",
            "https://gdc.cancer.gov/about-data/publications/lgg_2015",
            "official_publication_catalog",
            "2015-publication",
            "US government public information",
            "aggregate molecular subtype and cohort vocabulary boundary",
        ),
    )
    records = (
        _record(
            "C05-POS-001",
            MolecularAtlasOperation.IDH_MUTANT_PROFILE,
            MolecularAtlasRole.POSITIVE,
            {
                "input_format": "json",
                "source_id": "fixture-idh-mutant",
                "source_version": "state-v1",
                "molecular_state": "IDH-mutant",
                "input_text": _state_rows("IDH-mutant", "IDH-M-001"),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(),
            },
            "supported",
            (),
            ("gdc-lgg-publication", "nci-adult-glioma"),
            "one IDH-mutant record matches the exact adult diffuse-glioma context",
        ),
        _record(
            "C05-CTRL-001",
            MolecularAtlasOperation.IDH_MUTANT_PROFILE,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-idh-mutant",
                "source_version": "state-v1",
                "molecular_state": "IDH-mutant",
                "input_text": _state_rows(
                    "IDH-mutant",
                    "IDH-M-002",
                    context_key="GRCh38|diffuse_glioma|pediatric|stem_like|unknown|unknown",
                ),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(),
            },
            "out_of_domain",
            ("state_context_mismatch",),
            ("gdc-lgg-publication", "nci-adult-glioma"),
            "overlap exists but pediatric context cannot be transported to adult evidence",
        ),
        _record(
            "C05-CTRL-002",
            MolecularAtlasOperation.IDH_MUTANT_PROFILE,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-idh-mutant",
                "source_version": "state-v1",
                "molecular_state": "IDH-mutant",
                "input_text": _state_rows("IDH-mutant", "IDH-M-003", chromosome="8"),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(),
            },
            "abstained",
            ("no_state_atlas_overlap",),
            ("gdc-lgg-publication",),
            "no IDH-mutant record overlaps the requested interval",
        ),
        _record(
            "C05-CTRL-003",
            MolecularAtlasOperation.IDH_MUTANT_PROFILE,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-idh-mutant",
                "source_version": "state-v1",
                "molecular_state": "IDH-mutant",
                "input_text": _state_rows("IDH-mutant", "IDH-M-004", count=2),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(),
            },
            "ambiguous",
            ("ambiguous_state_match",),
            ("gdc-lgg-publication",),
            "two compatible IDH-mutant records remain ambiguous",
        ),
        _record(
            "C06-POS-001",
            MolecularAtlasOperation.IDH_WILDTYPE_PROFILE,
            MolecularAtlasRole.POSITIVE,
            {
                "input_format": "json",
                "source_id": "fixture-idh-wildtype",
                "source_version": "state-v1",
                "molecular_state": "IDH-wildtype",
                "input_text": _state_rows("IDH-wildtype", "IDH-W-001"),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(),
            },
            "supported",
            (),
            ("gdc-lgg-publication", "nci-adult-glioma"),
            "one IDH-wildtype record matches the exact adult diffuse-glioma context",
        ),
        _record(
            "C06-CTRL-001",
            MolecularAtlasOperation.IDH_WILDTYPE_PROFILE,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-idh-wildtype",
                "source_version": "state-v1",
                "molecular_state": "IDH-wildtype",
                "input_text": _state_rows(
                    "IDH-wildtype",
                    "IDH-W-002",
                    context_key="GRCh38|diffuse_glioma|pediatric|stem_like|unknown|unknown",
                ),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(),
            },
            "out_of_domain",
            ("state_context_mismatch",),
            ("gdc-lgg-publication", "nci-adult-glioma"),
            "IDH-wildtype evidence from another age group stays out of domain",
        ),
        _record(
            "C06-CTRL-002",
            MolecularAtlasOperation.IDH_WILDTYPE_PROFILE,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-idh-wildtype",
                "source_version": "state-v1",
                "molecular_state": "IDH-wildtype",
                "input_text": _state_rows("IDH-wildtype", "IDH-W-003", chromosome="8"),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(),
            },
            "abstained",
            ("no_state_atlas_overlap",),
            ("gdc-lgg-publication",),
            "IDH-wildtype absence is retained as abstention",
        ),
        _record(
            "C06-CTRL-003",
            MolecularAtlasOperation.IDH_WILDTYPE_PROFILE,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-idh-wildtype",
                "source_version": "state-v1",
                "molecular_state": "IDH-wildtype",
                "input_text": _state_rows("IDH-wildtype", "IDH-W-004", count=2),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(),
            },
            "ambiguous",
            ("ambiguous_state_match",),
            ("gdc-lgg-publication",),
            "multiple compatible IDH-wildtype records are not silently selected",
        ),
        _record(
            "C07-POS-001",
            MolecularAtlasOperation.H3K27_ALTERED_PROFILE,
            MolecularAtlasRole.POSITIVE,
            {
                "input_format": "json",
                "source_id": "fixture-h3k27-altered",
                "source_version": "state-v1",
                "molecular_state": "H3K27-altered",
                "input_text": _state_rows(
                    "H3K27-altered",
                    "H3K-001",
                    context_key="GRCh38|diffuse_midline_glioma|adult|midline_like|midline|unknown",
                ),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(
                    molecular_class="diffuse_midline_glioma",
                    cell_state="midline_like",
                    territory="midline",
                ),
            },
            "supported",
            (),
            ("nci-pediatric-glioma", "gdc-lgg-publication"),
            "one H3K27-altered record matches the declared midline context",
            context_key="GRCh38|diffuse_midline_glioma|adult|midline_like|midline|unknown",
        ),
        _record(
            "C07-CTRL-001",
            MolecularAtlasOperation.H3K27_ALTERED_PROFILE,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-h3k27-altered",
                "source_version": "state-v1",
                "molecular_state": "H3K27-altered",
                "input_text": _state_rows(
                    "H3K27-altered",
                    "H3K-002",
                    context_key="GRCh38|diffuse_midline_glioma|pediatric|midline_like|midline|unknown",
                ),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(
                    molecular_class="diffuse_midline_glioma",
                    cell_state="midline_like",
                    territory="midline",
                ),
            },
            "out_of_domain",
            ("state_context_mismatch",),
            ("nci-pediatric-glioma",),
            "pediatric H3K27-altered context is not transported to adult context",
        ),
        _record(
            "C07-CTRL-002",
            MolecularAtlasOperation.H3K27_ALTERED_PROFILE,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-h3k27-altered",
                "source_version": "state-v1",
                "molecular_state": "H3K27-altered",
                "input_text": _state_rows("H3K27-altered", "H3K-003", chromosome="8"),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(
                    molecular_class="diffuse_midline_glioma",
                    cell_state="midline_like",
                    territory="midline",
                ),
            },
            "abstained",
            ("no_state_atlas_overlap",),
            ("nci-pediatric-glioma",),
            "H3K27-altered absence remains an explicit abstention",
        ),
        _record(
            "C07-CTRL-003",
            MolecularAtlasOperation.H3K27_ALTERED_PROFILE,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "json",
                "source_id": "fixture-h3k27-altered",
                "source_version": "state-v1",
                "molecular_state": "H3K27-altered",
                "input_text": _state_rows(
                    "H3K27-altered",
                    "H3K-004",
                    context_key="GRCh38|diffuse_midline_glioma|adult|midline_like|midline|unknown",
                    count=2,
                ),
                "query": {"chromosome": "7", "start": 100, "end": 120},
                "context": _context(
                    molecular_class="diffuse_midline_glioma",
                    cell_state="midline_like",
                    territory="midline",
                ),
            },
            "ambiguous",
            ("ambiguous_state_match",),
            ("nci-pediatric-glioma",),
            "multiple exact H3K27-altered overlaps remain ambiguous",
            context_key="GRCh38|diffuse_midline_glioma|adult|midline_like|midline|unknown",
        ),
        _record(
            "C08-POS-001",
            MolecularAtlasOperation.HISTONE_HARMONIZATION,
            MolecularAtlasRole.POSITIVE,
            {
                "input_format": "tsv",
                "source_id": "fixture-histone",
                "source_version": "ENCODE-histone-v1",
                "spread_tolerance": 0.25,
                "input_text": _histone_tsv(
                    (
                        "7\t99\t120\tH3K27ac\t4.0\trep-1\tcaller-a\tGRCh38|diffuse_glioma|adult|stem_like|unknown|unknown\tENCODE-v4",
                        "7\t99\t120\tH3K27ac\t4.1\trep-2\tcaller-a\tGRCh38|diffuse_glioma|adult|stem_like|unknown|unknown\tENCODE-v4",
                    )
                ),
            },
            "supported",
            (),
            ("encode-histone-overview", "encode-histone-pipeline"),
            "two concordant H3K27ac replicates harmonize to a supported interval",
        ),
        _record(
            "C08-CTRL-001",
            MolecularAtlasOperation.HISTONE_HARMONIZATION,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "tsv",
                "source_id": "fixture-histone",
                "source_version": "ENCODE-histone-v1",
                "spread_tolerance": 0.25,
                "input_text": _histone_tsv(
                    (
                        "7\tbad\t120\tH3K27ac\t4.0\trep-1\tcaller-a\tGRCh38|diffuse_glioma|adult|stem_like|unknown|unknown\tENCODE-v4",
                    )
                ),
            },
            "partial",
            ("invalid_histone_row",),
            ("encode-histone-overview",),
            "an invalid histone coordinate is quarantined without dropping the receipt",
        ),
        _record(
            "C08-CTRL-002",
            MolecularAtlasOperation.HISTONE_HARMONIZATION,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "tsv",
                "source_id": "fixture-histone",
                "source_version": "ENCODE-histone-v1",
                "spread_tolerance": 0.25,
                "input_text": _histone_tsv(
                    (
                        "7\t99\t120\tH3K27ac\t2.0\trep-1\tcaller-a\tGRCh38|diffuse_glioma|adult|stem_like|unknown|unknown\tENCODE-v4",
                        "7\t99\t120\tH3K27ac\t8.0\trep-2\tcaller-a\tGRCh38|diffuse_glioma|adult|stem_like|unknown|unknown\tENCODE-v4",
                    )
                ),
            },
            "ambiguous",
            ("histone_signal_disagreement",),
            ("encode-histone-pipeline",),
            "large replicate signal disagreement remains ambiguous",
        ),
        _record(
            "C08-CTRL-003",
            MolecularAtlasOperation.HISTONE_HARMONIZATION,
            MolecularAtlasRole.CONTROL,
            {
                "input_format": "tsv",
                "source_id": "fixture-histone",
                "source_version": "ENCODE-histone-v1",
                "spread_tolerance": 0.25,
                "input_text": _histone_tsv(
                    (
                        "7\t99\t120\tH3K27ac\t4.0\trep-1\tcaller-a\tGRCh38|diffuse_glioma|adult|stem_like|unknown|unknown\tENCODE-v4",
                    )
                ),
            },
            "partial",
            ("histone_single_replicate",),
            ("encode-histone-pipeline",),
            "single-replicate signal remains partial rather than supported",
        ),
    )
    body = {
        "fixture_id": "molecular-atlas-public-aggregate",
        "fixture_version": MOLECULAR_ATLAS_FIXTURE_VERSION,
        "context_key": MOLECULAR_ATLAS_CONTEXT_KEY,
        "evidence_boundary": MOLECULAR_ATLAS_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return MolecularAtlasFixture(**body, content_address=_address(body))


def build_molecular_atlas_catalog(fixture: MolecularAtlasFixture) -> MolecularAtlasFixtureCatalog:
    """Build a deterministic index used by execution and reconciliation."""

    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "source_ids": tuple(source.source_id for source in fixture.sources),
        "record_ids": tuple(record.record_id for record in fixture.records),
        "operations": tuple(sorted({record.operation for record in fixture.records}, key=str)),
    }
    return MolecularAtlasFixtureCatalog(
        fixture,
        body["source_ids"],
        body["record_ids"],
        body["operations"],
        _address(body),
    )


def audit_molecular_atlas_data(fixture: MolecularAtlasFixture) -> MolecularAtlasDataAudit:
    """Check source closure, balanced controls, exact context, and scope."""

    catalog = build_molecular_atlas_catalog(fixture)
    source_ids = set(catalog.source_ids)
    checks: list[MolecularAtlasDataCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(MolecularAtlasDataCheck(check_id, passed, detail, _address(body)))

    add(
        "fixture-id",
        fixture.fixture_id == "molecular-atlas-public-aggregate",
        "fixture identity is declared",
    )
    add(
        "fixture-version",
        fixture.fixture_version == MOLECULAR_ATLAS_FIXTURE_VERSION,
        "fixture version is pinned",
    )
    add("context", fixture.context_key == MOLECULAR_ATLAS_CONTEXT_KEY, "fixture context is exact")
    add(
        "boundary",
        fixture.evidence_boundary == MOLECULAR_ATLAS_EVIDENCE_BOUNDARY,
        "fixture stays in aggregate public scope",
    )
    add(
        "source-count",
        len(fixture.sources) == MOLECULAR_ATLAS_SOURCE_COUNT,
        "five public source receipts are present",
    )
    add("record-count", len(fixture.records) == 16, "sixteen fixture records are present")
    add(
        "positive-count",
        len(fixture.positive_records) == MOLECULAR_ATLAS_POSITIVE_COUNT,
        "four positive records are present",
    )
    add(
        "control-count",
        len(fixture.control_records) == MOLECULAR_ATLAS_CONTROL_COUNT,
        "twelve controls are present",
    )
    add(
        "record-ids",
        len(catalog.record_ids) == len(set(catalog.record_ids)),
        "record IDs are unique",
    )
    add(
        "source-ids",
        len(catalog.source_ids) == len(set(catalog.source_ids)),
        "source IDs are unique",
    )
    add(
        "operation-coverage",
        set(catalog.operations) == set(MolecularAtlasOperation),
        "all four operation families are covered",
    )
    add(
        "operation-balance",
        all(
            sum(record.operation is operation for record in fixture.records) == 4
            for operation in MolecularAtlasOperation
        ),
        "each operation has one positive and three controls",
    )
    add(
        "positive-roles",
        all(record.role is MolecularAtlasRole.POSITIVE for record in fixture.positive_records),
        "positive role values are explicit",
    )
    add(
        "control-roles",
        all(record.role is MolecularAtlasRole.CONTROL for record in fixture.control_records),
        "control role values are explicit",
    )
    add(
        "source-closure",
        all(set(record.source_ids) <= source_ids for record in fixture.records),
        "record sources resolve to declared receipts",
    )
    add(
        "source-addresses",
        all(
            source.content_address
            == _address(
                {key: value for key, value in source.to_dict().items() if key != "content_address"}
            )
            for source in fixture.sources
        ),
        "source addresses verify",
    )
    add(
        "fixture-address",
        fixture.content_address
        == _address(
            {key: value for key, value in fixture.to_dict().items() if key != "content_address"}
        ),
        "fixture address verifies",
    )
    add(
        "record-addresses",
        all(
            record.content_address
            == _address(
                {key: value for key, value in record.to_dict().items() if key != "content_address"}
            )
            for record in fixture.records
        ),
        "record addresses verify",
    )
    add(
        "no-subject-fields",
        all(
            not {"subject_id", "patient_id", "sample_id", "donor_id"} & set(record.payload)
            for record in fixture.records
        ),
        "payloads contain no subject-level fields",
    )
    add(
        "https-sources",
        all(source.uri.startswith("https://") for source in fixture.sources),
        "public source receipts use HTTPS",
    )
    add(
        "context-declarations",
        all(record.context_key for record in fixture.records),
        "record context declarations are non-empty",
    )
    add(
        "expected-states",
        all(record.expected_state for record in fixture.records),
        "expected adapter states are declared",
    )
    add(
        "catalog-address",
        catalog.content_address
        == _address(
            {
                "fixture_id": catalog.fixture.fixture_id,
                "fixture_version": catalog.fixture.fixture_version,
                "source_ids": catalog.source_ids,
                "record_ids": catalog.record_ids,
                "operations": catalog.operations,
            }
        ),
        "catalog address verifies",
    )
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "evidence_boundary": fixture.evidence_boundary,
        "checks": checks,
    }
    return MolecularAtlasDataAudit(
        fixture.fixture_id,
        fixture.fixture_version,
        fixture.context_key,
        fixture.evidence_boundary,
        tuple(checks),
        _address(body),
    )


def load_molecular_atlas_fixture(payload: dict[str, Any]) -> MolecularAtlasFixture:
    """Load the built-in fixture from an explicit descriptor."""

    if not isinstance(payload, dict):
        raise ValidationError("molecular atlas descriptor must be an object")
    if (
        payload.get("fixture") == "default_molecular_atlas_fixture"
        or payload.get("fixture_id") == "molecular-atlas-public-aggregate"
    ):
        return default_molecular_atlas_fixture()
    raise ValidationError("unsupported molecular atlas fixture descriptor")


__all__ = [
    "MOLECULAR_ATLAS_CONTEXT_KEY",
    "MOLECULAR_ATLAS_CONTROL_COUNT",
    "MOLECULAR_ATLAS_EVIDENCE_BOUNDARY",
    "MOLECULAR_ATLAS_FIXTURE_VERSION",
    "MOLECULAR_ATLAS_POSITIVE_COUNT",
    "MOLECULAR_ATLAS_SOURCE_COUNT",
    "MolecularAtlasDataAudit",
    "MolecularAtlasDataCheck",
    "MolecularAtlasFixture",
    "MolecularAtlasFixtureCatalog",
    "MolecularAtlasOperation",
    "MolecularAtlasRecord",
    "MolecularAtlasRole",
    "MolecularAtlasSourceReceipt",
    "audit_molecular_atlas_data",
    "build_molecular_atlas_catalog",
    "default_molecular_atlas_fixture",
    "load_molecular_atlas_fixture",
]

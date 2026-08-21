"""Public aggregate fixture for Domain 05 C09-C12.

The fixture is intentionally small, deterministic, and executable.  Its rows
are shaped after public ENCODE and NCI contracts; they are not a download or a
claim that any synthetic row occurs in a public release.  The fixture tests
the important boundary cases for open chromatin, methylation, regulatory
roles, and super-enhancer candidate grouping without carrying patient-level
identifiers or subject data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

ATLAS_ALPHA_EVIDENCE_FIXTURE_VERSION = "2026.08.d05-c09-c12.v1"
ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|stem_like|unknown|unknown"
ATLAS_ALPHA_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
ATLAS_ALPHA_EVIDENCE_POSITIVE_COUNT = 4
ATLAS_ALPHA_EVIDENCE_CONTROL_COUNT = 12
ATLAS_ALPHA_EVIDENCE_SOURCE_COUNT = 5


class AtlasAlphaEvidenceOperation(StrEnum):
    """Executable operation families for C09-C12."""

    OPEN_CHROMATIN = "open_chromatin_harmonization"
    METHYLATION = "methylation_harmonization"
    REGULATORY_ROLE = "regulatory_role_classification"
    SUPER_ENHANCER = "super_enhancer_candidate_atlas"


class AtlasAlphaEvidenceRole(StrEnum):
    """Positive evidence path or deliberately failing control."""

    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceSourceReceipt:
    """Public source identity, provenance, release, and scope receipt."""

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
            raise ValidationError("atlas alpha source URI must use HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceRecord:
    """One executable adapter payload with a declared expected outcome."""

    record_id: str
    operation: AtlasAlphaEvidenceOperation
    role: AtlasAlphaEvidenceRole
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
            raise ValidationError("atlas alpha record requires source receipts")
        if not self.payload:
            raise ValidationError("atlas alpha payload must not be empty")
        if not isinstance(self.operation, AtlasAlphaEvidenceOperation):
            raise ValidationError("atlas alpha operation must be declared")
        if not isinstance(self.role, AtlasAlphaEvidenceRole):
            raise ValidationError("atlas alpha role must be declared")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceFixture:
    """Versioned fixture with source closure and balanced positive controls."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[AtlasAlphaEvidenceSourceReceipt, ...]
    records: tuple[AtlasAlphaEvidenceRecord, ...]
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
        if self.evidence_boundary != ATLAS_ALPHA_EVIDENCE_BOUNDARY:
            raise ValidationError("unsupported atlas alpha evidence boundary")
        if not self.sources or not self.records:
            raise ValidationError("atlas alpha fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[AtlasAlphaEvidenceRecord, ...]:
        return tuple(
            record for record in self.records if record.role is AtlasAlphaEvidenceRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[AtlasAlphaEvidenceRecord, ...]:
        return tuple(
            record for record in self.records if record.role is AtlasAlphaEvidenceRole.CONTROL
        )

    def source_map(self) -> dict[str, AtlasAlphaEvidenceSourceReceipt]:
        return {source.source_id: source for source in self.sources}

    def record_map(self) -> dict[str, AtlasAlphaEvidenceRecord]:
        return {record.record_id: record for record in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceCatalog:
    """Indexed fixture view used by contracts and replay."""

    fixture: AtlasAlphaEvidenceFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[AtlasAlphaEvidenceOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValidationError("atlas alpha source IDs must be unique")
        if len(set(self.record_ids)) != len(self.record_ids):
            raise ValidationError("atlas alpha record IDs must be unique")
        if set(self.operations) != set(AtlasAlphaEvidenceOperation):
            raise ValidationError("atlas alpha catalog must cover every operation")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceDataCheck:
    """One public-data boundary assertion."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class AtlasAlphaEvidenceDataAudit:
    """Audit of source closure, aggregate scope, and context balance."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[AtlasAlphaEvidenceDataCheck, ...]
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
    scope: str,
) -> AtlasAlphaEvidenceSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "source_kind": source_kind,
        "release": release,
        "accessed_on": "2026-08-21",
        "license": "public portal terms",
        "scope": scope,
    }
    return AtlasAlphaEvidenceSourceReceipt(**body, content_address=_address(body))


def _record(
    record_id: str,
    operation: AtlasAlphaEvidenceOperation,
    role: AtlasAlphaEvidenceRole,
    payload: dict[str, Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
    *,
    context_key: str = ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY,
) -> AtlasAlphaEvidenceRecord:
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
    return AtlasAlphaEvidenceRecord(**body, content_address=_address(body))


def _open_rows(
    *,
    signals: tuple[float, ...],
    context_key: str = ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY,
    missing_signal: bool = False,
) -> str:
    rows: list[dict[str, Any]] = []
    for index, signal in enumerate(signals, start=1):
        row: dict[str, Any] = {
            "observation_id": f"open-{index}",
            "chrom": "7",
            "start": 100,
            "end": 120,
            "track_kind": "ATAC-seq",
            "replicate_id": f"rep-{index}",
            "caller_id": "encode-peak-caller",
            "context_key": context_key,
            "source_id": "encode-atac",
            "source_version": "released-public",
        }
        if not (missing_signal and index == 1):
            row["signal"] = signal
        rows.append(row)
    return json.dumps({"records": rows}, sort_keys=True)


def _methylation_rows(
    *,
    fractions: tuple[float, ...],
    context_key: str = ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY,
    zero_coverage: bool = False,
) -> str:
    rows: list[dict[str, Any]] = []
    for index, fraction in enumerate(fractions, start=1):
        row = {
            "observation_id": f"meth-{index}",
            "chrom": "1",
            "start": 200,
            "end": 200,
            "replicate_id": f"rep-{index}",
            "context_key": context_key,
            "source_id": "encode-annotations",
            "source_version": "released-public",
        }
        if not zero_coverage:
            row.update({"methylated_count": round(fraction * 20), "total_count": 20})
        rows.append(row)
    return json.dumps({"records": rows}, sort_keys=True)


def _role_rows(*, mode: str, context_key: str = ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY) -> str:
    row: dict[str, Any] = {
        "element_id": f"role-{mode}",
        "chrom": "7",
        "start": 300,
        "end": 320,
        "context_key": context_key,
        "source_id": "encode-annotations",
        "source_version": "released-public",
        "target_gene_ids": ["EGFR"],
    }
    if mode == "positive":
        row.update(
            {
                "promoter_score": 0.9,
                "enhancer_score": 0.1,
                "silencer_score": 0.1,
                "open_chromatin_signal": 4.0,
                "contact_support": 0.8,
            }
        )
    elif mode == "missing":
        row.update({"enhancer_score": 0.9})
    elif mode == "ambiguous":
        row.update(
            {
                "promoter_score": 0.9,
                "enhancer_score": 0.8,
                "silencer_score": 0.1,
                "open_chromatin_signal": 3.0,
                "contact_support": 0.8,
            }
        )
    return json.dumps({"records": [row]}, sort_keys=True)


def _enhancer_rows(*, mode: str, context_key: str = ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY) -> str:
    if mode == "positive":
        values = (("enh-1", 100, 110, 9.0), ("enh-2", 115, 125, 8.0), ("enh-3", 130, 140, 7.0))
        rows = [
            {
                "enhancer_id": name,
                "chrom": "7",
                "start": start,
                "end": end,
                "signal": signal,
                "activity_score": 0.7,
                "target_gene_ids": ["EGFR"],
                "context_key": context_key,
                "source_id": "screen-encode",
                "source_version": "released-public",
            }
            for name, start, end, signal in values
        ]
    elif mode == "single":
        rows = [
            {
                "enhancer_id": "enh-single",
                "chrom": "7",
                "start": 100,
                "end": 110,
                "signal": 10.0,
                "context_key": context_key,
                "source_id": "screen-encode",
                "source_version": "released-public",
            }
        ]
    elif mode == "partial":
        rows = [
            {
                "enhancer_id": "enh-p1",
                "chrom": "7",
                "start": 100,
                "end": 110,
                "signal": 9.0,
                "target_gene_ids": ["EGFR"],
                "context_key": context_key,
                "source_id": "screen-encode",
                "source_version": "released-public",
            },
            {
                "enhancer_id": "enh-p2",
                "chrom": "7",
                "start": 115,
                "end": 125,
                "signal": 8.0,
                "target_gene_ids": ["EGFR"],
                "context_key": context_key,
                "source_id": "screen-encode",
                "source_version": "released-public",
            },
        ]
    else:
        rows = [
            {
                "enhancer_id": "enh-wrong",
                "chrom": "7",
                "start": 100,
                "end": 110,
                "signal": 10.0,
                "context_key": context_key,
                "source_id": "screen-encode",
                "source_version": "released-public",
            }
        ]
    return json.dumps({"records": rows}, sort_keys=True)


def default_atlas_alpha_evidence_fixture() -> AtlasAlphaEvidenceFixture:
    """Return the deterministic C09-C12 aggregate fixture."""

    sources = (
        _source(
            "encode-atac",
            "ENCODE ATAC-seq data standards and processing",
            "https://www.encodeproject.org/atac-seq/",
            "official_assay_standard",
            "released-overview",
            "open chromatin, replicate, and enrichment boundaries",
        ),
        _source(
            "encode-pipelines",
            "ENCODE data processing pipeline catalog",
            "https://www.encodeproject.org/pipelines/",
            "official_pipeline_catalog",
            "current-public-page",
            "ATAC-seq, DNase-seq, and WGBS processing boundaries",
        ),
        _source(
            "encode-annotations",
            "ENCODE genomic annotations and DNA methylation",
            "https://www.encodeproject.org/data/annotations/",
            "official_annotation_catalog",
            "current-public-page",
            "open chromatin, DNA methylation, and regulatory annotation vocabulary",
        ),
        _source(
            "screen-encode",
            "ENCODE SCREEN candidate cis-regulatory elements",
            "https://screen.encodeproject.org/index/about",
            "official_annotation_resource",
            "current-public-page",
            "candidate regulatory-element and cCRE boundary",
        ),
        _source(
            "nci-adult-glioma",
            "NCI adult central nervous system tumor reference",
            "https://www.cancer.gov/types/brain/hp/adult-brain-treatment-pdq",
            "official_disease_reference",
            "current-public-page",
            "adult glioma context vocabulary",
        ),
    )
    records = (
        _record(
            "C09-POS-001",
            AtlasAlphaEvidenceOperation.OPEN_CHROMATIN,
            AtlasAlphaEvidenceRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _open_rows(signals=(4.0, 4.1)),
                "source_id": "fixture-open",
                "source_version": "v1",
                "spread_tolerance": 0.25,
                "minimum_signal": 0.0,
            },
            "supported",
            (),
            ("encode-atac", "encode-pipelines"),
            "two concordant ATAC-seq replicates support an observed interval",
        ),
        _record(
            "C09-CTRL-001",
            AtlasAlphaEvidenceOperation.OPEN_CHROMATIN,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _open_rows(signals=(4.0,), missing_signal=True),
                "source_id": "fixture-open",
                "source_version": "v1",
                "spread_tolerance": 0.25,
                "minimum_signal": 0.0,
            },
            "partial",
            ("invalid_open_chromatin_row",),
            ("encode-atac",),
            "a missing signal is visible as an invalid row",
        ),
        _record(
            "C09-CTRL-002",
            AtlasAlphaEvidenceOperation.OPEN_CHROMATIN,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _open_rows(signals=(1.0, 5.0)),
                "source_id": "fixture-open",
                "source_version": "v1",
                "spread_tolerance": 0.25,
                "minimum_signal": 0.0,
            },
            "ambiguous",
            ("open_chromatin_signal_disagreement",),
            ("encode-atac",),
            "replicate disagreement is not averaged into a supported call",
        ),
        _record(
            "C09-CTRL-003",
            AtlasAlphaEvidenceOperation.OPEN_CHROMATIN,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _open_rows(
                    signals=(4.0,),
                    context_key="GRCh38|diffuse_glioma|pediatric|stem_like|unknown|unknown",
                ),
                "source_id": "fixture-open",
                "source_version": "v1",
                "spread_tolerance": 0.25,
                "minimum_signal": 0.0,
            },
            "out_of_domain",
            ("context_mismatch",),
            ("encode-atac", "nci-adult-glioma"),
            "pediatric context is not transported into the adult query",
        ),
        _record(
            "C10-POS-001",
            AtlasAlphaEvidenceOperation.METHYLATION,
            AtlasAlphaEvidenceRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _methylation_rows(fractions=(0.8, 0.75)),
                "source_id": "fixture-methylation",
                "source_version": "v1",
                "spread_tolerance": 0.25,
            },
            "supported",
            (),
            ("encode-annotations", "encode-pipelines"),
            "two covered methylation replicates produce a bounded fraction summary",
        ),
        _record(
            "C10-CTRL-001",
            AtlasAlphaEvidenceOperation.METHYLATION,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _methylation_rows(fractions=(0.5,), zero_coverage=True),
                "source_id": "fixture-methylation",
                "source_version": "v1",
                "spread_tolerance": 0.25,
            },
            "partial",
            ("methylation_zero_coverage",),
            ("encode-annotations",),
            "zero coverage remains partial and is not treated as unmethylated",
        ),
        _record(
            "C10-CTRL-002",
            AtlasAlphaEvidenceOperation.METHYLATION,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _methylation_rows(fractions=(0.1, 0.9)),
                "source_id": "fixture-methylation",
                "source_version": "v1",
                "spread_tolerance": 0.25,
            },
            "ambiguous",
            ("methylation_fraction_disagreement",),
            ("encode-annotations",),
            "replicate fraction disagreement remains reviewable",
        ),
        _record(
            "C10-CTRL-003",
            AtlasAlphaEvidenceOperation.METHYLATION,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _methylation_rows(
                    fractions=(0.8,),
                    context_key="GRCh38|diffuse_glioma|pediatric|stem_like|unknown|unknown",
                ),
                "source_id": "fixture-methylation",
                "source_version": "v1",
                "spread_tolerance": 0.25,
            },
            "out_of_domain",
            ("context_mismatch",),
            ("encode-annotations", "nci-adult-glioma"),
            "methylation context mismatch is an explicit domain boundary",
        ),
        _record(
            "C11-POS-001",
            AtlasAlphaEvidenceOperation.REGULATORY_ROLE,
            AtlasAlphaEvidenceRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _role_rows(mode="positive"),
                "source_id": "fixture-role",
                "source_version": "v1",
                "role_threshold": 0.5,
                "methylation_silencer_threshold": 0.8,
            },
            "supported",
            (),
            ("encode-annotations", "screen-encode"),
            "declared promoter channel with accessibility and contact support is complete",
        ),
        _record(
            "C11-CTRL-001",
            AtlasAlphaEvidenceOperation.REGULATORY_ROLE,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _role_rows(mode="missing"),
                "source_id": "fixture-role",
                "source_version": "v1",
                "role_threshold": 0.5,
                "methylation_silencer_threshold": 0.8,
            },
            "partial",
            ("regulatory_role_missing_channels",),
            ("encode-annotations",),
            "an enhancer candidate with missing corroborating channels remains partial",
        ),
        _record(
            "C11-CTRL-002",
            AtlasAlphaEvidenceOperation.REGULATORY_ROLE,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _role_rows(mode="ambiguous"),
                "source_id": "fixture-role",
                "source_version": "v1",
                "role_threshold": 0.5,
                "methylation_silencer_threshold": 0.8,
            },
            "ambiguous",
            ("regulatory_role_ambiguity",),
            ("encode-annotations", "screen-encode"),
            "promoter and enhancer channels both crossing threshold remain multi-role",
        ),
        _record(
            "C11-CTRL-003",
            AtlasAlphaEvidenceOperation.REGULATORY_ROLE,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _role_rows(
                    mode="positive",
                    context_key="GRCh38|diffuse_glioma|pediatric|stem_like|unknown|unknown",
                ),
                "source_id": "fixture-role",
                "source_version": "v1",
                "role_threshold": 0.5,
                "methylation_silencer_threshold": 0.8,
            },
            "out_of_domain",
            ("context_mismatch",),
            ("encode-annotations", "nci-adult-glioma"),
            "regulatory role labels remain context-qualified",
        ),
        _record(
            "C12-POS-001",
            AtlasAlphaEvidenceOperation.SUPER_ENHANCER,
            AtlasAlphaEvidenceRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _enhancer_rows(mode="positive"),
                "source_id": "fixture-super-enhancer",
                "source_version": "v1",
                "minimum_constituents": 2,
                "merge_gap_bp": 5,
                "rank_quantile": 0.0,
            },
            "supported",
            (),
            ("screen-encode", "encode-annotations"),
            "three ranked constituents with declared activity form a supported candidate grouping",
        ),
        _record(
            "C12-CTRL-001",
            AtlasAlphaEvidenceOperation.SUPER_ENHANCER,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _enhancer_rows(mode="single"),
                "source_id": "fixture-super-enhancer",
                "source_version": "v1",
                "minimum_constituents": 2,
                "merge_gap_bp": 5,
                "rank_quantile": 0.0,
            },
            "abstained",
            ("no_super_enhancer_candidate",),
            ("screen-encode",),
            "one ranked element cannot satisfy the constituent floor",
        ),
        _record(
            "C12-CTRL-002",
            AtlasAlphaEvidenceOperation.SUPER_ENHANCER,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _enhancer_rows(mode="partial"),
                "source_id": "fixture-super-enhancer",
                "source_version": "v1",
                "minimum_constituents": 2,
                "merge_gap_bp": 5,
                "rank_quantile": 0.0,
            },
            "partial",
            ("super_enhancer_partial_activity",),
            ("screen-encode",),
            "a candidate without declared activity remains partial",
        ),
        _record(
            "C12-CTRL-003",
            AtlasAlphaEvidenceOperation.SUPER_ENHANCER,
            AtlasAlphaEvidenceRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _enhancer_rows(
                    mode="wrong",
                    context_key="GRCh38|diffuse_glioma|pediatric|stem_like|unknown|unknown",
                ),
                "source_id": "fixture-super-enhancer",
                "source_version": "v1",
                "minimum_constituents": 2,
                "merge_gap_bp": 5,
                "rank_quantile": 0.0,
            },
            "out_of_domain",
            ("context_mismatch",),
            ("screen-encode", "nci-adult-glioma"),
            "candidate intervals do not cross an adult context boundary",
        ),
    )
    body = {
        "fixture_id": "atlas-alpha-public-aggregate",
        "fixture_version": ATLAS_ALPHA_EVIDENCE_FIXTURE_VERSION,
        "context_key": ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY,
        "evidence_boundary": ATLAS_ALPHA_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return AtlasAlphaEvidenceFixture(**body, content_address=_address(body))


def build_atlas_alpha_evidence_catalog(
    fixture: AtlasAlphaEvidenceFixture,
) -> AtlasAlphaEvidenceCatalog:
    """Build a stable source, record, and operation index."""

    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "source_ids": tuple(source.source_id for source in fixture.sources),
        "record_ids": tuple(record.record_id for record in fixture.records),
        "operations": tuple(dict.fromkeys(record.operation for record in fixture.records)),
    }
    return AtlasAlphaEvidenceCatalog(
        fixture=fixture,
        source_ids=body["source_ids"],
        record_ids=body["record_ids"],
        operations=body["operations"],
        content_address=_address(body),
    )


def audit_atlas_alpha_evidence_data(
    fixture: AtlasAlphaEvidenceFixture | None = None,
) -> AtlasAlphaEvidenceDataAudit:
    """Audit source closure and data-scope rules without fetching anything."""

    selected = fixture or default_atlas_alpha_evidence_fixture()
    source_map = selected.source_map()
    checks: list[AtlasAlphaEvidenceDataCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(AtlasAlphaEvidenceDataCheck(check_id, passed, detail, _address(body)))

    add(
        "fixture-context",
        selected.context_key == ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY,
        "fixture context is exact",
    )
    add(
        "fixture-boundary",
        selected.evidence_boundary == ATLAS_ALPHA_EVIDENCE_BOUNDARY,
        "fixture is aggregate non-patient evidence",
    )
    add(
        "source-count",
        len(selected.sources) == ATLAS_ALPHA_EVIDENCE_SOURCE_COUNT,
        "fixture has the expected public source receipts",
    )
    add("source-ids-unique", len(source_map) == len(selected.sources), "source IDs are unique")
    add(
        "record-ids-unique",
        len(selected.record_map()) == len(selected.records),
        "record IDs are unique",
    )
    add(
        "operation-coverage",
        {record.operation for record in selected.records} == set(AtlasAlphaEvidenceOperation),
        "all four operations are represented",
    )
    add(
        "positive-floor",
        len(selected.positive_records) == ATLAS_ALPHA_EVIDENCE_POSITIVE_COUNT,
        "one positive path per operation",
    )
    add(
        "control-floor",
        len(selected.control_records) == ATLAS_ALPHA_EVIDENCE_CONTROL_COUNT,
        "three review controls per operation",
    )
    add(
        "source-closure",
        all(
            source_id in source_map
            for record in selected.records
            for source_id in record.source_ids
        ),
        "every record source resolves",
    )
    add(
        "exact-record-context",
        all(
            record.context_key == selected.context_key
            for record in selected.records
            if record.role is AtlasAlphaEvidenceRole.POSITIVE
        ),
        "positive records retain exact context",
    )
    add(
        "no-subject-identifiers",
        not any(_contains_subject_key(record.payload) for record in selected.records),
        "fixture payloads contain no subject identifiers",
    )
    add(
        "no-fetch-receipts",
        all(source.uri.startswith("https://") for source in selected.sources),
        "source receipts are URLs, not fetched content",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "evidence_boundary": selected.evidence_boundary,
        "checks": checks,
    }
    return AtlasAlphaEvidenceDataAudit(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        selected.evidence_boundary,
        tuple(checks),
        _address(body),
    )


def _contains_subject_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.lower() in {"patient", "subject", "donor", "sample_id", "participant"}
            or _contains_subject_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_subject_key(item) for item in value)
    return False


def load_atlas_alpha_evidence_fixture(path: str) -> AtlasAlphaEvidenceFixture:
    """Load a serialized fixture and validate its stable content address."""

    from pathlib import Path

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = tuple(AtlasAlphaEvidenceSourceReceipt(**row) for row in payload["sources"])
    records = tuple(
        AtlasAlphaEvidenceRecord(
            record_id=row["record_id"],
            operation=AtlasAlphaEvidenceOperation(row["operation"]),
            role=AtlasAlphaEvidenceRole(row["role"]),
            context_key=row["context_key"],
            source_ids=tuple(row["source_ids"]),
            payload=dict(row["payload"]),
            expected_state=row["expected_state"],
            expected_issue_codes=tuple(row["expected_issue_codes"]),
            description=row["description"],
            content_address=row["content_address"],
        )
        for row in payload["records"]
    )
    fixture = AtlasAlphaEvidenceFixture(
        fixture_id=payload["fixture_id"],
        fixture_version=payload["fixture_version"],
        context_key=payload["context_key"],
        evidence_boundary=payload["evidence_boundary"],
        sources=sources,
        records=records,
        content_address=payload["content_address"],
    )
    body = {key: value for key, value in fixture.to_dict().items() if key != "content_address"}
    if fixture.content_address != _address(body):
        raise ValidationError("atlas alpha fixture content address does not verify")
    return fixture


__all__ = [
    "ATLAS_ALPHA_EVIDENCE_BOUNDARY",
    "ATLAS_ALPHA_EVIDENCE_CONTEXT_KEY",
    "ATLAS_ALPHA_EVIDENCE_CONTROL_COUNT",
    "ATLAS_ALPHA_EVIDENCE_FIXTURE_VERSION",
    "ATLAS_ALPHA_EVIDENCE_POSITIVE_COUNT",
    "ATLAS_ALPHA_EVIDENCE_SOURCE_COUNT",
    "AtlasAlphaEvidenceCatalog",
    "AtlasAlphaEvidenceDataAudit",
    "AtlasAlphaEvidenceDataCheck",
    "AtlasAlphaEvidenceFixture",
    "AtlasAlphaEvidenceOperation",
    "AtlasAlphaEvidenceRecord",
    "AtlasAlphaEvidenceRole",
    "AtlasAlphaEvidenceSourceReceipt",
    "audit_atlas_alpha_evidence_data",
    "build_atlas_alpha_evidence_catalog",
    "default_atlas_alpha_evidence_fixture",
    "load_atlas_alpha_evidence_fixture",
]

"""Public aggregate fixture and source-boundary types for Domain 07 C13-C16."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

CHROMATIN_FRONTIER_FIXTURE_VERSION = "2026.08.d07-c13-c16.v1"
CHROMATIN_FRONTIER_CONTEXT_KEY = "GRCh38|glioma|adult|stem_like|tumor|unknown"
CHROMATIN_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
CHROMATIN_FRONTIER_POSITIVE_COUNT = 4
CHROMATIN_FRONTIER_CONTROL_COUNT = 12
CHROMATIN_FRONTIER_SOURCE_COUNT = 5


class ChromatinFrontierOperation(StrEnum):
    CHROMATIN_SEGMENTATION = "chromatin_segmentation"
    ALLELE_SPECIFIC_CHROMATIN = "allele_specific_chromatin"
    EPIGENOMIC_PURITY = "epigenomic_purity"
    BATCH_COMPOSITION_CORRECTION = "batch_composition_correction"


class ChromatinFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class ChromatinFrontierSourceReceipt:
    source_id: str
    title: str
    uri: str
    source_kind: str
    release: str
    scope: str
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "title",
            "uri",
            "source_kind",
            "release",
            "scope",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("chromatin frontier source receipts require HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierRecord:
    record_id: str
    operation: ChromatinFrontierOperation
    role: ChromatinFrontierRole
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
        if not self.source_ids or not self.payload:
            raise ValidationError("chromatin frontier records require sources and payload")
        if not isinstance(self.operation, ChromatinFrontierOperation):
            raise ValidationError("chromatin frontier operation must be declared")
        if not isinstance(self.role, ChromatinFrontierRole):
            raise ValidationError("chromatin frontier role must be declared")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[ChromatinFrontierSourceReceipt, ...]
    records: tuple[ChromatinFrontierRecord, ...]
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
        if self.evidence_boundary != CHROMATIN_FRONTIER_EVIDENCE_BOUNDARY:
            raise ValidationError("unsupported chromatin frontier evidence boundary")
        if not self.sources or not self.records:
            raise ValidationError("chromatin frontier fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[ChromatinFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is ChromatinFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[ChromatinFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is ChromatinFrontierRole.CONTROL)

    def source_map(self) -> dict[str, ChromatinFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, ChromatinFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierCatalog:
    fixture: ChromatinFrontierFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[ChromatinFrontierOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValidationError("chromatin frontier catalog source IDs must be unique")
        if len(set(self.record_ids)) != len(self.record_ids):
            raise ValidationError("chromatin frontier catalog record IDs must be unique")
        if set(self.operations) != set(ChromatinFrontierOperation):
            raise ValidationError("chromatin frontier catalog must cover all operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierDataCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinFrontierDataAudit:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[ChromatinFrontierDataCheck, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return bool(self.checks) and all(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

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
    scope: str,
) -> ChromatinFrontierSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "source_kind": source_kind,
        "release": release,
        "scope": scope,
    }
    return ChromatinFrontierSourceReceipt(**body, content_address=_address(body))


def _text(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, sort_keys=True, separators=(",", ":"))


def _record(
    record_id: str,
    operation: ChromatinFrontierOperation,
    role: ChromatinFrontierRole,
    rows: list[dict[str, Any]],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
    **metadata: Any,
) -> ChromatinFrontierRecord:
    payload = {"input_text": _text(rows), **metadata}
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "description": description,
    }
    return ChromatinFrontierRecord(**body, content_address=_address(body))


def default_chromatin_frontier_fixture() -> ChromatinFrontierFixture:
    sources = (
        _source(
            "encode-atac",
            "ENCODE open chromatin aggregate",
            "https://www.encodeproject.org/",
            "public_portal",
            "2024-01",
            "aggregate accessibility and replicate context",
        ),
        _source(
            "roadmap-epigenomics",
            "Roadmap Epigenomics reference state maps",
            "https://egg2.wustl.edu/roadmap/web_portal/",
            "public_reference",
            "2015",
            "chromatin state and epigenomic reference context",
        ),
        _source(
            "ihec-epigenomes",
            "International Human Epigenome Consortium",
            "https://ihec-epigenomes.org/",
            "public_reference",
            "2024",
            "epigenome metadata and assay provenance",
        ),
        _source(
            "ncbi-geo",
            "NCBI Gene Expression Omnibus",
            "https://www.ncbi.nlm.nih.gov/geo/",
            "public_archive",
            "2025-01",
            "aggregate assay submission context",
        ),
        _source(
            "ucsc-genome-browser",
            "UCSC Genome Browser",
            "https://genome.ucsc.edu/",
            "reference_browser",
            "GRCh38",
            "coordinate and reference assembly context",
        ),
    )
    records = (
        _record(
            "C13-POS-001",
            ChromatinFrontierOperation.CHROMATIN_SEGMENTATION,
            ChromatinFrontierRole.POSITIVE,
            [
                {
                    "id": "seg-pos-1",
                    "chrom": "7",
                    "start": 100,
                    "end": 120,
                    "assay": "ATAC",
                    "signal": 0.9,
                    "state": "open",
                    "replicate": "rep-1",
                    "sample": "aggregate-open-1",
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "encode-atac",
                    "source_version": "2024-01",
                },
                {
                    "id": "seg-pos-2",
                    "chrom": "7",
                    "start": 100,
                    "end": 120,
                    "assay": "ATAC",
                    "signal": 0.86,
                    "state": "open",
                    "replicate": "rep-2",
                    "sample": "aggregate-open-2",
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "encode-atac",
                    "source_version": "2024-01",
                },
            ],
            "supported",
            (),
            ("encode-atac", "ucsc-genome-browser"),
            "replicate-supported open chromatin intervals form a stable segment",
            low_signal=0.25,
            high_signal=0.75,
        ),
        _record(
            "C13-CTRL-001",
            ChromatinFrontierOperation.CHROMATIN_SEGMENTATION,
            ChromatinFrontierRole.CONTROL,
            [
                {
                    "id": "seg-ambiguous-1",
                    "chrom": "7",
                    "start": 200,
                    "end": 220,
                    "assay": "ATAC",
                    "signal": 0.9,
                    "state": "open",
                    "replicate": "rep-1",
                    "sample": "aggregate-mixed-1",
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "encode-atac",
                },
                {
                    "id": "seg-ambiguous-2",
                    "chrom": "7",
                    "start": 200,
                    "end": 220,
                    "assay": "ATAC",
                    "signal": 0.1,
                    "state": "closed",
                    "replicate": "rep-2",
                    "sample": "aggregate-mixed-2",
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "encode-atac",
                },
            ],
            "ambiguous",
            (),
            ("encode-atac",),
            "contradictory replicate states remain ambiguous",
        ),
        _record(
            "C13-CTRL-002",
            ChromatinFrontierOperation.CHROMATIN_SEGMENTATION,
            ChromatinFrontierRole.CONTROL,
            [
                {
                    "id": "seg-out-context",
                    "chrom": "7",
                    "start": 300,
                    "end": 320,
                    "assay": "ATAC",
                    "signal": 0.9,
                    "context_key": "GRCh38|glioma|pediatric|stem_like|tumor|unknown",
                    "source_id": "encode-atac",
                }
            ],
            "out_of_domain",
            ("context_mismatch",),
            ("encode-atac",),
            "pediatric context is not reused for adult evidence",
        ),
        _record(
            "C13-CTRL-003",
            ChromatinFrontierOperation.CHROMATIN_SEGMENTATION,
            ChromatinFrontierRole.CONTROL,
            [{"id": "seg-invalid", "chrom": "7", "start": 400, "end": 390, "signal": 0.8}],
            "partial",
            ("invalid_segmentation_row",),
            ("encode-atac",),
            "reversed interval is quarantined without dropping the fixture",
        ),
        _record(
            "C14-POS-001",
            ChromatinFrontierOperation.ALLELE_SPECIFIC_CHROMATIN,
            ChromatinFrontierRole.POSITIVE,
            [
                {
                    "id": "asc-pos-1",
                    "variant_id": "7:140453136:G:A",
                    "assay": "ATAC",
                    "reference_signal": 2.0,
                    "alternate_signal": 3.0,
                    "replicate": "rep-1",
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "encode-atac",
                },
                {
                    "id": "asc-pos-2",
                    "variant_id": "7:140453136:G:A",
                    "assay": "ATAC",
                    "reference_signal": 2.0,
                    "alternate_signal": 2.8,
                    "replicate": "rep-2",
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "encode-atac",
                },
            ],
            "supported",
            (),
            ("encode-atac", "ucsc-genome-browser"),
            "replicate-consistent alternate accessibility delta is supported",
            ambiguity_tolerance=0.3,
            delta_threshold=0.05,
        ),
        _record(
            "C14-CTRL-001",
            ChromatinFrontierOperation.ALLELE_SPECIFIC_CHROMATIN,
            ChromatinFrontierRole.CONTROL,
            [
                {
                    "id": "asc-mixed-1",
                    "variant_id": "7:140453137:C:T",
                    "assay": "DNase",
                    "reference_signal": 2.0,
                    "alternate_signal": 3.0,
                    "replicate": "rep-1",
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "encode-atac",
                },
                {
                    "id": "asc-mixed-2",
                    "variant_id": "7:140453137:C:T",
                    "assay": "DNase",
                    "reference_signal": 2.0,
                    "alternate_signal": 1.0,
                    "replicate": "rep-2",
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "encode-atac",
                },
            ],
            "ambiguous",
            (),
            ("encode-atac",),
            "mixed allele-specific directions remain ambiguous",
        ),
        _record(
            "C14-CTRL-002",
            ChromatinFrontierOperation.ALLELE_SPECIFIC_CHROMATIN,
            ChromatinFrontierRole.CONTROL,
            [
                {
                    "id": "asc-out-context",
                    "variant_id": "7:140453138:A:G",
                    "assay": "ATAC",
                    "reference_signal": 2.0,
                    "alternate_signal": 3.0,
                    "replicate": "rep-1",
                    "context_key": "GRCh38|glioma|adult|differentiated|tumor|unknown",
                    "source_id": "encode-atac",
                }
            ],
            "out_of_domain",
            ("context_mismatch",),
            ("encode-atac",),
            "differentiated-state evidence remains out of domain",
        ),
        _record(
            "C14-CTRL-003",
            ChromatinFrontierOperation.ALLELE_SPECIFIC_CHROMATIN,
            ChromatinFrontierRole.CONTROL,
            [
                {
                    "id": "asc-invalid",
                    "variant_id": "7:140453139:A:C",
                    "assay": "ATAC",
                    "reference_signal": 2.0,
                    "alternate_signal": "not-a-signal",
                    "replicate": "rep-1",
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "encode-atac",
                }
            ],
            "partial",
            ("invalid_allele_specific_row",),
            ("encode-atac",),
            "non-numeric alternate signal is quarantined",
        ),
        _record(
            "C15-POS-001",
            ChromatinFrontierOperation.EPIGENOMIC_PURITY,
            ChromatinFrontierRole.POSITIVE,
            [
                {
                    "marker_id": "purity-m1",
                    "assay": "methylation",
                    "observed_signal": 0.6,
                    "tumor_signal": 1.0,
                    "normal_signal": 0.0,
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "ihec-epigenomes",
                },
                {
                    "marker_id": "purity-m2",
                    "assay": "ATAC",
                    "observed_signal": 0.34,
                    "tumor_signal": 0.5,
                    "normal_signal": 0.1,
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "ihec-epigenomes",
                },
            ],
            "supported",
            (),
            ("ihec-epigenomes", "ncbi-geo"),
            "two bounded markers agree on a descriptive mixture estimate",
            minimum_markers=2,
            spread_tolerance=0.2,
        ),
        _record(
            "C15-CTRL-001",
            ChromatinFrontierOperation.EPIGENOMIC_PURITY,
            ChromatinFrontierRole.CONTROL,
            [
                {
                    "marker_id": "purity-out-range",
                    "assay": "methylation",
                    "observed_signal": 2.0,
                    "tumor_signal": 1.0,
                    "normal_signal": 0.0,
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "ihec-epigenomes",
                }
            ],
            "partial",
            (),
            ("ihec-epigenomes",),
            "out-of-range marker is clipped for summary and retained as partial",
            minimum_markers=1,
        ),
        _record(
            "C15-CTRL-002",
            ChromatinFrontierOperation.EPIGENOMIC_PURITY,
            ChromatinFrontierRole.CONTROL,
            [
                {
                    "marker_id": "purity-out-context",
                    "assay": "ATAC",
                    "observed_signal": 0.5,
                    "tumor_signal": 1.0,
                    "normal_signal": 0.0,
                    "context_key": "GRCh38|glioma|adult|stem_like|normal|unknown",
                    "source_id": "ihec-epigenomes",
                }
            ],
            "out_of_domain",
            ("context_mismatch",),
            ("ihec-epigenomes",),
            "normal-territory marker is not substituted for tumor territory",
        ),
        _record(
            "C15-CTRL-003",
            ChromatinFrontierOperation.EPIGENOMIC_PURITY,
            ChromatinFrontierRole.CONTROL,
            [
                {
                    "marker_id": "purity-zero-denominator",
                    "assay": "ATAC",
                    "observed_signal": 0.5,
                    "tumor_signal": 0.5,
                    "normal_signal": 0.5,
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "ihec-epigenomes",
                }
            ],
            "partial",
            (),
            ("ihec-epigenomes",),
            "zero reference denominator abstains from a mixture estimate",
            minimum_markers=1,
        ),
        _record(
            "C16-POS-001",
            ChromatinFrontierOperation.BATCH_COMPOSITION_CORRECTION,
            ChromatinFrontierRole.POSITIVE,
            [
                {
                    "feature_id": "batch-feature-1",
                    "batch_id": "batch-1",
                    "assay": "ATAC",
                    "raw_signal": 1.0,
                    "batch_offset": 0.1,
                    "cell_composition": {"tumor": 0.8, "normal": 0.2},
                    "composition_coefficients": {"tumor": 0.5, "normal": -0.5},
                    "target_composition": {"tumor": 0.5, "normal": 0.5},
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "ncbi-geo",
                }
            ],
            "supported",
            (),
            ("ncbi-geo", "ihec-epigenomes"),
            "batch and composition terms remain visible in corrected signal",
        ),
        _record(
            "C16-CTRL-001",
            ChromatinFrontierOperation.BATCH_COMPOSITION_CORRECTION,
            ChromatinFrontierRole.CONTROL,
            [
                {
                    "feature_id": "batch-missing-offset",
                    "batch_id": "batch-missing",
                    "assay": "ATAC",
                    "raw_signal": 1.0,
                    "cell_composition": {"tumor": 1.0},
                    "composition_coefficients": {"tumor": 0.2},
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "ncbi-geo",
                }
            ],
            "partial",
            (),
            ("ncbi-geo",),
            "missing batch offset remains partial rather than imputed",
        ),
        _record(
            "C16-CTRL-002",
            ChromatinFrontierOperation.BATCH_COMPOSITION_CORRECTION,
            ChromatinFrontierRole.CONTROL,
            [
                {
                    "feature_id": "batch-out-context",
                    "batch_id": "batch-2",
                    "assay": "ATAC",
                    "raw_signal": 1.0,
                    "batch_offset": 0.1,
                    "cell_composition": {"tumor": 1.0},
                    "composition_coefficients": {"tumor": 0.2},
                    "context_key": "GRCh38|glioma|adult|differentiated|tumor|unknown",
                    "source_id": "ncbi-geo",
                }
            ],
            "out_of_domain",
            ("context_mismatch",),
            ("ncbi-geo",),
            "differentiated-state batch is not reused",
        ),
        _record(
            "C16-CTRL-003",
            ChromatinFrontierOperation.BATCH_COMPOSITION_CORRECTION,
            ChromatinFrontierRole.CONTROL,
            [
                {
                    "feature_id": "batch-invalid-composition",
                    "batch_id": "batch-3",
                    "assay": "ATAC",
                    "raw_signal": 1.0,
                    "batch_offset": 0.1,
                    "cell_composition": {"tumor": -0.2},
                    "composition_coefficients": {"tumor": 0.2},
                    "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
                    "source_id": "ncbi-geo",
                }
            ],
            "partial",
            ("invalid_batch_composition_row",),
            ("ncbi-geo",),
            "negative composition proportions are quarantined",
        ),
    )
    body = {
        "fixture_id": "chromatin-frontier-public-aggregate",
        "fixture_version": CHROMATIN_FRONTIER_FIXTURE_VERSION,
        "context_key": CHROMATIN_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": CHROMATIN_FRONTIER_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return ChromatinFrontierFixture(**body, content_address=_address(body))


def build_chromatin_frontier_catalog(
    fixture: ChromatinFrontierFixture,
) -> ChromatinFrontierCatalog:
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "source_ids": tuple(item.source_id for item in fixture.sources),
        "record_ids": tuple(item.record_id for item in fixture.records),
        "operations": tuple(dict.fromkeys(item.operation for item in fixture.records)),
    }
    return ChromatinFrontierCatalog(
        fixture,
        body["source_ids"],
        body["record_ids"],
        body["operations"],
        _address(body),
    )


def _contains_subject_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.lower() in {"patient", "subject", "donor", "participant", "sample_id"}
            or _contains_subject_key(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_subject_key(item) for item in value)
    return False


def audit_chromatin_frontier_data(
    fixture: ChromatinFrontierFixture | None = None,
) -> ChromatinFrontierDataAudit:
    selected = fixture or default_chromatin_frontier_fixture()
    source_ids = set(selected.source_map())
    checks: list[ChromatinFrontierDataCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(ChromatinFrontierDataCheck(check_id, passed, detail, _address(body)))

    add(
        "fixture-context",
        selected.context_key == CHROMATIN_FRONTIER_CONTEXT_KEY,
        "fixture context is exact",
    )
    add(
        "fixture-boundary",
        selected.evidence_boundary == CHROMATIN_FRONTIER_EVIDENCE_BOUNDARY,
        "fixture is public aggregate non-patient",
    )
    add(
        "source-closure",
        all(source_id in source_ids for item in selected.records for source_id in item.source_ids),
        "every record source resolves",
    )
    add(
        "source-floor",
        len(selected.sources) == CHROMATIN_FRONTIER_SOURCE_COUNT,
        "five source receipts are present",
    )
    add(
        "record-ids-unique",
        len(selected.record_map()) == len(selected.records),
        "record IDs are unique",
    )
    add(
        "operation-coverage",
        {item.operation for item in selected.records} == set(ChromatinFrontierOperation),
        "all four operations are represented",
    )
    add(
        "positive-floor",
        len(selected.positive_records) == CHROMATIN_FRONTIER_POSITIVE_COUNT,
        "one positive path per operation",
    )
    add(
        "control-floor",
        len(selected.control_records) == CHROMATIN_FRONTIER_CONTROL_COUNT,
        "three controls per operation",
    )
    add(
        "positive-context",
        all(item.context_key == selected.context_key for item in selected.positive_records),
        "positive records declare exact context",
    )
    add(
        "no-subject-identifiers",
        not any(_contains_subject_key(item.payload) for item in selected.records),
        "payloads contain no subject identifiers",
    )
    add(
        "https-receipts",
        all(item.uri.startswith("https://") for item in selected.sources),
        "source receipts use HTTPS",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "evidence_boundary": selected.evidence_boundary,
        "checks": checks,
    }
    return ChromatinFrontierDataAudit(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        selected.evidence_boundary,
        tuple(checks),
        _address(body),
    )


def load_chromatin_frontier_fixture(path: str) -> ChromatinFrontierFixture:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = tuple(ChromatinFrontierSourceReceipt(**row) for row in payload["sources"])
    records = tuple(
        ChromatinFrontierRecord(
            record_id=row["record_id"],
            operation=ChromatinFrontierOperation(row["operation"]),
            role=ChromatinFrontierRole(row["role"]),
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
    fixture = ChromatinFrontierFixture(
        fixture_id=payload["fixture_id"],
        fixture_version=payload["fixture_version"],
        context_key=payload["context_key"],
        evidence_boundary=payload["evidence_boundary"],
        sources=sources,
        records=records,
        content_address=payload["content_address"],
    )
    if fixture.content_address != _address(
        {
            "fixture_id": fixture.fixture_id,
            "fixture_version": fixture.fixture_version,
            "context_key": fixture.context_key,
            "evidence_boundary": fixture.evidence_boundary,
            "sources": fixture.sources,
            "records": fixture.records,
        }
    ):
        raise ValidationError("chromatin frontier fixture content address mismatch")
    return fixture


__all__ = [
    "CHROMATIN_FRONTIER_CONTEXT_KEY",
    "CHROMATIN_FRONTIER_CONTROL_COUNT",
    "CHROMATIN_FRONTIER_EVIDENCE_BOUNDARY",
    "CHROMATIN_FRONTIER_FIXTURE_VERSION",
    "CHROMATIN_FRONTIER_POSITIVE_COUNT",
    "CHROMATIN_FRONTIER_SOURCE_COUNT",
    "ChromatinFrontierCatalog",
    "ChromatinFrontierDataAudit",
    "ChromatinFrontierDataCheck",
    "ChromatinFrontierFixture",
    "ChromatinFrontierOperation",
    "ChromatinFrontierRecord",
    "ChromatinFrontierRole",
    "ChromatinFrontierSourceReceipt",
    "audit_chromatin_frontier_data",
    "build_chromatin_frontier_catalog",
    "default_chromatin_frontier_fixture",
    "load_chromatin_frontier_fixture",
]

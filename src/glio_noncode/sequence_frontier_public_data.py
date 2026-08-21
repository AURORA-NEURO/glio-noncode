"""Public aggregate fixture and source receipts for Domain 06 C13-C16."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

SEQUENCE_FRONTIER_FIXTURE_VERSION = "2026.08.d06-c13-c16.v1"
SEQUENCE_FRONTIER_CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|stem_like|core|untreated"
SEQUENCE_FRONTIER_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
SEQUENCE_FRONTIER_POSITIVE_COUNT = 4
SEQUENCE_FRONTIER_CONTROL_COUNT = 12
SEQUENCE_FRONTIER_SOURCE_COUNT = 5


class SequenceFrontierOperation(StrEnum):
    ENHANCER_GRAMMAR = "enhancer_grammar"
    ALLELE_SATURATION = "allele_saturation"
    ENSEMBLE_DISAGREEMENT = "ensemble_disagreement"
    SEQUENCE_EVIDENCE_PUBLISH = "sequence_evidence_publish"


class SequenceFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class SequenceFrontierSourceReceipt:
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
            raise ValidationError("sequence frontier source receipts require HTTPS")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierRecord:
    record_id: str
    operation: SequenceFrontierOperation
    role: SequenceFrontierRole
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
            raise ValidationError("sequence frontier records require sources and payload")
        if not isinstance(self.operation, SequenceFrontierOperation):
            raise ValidationError("sequence frontier operation must be declared")
        if not isinstance(self.role, SequenceFrontierRole):
            raise ValidationError("sequence frontier role must be declared")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[SequenceFrontierSourceReceipt, ...]
    records: tuple[SequenceFrontierRecord, ...]
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
        if self.evidence_boundary != SEQUENCE_FRONTIER_EVIDENCE_BOUNDARY:
            raise ValidationError("unsupported sequence frontier evidence boundary")
        if not self.sources or not self.records:
            raise ValidationError("sequence frontier fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[SequenceFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is SequenceFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[SequenceFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is SequenceFrontierRole.CONTROL)

    def source_map(self) -> dict[str, SequenceFrontierSourceReceipt]:
        return {item.source_id: item for item in self.sources}

    def record_map(self) -> dict[str, SequenceFrontierRecord]:
        return {item.record_id: item for item in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierCatalog:
    fixture: SequenceFrontierFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[SequenceFrontierOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValidationError("sequence frontier source IDs must be unique")
        if len(set(self.record_ids)) != len(self.record_ids):
            raise ValidationError("sequence frontier record IDs must be unique")
        if set(self.operations) != set(SequenceFrontierOperation):
            raise ValidationError("sequence frontier catalog must cover all operations")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierDataCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceFrontierDataAudit:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[SequenceFrontierDataCheck, ...]
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
) -> SequenceFrontierSourceReceipt:
    body = {
        "source_id": source_id,
        "title": title,
        "uri": uri,
        "source_kind": source_kind,
        "release": release,
        "scope": scope,
    }
    return SequenceFrontierSourceReceipt(**body, content_address=_address(body))


def _record(
    record_id: str,
    operation: SequenceFrontierOperation,
    role: SequenceFrontierRole,
    payload: dict[str, Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
    *,
    context_key: str = SEQUENCE_FRONTIER_CONTEXT_KEY,
) -> SequenceFrontierRecord:
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
    return SequenceFrontierRecord(**body, content_address=_address(body))


def _json_rows(rows: list[dict[str, Any]]) -> str:
    return json.dumps(rows, sort_keys=True, separators=(",", ":"))


def _grammar_rows(mode: str) -> str:
    context = SEQUENCE_FRONTIER_CONTEXT_KEY
    if mode == "positive":
        rows = [
            {
                "grammar_id": "enhancer-egfr",
                "context_key": context,
                "motif_hits": [
                    {"motif_id": "M1", "start": 100, "end": 110},
                    {"motif_id": "M2", "start": 150, "end": 160},
                ],
                "rules": [{"left_motif": "M1", "right_motif": "M2", "min_gap": 40, "max_gap": 60}],
            }
        ]
    elif mode == "empty":
        rows = [
            {"grammar_id": "enhancer-empty", "context_key": context, "motif_hits": [], "rules": []}
        ]
    elif mode == "low-coverage":
        rows = [
            {
                "grammar_id": "enhancer-low",
                "context_key": context,
                "motif_hits": [
                    {"motif_id": "M1", "start": 100, "end": 110},
                    {"motif_id": "M2", "start": 150, "end": 160},
                ],
                "rules": [
                    {"left_motif": "M1", "right_motif": "M2", "min_gap": 40, "max_gap": 60},
                    {"left_motif": "M2", "right_motif": "M3", "min_gap": 1, "max_gap": 5},
                ],
            }
        ]
    else:
        rows = [
            {
                "grammar_id": "enhancer-pediatric",
                "context_key": "GRCh38|diffuse_glioma|pediatric|stem_like|core|untreated",
                "motif_hits": [
                    {"motif_id": "M1", "start": 100, "end": 110},
                    {"motif_id": "M2", "start": 150, "end": 160},
                ],
                "rules": [{"left_motif": "M1", "right_motif": "M2", "min_gap": 40, "max_gap": 60}],
            }
        ]
    return _json_rows(rows)


def _saturation_rows(mode: str) -> str:
    context = SEQUENCE_FRONTIER_CONTEXT_KEY
    if mode == "positive":
        rows = [
            {
                "variant_id": "var-egfr-1",
                "context_key": context,
                "reference_score": 0.2,
                "alternate_alleles": ["A", "C"],
                "alternate_scores": {"A": 0.72, "C": 0.58},
                "uncertainty": 0.08,
            }
        ]
    elif mode == "uncertain":
        rows = [
            {
                "variant_id": "var-uncertain-1",
                "context_key": context,
                "reference_score": 0.2,
                "alternate_alleles": ["A"],
                "alternate_scores": {"A": 0.72},
                "uncertainty": 0.9,
            }
        ]
    elif mode == "flat":
        rows = [
            {
                "variant_id": "var-flat-1",
                "context_key": context,
                "reference_score": 0.5,
                "alternate_alleles": ["A"],
                "alternate_scores": {"A": 0.5},
                "uncertainty": 0.01,
            }
        ]
    else:
        rows = [
            {
                "variant_id": "var-pediatric-1",
                "context_key": "GRCh38|diffuse_glioma|pediatric|stem_like|core|untreated",
                "reference_score": 0.2,
                "alternate_alleles": ["A"],
                "alternate_scores": {"A": 0.72},
                "uncertainty": 0.08,
            }
        ]
    return _json_rows(rows)


def _ensemble_rows(mode: str) -> str:
    context = SEQUENCE_FRONTIER_CONTEXT_KEY
    if mode == "positive":
        rows = [
            {
                "prediction_id": "var-egfr-1",
                "context_key": context,
                "predictions": [0.6, 0.62, 0.61],
            }
        ]
    elif mode == "disagreement":
        rows = [
            {
                "prediction_id": "var-disagreement-1",
                "context_key": context,
                "predictions": [0.1, 0.5, 0.9],
            }
        ]
    elif mode == "single":
        rows = [{"prediction_id": "var-single-1", "context_key": context, "predictions": [0.4]}]
    else:
        rows = [
            {
                "prediction_id": "var-pediatric-1",
                "context_key": "GRCh38|diffuse_glioma|pediatric|stem_like|core|untreated",
                "predictions": [0.6, 0.61, 0.6],
            }
        ]
    return _json_rows(rows)


def _evidence_rows(mode: str) -> str:
    context = SEQUENCE_FRONTIER_CONTEXT_KEY
    if mode == "positive":
        rows = [
            {"sequence_id": "seq-egfr-ref", "context_key": context, "variant_id": "var-egfr-1"},
            {"sequence_id": "seq-egfr-alt", "context_key": context, "variant_id": "var-egfr-1"},
        ]
    elif mode == "empty":
        rows = []
    else:
        rows = [
            {
                "sequence_id": "seq-pediatric",
                "context_key": "GRCh38|diffuse_glioma|pediatric|stem_like|core|untreated",
                "variant_id": "var-pediatric-1",
            }
        ]
    return _json_rows(rows)


def default_sequence_frontier_fixture() -> SequenceFrontierFixture:
    """Return one accepted path and three controls for every operation."""

    sources = (
        _source(
            "ncbi-refseq",
            "NCBI Reference Sequence Database",
            "https://www.ncbi.nlm.nih.gov/refseq/",
            "official_reference_sequence",
            "release-236",
            "reference genomic, transcript, and protein sequence vocabulary",
        ),
        _source(
            "ga4gh-va-spec",
            "GA4GH Variant Annotation Specification",
            "https://va-spec.ga4gh.org/",
            "official_annotation_standard",
            "1.0",
            "variant evidence and study-result representation",
        ),
        _source(
            "encode-screen",
            "ENCODE SCREEN regulatory elements",
            "https://screen.encodeproject.org/index/about",
            "official_regulatory_catalog",
            "current-public-catalog",
            "candidate cis-regulatory and motif context",
        ),
        _source(
            "encode-tf",
            "ENCODE transcription-factor assay boundary",
            "https://www.encodeproject.org/chip-seq/transcription-factor/",
            "official_assay_boundary",
            "current-public-catalog",
            "transcription-factor and motif assay vocabulary",
        ),
        _source(
            "ensembl-regulation",
            "Ensembl regulation resources",
            "https://www.ensembl.org/info/genome/funcgen/regulation.html",
            "official_regulatory_reference",
            "current-public-catalog",
            "sequence regulatory annotation vocabulary",
        ),
    )
    records = (
        _record(
            "C13-POS-001",
            SequenceFrontierOperation.ENHANCER_GRAMMAR,
            SequenceFrontierRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _grammar_rows("positive"),
                "source_id": "fixture-grammar",
                "source_version": "v1",
                "minimum_coverage": 0.6,
            },
            "accepted",
            (),
            ("encode-screen", "encode-tf"),
            "compatible enhancer motif pair satisfies the declared spacing and coverage floor",
        ),
        _record(
            "C13-CTRL-001",
            SequenceFrontierOperation.ENHANCER_GRAMMAR,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _grammar_rows("empty"),
                "source_id": "fixture-grammar",
                "source_version": "v1",
                "minimum_coverage": 0.6,
            },
            "review",
            ("grammar_no_motif_hits",),
            ("encode-screen",),
            "missing motif hits remain review",
        ),
        _record(
            "C13-CTRL-002",
            SequenceFrontierOperation.ENHANCER_GRAMMAR,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _grammar_rows("low-coverage"),
                "source_id": "fixture-grammar",
                "source_version": "v1",
                "minimum_coverage": 0.8,
            },
            "review",
            ("grammar_coverage_below_floor",),
            ("encode-screen", "encode-tf"),
            "incomplete pair coverage remains review",
        ),
        _record(
            "C13-CTRL-003",
            SequenceFrontierOperation.ENHANCER_GRAMMAR,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _grammar_rows("wrong-context"),
                "source_id": "fixture-grammar",
                "source_version": "v1",
                "minimum_coverage": 0.6,
            },
            "out_of_domain",
            ("sequence_context_mismatch",),
            ("encode-screen", "ensembl-regulation"),
            "pediatric motif context is not transported into adult context",
        ),
        _record(
            "C14-POS-001",
            SequenceFrontierOperation.ALLELE_SATURATION,
            SequenceFrontierRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _saturation_rows("positive"),
                "source_id": "fixture-saturation",
                "source_version": "v1",
                "minimum_effect": 0.2,
            },
            "accepted",
            (),
            ("ncbi-refseq", "ga4gh-va-spec"),
            "declared alternate alleles show effects above the reference floor with bounded uncertainty",
        ),
        _record(
            "C14-CTRL-001",
            SequenceFrontierOperation.ALLELE_SATURATION,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _saturation_rows("uncertain"),
                "source_id": "fixture-saturation",
                "source_version": "v1",
                "minimum_effect": 0.2,
            },
            "review",
            ("saturation_uncertainty_above_floor",),
            ("ncbi-refseq",),
            "large uncertainty retains the alternate path for review",
        ),
        _record(
            "C14-CTRL-002",
            SequenceFrontierOperation.ALLELE_SATURATION,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _saturation_rows("flat"),
                "source_id": "fixture-saturation",
                "source_version": "v1",
                "minimum_effect": 0.2,
            },
            "review",
            ("saturation_no_positive_effect",),
            ("ncbi-refseq", "ga4gh-va-spec"),
            "flat alternate score is not a positive saturation effect",
        ),
        _record(
            "C14-CTRL-003",
            SequenceFrontierOperation.ALLELE_SATURATION,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _saturation_rows("wrong-context"),
                "source_id": "fixture-saturation",
                "source_version": "v1",
                "minimum_effect": 0.2,
            },
            "out_of_domain",
            ("sequence_context_mismatch",),
            ("ncbi-refseq", "ga4gh-va-spec"),
            "alternate score from another age context is not reused",
        ),
        _record(
            "C15-POS-001",
            SequenceFrontierOperation.ENSEMBLE_DISAGREEMENT,
            SequenceFrontierRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _ensemble_rows("positive"),
                "source_id": "fixture-ensemble",
                "source_version": "v1",
                "disagreement_threshold": 0.1,
                "interval_multiplier": 1.96,
            },
            "accepted",
            (),
            ("ga4gh-va-spec", "encode-tf", "ensembl-regulation"),
            "three close predictions retain a stable descriptive ensemble summary",
        ),
        _record(
            "C15-CTRL-001",
            SequenceFrontierOperation.ENSEMBLE_DISAGREEMENT,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _ensemble_rows("disagreement"),
                "source_id": "fixture-ensemble",
                "source_version": "v1",
                "disagreement_threshold": 0.2,
                "interval_multiplier": 1.96,
            },
            "review",
            ("ensemble_disagreement_above_floor",),
            ("ga4gh-va-spec", "encode-tf"),
            "wide model spread remains review",
        ),
        _record(
            "C15-CTRL-002",
            SequenceFrontierOperation.ENSEMBLE_DISAGREEMENT,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _ensemble_rows("single"),
                "source_id": "fixture-ensemble",
                "source_version": "v1",
                "disagreement_threshold": 0.2,
                "interval_multiplier": 1.96,
            },
            "review",
            ("ensemble_insufficient_predictions",),
            ("ga4gh-va-spec",),
            "one prediction cannot establish ensemble stability",
        ),
        _record(
            "C15-CTRL-003",
            SequenceFrontierOperation.ENSEMBLE_DISAGREEMENT,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _ensemble_rows("wrong-context"),
                "source_id": "fixture-ensemble",
                "source_version": "v1",
                "disagreement_threshold": 0.1,
                "interval_multiplier": 1.96,
            },
            "out_of_domain",
            ("sequence_context_mismatch",),
            ("ga4gh-va-spec", "ensembl-regulation"),
            "out-of-context ensemble predictions remain quarantined",
        ),
        _record(
            "C16-POS-001",
            SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH,
            SequenceFrontierRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": _evidence_rows("positive"),
                "source_id": "fixture-evidence",
                "source_version": "v1",
                "bundle_id": "sequence-evidence-adult",
                "model_ids": ["model-grammar-v1", "model-saturation-v1"],
            },
            "published",
            (),
            ("ga4gh-va-spec", "ncbi-refseq", "encode-screen"),
            "context-bound sequence observations publish with model and record addresses",
        ),
        _record(
            "C16-CTRL-001",
            SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _evidence_rows("empty"),
                "source_id": "fixture-evidence",
                "source_version": "v1",
                "bundle_id": "sequence-evidence-empty",
                "model_ids": ["model-grammar-v1"],
            },
            "abstained",
            ("empty_sequence_records",),
            ("ga4gh-va-spec",),
            "empty sequence evidence abstains rather than publishing absence",
        ),
        _record(
            "C16-CTRL-002",
            SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _evidence_rows("wrong-context"),
                "source_id": "fixture-evidence",
                "source_version": "v1",
                "bundle_id": "sequence-evidence-pediatric",
                "model_ids": ["model-grammar-v1"],
            },
            "out_of_domain",
            ("sequence_context_mismatch",),
            ("ga4gh-va-spec", "ncbi-refseq"),
            "context drift is retained as out-of-domain",
        ),
        _record(
            "C16-CTRL-003",
            SequenceFrontierOperation.SEQUENCE_EVIDENCE_PUBLISH,
            SequenceFrontierRole.CONTROL,
            {
                "input_format": "json",
                "input_text": _evidence_rows("positive"),
                "source_id": "fixture-evidence",
                "source_version": "v1",
                "bundle_id": "",
                "model_ids": [],
            },
            "invalid",
            ("publish_metadata_invalid",),
            ("ga4gh-va-spec",),
            "missing bundle and model metadata cannot publish",
        ),
    )
    body = {
        "fixture_id": "sequence-frontier-public-aggregate",
        "fixture_version": SEQUENCE_FRONTIER_FIXTURE_VERSION,
        "context_key": SEQUENCE_FRONTIER_CONTEXT_KEY,
        "evidence_boundary": SEQUENCE_FRONTIER_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return SequenceFrontierFixture(**body, content_address=_address(body))


def build_sequence_frontier_catalog(fixture: SequenceFrontierFixture) -> SequenceFrontierCatalog:
    body = {
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "source_ids": tuple(item.source_id for item in fixture.sources),
        "record_ids": tuple(item.record_id for item in fixture.records),
        "operations": tuple(dict.fromkeys(item.operation for item in fixture.records)),
    }
    return SequenceFrontierCatalog(
        fixture, body["source_ids"], body["record_ids"], body["operations"], _address(body)
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


def audit_sequence_frontier_data(
    fixture: SequenceFrontierFixture | None = None,
) -> SequenceFrontierDataAudit:
    selected = fixture or default_sequence_frontier_fixture()
    source_ids = set(selected.source_map())
    checks: list[SequenceFrontierDataCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(SequenceFrontierDataCheck(check_id, passed, detail, _address(body)))

    add(
        "fixture-context",
        selected.context_key == SEQUENCE_FRONTIER_CONTEXT_KEY,
        "fixture context is exact",
    )
    add(
        "fixture-boundary",
        selected.evidence_boundary == SEQUENCE_FRONTIER_EVIDENCE_BOUNDARY,
        "fixture is public aggregate non-patient",
    )
    add(
        "source-closure",
        all(source_id in source_ids for item in selected.records for source_id in item.source_ids),
        "every record source resolves",
    )
    add(
        "record-ids-unique",
        len(selected.record_map()) == len(selected.records),
        "record IDs are unique",
    )
    add(
        "operation-coverage",
        {item.operation for item in selected.records} == set(SequenceFrontierOperation),
        "all four operations are represented",
    )
    add(
        "positive-floor",
        len(selected.positive_records) == SEQUENCE_FRONTIER_POSITIVE_COUNT,
        "one positive path per operation",
    )
    add(
        "control-floor",
        len(selected.control_records) == SEQUENCE_FRONTIER_CONTROL_COUNT,
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
    return SequenceFrontierDataAudit(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        selected.evidence_boundary,
        tuple(checks),
        _address(body),
    )


def load_sequence_frontier_fixture(path: str) -> SequenceFrontierFixture:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    sources = tuple(SequenceFrontierSourceReceipt(**row) for row in payload["sources"])
    records = tuple(
        SequenceFrontierRecord(
            record_id=row["record_id"],
            operation=SequenceFrontierOperation(row["operation"]),
            role=SequenceFrontierRole(row["role"]),
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
    fixture = SequenceFrontierFixture(
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
        raise ValidationError("sequence frontier fixture content address does not verify")
    return fixture


__all__ = [
    "SEQUENCE_FRONTIER_CONTEXT_KEY",
    "SEQUENCE_FRONTIER_CONTROL_COUNT",
    "SEQUENCE_FRONTIER_EVIDENCE_BOUNDARY",
    "SEQUENCE_FRONTIER_FIXTURE_VERSION",
    "SEQUENCE_FRONTIER_POSITIVE_COUNT",
    "SEQUENCE_FRONTIER_SOURCE_COUNT",
    "SequenceFrontierCatalog",
    "SequenceFrontierDataAudit",
    "SequenceFrontierDataCheck",
    "SequenceFrontierFixture",
    "SequenceFrontierOperation",
    "SequenceFrontierRecord",
    "SequenceFrontierRole",
    "SequenceFrontierSourceReceipt",
    "audit_sequence_frontier_data",
    "build_sequence_frontier_catalog",
    "default_sequence_frontier_fixture",
    "load_sequence_frontier_fixture",
]

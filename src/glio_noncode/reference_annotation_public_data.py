"""Public aggregate fixtures for Domain 04 reference annotation boundaries.

The fixture is deliberately small, deterministic, and executable.  It exercises
four input families without embedding a downloaded release or any subject-level
record: GENCODE transcript annotation, MANE transcript matching, the Relation
Ontology vocabulary, and Mondo disease mappings.  Source receipts identify the
public authority and release boundary; the evaluator verifies adapter behavior
against the declared rows and keeps every review control visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty

REFERENCE_ANNOTATION_FIXTURE_VERSION = "2026.08.c05-c08.v1"
REFERENCE_ANNOTATION_CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline"
REFERENCE_ANNOTATION_EVIDENCE_BOUNDARY = "public_aggregate_non_patient"
REFERENCE_ANNOTATION_POSITIVE_COUNT = 4
REFERENCE_ANNOTATION_CONTROL_COUNT = 12
REFERENCE_ANNOTATION_SOURCE_COUNT = 5


class ReferenceAnnotationOperation(StrEnum):
    """Executable operation family covered by the fixture."""

    GENCODE_TRANSCRIPT = "gencode_transcript_catalog"
    MANE_TRANSCRIPT = "mane_transcript_catalog"
    REGULATORY_ONTOLOGY = "regulatory_ontology_catalog"
    DISEASE_ONTOLOGY = "disease_ontology_mapping"


class ReferenceAnnotationRole(StrEnum):
    """Fixture role used to distinguish acceptance from abstention tests."""

    POSITIVE = "positive"
    CONTROL = "control"


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationSourceReceipt:
    """A source identity receipt; it is not a claim that source bytes are vendored."""

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
class ReferenceAnnotationRecord:
    """One executable public fixture row with an explicit expected outcome."""

    record_id: str
    operation: ReferenceAnnotationOperation
    role: ReferenceAnnotationRole
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
            raise ValidationError("annotation record requires source IDs")
        if not self.payload:
            raise ValidationError("annotation record payload must not be empty")
        if not isinstance(self.operation, ReferenceAnnotationOperation):
            raise ValidationError("annotation operation must be a declared enum")
        if not isinstance(self.role, ReferenceAnnotationRole):
            raise ValidationError("annotation role must be a declared enum")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationFixture:
    """Versioned public aggregate fixture."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[ReferenceAnnotationSourceReceipt, ...]
    records: tuple[ReferenceAnnotationRecord, ...]
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
        if self.evidence_boundary != REFERENCE_ANNOTATION_EVIDENCE_BOUNDARY:
            raise ValidationError("fixture evidence boundary is not supported")
        if not self.sources or not self.records:
            raise ValidationError("annotation fixture requires sources and records")

    @property
    def positive_records(self) -> tuple[ReferenceAnnotationRecord, ...]:
        return tuple(
            record for record in self.records if record.role is ReferenceAnnotationRole.POSITIVE
        )

    @property
    def control_records(self) -> tuple[ReferenceAnnotationRecord, ...]:
        return tuple(
            record for record in self.records if record.role is ReferenceAnnotationRole.CONTROL
        )

    def source_map(self) -> dict[str, ReferenceAnnotationSourceReceipt]:
        return {source.source_id: source for source in self.sources}

    def record_map(self) -> dict[str, ReferenceAnnotationRecord]:
        return {record.record_id: record for record in self.records}

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationFixtureCatalog:
    """Indexed fixture view used by evaluators and release checks."""

    fixture: ReferenceAnnotationFixture
    source_ids: tuple[str, ...]
    record_ids: tuple[str, ...]
    operations: tuple[ReferenceAnnotationOperation, ...]
    content_address: str

    def __post_init__(self) -> None:
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValidationError("annotation catalog source IDs must be unique")
        if len(self.record_ids) != len(set(self.record_ids)):
            raise ValidationError("annotation catalog record IDs must be unique")
        if not self.operations:
            raise ValidationError("annotation catalog requires operation coverage")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationDataCheck:
    """Deterministic data-boundary check."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationDataAudit:
    """Audit result for public source and record closure."""

    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    checks: tuple[ReferenceAnnotationDataCheck, ...]
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
) -> ReferenceAnnotationSourceReceipt:
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
    return ReferenceAnnotationSourceReceipt(**body, content_address=_address(body))


def _record(
    record_id: str,
    operation: ReferenceAnnotationOperation,
    role: ReferenceAnnotationRole,
    payload: dict[str, Any],
    expected_state: str,
    expected_issue_codes: tuple[str, ...],
    source_ids: tuple[str, ...],
    description: str,
) -> ReferenceAnnotationRecord:
    body = {
        "record_id": record_id,
        "operation": operation,
        "role": role,
        "context_key": REFERENCE_ANNOTATION_CONTEXT_KEY,
        "source_ids": source_ids,
        "payload": payload,
        "expected_state": expected_state,
        "expected_issue_codes": expected_issue_codes,
        "description": description,
    }
    return ReferenceAnnotationRecord(**body, content_address=_address(body))


def _gencode_text(*rows: str) -> str:
    return "##gff-version 3\n" + "\n".join(rows) + "\n"


def default_reference_annotation_fixture() -> ReferenceAnnotationFixture:
    """Return the checked-in C05–C08 aggregate fixture."""

    sources = (
        _source(
            "gencode-human",
            "GENCODE human release page",
            "https://www.gencodegenes.org/human/",
            "release-index",
            "Release 50 (GRCh38.p14)",
            "GENCODE terms",
            "human transcript annotation release and download boundary",
        ),
        _source(
            "gencode-format",
            "GENCODE GTF data format",
            "https://www.gencodegenes.org/pages/data_format.html",
            "format-specification",
            "current public format page",
            "GENCODE terms",
            "nine-column GTF and attribute grammar boundary",
        ),
        _source(
            "ncbi-mane",
            "NCBI and EMBL-EBI MANE project",
            "https://www.ncbi.nlm.nih.gov/refseq/MANE/",
            "project-documentation",
            "MANE public documentation",
            "NCBI public data terms",
            "matched RefSeq and Ensembl transcript identity boundary",
        ),
        _source(
            "obo-ro",
            "OBO Relation Ontology",
            "https://obofoundry.org/ontology/ro.html",
            "ontology-catalog",
            "public RO catalog",
            "CC0 1.0",
            "declared relationship identifiers and labels",
        ),
        _source(
            "obo-mondo",
            "OBO Mondo Disease Ontology",
            "https://obofoundry.org/ontology/mondo.html",
            "ontology-catalog",
            "public Mondo catalog",
            "CC BY 4.0",
            "declared disease terminology mappings",
        ),
    )
    records = (
        _record(
            "C05-POS-001",
            ReferenceAnnotationOperation.GENCODE_TRANSCRIPT,
            ReferenceAnnotationRole.POSITIVE,
            {
                "input_format": "gtf",
                "input_text": _gencode_text(
                    'chr7\tHAVANA\ttranscript\t100\t500\t.\t+\t.\tgene_id "ENSG000001.2"; transcript_id "ENST000001.4"; gene_name "GLIO1"; transcript_type "lncRNA"; level "2";'  # noqa: E501
                ),
                "query": {"transcript_id": "ENST000001.4"},
                "assembly": "GRCh38",
            },
            "supported",
            (),
            ("gencode-human", "gencode-format"),
            "versioned GENCODE transcript resolves by exact identifier",
        ),
        _record(
            "C05-CTRL-001",
            ReferenceAnnotationOperation.GENCODE_TRANSCRIPT,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "gtf",
                "input_text": _gencode_text("bad\\trow"),
                "query": {"transcript_id": "ENST-MISSING"},
                "assembly": "GRCh38",
            },
            "abstained",
            ("invalid_gencode_row", "transcript_not_resolved"),
            ("gencode-human", "gencode-format"),
            "malformed GTF row is quarantined and cannot resolve a transcript",
        ),
        _record(
            "C05-CTRL-002",
            ReferenceAnnotationOperation.GENCODE_TRANSCRIPT,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "gtf",
                "input_text": _gencode_text(
                    'chr7\tHAVANA\ttranscript\t100\t200\t.\t+\t.\tgene_id "ENSG000002"; transcript_id "ENST000002.1"; transcript_type "lncRNA";',  # noqa: E501
                    'chr7\tHAVANA\ttranscript\t300\t400\t.\t+\t.\tgene_id "ENSG000002"; transcript_id "ENST000003.1"; transcript_type "lncRNA";',  # noqa: E501
                ),
                "query": {"gene_id": "ENSG000002"},
                "assembly": "GRCh38",
            },
            "ambiguous",
            ("ambiguous_transcript_match",),
            ("gencode-human", "gencode-format"),
            "one gene with two exact transcript records remains ambiguous",
        ),
        _record(
            "C05-CTRL-003",
            ReferenceAnnotationOperation.GENCODE_TRANSCRIPT,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "json",
                "input_text": '{"records": [{"transcript_id": "ENST000004", "gene_id": "ENSG000004", "chrom": "7", "start": 1, "end": 10, "strand": "+", "biotype": "lncRNA"}]}',  # noqa: E501
                "query": {"transcript_id": "ENST-UNKNOWN"},
                "assembly": "GRCh38",
            },
            "abstained",
            ("transcript_not_resolved",),
            ("gencode-human", "gencode-format"),
            "well-formed catalog with an unknown identifier abstains",
        ),
        _record(
            "C06-POS-001",
            ReferenceAnnotationOperation.MANE_TRANSCRIPT,
            ReferenceAnnotationRole.POSITIVE,
            {
                "input_format": "tsv",
                "input_text": "ensembl_transcript_id\trefseq_transcript_id\tgene_id\tgene_name\tmane_status\tassembly\tchrom\tstart\tend\nENST000010\tNM_000010.2\tGENE10\tGENE10\tMANE Select\tGRCh38\t7\t100\t500\n",  # noqa: E501
                "query": {"transcript_id": "NM_000010.2"},
            },
            "supported",
            (),
            ("ncbi-mane", "gencode-human"),
            "MANE Select record resolves the RefSeq identifier",
        ),
        _record(
            "C06-CTRL-001",
            ReferenceAnnotationOperation.MANE_TRANSCRIPT,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "tsv",
                "input_text": "ensembl_transcript_id\trefseq_transcript_id\tgene_id\tmane_status\nENST000011\tNM_000011.1\tGENE11\tMANE Select\nENST000012\tNM_000012.1\tGENE11\tMANE Plus Clinical\n",  # noqa: E501
                "query": {"gene_id": "GENE11"},
            },
            "ambiguous",
            ("ambiguous_mane_match",),
            ("ncbi-mane", "gencode-human"),
            "one gene with two MANE rows retains both transcript matches",
        ),
        _record(
            "C06-CTRL-002",
            ReferenceAnnotationOperation.MANE_TRANSCRIPT,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "tsv",
                "input_text": "ensembl_transcript_id\trefseq_transcript_id\tgene_id\tmane_status\n\t\tGENE13\tMANE Select\n",  # noqa: E501
                "query": {"transcript_id": "NM_000013.1"},
            },
            "abstained",
            ("mane_not_resolved",),
            ("ncbi-mane",),
            "invalid MANE identifier row is retained as an issue",
        ),
        _record(
            "C06-CTRL-003",
            ReferenceAnnotationOperation.MANE_TRANSCRIPT,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "json",
                "input_text": '{"records": [{"ensembl_transcript_id": "ENST000014", "refseq_transcript_id": "NM_000014.1", "gene_id": "GENE14", "mane_status": "MANE Select"}]}',  # noqa: E501
                "query": {"transcript_id": "NM-UNKNOWN"},
            },
            "abstained",
            ("mane_not_resolved",),
            ("ncbi-mane",),
            "well-formed MANE catalog with unknown identifier abstains",
        ),
        _record(
            "C07-POS-001",
            ReferenceAnnotationOperation.REGULATORY_ONTOLOGY,
            ReferenceAnnotationRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": '{"terms": [{"term_id": "RO:0001", "label": "regulates", "namespace": "RO", "definition": "declared regulatory relation", "aliases": ["regulation"]}]}',  # noqa: E501
                "query": {"term_id": "RO:0001"},
            },
            "supported",
            (),
            ("obo-ro",),
            "declared Relation Ontology identifier resolves exactly",
        ),
        _record(
            "C07-CTRL-001",
            ReferenceAnnotationOperation.REGULATORY_ONTOLOGY,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "json",
                "input_text": '{"terms": [{"term_id": "RO:0002", "label": "enhancer", "namespace": "RO", "definition": "first label", "aliases": ["enh"]}, {"term_id": "RO:0003", "label": "silencer", "namespace": "RO", "definition": "second label", "aliases": ["enh"]}]}',  # noqa: E501
                "query": {"label": "enh"},
            },
            "ambiguous",
            ("term_match_ambiguous",),
            ("obo-ro",),
            "an alias shared by two terms cannot be silently selected",
        ),
        _record(
            "C07-CTRL-002",
            ReferenceAnnotationOperation.REGULATORY_ONTOLOGY,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "json",
                "input_text": '{"terms": [{"term_id": "RO:0004", "label": "promoter", "namespace": "RO", "definition": "declared promoter"}]}',  # noqa: E501
                "query": {"label": "unknown_regulatory_label"},
            },
            "abstained",
            ("term_not_resolved",),
            ("obo-ro",),
            "unknown regulatory label abstains without lexical inference",
        ),
        _record(
            "C07-CTRL-003",
            ReferenceAnnotationOperation.REGULATORY_ONTOLOGY,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "json",
                "input_text": '{"terms": [{"term_id": "RO:0005", "label": "term-a", "namespace": "RO", "definition": "one"}, {"term_id": "RO:0005", "label": "term-b", "namespace": "RO", "definition": "duplicate"}]}',  # noqa: E501
                "query": {"term_id": "RO-UNKNOWN"},
            },
            "abstained",
            ("invalid_regulatory_term", "term_not_resolved"),
            ("obo-ro",),
            "duplicate ontology ID makes the catalog partial and non-resolvable",
        ),
        _record(
            "C08-POS-001",
            ReferenceAnnotationOperation.DISEASE_ONTOLOGY,
            ReferenceAnnotationRole.POSITIVE,
            {
                "input_format": "json",
                "input_text": '{"mappings": [{"source_term_id": "SRC:GLIOMA", "source_label": "diffuse glioma", "target_term_id": "MONDO:0000268", "target_namespace": "MONDO", "target_label": "glioma", "relationship": "exact"}]}',  # noqa: E501
                "query": {"source_term_id": "SRC:GLIOMA"},
            },
            "supported",
            (),
            ("obo-mondo",),
            "declared disease source identifier maps to one Mondo target",
        ),
        _record(
            "C08-CTRL-001",
            ReferenceAnnotationOperation.DISEASE_ONTOLOGY,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "json",
                "input_text": '{"mappings": [{"source_term_id": "SRC:AMB", "source_label": "ambiguous glioma", "target_term_id": "MONDO:1", "target_namespace": "MONDO", "relationship": "related"}, {"source_term_id": "SRC:AMB", "source_label": "ambiguous glioma", "target_term_id": "DOID:2", "target_namespace": "DOID", "relationship": "broader"}]}',  # noqa: E501
                "query": {"source_term_id": "SRC:AMB"},
            },
            "ambiguous",
            ("disease_mapping_ambiguous",),
            ("obo-mondo",),
            "one source term with two targets preserves mapping ambiguity",
        ),
        _record(
            "C08-CTRL-002",
            ReferenceAnnotationOperation.DISEASE_ONTOLOGY,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "json",
                "input_text": '{"mappings": [{"source_term_id": "SRC:KNOWN", "source_label": "known term", "target_term_id": "MONDO:3", "target_namespace": "MONDO", "relationship": "exact"}]}',  # noqa: E501
                "query": {"source_term_id": "SRC:UNKNOWN"},
            },
            "abstained",
            ("disease_not_resolved",),
            ("obo-mondo",),
            "unknown disease source identifier abstains",
        ),
        _record(
            "C08-CTRL-003",
            ReferenceAnnotationOperation.DISEASE_ONTOLOGY,
            ReferenceAnnotationRole.CONTROL,
            {
                "input_format": "json",
                "input_text": '{"mappings": [{"source_term_id": "SRC:REL", "source_label": "related term", "target_term_id": "MONDO:4", "target_namespace": "MONDO", "relationship": "exact"}]}',  # noqa: E501
                "query": {"source_label": "unlisted label"},
            },
            "abstained",
            ("disease_not_resolved",),
            ("obo-mondo",),
            "unknown disease label abstains without diagnosis inference",
        ),
    )
    body = {
        "fixture_id": "reference-annotation-public-aggregate",
        "fixture_version": REFERENCE_ANNOTATION_FIXTURE_VERSION,
        "context_key": REFERENCE_ANNOTATION_CONTEXT_KEY,
        "evidence_boundary": REFERENCE_ANNOTATION_EVIDENCE_BOUNDARY,
        "sources": sources,
        "records": records,
    }
    return ReferenceAnnotationFixture(**body, content_address=_address(body))


def build_reference_annotation_catalog(
    fixture: ReferenceAnnotationFixture | None = None,
) -> ReferenceAnnotationFixtureCatalog:
    """Build a deterministic index and reject duplicate source or record identities."""

    selected = fixture or default_reference_annotation_fixture()
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
    return ReferenceAnnotationFixtureCatalog(
        selected,
        source_ids,
        record_ids,
        operations,
        _address(body),
    )


def audit_reference_annotation_data(
    fixture: ReferenceAnnotationFixture | None = None,
) -> ReferenceAnnotationDataAudit:
    """Audit source closure, public boundary, context, and operation balance."""

    selected = fixture or default_reference_annotation_fixture()
    catalog = build_reference_annotation_catalog(selected)
    checks: list[ReferenceAnnotationDataCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        body = {"check_id": check_id, "passed": passed, "detail": detail}
        checks.append(ReferenceAnnotationDataCheck(check_id, passed, detail, _address(body)))

    add(
        "fixture-id",
        selected.fixture_id == "reference-annotation-public-aggregate",
        "fixture identity is stable",
    )
    add(
        "fixture-version",
        selected.fixture_version == REFERENCE_ANNOTATION_FIXTURE_VERSION,
        "fixture version is declared",
    )
    add(
        "fixture-context",
        selected.context_key == REFERENCE_ANNOTATION_CONTEXT_KEY,
        "one exact context key covers all records",
    )
    add(
        "public-boundary",
        selected.evidence_boundary == REFERENCE_ANNOTATION_EVIDENCE_BOUNDARY,
        "only public aggregate evidence is admitted",
    )
    add(
        "source-count",
        len(selected.sources) == REFERENCE_ANNOTATION_SOURCE_COUNT,
        "five official source receipts are present",
    )
    add(
        "source-unique",
        len(catalog.source_ids) == len(set(catalog.source_ids)),
        "source identities are unique",
    )
    add(
        "source-closure",
        set(catalog.source_ids) == {source.source_id for source in selected.sources},
        "catalog source index closes over receipts",
    )
    add(
        "record-count",
        len(selected.records)
        == REFERENCE_ANNOTATION_POSITIVE_COUNT + REFERENCE_ANNOTATION_CONTROL_COUNT,
        "sixteen executable records are present",
    )
    add(
        "record-unique",
        len(catalog.record_ids) == len(set(catalog.record_ids)),
        "record identities are unique",
    )
    add(
        "positive-count",
        len(selected.positive_records) == REFERENCE_ANNOTATION_POSITIVE_COUNT,
        "one positive record covers each operation",
    )
    add(
        "control-count",
        len(selected.control_records) == REFERENCE_ANNOTATION_CONTROL_COUNT,
        "three controls cover each operation",
    )
    add("operation-count", len(catalog.operations) == 4, "four operation families are declared")
    add(
        "operation-balance",
        all(
            sum(record.operation is operation for record in selected.records) == 4
            for operation in ReferenceAnnotationOperation
        ),
        "each operation has four records",
    )
    add(
        "positive-operation-balance",
        {record.operation for record in selected.positive_records}
        == set(ReferenceAnnotationOperation),
        "each operation has one positive",
    )
    add(
        "control-operation-balance",
        all(
            sum(
                record.operation is operation and record.role is ReferenceAnnotationRole.CONTROL
                for record in selected.records
            )
            == 3
            for operation in ReferenceAnnotationOperation
        ),
        "each operation has three controls",
    )
    add(
        "context-closure",
        all(record.context_key == selected.context_key for record in selected.records),
        "record contexts match fixture context",
    )
    add(
        "source-reference-closure",
        all(set(record.source_ids) <= set(catalog.source_ids) for record in selected.records),
        "records reference declared sources only",
    )
    add(
        "payload-shape",
        all(
            isinstance(record.payload.get("input_text"), str) and record.payload.get("input_text")
            for record in selected.records
        ),
        "each record has a text input",
    )
    add(
        "query-shape",
        all(
            isinstance(record.payload.get("query"), dict) and record.payload["query"]
            for record in selected.records
        ),
        "each record has a query",
    )
    add(
        "expected-state",
        all(
            record.expected_state in {"supported", "ambiguous", "abstained"}
            for record in selected.records
        ),
        "expected states are bounded",
    )
    add(
        "positive-state",
        all(record.expected_state == "supported" for record in selected.positive_records),
        "positive records require support",
    )
    add(
        "control-state",
        all(record.expected_state != "supported" for record in selected.control_records),
        "controls cannot be accepted",
    )
    add(
        "content-addresses",
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
    catalog_body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "source_ids": catalog.source_ids,
        "record_ids": catalog.record_ids,
        "operations": catalog.operations,
    }
    add(
        "catalog-address",
        catalog.content_address == _address(catalog_body),
        "catalog address verifies",
    )
    body = {
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "evidence_boundary": selected.evidence_boundary,
        "checks": checks,
    }
    return ReferenceAnnotationDataAudit(
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        selected.evidence_boundary,
        tuple(checks),
        _address(body),
    )


def load_reference_annotation_fixture(payload: dict[str, Any]) -> ReferenceAnnotationFixture:
    """Load a serialized fixture while rebuilding typed identities and addresses."""

    if not isinstance(payload, dict):
        raise ValidationError("annotation fixture payload must be an object")
    if payload.get("fixture") == "default_reference_annotation_fixture":
        return default_reference_annotation_fixture()
    try:
        sources = tuple(
            ReferenceAnnotationSourceReceipt(
                **{key: value for key, value in item.items() if key != "content_address"},
                content_address=item["content_address"],
            )
            for item in payload["sources"]
        )
        records = tuple(
            ReferenceAnnotationRecord(
                operation=ReferenceAnnotationOperation(item["operation"]),
                role=ReferenceAnnotationRole(item["role"]),
                **{
                    key: value
                    for key, value in item.items()
                    if key not in {"operation", "role", "content_address"}
                },
                content_address=item["content_address"],
            )
            for item in payload["records"]
        )
        return ReferenceAnnotationFixture(
            fixture_id=payload["fixture_id"],
            fixture_version=payload["fixture_version"],
            context_key=payload["context_key"],
            evidence_boundary=payload["evidence_boundary"],
            sources=sources,
            records=records,
            content_address=payload["content_address"],
        )
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise ValidationError(f"invalid reference annotation fixture: {exc}") from exc


__all__ = [
    "REFERENCE_ANNOTATION_CONTEXT_KEY",
    "REFERENCE_ANNOTATION_CONTROL_COUNT",
    "REFERENCE_ANNOTATION_EVIDENCE_BOUNDARY",
    "REFERENCE_ANNOTATION_FIXTURE_VERSION",
    "REFERENCE_ANNOTATION_POSITIVE_COUNT",
    "REFERENCE_ANNOTATION_SOURCE_COUNT",
    "ReferenceAnnotationDataAudit",
    "ReferenceAnnotationDataCheck",
    "ReferenceAnnotationFixture",
    "ReferenceAnnotationFixtureCatalog",
    "ReferenceAnnotationOperation",
    "ReferenceAnnotationRecord",
    "ReferenceAnnotationRole",
    "ReferenceAnnotationSourceReceipt",
    "audit_reference_annotation_data",
    "build_reference_annotation_catalog",
    "default_reference_annotation_fixture",
    "load_reference_annotation_fixture",
]

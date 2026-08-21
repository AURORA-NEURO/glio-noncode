"""Scientific-beta reference and annotation governance adapters.

The Domain 04 MVP already covers assemblies, liftover, ambiguity scoring, and
pangenome paths. This module adds four version-aware input boundaries:

* GENCODE transcript records;
* MANE transcript records;
* declared regulatory ontology terms; and
* disease ontology mappings.

All adapters preserve raw rows and source versions. They never infer a
transcript from a label, choose between competing MANE records, or turn a
disease label into a clinical diagnosis. The ontology operations are catalog
lookups, not live ontology downloads.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome
from .serialization import content_hash, jsonable, require_non_empty


class ReferenceBetaState(StrEnum):
    """Evidence state shared by transcript and ontology adapters."""

    SUPPORTED = "supported"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    ABSTAINED = "abstained"
    INVALID = "invalid"
    OUT_OF_DOMAIN = "out_of_domain"


@dataclass(frozen=True, slots=True)
class ReferenceBetaIssue:
    """Source-row-addressable annotation issue."""

    code: str
    message: str
    raw_hash: str
    row_number: int | None = None
    source_id: str = "unspecified"
    severity: str = "warning"
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "issue code")
        require_non_empty(self.message, "issue message")
        require_non_empty(self.raw_hash, "issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("issue row_number must be positive")
        if self.severity not in {"warning", "error"}:
            raise ValidationError("issue severity must be warning or error")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TranscriptRecord:
    """One normalized GENCODE transcript row."""

    transcript_id: str
    transcript_version: str | None
    gene_id: str
    gene_name: str | None
    assembly: str
    chromosome: str
    start: int
    end: int
    strand: str
    biotype: str
    source_id: str
    source_version: str
    raw_hash: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "transcript_id",
            "gene_id",
            "assembly",
            "chromosome",
            "source_id",
            "source_version",
            "raw_hash",
            "biotype",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.start < 1 or self.end < self.start:
            raise ValidationError("transcript interval is invalid")
        if self.strand not in {"+", "-", "."}:
            raise ValidationError("transcript strand must be +, -, or .")

    @property
    def versioned_id(self) -> str:
        return (
            f"{self.transcript_id}.{self.transcript_version}"
            if self.transcript_version
            else self.transcript_id
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"versioned_id": self.versioned_id}


@dataclass(frozen=True, slots=True)
class TranscriptCatalog:
    """Parsed transcript records with quarantined malformed rows."""

    source_id: str
    source_version: str
    assembly: str
    input_hash: str
    records: tuple[TranscriptRecord, ...]
    issues: tuple[ReferenceBetaIssue, ...]
    content_address: str

    @property
    def state(self) -> ReferenceBetaState:
        if not self.records:
            return ReferenceBetaState.ABSTAINED
        return ReferenceBetaState.PARTIAL if self.issues else ReferenceBetaState.SUPPORTED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "records": [record.to_dict() for record in self.records],
            "state": self.state.value,
        }


@dataclass(frozen=True, slots=True)
class TranscriptResolution:
    """Exact transcript lookup result with one-to-many ambiguity retained."""

    query_id: str
    state: ReferenceBetaState
    records: tuple[TranscriptRecord, ...]
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"records": [record.to_dict() for record in self.records]}


class GencodeTranscriptAdapter:
    """Parse GENCODE-like GTF/JSON transcript snapshots and resolve exact IDs."""

    _attribute_pattern = re.compile(r"([A-Za-z0-9_.-]+)\s+\"([^\"]*)\"")

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        assembly: str = "GRCh38",
        input_format: str | None = None,
        feature_types: tuple[str, ...] = ("transcript",),
    ) -> TranscriptCatalog:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("GENCODE transcript input must not be empty")
        selected = (input_format or "").lower().strip()
        if not selected:
            selected = "json" if text.lstrip().startswith(("{", "[")) else "gtf"
        if selected == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                return self._catalog(
                    source_id,
                    source_version,
                    assembly,
                    text,
                    (),
                    (
                        ReferenceBetaIssue(
                            "invalid_json",
                            str(exc),
                            content_hash(text),
                            severity="error",
                        ),
                    ),
                )
            rows = (
                payload.get("records", payload.get("transcripts"))
                if isinstance(payload, Mapping)
                else payload
            )
            if not isinstance(rows, list):
                return self._catalog(
                    source_id,
                    source_version,
                    assembly,
                    text,
                    (),
                    (
                        ReferenceBetaIssue(
                            "invalid_json_shape",
                            "GENCODE JSON must contain a records or transcripts list",
                            content_hash(payload),
                            severity="error",
                        ),
                    ),
                )
            return self._parse_rows(rows, source_id, source_version, assembly, text)
        if selected not in {"gtf", "gff3"}:
            raise ValidationError(f"unsupported GENCODE input format: {selected}")
        rows: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip() or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) != 9:
                rows.append({"__line_number": line_number, "__raw_line": line})
                continue
            attributes = self._parse_attributes(fields[8])
            if fields[2] not in feature_types:
                continue
            rows.append(
                {
                    "__line_number": line_number,
                    "chromosome": fields[0],
                    "feature": fields[2],
                    "start": fields[3],
                    "end": fields[4],
                    "strand": fields[6],
                    "attributes": attributes,
                    **attributes,
                }
            )
        return self._parse_rows(rows, source_id, source_version, assembly, text)

    def resolve(
        self,
        catalog: TranscriptCatalog,
        *,
        transcript_id: str | None = None,
        gene_id: str | None = None,
        version: str | None = None,
    ) -> TranscriptResolution:
        if not transcript_id and not gene_id:
            raise ValidationError("transcript resolution requires transcript_id or gene_id")
        query_id = transcript_id or gene_id or "unidentified"
        candidates = tuple(
            record
            for record in catalog.records
            if (
                transcript_id
                and (record.transcript_id == transcript_id or record.versioned_id == transcript_id)
                and (version is None or record.transcript_version == version)
            )
            or (gene_id and record.gene_id == gene_id)
        )
        if not candidates:
            state = ReferenceBetaState.ABSTAINED
            reason = "no exact transcript or gene identifier was found"
        elif transcript_id and len(candidates) == 1:
            state = ReferenceBetaState.SUPPORTED
            reason = "exact transcript identifier resolved"
        elif len(candidates) == 1:
            state = ReferenceBetaState.SUPPORTED
            reason = "exact gene identifier resolved to one transcript"
        else:
            state = ReferenceBetaState.AMBIGUOUS
            reason = "identifier resolves to multiple transcript records"
        body = {"query_id": query_id, "records": candidates, "state": state, "reason": reason}
        return TranscriptResolution(
            query_id=query_id,
            state=state,
            records=candidates,
            reason=reason,
            content_address=content_hash(body),
        )

    def _parse_rows(
        self,
        rows: Iterable[Mapping[str, Any]],
        source_id: str,
        source_version: str,
        assembly: str,
        text: str,
    ) -> TranscriptCatalog:
        records: list[TranscriptRecord] = []
        issues: list[ReferenceBetaIssue] = []
        for index, row in enumerate(rows, start=1):
            raw_hash = content_hash(dict(row))
            row_number = int(row.get("__line_number", index))
            try:
                attributes = dict(row.get("attributes", {}))
                transcript_value = _value(
                    row, "transcript_id", default=attributes.get("transcript_id")
                )
                gene_value = _value(row, "gene_id", default=attributes.get("gene_id"))
                transcript_id, transcript_version = _split_version(str(transcript_value))
                gene_id, _ = _split_version(str(gene_value))
                record = TranscriptRecord(
                    transcript_id=transcript_id,
                    transcript_version=transcript_version,
                    gene_id=gene_id,
                    gene_name=_optional_text(
                        _value(row, "gene_name", default=attributes.get("gene_name"))
                    ),
                    assembly=str(_value(row, "assembly", default=assembly)),
                    chromosome=normalize_chromosome(str(_value(row, "chromosome", "chrom"))),
                    start=int(_value(row, "start")),
                    end=int(_value(row, "end")),
                    strand=str(_value(row, "strand", default=".")),
                    biotype=str(
                        _value(
                            row,
                            "biotype",
                            "transcript_type",
                            default=attributes.get("transcript_type", "unknown"),
                        )
                    ),
                    source_id=source_id,
                    source_version=source_version,
                    raw_hash=raw_hash,
                    attributes=attributes
                    | {key: value for key, value in row.items() if not key.startswith("__")},
                )
                records.append(record)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ReferenceBetaIssue(
                        "invalid_gencode_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        body = {
            "source_id": source_id,
            "source_version": source_version,
            "assembly": assembly,
            "input_hash": content_hash(text),
            "records": tuple(records),
            "issues": tuple(issues),
        }
        return TranscriptCatalog(
            source_id=source_id,
            source_version=source_version,
            assembly=assembly,
            input_hash=content_hash(text),
            records=tuple(records),
            issues=tuple(issues),
            content_address=content_hash(body),
        )

    @staticmethod
    def _catalog(
        source_id: str,
        source_version: str,
        assembly: str,
        text: str,
        records: tuple[TranscriptRecord, ...],
        issues: tuple[ReferenceBetaIssue, ...],
    ) -> TranscriptCatalog:
        return TranscriptCatalog(
            source_id=source_id,
            source_version=source_version,
            assembly=assembly,
            input_hash=content_hash(text),
            records=records,
            issues=issues,
            content_address=content_hash(
                {
                    "source_id": source_id,
                    "source_version": source_version,
                    "assembly": assembly,
                    "input_hash": content_hash(text),
                    "records": records,
                    "issues": issues,
                }
            ),
        )

    @classmethod
    def _parse_attributes(cls, text: str) -> dict[str, str]:
        return {key: value for key, value in cls._attribute_pattern.findall(text)}


@dataclass(frozen=True, slots=True)
class ManeTranscriptRecord:
    """One MANE Select or MANE Plus Clinical transcript mapping."""

    transcript_id: str
    gene_id: str
    gene_name: str | None
    mane_status: str
    ensembl_transcript_id: str | None
    refseq_transcript_id: str | None
    assembly: str
    chromosome: str | None
    start: int | None
    end: int | None
    source_id: str
    source_version: str
    raw_hash: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "transcript_id",
            "gene_id",
            "mane_status",
            "assembly",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if self.start is not None and self.start < 1:
            raise ValidationError("MANE start must be positive")
        if self.end is not None and self.start is not None and self.end < self.start:
            raise ValidationError("MANE end must be at or after start")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ManeTranscriptCatalog:
    source_id: str
    source_version: str
    input_hash: str
    records: tuple[ManeTranscriptRecord, ...]
    issues: tuple[ReferenceBetaIssue, ...]
    content_address: str

    @property
    def state(self) -> ReferenceBetaState:
        if not self.records:
            return ReferenceBetaState.ABSTAINED
        return ReferenceBetaState.PARTIAL if self.issues else ReferenceBetaState.SUPPORTED

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"state": self.state.value}


@dataclass(frozen=True, slots=True)
class ManeTranscriptResolution:
    query_id: str
    state: ReferenceBetaState
    records: tuple[ManeTranscriptRecord, ...]
    reason: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ManeTranscriptAdapter:
    """Parse and resolve MANE transcript snapshots without preferred-row guessing."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
    ) -> ManeTranscriptCatalog:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("MANE transcript input must not be empty")
        selected = (input_format or "").lower().strip()
        if not selected:
            selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
        if selected == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                return self._catalog(
                    source_id,
                    source_version,
                    text,
                    (),
                    (
                        ReferenceBetaIssue(
                            "invalid_json", str(exc), content_hash(text), severity="error"
                        ),
                    ),
                )
            rows = (
                payload.get("records", payload.get("transcripts"))
                if isinstance(payload, Mapping)
                else payload
            )
            if not isinstance(rows, list):
                return self._catalog(
                    source_id,
                    source_version,
                    text,
                    (),
                    (
                        ReferenceBetaIssue(
                            "invalid_json_shape",
                            "MANE JSON must contain a records or transcripts list",
                            content_hash(payload),
                            severity="error",
                        ),
                    ),
                )
        elif selected in {"tsv", "csv"}:
            reader = csv.DictReader(io.StringIO(text), delimiter="\t" if selected == "tsv" else ",")
            if not reader.fieldnames:
                raise ValidationError("MANE delimited input requires a header")
            rows = list(reader)
        else:
            raise ValidationError(f"unsupported MANE input format: {selected}")
        records: list[ManeTranscriptRecord] = []
        issues: list[ReferenceBetaIssue] = []
        for row_number, row in enumerate(rows, start=1):
            raw_hash = content_hash(row)
            if not isinstance(row, Mapping):
                issues.append(
                    ReferenceBetaIssue(
                        "row_not_object",
                        "MANE row must be an object",
                        raw_hash,
                        row_number,
                        source_id=source_id,
                        severity="error",
                    )
                )
                continue
            try:
                start = _optional_int(_value(row, "start", "genomic_start"))
                end = _optional_int(_value(row, "end", "genomic_end"))
                chromosome = _value(row, "chromosome", "chrom", "contig")
                records.append(
                    ManeTranscriptRecord(
                        transcript_id=str(
                            _value(row, "transcript_id", "mane_transcript", "ensembl_transcript_id")
                        ),
                        gene_id=str(_value(row, "gene_id", "entrez_gene_id", "hgnc_id")),
                        gene_name=_optional_text(_value(row, "gene_name", "symbol")),
                        mane_status=str(
                            _value(
                                row, "mane_status", "mane_select", "status", default="unspecified"
                            )
                        ),
                        ensembl_transcript_id=_optional_text(
                            _value(row, "ensembl_transcript_id", "ensembl")
                        ),
                        refseq_transcript_id=_optional_text(
                            _value(row, "refseq_transcript_id", "refseq")
                        ),
                        assembly=str(
                            _value(row, "assembly", "genome_build", default="unspecified")
                        ),
                        chromosome=(normalize_chromosome(str(chromosome)) if chromosome else None),
                        start=start,
                        end=end,
                        source_id=source_id,
                        source_version=source_version,
                        raw_hash=raw_hash,
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ReferenceBetaIssue(
                        "invalid_mane_row",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row),
                    )
                )
        return self._catalog(source_id, source_version, text, tuple(records), tuple(issues))

    def resolve(
        self,
        catalog: ManeTranscriptCatalog,
        *,
        transcript_id: str | None = None,
        gene_id: str | None = None,
        mane_status: str | None = None,
    ) -> ManeTranscriptResolution:
        if not transcript_id and not gene_id:
            raise ValidationError("MANE resolution requires transcript_id or gene_id")
        query_id = transcript_id or gene_id or "unidentified"
        records = tuple(
            record
            for record in catalog.records
            if (
                transcript_id
                and transcript_id
                in {record.transcript_id, record.ensembl_transcript_id, record.refseq_transcript_id}
            )
            or (gene_id and record.gene_id == gene_id)
        )
        if mane_status:
            records = tuple(
                record
                for record in records
                if record.mane_status.casefold() == mane_status.casefold()
            )
        if not records:
            state = ReferenceBetaState.ABSTAINED
            reason = "no exact MANE identifier was found"
        elif len(records) == 1:
            state = ReferenceBetaState.SUPPORTED
            reason = "exact MANE record resolved"
        else:
            state = ReferenceBetaState.AMBIGUOUS
            reason = "identifier resolves to multiple MANE records"
        body = {"query_id": query_id, "records": records, "state": state}
        return ManeTranscriptResolution(query_id, state, records, reason, content_hash(body))

    @staticmethod
    def _catalog(
        source_id: str,
        source_version: str,
        text: str,
        records: tuple[ManeTranscriptRecord, ...],
        issues: tuple[ReferenceBetaIssue, ...],
    ) -> ManeTranscriptCatalog:
        body = {
            "source_id": source_id,
            "source_version": source_version,
            "input_hash": content_hash(text),
            "records": records,
            "issues": issues,
        }
        return ManeTranscriptCatalog(
            source_id=source_id,
            source_version=source_version,
            input_hash=content_hash(text),
            records=records,
            issues=issues,
            content_address=content_hash(body),
        )


@dataclass(frozen=True, slots=True)
class RegulatoryOntologyTerm:
    """One declared regulatory ontology term."""

    term_id: str
    label: str
    namespace: str
    definition: str
    parent_ids: tuple[str, ...]
    aliases: tuple[str, ...]
    source_id: str
    source_version: str
    raw_hash: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "term_id",
            "label",
            "namespace",
            "definition",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryOntologyCatalog:
    source_id: str
    source_version: str
    input_hash: str
    terms: tuple[RegulatoryOntologyTerm, ...]
    issues: tuple[ReferenceBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryTermMatch:
    term: RegulatoryOntologyTerm
    match_basis: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryNormalization:
    query_id: str
    state: ReferenceBetaState
    matches: tuple[RegulatoryTermMatch, ...]
    issues: tuple[ReferenceBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RegulatoryOntologyAdapter:
    """Parse declared regulatory terms and match only explicit identifiers."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
    ) -> RegulatoryOntologyCatalog:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("regulatory ontology input must not be empty")
        selected = (input_format or "").lower().strip()
        if not selected:
            selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
        if selected == "json":
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                return self._catalog(
                    source_id,
                    source_version,
                    text,
                    (),
                    (
                        ReferenceBetaIssue(
                            "invalid_json", str(exc), content_hash(text), severity="error"
                        ),
                    ),
                )
            rows = (
                payload.get("terms", payload.get("records"))
                if isinstance(payload, Mapping)
                else payload
            )
            if not isinstance(rows, list):
                return self._catalog(
                    source_id,
                    source_version,
                    text,
                    (),
                    (
                        ReferenceBetaIssue(
                            "invalid_json_shape",
                            "regulatory ontology JSON must contain a terms list",
                            content_hash(payload),
                            severity="error",
                        ),
                    ),
                )
        elif selected in {"tsv", "csv"}:
            reader = csv.DictReader(io.StringIO(text), delimiter="\t" if selected == "tsv" else ",")
            if not reader.fieldnames:
                raise ValidationError("regulatory ontology input requires a header")
            rows = list(reader)
        else:
            raise ValidationError(f"unsupported regulatory ontology format: {selected}")
        terms: list[RegulatoryOntologyTerm] = []
        issues: list[ReferenceBetaIssue] = []
        seen: set[str] = set()
        for row_number, row in enumerate(rows, start=1):
            raw_hash = content_hash(row)
            try:
                term_id = str(_value(row, "term_id", "id", "ontology_id"))
                if term_id in seen:
                    raise ValidationError(f"duplicate regulatory term ID: {term_id}")
                term = RegulatoryOntologyTerm(
                    term_id=term_id,
                    label=str(_value(row, "label", "name")),
                    namespace=str(_value(row, "namespace", "ontology", default="regulatory")),
                    definition=str(
                        _value(row, "definition", "description", default="declared term")
                    ),
                    parent_ids=_text_tuple(_value(row, "parent_ids", "parents", default=())),
                    aliases=_text_tuple(_value(row, "aliases", "synonyms", default=())),
                    source_id=source_id,
                    source_version=source_version,
                    raw_hash=raw_hash,
                    attributes=dict(row),
                )
                seen.add(term.term_id)
                terms.append(term)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ReferenceBetaIssue(
                        "invalid_regulatory_term",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row) if isinstance(row, Mapping) else {},
                    )
                )
        return self._catalog(source_id, source_version, text, tuple(terms), tuple(issues))

    def normalize(
        self,
        raw: Mapping[str, Any] | str,
        *,
        catalog: RegulatoryOntologyCatalog | None = None,
        terms: Iterable[RegulatoryOntologyTerm] = (),
    ) -> RegulatoryNormalization:
        payload = {"term_id": raw} if isinstance(raw, str) else dict(raw)
        query_id = str(_value(payload, "term_id", "id", "label", default="unidentified"))
        values = tuple(catalog.terms if catalog is not None else terms)
        query_values = _text_tuple(
            (
                _value(payload, "term_id", "id", default=""),
                _value(payload, "label", "name", default=""),
                _value(payload, "alias", "synonym", default=""),
            )
        )
        matches: list[RegulatoryTermMatch] = []
        for term in values:
            basis: list[str] = []
            identifiers = {item.casefold() for item in query_values}
            if term.term_id.casefold() in identifiers:
                basis.append("exact_term_id")
            if term.label.casefold() in identifiers or any(
                alias.casefold() in identifiers for alias in term.aliases
            ):
                basis.append("declared_label_or_alias")
            if basis:
                body = {"term_id": term.term_id, "basis": tuple(basis), "query": query_values}
                matches.append(
                    RegulatoryTermMatch(term, tuple(dict.fromkeys(basis)), content_hash(body))
                )
        if not matches:
            state = ReferenceBetaState.ABSTAINED
            issues = (
                ReferenceBetaIssue(
                    "term_not_resolved",
                    "no declared regulatory term matched the input",
                    content_hash(payload),
                    severity="warning",
                ),
            )
        elif len(matches) > 1:
            state = ReferenceBetaState.AMBIGUOUS
            issues = (
                ReferenceBetaIssue(
                    "term_match_ambiguous",
                    "multiple declared regulatory terms matched the input",
                    content_hash(payload),
                    severity="warning",
                ),
            )
        else:
            state = ReferenceBetaState.SUPPORTED
            issues = ()
        body = {"query_id": query_id, "matches": matches, "state": state, "issues": issues}
        return RegulatoryNormalization(
            query_id=query_id,
            state=state,
            matches=tuple(matches),
            issues=issues,
            warnings=(
                "Regulatory ontology matching uses only declared catalog identifiers and aliases.",
            ),
            content_address=content_hash(body),
        )

    @staticmethod
    def _catalog(
        source_id: str,
        source_version: str,
        text: str,
        terms: tuple[RegulatoryOntologyTerm, ...],
        issues: tuple[ReferenceBetaIssue, ...],
    ) -> RegulatoryOntologyCatalog:
        body = {
            "source_id": source_id,
            "source_version": source_version,
            "input_hash": content_hash(text),
            "terms": terms,
            "issues": issues,
        }
        return RegulatoryOntologyCatalog(
            source_id, source_version, content_hash(text), terms, issues, content_hash(body)
        )


@dataclass(frozen=True, slots=True)
class DiseaseOntologyMapping:
    """One source disease term and its declared target mapping."""

    source_term_id: str
    source_label: str
    target_term_id: str
    target_namespace: str
    target_label: str | None
    relationship: str
    source_id: str
    source_version: str
    raw_hash: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "source_term_id",
            "source_label",
            "target_term_id",
            "target_namespace",
            "relationship",
            "source_id",
            "source_version",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DiseaseOntologyCatalog:
    source_id: str
    source_version: str
    input_hash: str
    mappings: tuple[DiseaseOntologyMapping, ...]
    issues: tuple[ReferenceBetaIssue, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DiseaseMappingResult:
    query_id: str
    state: ReferenceBetaState
    mappings: tuple[DiseaseOntologyMapping, ...]
    issues: tuple[ReferenceBetaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class DiseaseOntologyMapper:
    """Map declared disease IDs/labels to explicit ontology targets."""

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        source_version: str = "unspecified",
        input_format: str | None = None,
    ) -> DiseaseOntologyCatalog:
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("disease ontology input must not be empty")
        selected = (input_format or "").lower().strip()
        if not selected:
            selected = "json" if text.lstrip().startswith(("{", "[")) else "tsv"
        if selected == "json":
            payload = json.loads(text)
            rows = (
                payload.get("mappings", payload.get("records"))
                if isinstance(payload, Mapping)
                else payload
            )
            if not isinstance(rows, list):
                raise ValidationError("disease ontology JSON must contain a mappings list")
        elif selected in {"tsv", "csv"}:
            reader = csv.DictReader(io.StringIO(text), delimiter="\t" if selected == "tsv" else ",")
            if not reader.fieldnames:
                raise ValidationError("disease ontology input requires a header")
            rows = list(reader)
        else:
            raise ValidationError(f"unsupported disease ontology format: {selected}")
        mappings: list[DiseaseOntologyMapping] = []
        issues: list[ReferenceBetaIssue] = []
        for row_number, row in enumerate(rows, start=1):
            raw_hash = content_hash(row)
            try:
                mappings.append(
                    DiseaseOntologyMapping(
                        source_term_id=str(_value(row, "source_term_id", "source_id_term", "id")),
                        source_label=str(_value(row, "source_label", "label", "name")),
                        target_term_id=str(
                            _value(row, "target_term_id", "target_id", "mondo_id", "doid")
                        ),
                        target_namespace=str(
                            _value(row, "target_namespace", "namespace", default="MONDO")
                        ),
                        target_label=_optional_text(_value(row, "target_label", "target_name")),
                        relationship=str(
                            _value(row, "relationship", "mapping_relation", default="exact")
                        ),
                        source_id=source_id,
                        source_version=source_version,
                        raw_hash=raw_hash,
                        attributes=dict(row),
                    )
                )
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    ReferenceBetaIssue(
                        "invalid_disease_mapping",
                        str(exc),
                        raw_hash,
                        row_number,
                        source_id=source_id,
                        severity="error",
                        raw_record=dict(row) if isinstance(row, Mapping) else {},
                    )
                )
        body = {
            "source_id": source_id,
            "source_version": source_version,
            "input_hash": content_hash(text),
            "mappings": tuple(mappings),
            "issues": tuple(issues),
        }
        return DiseaseOntologyCatalog(
            source_id,
            source_version,
            content_hash(text),
            tuple(mappings),
            tuple(issues),
            content_hash(body),
        )

    def map(
        self,
        raw: Mapping[str, Any] | str,
        *,
        catalog: DiseaseOntologyCatalog | None = None,
        mappings: Iterable[DiseaseOntologyMapping] = (),
    ) -> DiseaseMappingResult:
        payload = {"source_term_id": raw} if isinstance(raw, str) else dict(raw)
        query_id = str(
            _value(
                payload,
                "source_term_id",
                "term_id",
                "id",
                "source_label",
                "label",
                default="unidentified",
            )
        )
        source_id = str(_value(payload, "source_term_id", "term_id", "id", default=""))
        source_label = str(_value(payload, "source_label", "label", "name", default=""))
        values = tuple(catalog.mappings if catalog is not None else mappings)
        matches = tuple(
            mapping
            for mapping in values
            if (source_id and mapping.source_term_id.casefold() == source_id.casefold())
            or (source_label and mapping.source_label.casefold() == source_label.casefold())
        )
        if not matches:
            state = ReferenceBetaState.ABSTAINED
            issues = (
                ReferenceBetaIssue(
                    "disease_not_resolved",
                    "no declared disease ontology mapping matched the input",
                    content_hash(payload),
                    severity="warning",
                ),
            )
        elif len({(item.target_namespace, item.target_term_id) for item in matches}) > 1:
            state = ReferenceBetaState.AMBIGUOUS
            issues = (
                ReferenceBetaIssue(
                    "disease_mapping_ambiguous",
                    "multiple ontology targets remain for the disease input",
                    content_hash(payload),
                    severity="warning",
                ),
            )
        else:
            state = ReferenceBetaState.SUPPORTED
            issues = ()
        body = {"query_id": query_id, "matches": matches, "state": state, "issues": issues}
        return DiseaseMappingResult(
            query_id=query_id,
            state=state,
            mappings=matches,
            issues=issues,
            warnings=(
                "Disease ontology mapping is a declared identity mapping and not a diagnosis.",
            ),
            content_address=content_hash(body),
        )


def _value(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        value = row.get(name)
        if value is not None and value != "":
            return value
    return default


def _optional_text(value: Any) -> str | None:
    if value in {None, "", "."}:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value in {None, "", "."}:
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _split_version(value: str) -> tuple[str, str | None]:
    text = value.strip()
    if not text:
        return "", None
    if "." not in text:
        return text, None
    identifier, version = text.rsplit(".", 1)
    return identifier, version or None


def _text_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = value.replace(";", "|").replace(",", "|").split("|")
    elif isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, Mapping)):
        values = [str(item) for item in value]
    else:
        values = [str(value)]
    return tuple(dict.fromkeys(item.strip() for item in values if item.strip()))


__all__ = [
    "DiseaseMappingResult",
    "DiseaseOntologyCatalog",
    "DiseaseOntologyMapping",
    "DiseaseOntologyMapper",
    "GencodeTranscriptAdapter",
    "ManeTranscriptAdapter",
    "ManeTranscriptCatalog",
    "ManeTranscriptRecord",
    "ManeTranscriptResolution",
    "ReferenceBetaIssue",
    "ReferenceBetaState",
    "RegulatoryNormalization",
    "RegulatoryOntologyAdapter",
    "RegulatoryOntologyCatalog",
    "RegulatoryOntologyTerm",
    "RegulatoryTermMatch",
    "TranscriptCatalog",
    "TranscriptRecord",
    "TranscriptResolution",
]

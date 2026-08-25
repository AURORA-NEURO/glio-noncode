"""Bounded streaming intake for VCF, GVCF, raw BCF, and BGZF BCF.

The original intake adapter is intentionally convenient for small source
documents.  This module provides the complementary boundary for larger
variant streams: it consumes one text line or one compressed block at a time,
keeps only a bounded number of result rows, hashes the complete source as it
passes through, and makes every normalization decision explicit.

The implementation is dependency-free.  It is not a replacement for a
production-grade indexed variant store and it does not attempt to infer
reference equivalence without a supplied sequence digest.  It is a reliable
transport and review boundary that can be used before a more specialized
structural variant service is selected.
"""

from __future__ import annotations

import codecs
import hashlib
import re
import struct
import zlib
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

from .bcf import BcfReader, BcfRecord
from .errors import ValidationError
from .identity import normalize_chromosome
from .models import VariantIdentity, VariantKind
from .serialization import content_hash, hash_bytes, jsonable
from .variant_normalization import NormalizationState, VRSNormalizer


STREAMING_INTAKE_VERSION = "streaming-intake-v1"
STREAMING_DEFAULT_MAX_RECORDS = 1_000_000
STREAMING_DEFAULT_MAX_RETAINED_ROWS = 100_000
STREAMING_DEFAULT_MAX_ISSUES = 10_000
STREAMING_DEFAULT_MAX_HEADER_BYTES = 5_000_000
STREAMING_DEFAULT_MAX_RECORD_BYTES = 16_000_000
STREAMING_DEFAULT_MAX_BGZF_BLOCK_BYTES = 65_536
STREAMING_DEFAULT_MAX_INPUT_BYTES = 20_000_000_000


class StreamingInputFormat(StrEnum):
    """Encodings supported by the bounded reader."""

    VCF = "vcf"
    GVCF = "gvcf"
    BCF = "bcf"


class StreamingIssueSeverity(StrEnum):
    """Severity used for source and normalization issues."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class BreakendMate:
    """The coordinate and bracket orientation parsed from a VCF BND ALT."""

    chromosome: str
    position: int
    bracket: str
    local_side: str
    local_sequence: str
    remote_sequence: str
    orientation: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StreamingNormalizationReport:
    """A deterministic, row-level decision about canonicalization."""

    input_id: str
    input_hash: str
    state: NormalizationState
    normalization_kind: str
    variant: VariantIdentity | None
    candidate_count: int
    mate: BreakendMate | None
    warnings: tuple[str, ...]
    provenance: tuple[str, ...]
    content_address: str

    @property
    def deferred(self) -> bool:
        return self.state in {NormalizationState.ABSTAINED, NormalizationState.AMBIGUOUS} or (
            self.normalization_kind == "breakend-boundary"
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StreamingVariantRow:
    """One retained source row after normalization and provenance capture."""

    record_index: int
    record_id: str
    chromosome: str
    position: int
    reference: str
    alternate: str
    raw_hash: str
    info: Mapping[str, Any]
    sample_name: str | None
    sample_values: Mapping[str, Any]
    filter_value: str
    quality: str
    normalization: StreamingNormalizationReport
    variant: VariantIdentity | None
    deferred: bool
    duplicate: bool = False
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            body = {
                "record_index": self.record_index,
                "record_id": self.record_id,
                "chromosome": self.chromosome,
                "position": self.position,
                "reference": self.reference,
                "alternate": self.alternate,
                "raw_hash": self.raw_hash,
                "info": self.info,
                "sample_name": self.sample_name,
                "sample_values": self.sample_values,
                "filter_value": self.filter_value,
                "quality": self.quality,
                "normalization": self.normalization,
                "variant": self.variant,
                "deferred": self.deferred,
                "duplicate": self.duplicate,
            }
            object.__setattr__(self, "content_address", content_hash(body, prefix="stream-row"))

    @property
    def accepted(self) -> bool:
        return (
            not self.duplicate
            and not self.deferred
            and self.variant is not None
            and self.normalization.state is NormalizationState.SUPPORTED
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


@dataclass(frozen=True, slots=True)
class StreamingImportIssue:
    """A bounded issue record with enough source location for reinspection."""

    code: str
    severity: StreamingIssueSeverity
    message: str
    line_number: int | None = None
    record_index: int | None = None
    raw_hash: str | None = None
    remediation: str = "Inspect the source record and route or correct it explicitly."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class StreamingImportReport:
    """Deterministic aggregate receipt for one complete source traversal."""

    version: str
    source_id: str
    input_format: StreamingInputFormat
    input_hash: str
    header_hash: str
    record_count: int
    row_count: int
    accepted_count: int
    deferred_count: int
    invalid_count: int
    warning_count: int
    error_count: int
    duplicate_count: int
    truncated: bool
    retained_row_count: int
    omitted_row_count: int
    issue_count: int
    omitted_issue_count: int
    issue_counts: Mapping[str, int]
    issues: tuple[StreamingImportIssue, ...]
    rows: tuple[StreamingVariantRow, ...]
    max_records: int
    max_retained_rows: int
    max_issues: int
    compression_mode: str
    compressed_block_count: int
    content_address: str

    @property
    def accepted(self) -> bool:
        """True when the stream completed without a lossy or invalid outcome."""

        return not self.truncated and self.error_count == 0 and self.invalid_count == 0

    @property
    def requires_review(self) -> bool:
        return self.deferred_count > 0 or self.warning_count > 0

    @property
    def has_rows(self) -> bool:
        return bool(self.rows)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "accepted": self.accepted,
            "requires_review": self.requires_review,
            "has_rows": self.has_rows,
        }


@dataclass(frozen=True, slots=True)
class _BcfPayload:
    data: bytes
    mode: str


class BreakendNormalizer:
    """Parse bounded VCF breakend syntax without pretending it is VRS-linear."""

    _pattern = re.compile(
        r"^(?P<left>[ACGTNacgtn]*)"
        r"(?P<bracket>[\[\]])"
        r"(?P<chrom>[^:\[\]]+):(?P<position>[1-9][0-9]*)"
        r"(?P=bracket)"
        r"(?P<right>[ACGTNacgtn]*)$"
    )

    def normalize(
        self,
        *,
        chromosome: str,
        position: int,
        reference: str,
        alternate: str,
        genome_build: str,
        input_id: str,
        input_hash: str,
    ) -> StreamingNormalizationReport:
        """Return a structural boundary receipt for one BND ALT allele."""

        try:
            local_chromosome = normalize_chromosome(chromosome)
            if position < 1:
                raise ValidationError("breakend position must be positive")
            alt = alternate.strip().upper()
            match = self._pattern.fullmatch(alt)
            if match is None:
                raise ValidationError(
                    "breakend ALT must contain matching brackets around CHROM:POS"
                )
            groups = match.groupdict()
            mate_chromosome = normalize_chromosome(groups["chrom"])
            mate_position = int(groups["position"])
            left = groups["left"].upper()
            right = groups["right"].upper()
            if bool(left) == bool(right):
                raise ValidationError(
                    "breakend ALT must place the local sequence on exactly one bracket side"
                )
            local_side = "prefix" if left else "suffix"
            local_sequence = left or right
            remote_sequence = right if left else left
            orientation = (
                "remote-forward" if groups["bracket"] == "]" else "remote-reverse"
            )
            mate_body = {
                "chromosome": mate_chromosome,
                "position": mate_position,
                "bracket": groups["bracket"],
                "local_side": local_side,
                "local_sequence": local_sequence,
                "remote_sequence": remote_sequence,
                "orientation": orientation,
            }
            mate = BreakendMate(
                chromosome=mate_chromosome,
                position=mate_position,
                bracket=groups["bracket"],
                local_side=local_side,
                local_sequence=local_sequence,
                remote_sequence=remote_sequence,
                orientation=orientation,
                content_address=content_hash(mate_body, prefix="breakend-mate"),
            )
            reference_text = reference.strip().upper() or "N"
            if not re.fullmatch(r"[ACGTN]+", reference_text):
                raise ValidationError("breakend REF must contain only A/C/G/T/N bases")
            variant_id = (
                f"{genome_build}:{local_chromosome}:{position}:BND:"
                f"{mate_chromosome}:{mate_position}:{alt}"
            )
            variant = VariantIdentity(
                variant_id=variant_id,
                kind=VariantKind.BREAKEND,
                chromosome=local_chromosome,
                start=position,
                end=position,
                reference=reference_text,
                alternate=alt,
                genome_build=genome_build,
                annotations={
                    "mate_chromosome": mate_chromosome,
                    "mate_position": mate_position,
                    "bracket": groups["bracket"],
                    "local_side": local_side,
                    "orientation": orientation,
                    "normalization_boundary": "mate-coordinate-parsed",
                },
            )
            return _normalization_report(
                input_id=input_id,
                input_hash=input_hash,
                state=NormalizationState.SUPPORTED,
                normalization_kind="breakend-boundary",
                variant=variant,
                candidate_count=1,
                mate=mate,
                warnings=(
                    "breakend mate coordinates were parsed, but sequence-equivalent VRS "
                    "normalization remains deferred",
                ),
                provenance=(
                    "VCF bracket grammar validated",
                    "mate contig and one-based coordinate extracted",
                    "structural mate identity retained without linear flattening",
                ),
            )
        except (TypeError, ValueError, ValidationError) as exc:
            return _normalization_report(
                input_id=input_id,
                input_hash=input_hash,
                state=NormalizationState.INVALID,
                normalization_kind="breakend-boundary",
                variant=None,
                candidate_count=0,
                mate=None,
                warnings=(str(exc),),
                provenance=("breakend grammar validation failed",),
            )


def normalize_breakend(
    *,
    chromosome: str,
    position: int,
    reference: str,
    alternate: str,
    genome_build: str = "GRCh38",
    input_id: str = "breakend",
    input_hash: str | None = None,
) -> StreamingNormalizationReport:
    """Convenience boundary for API and CLI consumers."""

    digest = input_hash or content_hash(
        {
            "chromosome": chromosome,
            "position": position,
            "reference": reference,
            "alternate": alternate,
            "genome_build": genome_build,
            "input_id": input_id,
        }
    )
    return BreakendNormalizer().normalize(
        chromosome=chromosome,
        position=position,
        reference=reference,
        alternate=alternate,
        genome_build=genome_build,
        input_id=input_id,
        input_hash=digest,
    )


def _normalization_report(
    *,
    input_id: str,
    input_hash: str,
    state: NormalizationState,
    normalization_kind: str,
    variant: VariantIdentity | None,
    candidate_count: int,
    mate: BreakendMate | None,
    warnings: tuple[str, ...],
    provenance: tuple[str, ...],
) -> StreamingNormalizationReport:
    body = {
        "input_id": input_id,
        "input_hash": input_hash,
        "state": state,
        "normalization_kind": normalization_kind,
        "variant": variant,
        "candidate_count": candidate_count,
        "mate": mate,
        "warnings": warnings,
        "provenance": provenance,
    }
    return StreamingNormalizationReport(
        input_id=input_id,
        input_hash=input_hash,
        state=state,
        normalization_kind=normalization_kind,
        variant=variant,
        candidate_count=candidate_count,
        mate=mate,
        warnings=warnings,
        provenance=provenance,
        content_address=content_hash(body, prefix="stream-normalization"),
    )


def _linear_normalization(
    *,
    chromosome: str,
    position: int,
    reference: str,
    alternate: str,
    genome_build: str,
    input_id: str,
    input_hash: str,
) -> StreamingNormalizationReport:
    """Adapt the existing VRS-shaped normalizer into the stream contract."""

    normalizer = VRSNormalizer()
    report = normalizer.normalize(
        {
            "variant_id": input_id,
            "chromosome": chromosome,
            "position": position,
            "reference": reference,
            "alternate": alternate,
            "genome_build": genome_build,
        },
        genome_build=genome_build,
    )
    selected = next(
        (candidate.variant for candidate in report.candidates if candidate.variant.variant_id == report.selected_candidate_id),
        None,
    )
    return _normalization_report(
        input_id=input_id,
        input_hash=input_hash,
        state=report.state,
        normalization_kind="linear-vrs-shaped",
        variant=selected,
        candidate_count=len(report.candidates),
        mate=None,
        warnings=report.warnings,
        provenance=report.transformation_provenance,
    )


def _normalize_row(
    *,
    record_index: int,
    record_id: str,
    chromosome: str,
    position: int,
    reference: str,
    alternate: str,
    raw_hash: str,
    info: Mapping[str, Any],
    sample_name: str | None,
    sample_values: Mapping[str, Any],
    filter_value: str,
    quality: str,
    genome_build: str,
) -> StreamingVariantRow:
    input_id = record_id or f"stream:{record_index}"
    alt = alternate.strip().upper()
    if "[" in alt or "]" in alt:
        normalization = normalize_breakend(
            chromosome=chromosome,
            position=position,
            reference=reference,
            alternate=alt,
            genome_build=genome_build,
            input_id=input_id,
            input_hash=raw_hash,
        )
    elif alt.startswith("<") or alt.endswith(">") or alt == "*":
        normalization = _normalization_report(
            input_id=input_id,
            input_hash=raw_hash,
            state=NormalizationState.ABSTAINED,
            normalization_kind="symbolic-allele",
            variant=None,
            candidate_count=0,
            mate=None,
            warnings=(
                "symbolic or spanning-deletion ALT is retained as deferred structural input",
            ),
            provenance=("symbolic allele was not flattened into a linear identity",),
        )
    else:
        normalization = _linear_normalization(
            chromosome=chromosome,
            position=position,
            reference=reference,
            alternate=alt,
            genome_build=genome_build,
            input_id=input_id,
            input_hash=raw_hash,
        )
    return StreamingVariantRow(
        record_index=record_index,
        record_id=input_id,
        chromosome=chromosome,
        position=position,
        reference=reference,
        alternate=alt,
        raw_hash=raw_hash,
        info=dict(info),
        sample_name=sample_name,
        sample_values=dict(sample_values),
        filter_value=filter_value,
        quality=quality,
        normalization=normalization,
        variant=normalization.variant,
        deferred=normalization.deferred,
    )


def _parse_info(value: str) -> dict[str, Any]:
    if value in {"", "."}:
        return {}
    parsed: dict[str, Any] = {}
    for item in value.split(";"):
        if not item:
            continue
        if "=" not in item:
            parsed[item] = True
            continue
        key, raw = item.split("=", 1)
        if raw == ".":
            parsed[key] = None
        else:
            try:
                parsed[key] = int(raw)
            except ValueError:
                try:
                    parsed[key] = float(raw)
                except ValueError:
                    parsed[key] = raw
    return parsed


def _parse_sample(format_text: str, sample_text: str) -> dict[str, Any]:
    if format_text in {"", "."} or sample_text in {"", "."}:
        return {}
    keys = format_text.split(":")
    values = sample_text.split(":")
    result: dict[str, Any] = {}
    for index, key in enumerate(keys):
        raw = values[index] if index < len(values) else "."
        if key == "GT":
            result[key] = raw
        elif raw == ".":
            result[key] = None
        else:
            try:
                result[key] = int(raw)
            except ValueError:
                try:
                    result[key] = float(raw)
                except ValueError:
                    result[key] = raw
    return result


def _is_no_call(genotype: object) -> bool:
    return isinstance(genotype, str) and any(part == "." for part in re.split(r"[/|]", genotype))


def _is_reference_genotype(genotype: object) -> bool:
    if not isinstance(genotype, str) or not genotype:
        return False
    alleles = [part for part in re.split(r"[/|]", genotype) if part]
    return bool(alleles) and all(part == "0" for part in alleles)


class _StreamAccumulator:
    """Mutable state isolated to one importer call."""

    def __init__(
        self,
        *,
        source_id: str,
        input_format: StreamingInputFormat,
        genome_build: str,
        max_records: int,
        max_retained_rows: int,
        max_issues: int,
        on_row: Callable[[StreamingVariantRow], None] | None,
    ) -> None:
        self.source_id = source_id
        self.input_format = input_format
        self.genome_build = genome_build
        self.max_records = max_records
        self.max_retained_rows = max_retained_rows
        self.max_issues = max_issues
        self.on_row = on_row
        self.input_digest = hashlib.sha256()
        self.header_digest = hashlib.sha256()
        self.header_lines: list[str] = []
        self.header_bytes = 0
        self._header_limit_reported = False
        self.rows: list[StreamingVariantRow] = []
        self.issues: list[StreamingImportIssue] = []
        self.issue_counts: dict[str, int] = {}
        self.seen_keys: set[str] = set()
        self.record_count = 0
        self.row_count = 0
        self.accepted_count = 0
        self.deferred_count = 0
        self.invalid_count = 0
        self.warning_count = 0
        self.error_count = 0
        self.duplicate_count = 0
        self.omitted_row_count = 0
        self.omitted_issue_count = 0
        self.truncated = False
        self.compression_mode = "text"
        self.compressed_block_count = 0

    def add_bytes(self, value: bytes) -> None:
        self.input_digest.update(value)

    def add_header(self, line: str, *, line_number: int | None = None) -> None:
        encoded = line.encode("utf-8")
        self.header_bytes += len(encoded)
        self.header_digest.update(encoded)
        if self.header_bytes <= STREAMING_DEFAULT_MAX_HEADER_BYTES:
            self.header_lines.append(line)
        elif not self._header_limit_reported:
            self._header_limit_reported = True
            self.truncated = True
            self.issue(
                "header_size_exceeded",
                StreamingIssueSeverity.ERROR,
                f"header exceeds {STREAMING_DEFAULT_MAX_HEADER_BYTES} bytes",
                line_number=line_number,
                remediation="Use a bounded header or a source-specific header adapter.",
            )

    def note_record(self) -> bool:
        self.record_count += 1
        if self.record_count > self.max_records:
            if self.record_count == self.max_records + 1:
                self.issue(
                    "max_records_exceeded",
                    StreamingIssueSeverity.ERROR,
                    f"record ceiling of {self.max_records} was exceeded",
                    record_index=self.record_count,
                    remediation="Increase max_records only after reviewing resource capacity.",
                )
            self.truncated = True
            return False
        return True

    def issue(
        self,
        code: str,
        severity: StreamingIssueSeverity,
        message: str,
        *,
        line_number: int | None = None,
        record_index: int | None = None,
        raw_hash: str | None = None,
        remediation: str = "Inspect the source record and route or correct it explicitly.",
    ) -> None:
        self.issue_counts[code] = self.issue_counts.get(code, 0) + 1
        if severity is StreamingIssueSeverity.WARNING:
            self.warning_count += 1
        else:
            self.error_count += 1
        issue = StreamingImportIssue(
            code=code,
            severity=severity,
            message=message,
            line_number=line_number,
            record_index=record_index,
            raw_hash=raw_hash,
            remediation=remediation,
        )
        if len(self.issues) < self.max_issues:
            self.issues.append(issue)
        else:
            self.omitted_issue_count += 1

    def add_row(self, row: StreamingVariantRow, *, line_number: int | None = None) -> None:
        self.row_count += 1
        if row.normalization.state is NormalizationState.INVALID:
            self.invalid_count += 1
        if row.deferred:
            self.deferred_count += 1
        if row.variant is not None and not row.deferred:
            key = row.variant.canonical_key
            if key in self.seen_keys:
                self.duplicate_count += 1
                self.issue(
                    "duplicate_variant",
                    StreamingIssueSeverity.WARNING,
                    f"duplicate canonical variant ignored: {key}",
                    line_number=line_number,
                    record_index=row.record_index,
                    raw_hash=row.raw_hash,
                    remediation="Retain one source record or declare the replicate explicitly.",
                )
                row = replace(row, duplicate=True, content_address="")
            else:
                self.seen_keys.add(key)
        if row.accepted:
            self.accepted_count += 1
        for warning in row.normalization.warnings:
            self.issue(
                "normalization_warning",
                StreamingIssueSeverity.WARNING,
                warning,
                line_number=line_number,
                record_index=row.record_index,
                raw_hash=row.raw_hash,
            )
        if self.on_row is not None:
            self.on_row(row)
        if len(self.rows) < self.max_retained_rows:
            self.rows.append(row)
        else:
            self.omitted_row_count += 1
            self.truncated = True

    def finish(self) -> StreamingImportReport:
        report_body = {
            "version": STREAMING_INTAKE_VERSION,
            "source_id": self.source_id,
            "input_format": self.input_format,
            "input_hash": f"sha256:{self.input_digest.hexdigest()}",
            "header_hash": f"sha256:{self.header_digest.hexdigest()}",
            "record_count": self.record_count,
            "row_count": self.row_count,
            "accepted_count": self.accepted_count,
            "deferred_count": self.deferred_count,
            "invalid_count": self.invalid_count,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "duplicate_count": self.duplicate_count,
            "truncated": self.truncated,
            "retained_row_count": len(self.rows),
            "omitted_row_count": self.omitted_row_count,
            "issue_count": self.warning_count + self.error_count,
            "omitted_issue_count": self.omitted_issue_count,
            "issue_counts": self.issue_counts,
            "issues": self.issues,
            "rows": self.rows,
            "max_records": self.max_records,
            "max_retained_rows": self.max_retained_rows,
            "max_issues": self.max_issues,
            "compression_mode": self.compression_mode,
            "compressed_block_count": self.compressed_block_count,
        }
        address = content_hash(report_body, prefix="stream-intake")
        return StreamingImportReport(
            version=STREAMING_INTAKE_VERSION,
            source_id=self.source_id,
            input_format=self.input_format,
            input_hash=report_body["input_hash"],
            header_hash=report_body["header_hash"],
            record_count=self.record_count,
            row_count=self.row_count,
            accepted_count=self.accepted_count,
            deferred_count=self.deferred_count,
            invalid_count=self.invalid_count,
            warning_count=self.warning_count,
            error_count=self.error_count,
            duplicate_count=self.duplicate_count,
            truncated=self.truncated,
            retained_row_count=len(self.rows),
            omitted_row_count=self.omitted_row_count,
            issue_count=self.warning_count + self.error_count,
            omitted_issue_count=self.omitted_issue_count,
            issue_counts=dict(sorted(self.issue_counts.items())),
            issues=tuple(self.issues),
            rows=tuple(self.rows),
            max_records=self.max_records,
            max_retained_rows=self.max_retained_rows,
            max_issues=self.max_issues,
            compression_mode=self.compression_mode,
            compressed_block_count=self.compressed_block_count,
            content_address=address,
        )


def _validate_limits(
    *,
    max_records: int,
    max_retained_rows: int,
    max_issues: int,
) -> None:
    for name, value in (
        ("max_records", max_records),
        ("max_retained_rows", max_retained_rows),
        ("max_issues", max_issues),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValidationError(f"{name} must be a positive integer")


class StreamingVariantImporter:
    """Incrementally parse source rows into bounded deterministic receipts."""

    def __init__(self, *, default_build: str = "GRCh38") -> None:
        if not default_build.strip():
            raise ValidationError("default_build must not be empty")
        self.default_build = default_build

    def import_vcf(
        self,
        lines: Iterable[str],
        *,
        source_id: str,
        genome_build: str | None = None,
        sample_id: str | None = None,
        include_no_call: bool = False,
        include_reference: bool = False,
        input_format: StreamingInputFormat | str = StreamingInputFormat.VCF,
        max_records: int = STREAMING_DEFAULT_MAX_RECORDS,
        max_retained_rows: int = STREAMING_DEFAULT_MAX_RETAINED_ROWS,
        max_issues: int = STREAMING_DEFAULT_MAX_ISSUES,
        on_row: Callable[[StreamingVariantRow], None] | None = None,
    ) -> StreamingImportReport:
        """Consume a VCF iterator without materializing the source text."""

        if isinstance(lines, str):
            raise ValidationError("import_vcf requires an iterable of lines, not one whole text string")
        fmt = StreamingInputFormat(str(input_format))
        build = (genome_build or self.default_build).strip()
        if not source_id.strip() or not build:
            raise ValidationError("source_id and genome_build must not be empty")
        _validate_limits(
            max_records=max_records,
            max_retained_rows=max_retained_rows,
            max_issues=max_issues,
        )
        accumulator = _StreamAccumulator(
            source_id=source_id,
            input_format=fmt,
            genome_build=build,
            max_records=max_records,
            max_retained_rows=max_retained_rows,
            max_issues=max_issues,
            on_row=on_row,
        )
        header_columns: list[str] | None = None
        selected_sample_index: int | None = None
        saw_header = False
        for line_number, source_line in enumerate(lines, start=1):
            if not isinstance(source_line, str):
                raise ValidationError("VCF line iterables must yield strings")
            accumulator.add_bytes(source_line.encode("utf-8"))
            line = source_line.rstrip("\r\n")
            if not line.strip():
                continue
            if line.startswith("##"):
                accumulator.add_header(source_line, line_number=line_number)
                continue
            if line.startswith("#"):
                accumulator.add_header(source_line, line_number=line_number)
                if line.lower().startswith("#chrom"):
                    header_columns = line.lstrip("#").split("\t")
                    sample_columns = header_columns[9:]
                    if sample_id and sample_id in sample_columns:
                        selected_sample_index = sample_columns.index(sample_id)
                    elif sample_columns:
                        selected_sample_index = 0
                    saw_header = len(header_columns) >= 8
                continue
            raw_hash = hash_bytes(source_line.encode("utf-8"))
            record_index = accumulator.record_count + 1
            if not accumulator.note_record():
                continue
            if len(source_line.encode("utf-8")) > STREAMING_DEFAULT_MAX_RECORD_BYTES:
                accumulator.issue(
                    "record_size_exceeded",
                    StreamingIssueSeverity.ERROR,
                    f"VCF record exceeds {STREAMING_DEFAULT_MAX_RECORD_BYTES} bytes",
                    line_number=line_number,
                    record_index=record_index,
                    raw_hash=raw_hash,
                    remediation="Split the source or route large annotations through a specialized adapter.",
                )
                accumulator.truncated = True
                continue
            fields = line.split("\t")
            if len(fields) < 8:
                accumulator.issue(
                    "invalid_record",
                    StreamingIssueSeverity.ERROR,
                    "VCF record has fewer than eight required columns",
                    line_number=line_number,
                    record_index=record_index,
                    raw_hash=raw_hash,
                )
                continue
            if header_columns is None or not saw_header:
                accumulator.issue(
                    "missing_vcf_header",
                    StreamingIssueSeverity.ERROR,
                    "VCF data appeared before a valid #CHROM header",
                    line_number=line_number,
                    record_index=record_index,
                    raw_hash=raw_hash,
                    remediation="Provide a standards-compliant VCF header before data records.",
                )
                continue
            chromosome, position_text, record_id, reference, alternate_text, quality, filter_value, info_text = fields[:8]
            try:
                position = int(position_text)
                if position < 1:
                    raise ValueError("position must be positive")
            except ValueError as exc:
                accumulator.issue(
                    "invalid_coordinate",
                    StreamingIssueSeverity.ERROR,
                    f"invalid VCF position: {position_text!r} ({exc})",
                    line_number=line_number,
                    record_index=record_index,
                    raw_hash=raw_hash,
                )
                continue
            info = _parse_info(info_text)
            sample_name, sample_values = self._selected_sample(
                fields,
                header_columns,
                selected_sample_index,
                sample_id,
            )
            genotype = sample_values.get("GT")
            if _is_no_call(genotype) and not include_no_call:
                accumulator.issue(
                    "no_call_genotype",
                    StreamingIssueSeverity.WARNING,
                    "record skipped because the selected genotype is a no-call",
                    line_number=line_number,
                    record_index=record_index,
                    raw_hash=raw_hash,
                    remediation="Set include_no_call=True only when an uncalled observation is intended.",
                )
                continue
            if _is_reference_genotype(genotype) and not include_reference:
                accumulator.issue(
                    "reference_genotype",
                    StreamingIssueSeverity.WARNING,
                    "record skipped because the selected genotype is reference-only",
                    line_number=line_number,
                    record_index=record_index,
                    raw_hash=raw_hash,
                )
                continue
            alternates = alternate_text.split(",")
            if not alternates or any(not alternate for alternate in alternates):
                accumulator.issue(
                    "invalid_alternate",
                    StreamingIssueSeverity.ERROR,
                    "VCF ALT must contain at least one non-empty allele",
                    line_number=line_number,
                    record_index=record_index,
                    raw_hash=raw_hash,
                )
                continue
            for alternate_index, alternate in enumerate(alternates, start=1):
                normalized_id = record_id if record_id not in {"", "."} else f"{source_id}:{line_number}"
                if len(alternates) > 1:
                    normalized_id = f"{normalized_id}:alt{alternate_index}"
                row = _normalize_row(
                    record_index=record_index,
                    record_id=normalized_id,
                    chromosome=chromosome,
                    position=position,
                    reference=reference,
                    alternate=alternate,
                    raw_hash=raw_hash,
                    info=info,
                    sample_name=sample_name,
                    sample_values=sample_values,
                    filter_value=filter_value,
                    quality=quality,
                    genome_build=build,
                )
                accumulator.add_row(row, line_number=line_number)
        if header_columns is None:
            accumulator.issue(
                "missing_vcf_header",
                StreamingIssueSeverity.ERROR,
                "no #CHROM header was found",
                remediation="Provide a VCF header with at least eight required columns.",
            )
        return accumulator.finish()

    @staticmethod
    def _selected_sample(
        fields: list[str],
        header_columns: list[str],
        selected_index: int | None,
        requested_name: str | None,
    ) -> tuple[str | None, Mapping[str, Any]]:
        if len(fields) < 10 or len(header_columns) < 10 or selected_index is None:
            return None, {}
        sample_name = header_columns[9 + selected_index]
        sample_text = fields[9 + selected_index] if len(fields) > 9 + selected_index else "."
        return sample_name or requested_name, _parse_sample(fields[8], sample_text)

    def import_bcf(
        self,
        chunks: Iterable[bytes],
        *,
        source_id: str,
        genome_build: str | None = None,
        sample_id: str | None = None,
        include_no_call: bool = False,
        include_reference: bool = False,
        max_records: int = STREAMING_DEFAULT_MAX_RECORDS,
        max_retained_rows: int = STREAMING_DEFAULT_MAX_RETAINED_ROWS,
        max_issues: int = STREAMING_DEFAULT_MAX_ISSUES,
        on_row: Callable[[StreamingVariantRow], None] | None = None,
    ) -> StreamingImportReport:
        """Consume raw BCF or BGZF BCF chunks incrementally."""

        if isinstance(chunks, (bytes, bytearray, memoryview)):
            raise ValidationError("import_bcf requires an iterable of byte chunks")
        build = (genome_build or self.default_build).strip()
        if not source_id.strip() or not build:
            raise ValidationError("source_id and genome_build must not be empty")
        _validate_limits(
            max_records=max_records,
            max_retained_rows=max_retained_rows,
            max_issues=max_issues,
        )
        accumulator = _StreamAccumulator(
            source_id=source_id,
            input_format=StreamingInputFormat.BCF,
            genome_build=build,
            max_records=max_records,
            max_retained_rows=max_retained_rows,
            max_issues=max_issues,
            on_row=on_row,
        )
        decoder = _BcfStreamDecoder()
        record_index = 0
        for payload in _iter_bcf_payloads(chunks, accumulator):
            if decoder.compression_mode == "unknown":
                decoder.compression_mode = payload.mode
            for record in decoder.feed(payload.data):
                record_index = record.record_index + 1
                accumulator.record_count = record_index - 1
                if not accumulator.note_record():
                    continue
                self._add_bcf_record(
                    accumulator,
                    record,
                    build,
                    sample_id,
                    include_no_call,
                    include_reference,
                )
        decoder.finish()
        accumulator.header_lines.append(decoder.header_text)
        accumulator.header_digest.update(decoder.header_text.encode("utf-8"))
        accumulator.compression_mode = decoder.compression_mode
        return accumulator.finish()

    @staticmethod
    def _add_bcf_record(
        accumulator: _StreamAccumulator,
        record: BcfRecord,
        build: str,
        sample_id: str | None,
        include_no_call: bool,
        include_reference: bool,
    ) -> None:
        selected_name: str | None = None
        sample_values: Mapping[str, Any] = {}
        if record.samples:
            selected_name = sample_id if sample_id in record.samples else next(iter(record.samples))
            sample_values = record.samples[selected_name]
        genotype = sample_values.get("GT")
        if _is_no_call(genotype) and not include_no_call:
            accumulator.issue(
                "no_call_genotype",
                StreamingIssueSeverity.WARNING,
                "BCF record skipped because the selected genotype is a no-call",
                record_index=record.record_index + 1,
                raw_hash=record.raw_hash,
            )
            return
        if _is_reference_genotype(genotype) and not include_reference:
            accumulator.issue(
                "reference_genotype",
                StreamingIssueSeverity.WARNING,
                "BCF record skipped because the selected genotype is reference-only",
                record_index=record.record_index + 1,
                raw_hash=record.raw_hash,
            )
            return
        for alternate_index, alternate in enumerate(record.alternates, start=1):
            record_id = record.record_id
            if len(record.alternates) > 1:
                record_id = f"{record_id}:alt{alternate_index}"
            row = _normalize_row(
                record_index=record.record_index + 1,
                record_id=record_id,
                chromosome=record.chromosome,
                position=record.position,
                reference=record.reference,
                alternate=alternate,
                raw_hash=record.raw_hash,
                info=record.info,
                sample_name=selected_name,
                sample_values=sample_values,
                filter_value=";".join(record.filters),
                quality="." if record.quality is None else str(record.quality),
                genome_build=build,
            )
            accumulator.add_row(row, line_number=record.record_index + 1)


class _BcfStreamDecoder:
    """Incremental BCF framing and delegation to the typed record decoder."""

    def __init__(self) -> None:
        self.buffer = bytearray()
        self.reader = BcfReader()
        self.header: dict[str, Any] | None = None
        self.header_text = ""
        self.version = ""
        self.compression_mode = "unknown"
        self.compressed_block_count = 0
        self.record_index = 0

    def feed(self, data: bytes) -> Iterator[BcfRecord]:
        self.buffer.extend(data)
        if self.header is None:
            if len(self.buffer) < 9:
                return
            if bytes(self.buffer[:3]) != b"BCF" or self.buffer[3] != 2:
                raise ValidationError("unsupported BCF magic in stream")
            self.version = f"{self.buffer[3]}.{self.buffer[4]}"
            header_length = struct.unpack_from("<I", self.buffer, 5)[0]
            if header_length > STREAMING_DEFAULT_MAX_HEADER_BYTES:
                raise ValidationError("BCF header exceeds the bounded header ceiling")
            required = 9 + header_length
            if len(self.buffer) < required:
                return
            header_bytes = bytes(self.buffer[9:required])
            self.header_text = header_bytes.rstrip(b"\x00").decode("utf-8", errors="strict")
            self.header = self.reader._parse_header(self.header_text)
            del self.buffer[:required]
        while len(self.buffer) >= 8:
            shared_length, individual_length = struct.unpack_from("<II", self.buffer, 0)
            total = 8 + shared_length + individual_length
            if total > STREAMING_DEFAULT_MAX_RECORD_BYTES:
                raise ValidationError("BCF record exceeds the bounded record ceiling")
            if len(self.buffer) < total:
                return
            shared = bytes(self.buffer[8 : 8 + shared_length])
            individual = bytes(self.buffer[8 + shared_length : total])
            del self.buffer[:total]
            assert self.header is not None
            yield self.reader._record(self.record_index, shared, individual, self.header)
            self.record_index += 1

    def finish(self) -> None:
        if self.header is None:
            raise ValidationError("BCF stream ended before a complete header was received")
        if self.buffer and any(self.buffer):
            raise ValidationError("BCF stream ended with a non-zero truncated record trailer")


def _iter_bcf_payloads(
    chunks: Iterable[bytes],
    accumulator: _StreamAccumulator,
) -> Iterator[_BcfPayload]:
    """Frame raw BCF chunks or BGZF members while hashing source bytes."""

    pending = bytearray()
    mode: str | None = None
    for chunk in chunks:
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise ValidationError("BCF chunk iterables must yield bytes")
        raw = bytes(chunk)
        if not raw:
            continue
        accumulator.add_bytes(raw)
        pending.extend(raw)
        if mode is None:
            if len(pending) >= 3 and bytes(pending[:3]) == b"BCF":
                mode = "raw"
                accumulator.compression_mode = mode
            elif len(pending) >= 2 and bytes(pending[:2]) == b"\x1f\x8b":
                mode = "bgzf"
                accumulator.compression_mode = mode
            elif len(pending) >= 3:
                raise ValidationError("BCF input is neither raw BCF nor BGZF")
        if mode == "raw":
            payload = bytes(pending)
            pending.clear()
            yield _BcfPayload(payload, "raw")
            continue
        while mode == "bgzf":
            if len(pending) < 12:
                break
            if pending[:2] != b"\x1f\x8b" or pending[3] & 4 == 0:
                raise ValidationError("BGZF stream has an invalid member header")
            extra_length = struct.unpack_from("<H", pending, 10)[0]
            extra_end = 12 + extra_length
            if extra_end > STREAMING_DEFAULT_MAX_BGZF_BLOCK_BYTES:
                raise ValidationError("BGZF extra field exceeds the bounded block ceiling")
            if len(pending) < extra_end:
                break
            block_size: int | None = None
            cursor = 12
            while cursor + 4 <= extra_end:
                subfield = bytes(pending[cursor : cursor + 2])
                length = struct.unpack_from("<H", pending, cursor + 2)[0]
                value_end = cursor + 4 + length
                if value_end > extra_end:
                    raise ValidationError("invalid BGZF subfield length")
                if subfield == b"BC" and length == 2:
                    block_size = struct.unpack_from("<H", pending, cursor + 4)[0] + 1
                cursor = value_end
            if block_size is None:
                raise ValidationError("BGZF BC subfield is missing")
            if block_size > STREAMING_DEFAULT_MAX_BGZF_BLOCK_BYTES:
                raise ValidationError("BGZF member exceeds the bounded block ceiling")
            if len(pending) < block_size:
                break
            block = bytes(pending[:block_size])
            del pending[:block_size]
            try:
                payload = zlib.decompress(block, wbits=31)
            except zlib.error as exc:
                raise ValidationError(f"invalid BGZF compressed block: {exc}") from exc
            accumulator.compressed_block_count += 1
            yield _BcfPayload(payload, "bgzf")
    if mode == "bgzf" and pending:
        raise ValidationError("BCF stream ended with a truncated BGZF member")


def iter_text_lines_from_chunks(chunks: Iterable[bytes]) -> Iterator[str]:
    """Decode UTF-8 byte chunks into lines without joining the complete body."""

    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    pending = ""
    for chunk in chunks:
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise ValidationError("text chunk iterables must yield bytes")
        pending += decoder.decode(bytes(chunk), final=False)
        while True:
            newline = pending.find("\n")
            if newline < 0:
                break
            yield pending[: newline + 1]
            pending = pending[newline + 1 :]
    pending += decoder.decode(b"", final=True)
    if pending:
        yield pending


def streaming_intake_schema() -> dict[str, Any]:
    """Return the stable machine-readable stream contract."""

    return {
        "version": STREAMING_INTAKE_VERSION,
        "formats": [item.value for item in StreamingInputFormat],
        "normalization_states": [item.value for item in NormalizationState],
        "limits": {
            "default_max_records": STREAMING_DEFAULT_MAX_RECORDS,
            "default_max_retained_rows": STREAMING_DEFAULT_MAX_RETAINED_ROWS,
            "default_max_issues": STREAMING_DEFAULT_MAX_ISSUES,
            "max_header_bytes": STREAMING_DEFAULT_MAX_HEADER_BYTES,
            "max_record_bytes": STREAMING_DEFAULT_MAX_RECORD_BYTES,
            "max_bgzf_block_bytes": STREAMING_DEFAULT_MAX_BGZF_BLOCK_BYTES,
        },
        "report_fields": {
            "input_hash": "sha256 address of every source byte",
            "header_hash": "sha256 address of the retained header stream",
            "record_count": "source records traversed, including skipped records",
            "row_count": "variant rows produced after multiallelic decomposition",
            "accepted_count": "unique linear rows with supported normalization",
            "deferred_count": "symbolic or structural rows retained for a later service",
            "truncated": "true when a ceiling omitted records or result rows",
        },
        "row_fields": {
            "normalization": "explicit state, provenance, warnings, and optional mate",
            "raw_hash": "content address of the source row or BCF record payload",
            "duplicate": "true when a canonical duplicate was retained for audit only",
        },
        "streaming_guarantees": [
            "VCF text is consumed one line at a time",
            "BGZF BCF is decompressed one member at a time",
            "raw BCF is framed from byte chunks without a complete-body copy",
            "the complete source hash is accumulated while the stream is read",
            "retained rows and issues are independently bounded",
        ],
    }


def breakend_normalization_schema() -> dict[str, Any]:
    """Return the explicit breakend boundary contract."""

    return {
        "version": "breakend-normalization-v1",
        "grammar": "LOCAL[CHROM:POS[REMOTE or LOCAL]CHROM:POS]REMOTE",
        "states": [item.value for item in NormalizationState],
        "mate_fields": {
            "chromosome": "normalized mate contig",
            "position": "one-based mate coordinate",
            "bracket": "the VCF bracket token",
            "local_side": "prefix or suffix relative to the bracket pair",
            "orientation": "remote-forward or remote-reverse boundary label",
        },
        "limitations": [
            "a parsed mate is not a sequence-equivalent VRS allele",
            "paired breakend reconciliation remains deferred",
            "malformed bracket grammar is invalid rather than guessed",
        ],
    }


def streaming_intake_capabilities() -> dict[str, Any]:
    """Summarize operational behavior without source-specific data."""

    return {
        "version": STREAMING_INTAKE_VERSION,
        "formats": ["vcf", "gvcf", "bcf"],
        "compression": ["raw-bcf", "bgzf"],
        "multiallelic_policy": "one retained row per ALT with parent record hash",
        "genotype_policy": "no-call and reference-only rows are skipped by default",
        "symbolic_policy": "retained as explicit deferred rows",
        "breakend_policy": "mate coordinate parsed with structural normalization boundary",
        "determinism": "content-addressed report without wall-clock fields",
        "limits": streaming_intake_schema()["limits"],
    }


__all__ = [
    "BreakendMate",
    "BreakendNormalizer",
    "STREAMING_DEFAULT_MAX_ISSUES",
    "STREAMING_DEFAULT_MAX_RECORDS",
    "STREAMING_DEFAULT_MAX_RETAINED_ROWS",
    "STREAMING_INTAKE_VERSION",
    "StreamingImportIssue",
    "StreamingImportReport",
    "StreamingInputFormat",
    "StreamingIssueSeverity",
    "StreamingNormalizationReport",
    "StreamingVariantImporter",
    "StreamingVariantRow",
    "breakend_normalization_schema",
    "iter_text_lines_from_chunks",
    "normalize_breakend",
    "streaming_intake_capabilities",
    "streaming_intake_schema",
]

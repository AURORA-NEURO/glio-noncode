"""Canonical variant intake for VCF, TSV, and JSON source material.

Intake is deliberately conservative.  It preserves the source line, source
hash, INFO/sample fields, and a typed receipt.  Multiallelic records become
separate canonical identities.  No-call genotypes are not silently treated as
observed variants, and symbolic/breakend alleles are retained as explicit
unsupported records until structural reconstruction is available.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from itertools import islice
from math import isfinite
from typing import Any

from .bcf import BcfReader
from .errors import ValidationError
from .identity import normalize_chromosome, normalize_variant
from .models import CaseManifest, ReferenceContext, VariantIdentity
from .serialization import content_hash, jsonable, utc_now

# Keep the legacy in-memory parsers and index suitable for focused case-sized
# collections. Larger cohorts should use the independently bounded streaming
# and reference-index surfaces.
MAX_VARIANT_INTAKE_RECORDS = 100_000
MAX_VARIANT_INTAKE_AUXILIARY_LINES = 10_000
MAX_VARIANT_INDEX_RECORDS = MAX_VARIANT_INTAKE_RECORDS


class _StrictJsonError(ValueError):
    """Internal signal for JSON extensions that the scientific contract rejects."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _strict_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _StrictJsonError(
                "duplicate_json_key",
                f"JSON object contains duplicate key {key!r}",
            )
        value[key] = item
    return value


def _reject_non_finite_json(value: str) -> Any:
    raise _StrictJsonError(
        "non_finite_json_number",
        f"JSON number must be finite, received {value}",
    )


def _strict_json_float(value: str) -> float:
    parsed = float(value)
    if not isfinite(parsed):
        raise _StrictJsonError(
            "non_finite_json_number",
            f"JSON number must be finite, received {value}",
        )
    return parsed


class IntakeFormat(StrEnum):
    """Supported source encodings."""

    VCF = "vcf"
    GVCF = "gvcf"
    BCF = "bcf"
    TSV = "tsv"
    JSON = "json"


class IntakeSeverity(StrEnum):
    """Severity of an intake issue."""

    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class IntakeIssue:
    """A line-addressable intake problem that survives into the receipt."""

    code: str
    severity: IntakeSeverity
    message: str
    line_number: int | None = None
    raw_hash: str | None = None
    remediation: str = "Inspect the source record and correct or explicitly route it."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RawVariantRecord:
    """A normalized view of one source row before canonical acceptance."""

    record_id: str
    chromosome: str
    position: int
    reference: str
    alternate: str
    source_line: int
    raw_hash: str
    info: Mapping[str, Any] = field(default_factory=dict)
    sample: Mapping[str, Any] = field(default_factory=dict)
    filter_value: str = "."
    quality: str = "."

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class IntakeReceipt:
    """Immutable source accounting and content address."""

    source_id: str
    input_format: IntakeFormat
    input_hash: str
    header_hash: str
    created_at: str
    record_count: int
    accepted_count: int
    rejected_count: int
    warning_count: int
    error_count: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)

    def provenance_dict(self) -> dict[str, Any]:
        """Return the stable receipt projection suitable for scientific identity."""

        payload = self.to_dict()
        payload.pop("created_at", None)
        return payload


@dataclass(frozen=True, slots=True)
class IntakeBatch:
    """Canonical variants plus every issue needed for review and replay."""

    source_id: str
    input_format: IntakeFormat
    variants: tuple[VariantIdentity, ...]
    records: tuple[RawVariantRecord, ...]
    deferred_records: tuple[RawVariantRecord, ...]
    issues: tuple[IntakeIssue, ...]
    receipt: IntakeReceipt

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == IntakeSeverity.ERROR for issue in self.issues)

    @property
    def content_address(self) -> str:
        return content_hash(
            {
                "source_id": self.source_id,
                "input_format": self.input_format,
                "variants": self.variants,
                "issues": self.issues,
                "receipt": self.receipt.provenance_dict(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"content_address": self.content_address}

    def to_manifest(
        self,
        *,
        case_id: str,
        subject_id: str,
        context: ReferenceContext,
        metadata: Mapping[str, Any] | None = None,
    ) -> CaseManifest:
        """Build a normal case manifest while preserving intake provenance."""

        merged_metadata = dict(metadata or {})
        # ``created_at`` is operational provenance, not a property of the
        # scientific input.  Keeping it out of the manifest makes identical
        # source material resolve to the same manifest and run addresses.
        merged_metadata["intake_receipt"] = self.receipt.provenance_dict()
        merged_metadata["intake_content_address"] = self.content_address
        return CaseManifest(
            case_id=case_id,
            subject_id=subject_id,
            context=context,
            variants=self.variants,
            metadata=merged_metadata,
            input_versions={self.source_id: self.receipt.input_hash},
        )


class _BatchBuilder:
    """Mutable parser accumulator kept private to one parse call."""

    def __init__(
        self,
        source_id: str,
        input_format: IntakeFormat,
        max_records: int,
        max_auxiliary_lines: int,
    ) -> None:
        self.source_id = source_id
        self.input_format = input_format
        self.max_records = max_records
        self.max_auxiliary_lines = max_auxiliary_lines
        self.variants: list[VariantIdentity] = []
        self.records: list[RawVariantRecord] = []
        self.deferred_records: list[RawVariantRecord] = []
        self.issues: list[IntakeIssue] = []
        self._seen_keys: set[str] = set()
        self.record_count = 0
        self.auxiliary_line_count = 0
        self.auxiliary_limit_exceeded = False

    def note_record(
        self,
        *,
        line_number: int | None = None,
        raw_hash: str | None = None,
    ) -> bool:
        self.record_count += 1
        if self.record_count <= self.max_records:
            return True
        self.issue(
            "max_records_exceeded",
            IntakeSeverity.ERROR,
            f"variant intake record ceiling of {self.max_records} was exceeded",
            line_number=line_number,
            raw_hash=raw_hash,
            remediation=(
                "Split the source or use the bounded streaming intake surface after "
                "reviewing resource capacity."
            ),
        )
        return False

    def note_auxiliary_line(
        self,
        *,
        line_number: int,
        raw_hash: str,
    ) -> bool:
        self.auxiliary_line_count += 1
        if self.auxiliary_line_count <= self.max_auxiliary_lines:
            return True
        self.auxiliary_limit_exceeded = True
        self.issue(
            "max_auxiliary_lines_exceeded",
            IntakeSeverity.ERROR,
            f"variant intake auxiliary-line ceiling of {self.max_auxiliary_lines} was exceeded",
            line_number=line_number,
            raw_hash=raw_hash,
            remediation="Remove excessive blank/header lines or split the source.",
        )
        return False

    def issue(
        self,
        code: str,
        severity: IntakeSeverity,
        message: str,
        *,
        line_number: int | None = None,
        raw_hash: str | None = None,
        remediation: str = "Inspect the source record and correct or explicitly route it.",
    ) -> None:
        self.issues.append(IntakeIssue(code, severity, message, line_number, raw_hash, remediation))

    def accept(self, record: RawVariantRecord, variant: VariantIdentity) -> None:
        if variant.canonical_key in self._seen_keys:
            self.issue(
                "duplicate_variant",
                IntakeSeverity.WARNING,
                f"duplicate canonical variant ignored: {variant.canonical_key}",
                line_number=record.source_line,
                raw_hash=record.raw_hash,
                remediation=(
                    "Retain one source record or declare the duplicate as an intentional replicate."
                ),
            )
            return
        self._seen_keys.add(variant.canonical_key)
        self.records.append(record)
        self.variants.append(variant)

    def defer(self, record: RawVariantRecord) -> None:
        self.deferred_records.append(record)

    def finish(
        self,
        text: str,
        header_lines: Iterable[str],
        *,
        input_hash: str | None = None,
    ) -> IntakeBatch:
        warning_count = sum(issue.severity == IntakeSeverity.WARNING for issue in self.issues)
        error_count = sum(issue.severity == IntakeSeverity.ERROR for issue in self.issues)
        input_hash = input_hash or content_hash(text)
        header_hash = content_hash(tuple(header_lines))
        receipt_body = {
            "source_id": self.source_id,
            "input_format": self.input_format,
            "input_hash": input_hash,
            "header_hash": header_hash,
            "record_count": self.record_count,
            "accepted_count": len(self.variants),
            "rejected_count": error_count,
            "warning_count": warning_count,
            "error_count": error_count,
        }
        receipt = IntakeReceipt(
            source_id=self.source_id,
            input_format=self.input_format,
            input_hash=input_hash,
            header_hash=header_hash,
            created_at=utc_now().isoformat(),
            record_count=receipt_body["record_count"],
            accepted_count=len(self.variants),
            rejected_count=error_count,
            warning_count=warning_count,
            error_count=error_count,
            content_address=content_hash(receipt_body),
        )
        return IntakeBatch(
            source_id=self.source_id,
            input_format=self.input_format,
            variants=tuple(self.variants),
            records=tuple(self.records),
            deferred_records=tuple(self.deferred_records),
            issues=tuple(self.issues),
            receipt=receipt,
        )


class VariantIntake:
    """Parse bounded source encodings into canonical variant identities.

    ``max_records`` bounds source records, while ``max_auxiliary_lines`` bounds
    VCF/gVCF, TSV, and decoded BCF header/blank-line traversal.
    """

    def __init__(
        self,
        *,
        default_build: str = "GRCh38",
        max_records: int = MAX_VARIANT_INTAKE_RECORDS,
        max_auxiliary_lines: int = MAX_VARIANT_INTAKE_AUXILIARY_LINES,
    ) -> None:
        if not isinstance(default_build, str) or not default_build.strip():
            raise ValidationError("default_build must not be empty")
        if (
            isinstance(max_records, bool)
            or not isinstance(max_records, int)
            or not 1 <= max_records <= MAX_VARIANT_INTAKE_RECORDS
        ):
            raise ValidationError(
                "max_records must be an integer between 1 and "
                f"MAX_VARIANT_INTAKE_RECORDS ({MAX_VARIANT_INTAKE_RECORDS})"
            )
        if (
            isinstance(max_auxiliary_lines, bool)
            or not isinstance(max_auxiliary_lines, int)
            or not 1 <= max_auxiliary_lines <= MAX_VARIANT_INTAKE_AUXILIARY_LINES
        ):
            raise ValidationError(
                "max_auxiliary_lines must be an integer between 1 and "
                "MAX_VARIANT_INTAKE_AUXILIARY_LINES "
                f"({MAX_VARIANT_INTAKE_AUXILIARY_LINES})"
            )
        self.default_build = default_build
        self.max_records = max_records
        self.max_auxiliary_lines = max_auxiliary_lines

    def parse_text(
        self,
        text: str,
        *,
        source_id: str,
        input_format: IntakeFormat | str | None = None,
        genome_build: str | None = None,
        sample_id: str | None = None,
        include_no_call: bool = False,
    ) -> IntakeBatch:
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValidationError("source_id must not be empty")
        if not isinstance(text, str) or not text or text.isspace():
            raise ValidationError("intake text must not be empty")
        if genome_build is not None and (
            not isinstance(genome_build, str) or not genome_build.strip()
        ):
            raise ValidationError("genome_build must not be empty")
        if sample_id is not None and (
            not isinstance(sample_id, str) or not sample_id.strip()
        ):
            raise ValidationError("sample_id must not be empty")
        if type(include_no_call) is not bool:
            raise ValidationError("include_no_call must be a boolean")
        selected = self._select_format(text, input_format)
        build = self.default_build if genome_build is None else genome_build
        if selected == IntakeFormat.VCF:
            return self._parse_vcf(text, source_id, build, sample_id, include_no_call)
        if selected == IntakeFormat.GVCF:
            return self._parse_vcf(
                text,
                source_id,
                build,
                sample_id,
                include_no_call,
                input_format=IntakeFormat.GVCF,
            )
        if selected == IntakeFormat.BCF:
            raise ValidationError("BCF input is binary; call parse_bytes instead of parse_text")
        if selected == IntakeFormat.TSV:
            return self._parse_tsv(text, source_id, build, sample_id)
        return self._parse_json(text, source_id, build, sample_id)

    def parse_bytes(
        self,
        data: bytes,
        *,
        source_id: str,
        genome_build: str | None = None,
        sample_id: str | None = None,
        include_no_call: bool = False,
    ) -> IntakeBatch:
        """Decode a BCF2 byte stream and preserve the same intake contract."""

        if not isinstance(source_id, str) or not source_id.strip():
            raise ValidationError("source_id must not be empty")
        if genome_build is not None and (
            not isinstance(genome_build, str) or not genome_build.strip()
        ):
            raise ValidationError("genome_build must not be empty")
        if sample_id is not None and (
            not isinstance(sample_id, str) or not sample_id.strip()
        ):
            raise ValidationError("sample_id must not be empty")
        if type(include_no_call) is not bool:
            raise ValidationError("include_no_call must be a boolean")
        build = self.default_build if genome_build is None else genome_build
        # BcfReader's legacy contract returns a fully materialized document.
        # The checks below bound header retention and variant normalization;
        # callers needing bounded decode should use StreamingVariantImporter.
        document = BcfReader().read(data)
        builder = _BatchBuilder(
            source_id,
            IntakeFormat.BCF,
            self.max_records,
            self.max_auxiliary_lines,
        )
        header_lines: list[str] = []
        for line_number, source_line in enumerate(
            io.StringIO(document.header_text, newline=None),
            start=1,
        ):
            line = source_line.rstrip("\r\n")
            if not builder.note_auxiliary_line(
                line_number=line_number,
                raw_hash=content_hash(line),
            ):
                break
            header_lines.append(line)
        if builder.auxiliary_limit_exceeded:
            return builder.finish("", header_lines, input_hash=document.input_hash)
        for record in document.records:
            if not builder.note_record(
                line_number=record.record_index + 1,
                raw_hash=record.raw_hash,
            ):
                break
            sample: Mapping[str, Any] = {}
            if record.samples:
                selected_name = (
                    sample_id if sample_id in record.samples else next(iter(record.samples))
                )
                sample = dict(record.samples[selected_name]) | {"sample_id": selected_name}
            genotype = sample.get("GT")
            if genotype is not None and self._is_no_call(genotype) and not include_no_call:
                builder.issue(
                    "no_call_genotype",
                    IntakeSeverity.WARNING,
                    "BCF record skipped because the selected genotype is a no-call",
                    line_number=record.record_index + 1,
                    raw_hash=record.raw_hash,
                )
                continue
            if genotype is not None and not self._is_non_reference_genotype(genotype):
                builder.issue(
                    "reference_genotype",
                    IntakeSeverity.WARNING,
                    "BCF record skipped because the selected genotype is reference-only",
                    line_number=record.record_index + 1,
                    raw_hash=record.raw_hash,
                )
                continue
            for alternate_index, alternate in enumerate(record.alternates, start=1):
                record_id = record.record_id
                if len(record.alternates) > 1:
                    record_id = f"{record_id}:alt{alternate_index}"
                raw_record = RawVariantRecord(
                    record_id=record_id,
                    chromosome=record.chromosome,
                    position=record.position,
                    reference=record.reference,
                    alternate=alternate,
                    source_line=record.record_index + 1,
                    raw_hash=record.raw_hash,
                    info=dict(record.info),
                    sample=sample,
                    filter_value=";".join(record.filters),
                    quality="." if record.quality is None else str(record.quality),
                )
                self._add_record(builder, raw_record, build, source_id)
        return builder.finish("", header_lines, input_hash=document.input_hash)

    def _select_format(
        self,
        text: str,
        input_format: IntakeFormat | str | None,
    ) -> IntakeFormat:
        if input_format is not None:
            try:
                return IntakeFormat(str(input_format))
            except ValueError as exc:
                raise ValidationError(f"unsupported intake format: {input_format}") from exc
        first = ""
        blank_lines = 0
        for line in io.StringIO(text, newline=None):
            first = line.strip()
            if first:
                break
            blank_lines += 1
            if blank_lines > self.max_auxiliary_lines:
                raise ValidationError(
                    "max_auxiliary_lines_exceeded: format detection exceeded the "
                    f"auxiliary-line ceiling of {self.max_auxiliary_lines}"
                )
        if first.startswith("##fileformat=VCF") or first.startswith("#CHROM"):
            return IntakeFormat.VCF
        if first.startswith("{") or first.startswith("["):
            return IntakeFormat.JSON
        return IntakeFormat.TSV

    def _parse_vcf(
        self,
        text: str,
        source_id: str,
        build: str,
        sample_id: str | None,
        include_no_call: bool,
        *,
        input_format: IntakeFormat = IntakeFormat.VCF,
    ) -> IntakeBatch:
        builder = _BatchBuilder(
            source_id,
            input_format,
            self.max_records,
            self.max_auxiliary_lines,
        )
        header_lines: list[str] = []
        header_columns: list[str] | None = None
        selected_sample_index: int | None = None
        for line_number, source_line in enumerate(io.StringIO(text, newline=None), start=1):
            line = source_line.rstrip("\r\n")
            if not line.strip():
                if not builder.note_auxiliary_line(
                    line_number=line_number,
                    raw_hash=content_hash(line),
                ):
                    break
                continue
            if line.startswith("##"):
                if not builder.note_auxiliary_line(
                    line_number=line_number,
                    raw_hash=content_hash(line),
                ):
                    break
                header_lines.append(line)
                continue
            if line.startswith("#"):
                if not builder.note_auxiliary_line(
                    line_number=line_number,
                    raw_hash=content_hash(line),
                ):
                    break
                header_lines.append(line)
                if line.lower().startswith("#chrom"):
                    header_columns = line.lstrip("#").split("\t")
                    sample_columns = header_columns[9:]
                    if sample_id and sample_id in sample_columns:
                        selected_sample_index = sample_columns.index(sample_id)
                    elif sample_columns:
                        selected_sample_index = 0
                continue
            raw_hash = content_hash(line)
            if not builder.note_record(line_number=line_number, raw_hash=raw_hash):
                break
            fields = line.split("\t")
            if len(fields) < 8:
                builder.issue(
                    "invalid_record",
                    IntakeSeverity.ERROR,
                    "VCF record has fewer than eight required columns",
                    line_number=line_number,
                    raw_hash=raw_hash,
                )
                continue
            if header_columns is None:
                builder.issue(
                    "missing_vcf_header",
                    IntakeSeverity.ERROR,
                    "VCF data appeared before a #CHROM header",
                    line_number=line_number,
                    raw_hash=raw_hash,
                    remediation="Provide a standards-compliant VCF header before data records.",
                )
                continue
            (
                chromosome,
                position_text,
                record_id,
                reference,
                alternate_text,
                quality,
                filter_value,
                info_text,
            ) = fields[:8]
            try:
                position = int(position_text)
                if position < 1:
                    raise ValueError("position must be positive")
            except ValueError as exc:
                builder.issue(
                    "invalid_coordinate",
                    IntakeSeverity.ERROR,
                    f"invalid VCF position: {position_text!r} ({exc})",
                    line_number=line_number,
                    raw_hash=raw_hash,
                )
                continue
            info = self._parse_info(info_text)
            sample, selected_name = self._select_vcf_sample(
                fields, header_columns, selected_sample_index, sample_id
            )
            if selected_name:
                sample = dict(sample) | {"sample_id": selected_name}
            if sample and self._is_no_call(sample.get("GT")) and not include_no_call:
                builder.issue(
                    "no_call_genotype",
                    IntakeSeverity.WARNING,
                    "record skipped because the selected genotype is a no-call",
                    line_number=line_number,
                    raw_hash=raw_hash,
                    remediation=(
                        "Set include_no_call=True only when an uncalled observation "
                        "is intentionally retained."
                    ),
                )
                continue
            is_gvcf_reference_block = input_format == IntakeFormat.GVCF and (
                "<NON_REF>" in alternate_text or "END" in info
            )
            if (
                sample
                and not is_gvcf_reference_block
                and not self._is_non_reference_genotype(sample.get("GT"))
                and "GT" in sample
            ):
                builder.issue(
                    "reference_genotype",
                    IntakeSeverity.WARNING,
                    "record skipped because the selected genotype is reference-only",
                    line_number=line_number,
                    raw_hash=raw_hash,
                )
                continue
            alternates = alternate_text.split(",")
            if not alternates or any(not alternate for alternate in alternates):
                builder.issue(
                    "invalid_alternate",
                    IntakeSeverity.ERROR,
                    "VCF ALT must contain at least one non-empty allele",
                    line_number=line_number,
                    raw_hash=raw_hash,
                )
                continue
            for alternate_index, alternate in enumerate(alternates, start=1):
                record_name = (
                    record_id if record_id not in {"", "."} else f"{source_id}:{line_number}"
                )
                variant_id = (
                    record_name if len(alternates) == 1 else f"{record_name}:alt{alternate_index}"
                )
                record = RawVariantRecord(
                    record_id=variant_id,
                    chromosome=chromosome,
                    position=position,
                    reference=reference,
                    alternate=alternate,
                    source_line=line_number,
                    raw_hash=raw_hash,
                    info=info,
                    sample=sample,
                    filter_value=filter_value,
                    quality=quality,
                )
                if selected_name:
                    info = dict(info) | {"selected_sample": selected_name}
                    record = RawVariantRecord(**(record.to_dict() | {"info": info}))
                self._add_record(builder, record, build, source_id)
        if header_columns is None and not builder.auxiliary_limit_exceeded:
            builder.issue(
                "missing_vcf_header",
                IntakeSeverity.ERROR,
                "no #CHROM header was found",
                remediation="Provide a VCF header with at least the eight required columns.",
            )
        return builder.finish(text, header_lines)

    def _parse_tsv(
        self, text: str, source_id: str, build: str, sample_id: str | None
    ) -> IntakeBatch:
        builder = _BatchBuilder(
            source_id,
            IntakeFormat.TSV,
            self.max_records,
            self.max_auxiliary_lines,
        )
        source_line_numbers: list[int] = []
        first_content_line = True

        def bounded_lines() -> Iterable[str]:
            nonlocal first_content_line
            for line_number, source_line in enumerate(
                io.StringIO(text, newline=None),
                start=1,
            ):
                line = source_line.rstrip("\r\n")
                if not line.strip():
                    if not builder.note_auxiliary_line(
                        line_number=line_number,
                        raw_hash=content_hash(line),
                    ):
                        return
                    continue
                if first_content_line:
                    first_content_line = False
                    if not builder.note_auxiliary_line(
                        line_number=line_number,
                        raw_hash=content_hash(line),
                    ):
                        return
                source_line_numbers.append(line_number)
                yield source_line

        reader = csv.DictReader(bounded_lines(), delimiter="\t")
        if not reader.fieldnames:
            if builder.auxiliary_limit_exceeded:
                return builder.finish(text, ())
            builder.issue("missing_tsv_header", IntakeSeverity.ERROR, "TSV input has no header")
            return builder.finish(text, ())
        header_lines = ["\t".join(reader.fieldnames)]
        aliases = self._column_aliases(reader.fieldnames)
        required = {"chromosome", "position", "reference", "alternate"}
        missing = required - set(aliases)
        if missing:
            builder.issue(
                "missing_tsv_columns",
                IntakeSeverity.ERROR,
                f"TSV is missing required columns: {sorted(missing)}",
                remediation="Provide chromosome, position, reference, and alternate columns.",
            )
            return builder.finish(text, header_lines)
        for row in reader:
            line_number = source_line_numbers[reader.line_num - 1]
            raw_line = "\t".join(str(row.get(key, "")) for key in reader.fieldnames)
            raw_hash = content_hash(raw_line)
            if not builder.note_record(line_number=line_number, raw_hash=raw_hash):
                break
            try:
                chromosome = str(row[aliases["chromosome"]])
                position = int(str(row[aliases["position"]]))
                reference = str(row[aliases["reference"]])
                alternate = str(row[aliases["alternate"]])
            except (KeyError, TypeError, ValueError) as exc:
                builder.issue(
                    "invalid_record",
                    IntakeSeverity.ERROR,
                    f"invalid TSV variant row: {exc}",
                    line_number=line_number,
                    raw_hash=raw_hash,
                )
                continue
            record_id = (
                str(row.get(aliases.get("variant_id", ""), "")) or f"{source_id}:{line_number}"
            )
            record = RawVariantRecord(
                record_id=record_id,
                chromosome=chromosome,
                position=position,
                reference=reference,
                alternate=alternate,
                source_line=line_number,
                raw_hash=raw_hash,
                info={
                    str(key): value
                    for key, value in row.items()
                    if key
                    not in {
                        aliases[name]
                        for name in aliases
                        if name
                        in {"chromosome", "position", "reference", "alternate", "variant_id"}
                    }
                },
                sample={
                    "sample_id": sample_id or row.get(aliases.get("sample_id", ""), "unspecified")
                },
            )
            self._add_record(
                builder, record, str(row.get(aliases.get("genome_build", ""), build)), source_id
            )
        return builder.finish(text, header_lines)

    def _parse_json(
        self, text: str, source_id: str, build: str, sample_id: str | None
    ) -> IntakeBatch:
        builder = _BatchBuilder(
            source_id,
            IntakeFormat.JSON,
            self.max_records,
            self.max_auxiliary_lines,
        )
        try:
            payload = json.loads(
                text,
                object_pairs_hook=_strict_json_object,
                parse_constant=_reject_non_finite_json,
                parse_float=_strict_json_float,
            )
        except _StrictJsonError as exc:
            builder.issue(
                exc.code,
                IntakeSeverity.ERROR,
                str(exc),
                remediation="Provide strict JSON with unique keys and finite numbers.",
            )
            return builder.finish(text, ())
        except json.JSONDecodeError as exc:
            builder.issue("invalid_json", IntakeSeverity.ERROR, str(exc))
            return builder.finish(text, ())
        rows: object
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, Mapping) and isinstance(payload.get("variants"), list):
            rows = payload["variants"]
        else:
            builder.issue(
                "invalid_json_shape",
                IntakeSeverity.ERROR,
                "JSON intake must be a list or an object with a variants list",
            )
            return builder.finish(text, ())
        assert isinstance(rows, list)
        for index, raw in enumerate(islice(rows, self.max_records + 1), start=1):
            raw_hash = content_hash(raw)
            if not builder.note_record(line_number=index, raw_hash=raw_hash):
                break
            if not isinstance(raw, Mapping):
                builder.issue(
                    "invalid_json_variant",
                    IntakeSeverity.ERROR,
                    "JSON variant must be an object",
                    line_number=index,
                )
                continue
            if raw.get("notation"):
                try:
                    variant = normalize_variant(raw, default_build=build)
                    record = RawVariantRecord(
                        record_id=variant.variant_id,
                        chromosome=variant.chromosome,
                        position=variant.start,
                        reference=variant.reference,
                        alternate=variant.alternate,
                        source_line=index,
                        raw_hash=raw_hash,
                        info=dict(raw.get("annotations", {})),
                        sample={"sample_id": variant.sample_id},
                    )
                    builder.accept(record, variant)
                except (ValidationError, ValueError, TypeError) as exc:
                    builder.issue(
                        "invalid_json_variant",
                        IntakeSeverity.ERROR,
                        f"invalid JSON notation: {exc}",
                        line_number=index,
                        raw_hash=raw_hash,
                    )
                continue
            try:
                chromosome = str(raw.get("chromosome", raw.get("chrom", "")))
                position = int(raw.get("position", raw.get("pos", raw.get("start", 0))))
                reference = str(raw.get("reference", raw.get("ref", "")))
                alternate = str(raw.get("alternate", raw.get("alt", "")))
                record = RawVariantRecord(
                    record_id=str(raw.get("variant_id", raw.get("id", f"{source_id}:{index}"))),
                    chromosome=chromosome,
                    position=position,
                    reference=reference,
                    alternate=alternate,
                    source_line=index,
                    raw_hash=raw_hash,
                    info=dict(raw.get("annotations", {})),
                    sample={"sample_id": str(raw.get("sample_id", sample_id or "unspecified"))},
                )
            except (TypeError, ValueError) as exc:
                builder.issue(
                    "invalid_json_variant",
                    IntakeSeverity.ERROR,
                    f"invalid JSON variant: {exc}",
                    line_number=index,
                    raw_hash=raw_hash,
                )
                continue
            self._add_record(builder, record, str(raw.get("genome_build", build)), source_id)
        return builder.finish(text, ("json",))

    def _add_record(
        self,
        builder: _BatchBuilder,
        record: RawVariantRecord,
        build: str,
        source_id: str,
    ) -> None:
        alternate = record.alternate.strip()
        if alternate.startswith("<") or any(marker in alternate for marker in "[]"):
            builder.defer(record)
            builder.issue(
                "unsupported_symbolic_allele",
                IntakeSeverity.WARNING,
                f"symbolic or breakend allele deferred: {alternate}",
                line_number=record.source_line,
                raw_hash=record.raw_hash,
                remediation=(
                    "Route the record to structural reconstruction; it is not "
                    "treated as an SNV or indel."
                ),
            )
            return
        try:
            variant = normalize_variant(
                {
                    "notation": (
                        f"{record.chromosome}:{record.position}:{record.reference}>{alternate}"
                    ),
                    "genome_build": build,
                    "variant_id": record.record_id,
                    "sample_id": str(record.sample.get("sample_id", "unspecified")),
                    "annotations": {
                        "source_id": source_id,
                        "source_line": record.source_line,
                        "raw_hash": record.raw_hash,
                        "info": dict(record.info),
                        "sample": dict(record.sample),
                        "filter": record.filter_value,
                        "quality": record.quality,
                    },
                }
            )
        except (ValidationError, ValueError) as exc:
            builder.issue(
                "invalid_variant",
                IntakeSeverity.ERROR,
                f"variant could not be normalized: {exc}",
                line_number=record.source_line,
                raw_hash=record.raw_hash,
                remediation=(
                    "Correct chromosome and allele syntax or route the record "
                    "to structural handling."
                ),
            )
            return
        builder.accept(record, variant)

    @staticmethod
    def _parse_info(value: str) -> dict[str, Any]:
        if value in {"", "."}:
            return {}
        result: dict[str, Any] = {}
        for item in value.split(";"):
            if not item:
                continue
            if "=" not in item:
                result[item] = True
                continue
            key, raw_value = item.split("=", 1)
            values = raw_value.split(",") if "," in raw_value else raw_value
            result[key] = values
        return result

    @staticmethod
    def _select_vcf_sample(
        fields: list[str],
        header_columns: list[str],
        selected_sample_index: int | None,
        requested_sample_id: str | None,
    ) -> tuple[dict[str, Any], str | None]:
        if len(fields) < 10 or len(header_columns) < 10:
            return {}, requested_sample_id
        format_keys = fields[8].split(":")
        sample_index = selected_sample_index or 0
        field_index = 9 + sample_index
        if field_index >= len(fields):
            return {}, requested_sample_id
        values = fields[field_index].split(":")
        return dict(zip(format_keys, values, strict=False)), header_columns[field_index]

    @staticmethod
    def _is_no_call(genotype: object) -> bool:
        return isinstance(genotype, str) and (genotype in {".", "./.", ".|."} or "." in genotype)

    @classmethod
    def _is_non_reference_genotype(cls, genotype: object) -> bool:
        if not isinstance(genotype, str) or cls._is_no_call(genotype):
            return False
        alleles = genotype.replace("|", "/").split("/")
        return any(allele not in {"0", "."} for allele in alleles)

    @staticmethod
    def _column_aliases(fieldnames: list[str]) -> dict[str, str]:
        normalized = {name.strip().lower(): name for name in fieldnames if name}
        aliases: dict[str, str] = {}
        for canonical, names in {
            "chromosome": ("chromosome", "chrom", "chr"),
            "position": ("position", "pos", "start"),
            "reference": ("reference", "ref"),
            "alternate": ("alternate", "alt"),
            "variant_id": ("variant_id", "id", "name"),
            "genome_build": ("genome_build", "build", "assembly"),
            "sample_id": ("sample_id", "sample", "subject_id"),
        }.items():
            for name in names:
                if name in normalized:
                    aliases[canonical] = normalized[name]
                    break
        return aliases


class VariantIndex:
    """Deterministic, bounded interval index for accepted canonical variants."""

    def __init__(
        self,
        variants: Iterable[VariantIdentity],
        *,
        max_records: int = MAX_VARIANT_INDEX_RECORDS,
    ) -> None:
        if (
            isinstance(max_records, bool)
            or not isinstance(max_records, int)
            or not 1 <= max_records <= MAX_VARIANT_INDEX_RECORDS
        ):
            raise ValidationError(
                "max_records must be an integer between 1 and "
                f"MAX_VARIANT_INDEX_RECORDS ({MAX_VARIANT_INDEX_RECORDS})"
            )
        if isinstance(variants, (str, bytes, bytearray, Mapping)):
            raise ValidationError("variants must be an iterable of VariantIdentity objects")
        try:
            values = tuple(islice(iter(variants), max_records + 1))
        except TypeError as exc:
            raise ValidationError("variants must be iterable") from exc
        if len(values) > max_records:
            raise ValidationError(
                "variant_index_record_limit_exceeded: "
                f"variant index record ceiling of {max_records} was exceeded"
            )
        if any(not isinstance(variant, VariantIdentity) for variant in values):
            raise ValidationError("variants must contain only VariantIdentity objects")
        if len({variant.variant_id for variant in values}) != len(values):
            raise ValidationError("variant index requires unique variant IDs")
        self._variants = tuple(
            sorted(
                values, key=lambda item: (item.chromosome, item.start, item.end, item.variant_id)
            )
        )
        self._by_id = {variant.variant_id: variant for variant in self._variants}

    def get(self, variant_id: str) -> VariantIdentity:
        try:
            return self._by_id[variant_id]
        except KeyError as exc:
            raise ValidationError(f"variant not found: {variant_id}") from exc

    def overlap(self, chromosome: str, start: int, end: int) -> tuple[VariantIdentity, ...]:
        if start < 1 or end < start:
            raise ValidationError("query interval must satisfy 1 <= start <= end")
        normalized = normalize_chromosome(chromosome)
        return tuple(
            variant
            for variant in self._variants
            if variant.chromosome == normalized and variant.start <= end and variant.end >= start
        )

    def all(self) -> tuple[VariantIdentity, ...]:
        return self._variants

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self._variants),
            "variants": [variant.to_dict() for variant in self._variants],
            "content_address": content_hash(self._variants),
        }

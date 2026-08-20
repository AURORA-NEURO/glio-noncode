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
from typing import Any

from .errors import ValidationError
from .identity import normalize_chromosome, normalize_variant
from .models import CaseManifest, ReferenceContext, VariantIdentity
from .serialization import content_hash, jsonable, utc_now


class IntakeFormat(StrEnum):
    """Supported source encodings."""

    VCF = "vcf"
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
                "receipt": self.receipt,
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
        merged_metadata["intake_receipt"] = self.receipt.to_dict()
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

    def __init__(self, source_id: str, input_format: IntakeFormat) -> None:
        self.source_id = source_id
        self.input_format = input_format
        self.variants: list[VariantIdentity] = []
        self.records: list[RawVariantRecord] = []
        self.deferred_records: list[RawVariantRecord] = []
        self.issues: list[IntakeIssue] = []
        self._seen_keys: set[str] = set()
        self.record_count = 0

    def note_record(self) -> None:
        self.record_count += 1

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

    def finish(self, text: str, header_lines: Iterable[str]) -> IntakeBatch:
        warning_count = sum(issue.severity == IntakeSeverity.WARNING for issue in self.issues)
        error_count = sum(issue.severity == IntakeSeverity.ERROR for issue in self.issues)
        input_hash = content_hash(text)
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
    """Parse bounded source encodings into canonical variant identities."""

    def __init__(self, *, default_build: str = "GRCh38") -> None:
        if not default_build.strip():
            raise ValidationError("default_build must not be empty")
        self.default_build = default_build

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
        if not source_id.strip():
            raise ValidationError("source_id must not be empty")
        if not isinstance(text, str) or not text.strip():
            raise ValidationError("intake text must not be empty")
        selected = self._select_format(text, input_format)
        build = genome_build or self.default_build
        if not build.strip():
            raise ValidationError("genome_build must not be empty")
        if selected == IntakeFormat.VCF:
            return self._parse_vcf(text, source_id, build, sample_id, include_no_call)
        if selected == IntakeFormat.TSV:
            return self._parse_tsv(text, source_id, build, sample_id)
        return self._parse_json(text, source_id, build, sample_id)

    @staticmethod
    def _select_format(text: str, input_format: IntakeFormat | str | None) -> IntakeFormat:
        if input_format is not None:
            try:
                return IntakeFormat(str(input_format))
            except ValueError as exc:
                raise ValidationError(f"unsupported intake format: {input_format}") from exc
        first = next((line.strip() for line in text.splitlines() if line.strip()), "")
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
    ) -> IntakeBatch:
        builder = _BatchBuilder(source_id, IntakeFormat.VCF)
        header_lines: list[str] = []
        header_columns: list[str] | None = None
        selected_sample_index: int | None = None
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            if line.startswith("##"):
                header_lines.append(line)
                continue
            if line.startswith("#"):
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
            builder.note_record()
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
            if sample and not self._is_non_reference_genotype(sample.get("GT")) and "GT" in sample:
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
        if header_columns is None:
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
        builder = _BatchBuilder(source_id, IntakeFormat.TSV)
        reader = csv.DictReader(io.StringIO(text), delimiter="\t")
        if not reader.fieldnames:
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
        for line_number, row in enumerate(reader, start=2):
            builder.note_record()
            raw_line = "\t".join(str(row.get(key, "")) for key in reader.fieldnames)
            raw_hash = content_hash(raw_line)
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
        builder = _BatchBuilder(source_id, IntakeFormat.JSON)
        try:
            payload = json.loads(text)
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
        for index, raw in enumerate(rows, start=1):
            builder.note_record()
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
                        raw_hash=content_hash(raw),
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
                        raw_hash=content_hash(raw),
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
                    raw_hash=content_hash(raw),
                    info=dict(raw.get("annotations", {})),
                    sample={"sample_id": str(raw.get("sample_id", sample_id or "unspecified"))},
                )
            except (TypeError, ValueError) as exc:
                builder.issue(
                    "invalid_json_variant",
                    IntakeSeverity.ERROR,
                    f"invalid JSON variant: {exc}",
                    line_number=index,
                    raw_hash=content_hash(raw),
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
    """Deterministic interval index for accepted canonical variants."""

    def __init__(self, variants: Iterable[VariantIdentity]) -> None:
        values = tuple(variants)
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

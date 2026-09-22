"""Canonical variant and reference-block intake for VCF/gVCF, BCF, TSV, and JSON.

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
from bisect import bisect_left
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
from .serialization import content_hash, freeze_json, jsonable, utc_now
from .variant_genotype import (
    FormatFieldDefinition,
    InfoFieldDefinition,
    called_alternate_indices,
    format_key_issue,
    has_duplicate_sample_ids,
    parse_info_fields,
    register_format_definition,
    register_info_definition,
    sample_format_values,
    sample_value_issue,
    validate_format_values,
    validate_info_values,
)

# Keep the legacy in-memory parsers and index suitable for focused case-sized
# collections. Larger cohorts should use the independently bounded streaming
# and reference-index surfaces.
MAX_VARIANT_INTAKE_RECORDS = 100_000
MAX_VARIANT_INTAKE_AUXILIARY_LINES = 10_000
MAX_VARIANT_INDEX_RECORDS = MAX_VARIANT_INTAKE_RECORDS
MAX_REFERENCE_BLOCK_INDEX_RECORDS = MAX_VARIANT_INTAKE_RECORDS
MAX_REFERENCE_COVERAGE_PROVENANCE_REFERENCES = 250_000


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


class ReferenceBlockCallState(StrEnum):
    """Selected-sample call state carried by a reference-only block record."""

    REFERENCE = "reference"
    NO_CALL = "no_call"
    UNKNOWN = "unknown"


class ReferenceBlockSpanSource(StrEnum):
    """Field used to determine a sample's reference-block interval length."""

    FORMAT_LEN = "format_len"
    INFO_END = "info_end"


class ReferenceCoverageState(StrEnum):
    """Observed per-sample state over one partition of a reference query."""

    REFERENCE = "reference"
    NO_CALL = "no_call"
    UNKNOWN = "unknown"
    UNCOVERED = "uncovered"
    CONFLICT = "conflict"


class ReferenceCoverageStatus(StrEnum):
    """Summary of a complete query partition, without collapsing its segments."""

    COMPLETE_REFERENCE = "complete_reference"
    COMPLETE_NO_CALL = "complete_no_call"
    COMPLETE_UNKNOWN = "complete_unknown"
    MIXED = "mixed"
    PARTIAL = "partial"
    CONFLICTING = "conflicting"
    UNCOVERED = "uncovered"


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
class ReferenceBlockRecord:
    """One explicit reference-confidence interval retained outside variant rows.

    Coordinates are zero-based and half-open. ``end`` is derived from the
    sample-specific FORMAT/LEN when present, falling back to one-based inclusive
    INFO/END. The original symbolic allele and selected-sample fields remain
    available for audit; this record is never normalized as a variant.
    """

    source_id: str
    record_id: str
    source_line: int
    raw_hash: str
    genome_build: str
    chromosome: str
    start: int
    end: int
    reference: str
    alternate: str
    sample_id: str | None
    genotype: str | None
    call_state: ReferenceBlockCallState
    span_source: ReferenceBlockSpanSource
    info: Mapping[str, Any] = field(default_factory=dict)
    sample_values: Mapping[str, Any] = field(default_factory=dict)
    filter_value: str = "."
    quality: str = "."

    def __post_init__(self) -> None:
        for name in (
            "source_id",
            "record_id",
            "genome_build",
            "chromosome",
            "reference",
            "alternate",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"reference block {name} must be non-empty text")
        if type(self.source_line) is not int or self.source_line < 1:
            raise ValidationError("reference block source_line must be a positive integer")
        if type(self.start) is not int or type(self.end) is not int:
            raise ValidationError("reference block interval coordinates must be integers")
        if not isinstance(self.call_state, ReferenceBlockCallState):
            raise ValidationError("reference block call_state must be a typed call state")
        if not isinstance(self.span_source, ReferenceBlockSpanSource):
            raise ValidationError("reference block span_source must be a typed span source")
        if not isinstance(self.filter_value, str) or not isinstance(self.quality, str):
            raise ValidationError("reference block filter and quality must be text")
        if not isinstance(self.raw_hash, str) or not self.raw_hash.startswith("sha256:"):
            raise ValidationError("reference block raw_hash must be a sha256 content address")
        if not self.raw_hash[7:] or any(
            character not in "0123456789abcdef" for character in self.raw_hash[7:]
        ) or len(self.raw_hash) != 71:
            raise ValidationError("reference block raw_hash must be a sha256 content address")
        if not isinstance(self.info, Mapping) or not isinstance(self.sample_values, Mapping):
            raise ValidationError("reference block INFO and sample values must be objects")
        info = freeze_json(self.info, field="reference block info")
        sample_values = freeze_json(self.sample_values, field="reference block sample_values")
        if not isinstance(info, Mapping) or not isinstance(sample_values, Mapping):
            raise ValidationError("reference block INFO and sample values must be objects")
        object.__setattr__(self, "info", info)
        object.__setattr__(self, "sample_values", sample_values)
        if self.sample_id is not None and (
            not isinstance(self.sample_id, str) or not self.sample_id.strip()
        ):
            raise ValidationError("reference block sample_id must be non-empty when present")
        if self.genotype is not None and not isinstance(self.genotype, str):
            raise ValidationError("reference block genotype must be text when present")
        if self.alternate.upper() not in {"<*>", "<NON_REF>"}:
            raise ValidationError("reference block ALT must be <*> or <NON_REF>")
        if self.start < 0 or self.end <= self.start:
            raise ValidationError("reference block must have a non-empty zero-based interval")
        if not self.filter_value.strip() or not self.quality.strip():
            raise ValidationError("reference block filter and quality must not be empty")

    @property
    def length(self) -> int:
        return self.end - self.start

    @property
    def content_address(self) -> str:
        return content_hash(
            {
                "source_id": self.source_id,
                "record_id": self.record_id,
                "source_line": self.source_line,
                "raw_hash": self.raw_hash,
                "genome_build": self.genome_build,
                "chromosome": self.chromosome,
                "start": self.start,
                "end": self.end,
                "reference": self.reference,
                "alternate": self.alternate,
                "sample_id": self.sample_id,
                "genotype": self.genotype,
                "call_state": self.call_state,
                "span_source": self.span_source,
                "info": self.info,
                "sample_values": self.sample_values,
                "filter_value": self.filter_value,
                "quality": self.quality,
            },
            prefix="intake-reference-block",
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"length": self.length, "content_address": self.content_address}


def _reference_coverage_status(
    segments: tuple[ReferenceCoverageSegment, ...],
) -> ReferenceCoverageStatus:
    states = {segment.state for segment in segments}
    if ReferenceCoverageState.CONFLICT in states:
        return ReferenceCoverageStatus.CONFLICTING
    if states == {ReferenceCoverageState.UNCOVERED}:
        return ReferenceCoverageStatus.UNCOVERED
    if ReferenceCoverageState.UNCOVERED in states:
        return ReferenceCoverageStatus.PARTIAL
    if states == {ReferenceCoverageState.REFERENCE}:
        return ReferenceCoverageStatus.COMPLETE_REFERENCE
    if states == {ReferenceCoverageState.NO_CALL}:
        return ReferenceCoverageStatus.COMPLETE_NO_CALL
    if states == {ReferenceCoverageState.UNKNOWN}:
        return ReferenceCoverageStatus.COMPLETE_UNKNOWN
    return ReferenceCoverageStatus.MIXED


@dataclass(frozen=True, slots=True)
class ReferenceCoverageSegment:
    """One homogeneous segment in a sample- and build-specific coverage query."""

    start: int
    end: int
    state: ReferenceCoverageState
    block_addresses: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.start) is not int or type(self.end) is not int:
            raise ValidationError("reference coverage segment coordinates must be integers")
        if self.start < 0 or self.end <= self.start:
            raise ValidationError("reference coverage segment must be a non-empty interval")
        if not isinstance(self.state, ReferenceCoverageState):
            raise ValidationError("reference coverage segment state must be typed")
        if isinstance(self.block_addresses, (str, bytes, bytearray, Mapping)):
            raise ValidationError(
                "reference coverage block addresses must be an iterable of hashes"
            )
        try:
            addresses = tuple(self.block_addresses)
        except TypeError as exc:
            raise ValidationError("reference coverage block addresses must be iterable") from exc
        if any(not isinstance(address, str) or not address for address in addresses):
            raise ValidationError("reference coverage block addresses must be non-empty text")
        if addresses != tuple(sorted(set(addresses))):
            raise ValidationError("reference coverage block addresses must be sorted and unique")
        if self.state == ReferenceCoverageState.UNCOVERED and addresses:
            raise ValidationError("uncovered reference segments cannot cite reference blocks")
        if self.state != ReferenceCoverageState.UNCOVERED and not addresses:
            raise ValidationError("observed reference segments must cite their source blocks")
        if self.state == ReferenceCoverageState.CONFLICT and len(addresses) < 2:
            raise ValidationError("conflicting reference segments must cite at least two blocks")
        object.__setattr__(self, "block_addresses", addresses)

    @property
    def length(self) -> int:
        return self.end - self.start

    @property
    def content_address(self) -> str:
        return content_hash(
            {
                "start": self.start,
                "end": self.end,
                "state": self.state,
                "block_addresses": self.block_addresses,
            },
            prefix="intake-reference-coverage-segment",
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"length": self.length, "content_address": self.content_address}


@dataclass(frozen=True, slots=True)
class ReferenceCoverageResult:
    """Auditable partition of a queried interval for exactly one sample/build."""

    genome_build: str
    chromosome: str
    start: int
    end: int
    sample_id: str | None
    segments: tuple[ReferenceCoverageSegment, ...]
    block_addresses: tuple[str, ...]
    status: ReferenceCoverageStatus = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.genome_build, str) or not self.genome_build.strip():
            raise ValidationError("reference coverage genome_build must be non-empty text")
        if not isinstance(self.chromosome, str) or not self.chromosome.strip():
            raise ValidationError("reference coverage chromosome must be non-empty text")
        if type(self.start) is not int or type(self.end) is not int:
            raise ValidationError("reference coverage query coordinates must be integers")
        if self.start < 0 or self.end <= self.start:
            raise ValidationError("reference coverage query must be a non-empty half-open interval")
        if self.sample_id is not None and (
            not isinstance(self.sample_id, str) or not self.sample_id.strip()
        ):
            raise ValidationError("reference coverage sample_id must be non-empty when present")
        if isinstance(self.segments, (str, bytes, bytearray, Mapping)):
            raise ValidationError("reference coverage segments must be an iterable of segments")
        try:
            segments = tuple(self.segments)
        except TypeError as exc:
            raise ValidationError("reference coverage segments must be iterable") from exc
        if not segments or any(not isinstance(item, ReferenceCoverageSegment) for item in segments):
            raise ValidationError("reference coverage result requires typed segments")
        cursor = self.start
        for segment in segments:
            if segment.start != cursor:
                raise ValidationError("reference coverage segments must partition the query")
            cursor = segment.end
        if cursor != self.end:
            raise ValidationError("reference coverage segments must span the complete query")
        if isinstance(self.block_addresses, (str, bytes, bytearray, Mapping)):
            raise ValidationError(
                "reference coverage block addresses must be an iterable of hashes"
            )
        try:
            addresses = tuple(self.block_addresses)
        except TypeError as exc:
            raise ValidationError("reference coverage block addresses must be iterable") from exc
        if any(not isinstance(address, str) or not address for address in addresses):
            raise ValidationError("reference coverage block addresses must be non-empty text")
        addresses = tuple(sorted(set(addresses)))
        cited_addresses = tuple(
            sorted({address for segment in segments for address in segment.block_addresses})
        )
        if addresses != cited_addresses:
            raise ValidationError(
                "reference coverage result block addresses must match its segments"
            )
        object.__setattr__(self, "genome_build", self.genome_build.strip())
        object.__setattr__(self, "chromosome", normalize_chromosome(self.chromosome))
        object.__setattr__(self, "sample_id", self.sample_id.strip() if self.sample_id else None)
        object.__setattr__(self, "segments", segments)
        object.__setattr__(self, "block_addresses", addresses)
        object.__setattr__(self, "status", _reference_coverage_status(segments))

    @property
    def base_counts(self) -> dict[str, int]:
        """Return queried bases partitioned by observed state."""

        counts = {state.value: 0 for state in ReferenceCoverageState}
        for segment in self.segments:
            counts[segment.state.value] += segment.length
        return counts

    @property
    def content_address(self) -> str:
        return content_hash(
            {
                "genome_build": self.genome_build,
                "chromosome": self.chromosome,
                "start": self.start,
                "end": self.end,
                "sample_id": self.sample_id,
                "segments": [segment.content_address for segment in self.segments],
                "block_addresses": self.block_addresses,
                "status": self.status,
            },
            prefix="intake-reference-coverage",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "glio-noncode.reference-coverage.v1",
            "genome_build": self.genome_build,
            "chromosome": self.chromosome,
            "start": self.start,
            "end": self.end,
            "coordinate_system": "zero_based_half_open",
            "sample_id": self.sample_id,
            "status": self.status.value,
            "base_counts": self.base_counts,
            "segments": [segment.to_dict() for segment in self.segments],
            "block_addresses": list(self.block_addresses),
            "content_address": self.content_address,
        }


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
    reference_block_count: int
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
    """Canonical variants, reference blocks, and issues needed for review and replay."""

    source_id: str
    input_format: IntakeFormat
    variants: tuple[VariantIdentity, ...]
    records: tuple[RawVariantRecord, ...]
    deferred_records: tuple[RawVariantRecord, ...]
    reference_blocks: tuple[ReferenceBlockRecord, ...]
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
                "reference_blocks": self.reference_blocks,
                "issues": self.issues,
                "receipt": self.receipt.provenance_dict(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"content_address": self.content_address}

    @property
    def reference_block_address(self) -> str:
        return content_hash(
            [item.content_address for item in self.reference_blocks],
            prefix="intake-reference-block-set",
        )

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
        merged_metadata["reference_block_count"] = len(self.reference_blocks)
        merged_metadata["reference_block_address"] = self.reference_block_address
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
        self.reference_blocks: list[ReferenceBlockRecord] = []
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

    def add_reference_block(self, record: ReferenceBlockRecord) -> None:
        self.reference_blocks.append(record)

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
            "reference_block_count": len(self.reference_blocks),
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
            reference_block_count=len(self.reference_blocks),
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
            reference_blocks=tuple(self.reference_blocks),
            issues=tuple(self.issues),
            receipt=receipt,
        )


_REFERENCE_BLOCK_ALLELES = frozenset({"<*>", "<NON_REF>"})


def _parse_positive_vcf_integer(value: object, label: str) -> int:
    if isinstance(value, (list, tuple)):
        if len(value) != 1:
            raise ValidationError(f"reference-block {label} must contain exactly one value")
        value = value[0]
    if isinstance(value, bool):
        raise ValidationError(f"reference-block {label} must be a positive integer")
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, str) and value.isascii() and value.isdecimal():
        parsed = int(value)
    else:
        raise ValidationError(f"reference-block {label} must be a positive integer")
    if parsed < 1:
        raise ValidationError(f"reference-block {label} must be a positive integer")
    return parsed


def _reference_block_length(
    *,
    alternate: str,
    position: int,
    info: Mapping[str, Any],
    sample_values: Mapping[str, Any],
) -> tuple[int, ReferenceBlockSpanSource] | None:
    """Return a REF-only block span, honoring per-sample LEN before INFO END."""

    if alternate.upper() not in _REFERENCE_BLOCK_ALLELES:
        return None
    sample_length = sample_values.get("LEN")
    if sample_length is None:
        sample_length_missing = True
    elif isinstance(sample_length, str):
        sample_length_missing = sample_length in ("", ".")
    elif isinstance(sample_length, (list, tuple)):
        sample_length_missing = len(sample_length) == 1 and sample_length[0] is None
    else:
        sample_length_missing = False
    if not sample_length_missing:
        return (
            _parse_positive_vcf_integer(sample_length, "FORMAT/LEN"),
            ReferenceBlockSpanSource.FORMAT_LEN,
        )
    if "END" not in info:
        return None
    inclusive_end = _parse_positive_vcf_integer(info["END"], "INFO/END")
    if inclusive_end < position:
        raise ValidationError("reference-block INFO/END must not precede POS")
    return inclusive_end - position + 1, ReferenceBlockSpanSource.INFO_END


def _reference_block_call_state(
    genotype: object,
) -> ReferenceBlockCallState | None:
    if genotype is None:
        return ReferenceBlockCallState.UNKNOWN
    if not isinstance(genotype, str) or not genotype:
        return ReferenceBlockCallState.UNKNOWN
    alleles = genotype.replace("|", "/").split("/")
    if any(allele == "." for allele in alleles):
        return ReferenceBlockCallState.NO_CALL
    if all(allele == "0" for allele in alleles):
        return ReferenceBlockCallState.REFERENCE
    return None


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
        format_definitions: dict[str, FormatFieldDefinition] = {}
        invalid_format_definitions: set[str] = set()
        sample_selection_issue = (
            "duplicate_sample_id"
            if has_duplicate_sample_ids(document.samples)
            else "sample_not_found"
            if sample_id is not None and sample_id not in document.samples
            else "sample_selection_required"
            if sample_id is None and len(document.samples) > 1
            else None
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
            if line.startswith("##FORMAT="):
                format_definition_issue = register_format_definition(
                    line,
                    format_definitions,
                    invalid_format_definitions,
                )
                if format_definition_issue is not None:
                    builder.issue(
                        format_definition_issue,
                        IntakeSeverity.ERROR,
                        "BCF FORMAT schema declaration is invalid or duplicated",
                        line_number=line_number,
                        raw_hash=content_hash(line),
                        remediation=(
                            "Declare each FORMAT ID once with a valid Number, Type, "
                            "and a quoted Description."
                        ),
                    )
        if builder.auxiliary_limit_exceeded:
            return builder.finish("", header_lines, input_hash=document.input_hash)
        if sample_selection_issue is not None:
            builder.issue(
                sample_selection_issue,
                IntakeSeverity.ERROR,
                (
                    "requested sample_id is not present in the BCF header"
                    if sample_selection_issue == "sample_not_found"
                    else "sample_id is required when the BCF header contains multiple samples"
                    if sample_selection_issue == "sample_selection_required"
                    else "BCF header contains duplicate sample IDs"
                ),
                raw_hash=content_hash(document.header_text),
                remediation=(
                    "Use a sample_id that exactly matches a BCF header sample name."
                    if sample_selection_issue == "sample_not_found"
                    else "Specify the sample_id to analyze; multi-sample BCF is not auto-selected."
                    if sample_selection_issue == "sample_selection_required"
                    else "Correct the BCF header so every sample ID is unique."
                ),
            )
        for record in document.records:
            if not builder.note_record(
                line_number=record.record_index + 1,
                raw_hash=record.raw_hash,
            ):
                break
            if sample_selection_issue is not None:
                continue
            format_issue = format_key_issue(record.format_keys)
            if format_issue is not None:
                builder.issue(
                    format_issue,
                    IntakeSeverity.ERROR,
                    "BCF record FORMAT keys are invalid or ambiguous",
                    line_number=record.record_index + 1,
                    raw_hash=record.raw_hash,
                    remediation=(
                        "Use unique FORMAT keys with valid identifiers "
                        "and put GT first when present."
                    ),
                )
                continue
            no_alternate = not record.alternates or record.alternates == (".",)
            if not no_alternate and (
                any(not alternate for alternate in record.alternates)
                or "." in record.alternates
            ):
                builder.issue(
                    "invalid_alternate",
                    IntakeSeverity.ERROR,
                    "BCF ALT list contains an empty or misplaced missing-value allele",
                    line_number=record.record_index + 1,
                    raw_hash=record.raw_hash,
                )
                continue
            sample: Mapping[str, Any] = {}
            selected_name: str | None = None
            if record.samples:
                selected_name = (
                    sample_id if sample_id in record.samples else next(iter(record.samples))
                )
                sample = dict(record.samples[selected_name]) | {"sample_id": selected_name}
            format_schema_issue = validate_format_values(
                sample,
                format_definitions,
                invalid_format_definitions,
                len(record.alternates),
                typed_values=True,
            )
            if format_schema_issue is not None:
                builder.issue(
                    format_schema_issue,
                    IntakeSeverity.ERROR,
                    "selected BCF sample FORMAT values do not match their declarations",
                    line_number=record.record_index + 1,
                    raw_hash=record.raw_hash,
                    remediation=(
                        "Correct the selected sample's typed FORMAT values to match "
                        "the declared Type and Number."
                    ),
                )
                continue
            genotype = sample.get("GT")
            try:
                selected_alternates = called_alternate_indices(
                    genotype,
                    len(record.alternates),
                )
            except ValidationError as exc:
                builder.issue(
                    "invalid_genotype",
                    IntakeSeverity.ERROR,
                    f"invalid selected-sample GT: {exc}",
                    line_number=record.record_index + 1,
                    raw_hash=record.raw_hash,
                    remediation=(
                        "Correct the GT allele indices or retain only valid source records."
                    ),
                )
                continue
            try:
                block_span = (
                    _reference_block_length(
                        alternate=record.alternates[0],
                        position=record.position,
                        info=record.info,
                        sample_values=sample,
                    )
                    if len(record.alternates) == 1
                    else None
                )
            except ValidationError as exc:
                builder.issue(
                    "invalid_reference_block_span",
                    IntakeSeverity.ERROR,
                    str(exc),
                    line_number=record.record_index + 1,
                    raw_hash=record.raw_hash,
                    remediation=(
                        "Use one positive per-sample FORMAT/LEN or a positive one-based "
                        "inclusive INFO/END for a <*> or <NON_REF> block."
                    ),
                )
                continue
            if block_span is not None:
                call_state = _reference_block_call_state(genotype)
                if call_state is not None:
                    block_length, span_source = block_span
                    block_start = record.position - 1
                    builder.add_reference_block(
                        ReferenceBlockRecord(
                            source_id=source_id,
                            record_id=(
                                record.record_id
                                if record.record_id not in {"", "."}
                                else f"{source_id}:{record.record_index + 1}"
                            ),
                            source_line=record.record_index + 1,
                            raw_hash=record.raw_hash,
                            genome_build=build,
                            chromosome=record.chromosome,
                            start=block_start,
                            end=block_start + block_length,
                            reference=record.reference,
                            alternate=record.alternates[0],
                            sample_id=selected_name,
                            genotype=genotype if isinstance(genotype, str) else None,
                            call_state=call_state,
                            span_source=span_source,
                            info=dict(record.info),
                            sample_values=dict(sample),
                            filter_value=";".join(record.filters),
                            quality="." if record.quality is None else str(record.quality),
                        )
                    )
                    continue
            if no_alternate:
                builder.issue(
                    "no_alternate_allele",
                    IntakeSeverity.WARNING,
                    "BCF record has no alternate allele and is not emitted as a variant",
                    line_number=record.record_index + 1,
                    raw_hash=record.raw_hash,
                )
                continue
            if genotype is not None and self._is_no_call(genotype) and not include_no_call:
                builder.issue(
                    "no_call_genotype",
                    IntakeSeverity.WARNING,
                    "BCF record skipped because the selected genotype is a no-call",
                    line_number=record.record_index + 1,
                    raw_hash=record.raw_hash,
                )
                continue
            has_symbolic_alternate = any(
                alternate == "*"
                or alternate.startswith("<")
                or any(marker in alternate for marker in "[]")
                for alternate in record.alternates
            )
            if (
                genotype is not None
                and not self._is_no_call(genotype)
                and not selected_alternates
                and not has_symbolic_alternate
            ):
                builder.issue(
                    "reference_genotype",
                    IntakeSeverity.WARNING,
                    "BCF record skipped because the selected genotype is reference-only",
                    line_number=record.record_index + 1,
                    raw_hash=record.raw_hash,
                )
                continue
            for alternate_index, alternate in enumerate(record.alternates, start=1):
                if selected_alternates and alternate_index not in selected_alternates:
                    builder.issue(
                        "alternate_not_in_selected_genotype",
                        IntakeSeverity.WARNING,
                        f"ALT index {alternate_index} was not called in the selected genotype",
                        line_number=record.record_index + 1,
                        raw_hash=record.raw_hash,
                        remediation=(
                            "Review the selected sample GT before using this alternate allele."
                        ),
                    )
                    continue
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
        sample_selection_failed = False
        info_definitions: dict[str, InfoFieldDefinition] = {}
        invalid_info_definitions: set[str] = set()
        format_definitions: dict[str, FormatFieldDefinition] = {}
        invalid_format_definitions: set[str] = set()
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
                if line.startswith("##INFO="):
                    info_definition_issue = register_info_definition(
                        line,
                        info_definitions,
                        invalid_info_definitions,
                    )
                    if info_definition_issue is not None:
                        builder.issue(
                            info_definition_issue,
                            IntakeSeverity.ERROR,
                            "VCF INFO schema declaration is invalid or duplicated",
                            line_number=line_number,
                            raw_hash=content_hash(line),
                            remediation=(
                                "Declare each INFO ID once with valid Number, Type, "
                                "and a quoted Description."
                            ),
                        )
                elif line.startswith("##FORMAT="):
                    format_definition_issue = register_format_definition(
                        line,
                        format_definitions,
                        invalid_format_definitions,
                    )
                    if format_definition_issue is not None:
                        builder.issue(
                            format_definition_issue,
                            IntakeSeverity.ERROR,
                            "VCF FORMAT schema declaration is invalid or duplicated",
                            line_number=line_number,
                            raw_hash=content_hash(line),
                            remediation=(
                                "Declare each FORMAT ID once with a valid Number, Type, "
                                "and a quoted Description.",
                            ),
                        )
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
                    if has_duplicate_sample_ids(sample_columns):
                        sample_selection_failed = True
                        builder.issue(
                            "duplicate_sample_id",
                            IntakeSeverity.ERROR,
                            "VCF header contains duplicate sample IDs",
                            line_number=line_number,
                            raw_hash=content_hash(line),
                            remediation="Correct the VCF header so every sample ID is unique.",
                        )
                    elif sample_id is not None:
                        if sample_id in sample_columns:
                            selected_sample_index = sample_columns.index(sample_id)
                        else:
                            sample_selection_failed = True
                            builder.issue(
                                "sample_not_found",
                                IntakeSeverity.ERROR,
                                "requested sample_id is not present in the VCF header",
                                line_number=line_number,
                                raw_hash=content_hash(line),
                                remediation=(
                                    "Use a sample_id that exactly matches a VCF header sample name."
                                ),
                            )
                    elif len(sample_columns) == 1:
                        selected_sample_index = 0
                    elif len(sample_columns) > 1:
                        sample_selection_failed = True
                        builder.issue(
                            "sample_selection_required",
                            IntakeSeverity.ERROR,
                            "sample_id is required when the VCF header contains multiple samples",
                            line_number=line_number,
                            raw_hash=content_hash(line),
                            remediation=(
                                "Specify an exact sample_id; "
                                "multi-sample VCF is not auto-selected."
                            ),
                        )
                continue
            raw_hash = content_hash(line)
            if not builder.note_record(line_number=line_number, raw_hash=raw_hash):
                break
            if sample_selection_failed:
                continue
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
            if (
                selected_sample_index is not None
                and len(fields) <= 9 + selected_sample_index
            ):
                builder.issue(
                    "sample_data_missing",
                    IntakeSeverity.ERROR,
                    "selected sample field is missing from the VCF record",
                    line_number=line_number,
                    raw_hash=raw_hash,
                    remediation="Restore the sample column or remove the malformed record.",
                )
                continue
            format_keys = (
                ()
                if len(fields) < 9 or fields[8] == "."
                else tuple(fields[8].split(":"))
            )
            format_issue = format_key_issue(format_keys)
            if format_issue is not None:
                builder.issue(
                    format_issue,
                    IntakeSeverity.ERROR,
                    "VCF record FORMAT keys are invalid or ambiguous",
                    line_number=line_number,
                    raw_hash=raw_hash,
                    remediation=(
                        "Use unique FORMAT keys with valid identifiers "
                        "and put GT first when present."
                    ),
                )
                continue
            if selected_sample_index is not None:
                sample_issue = sample_value_issue(
                    format_keys,
                    fields[9 + selected_sample_index],
                )
                if sample_issue is not None:
                    builder.issue(
                        sample_issue,
                        IntakeSeverity.ERROR,
                        "selected VCF sample cell is empty or has excess subfields",
                        line_number=line_number,
                        raw_hash=raw_hash,
                        remediation=(
                            "Use '.' for missing sample values and do not add fields beyond FORMAT."
                        ),
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
            info, info_issue = parse_info_fields(info_text)
            if info_issue is not None:
                builder.issue(
                    info_issue,
                    IntakeSeverity.ERROR,
                    "VCF INFO field is malformed or contains an ambiguous key",
                    line_number=line_number,
                    raw_hash=raw_hash,
                    remediation=(
                        "Use unique valid INFO keys and encode missing values as '.'; "
                        "do not leave empty fields or values."
                    ),
                )
                continue
            sample, selected_name = self._select_vcf_sample(
                fields, header_columns, selected_sample_index, sample_id
            )
            if selected_name:
                sample = dict(sample) | {"sample_id": selected_name}
            no_alternate = alternate_text == "."
            alternates = [] if no_alternate else alternate_text.split(",")
            if not no_alternate and (
                not alternates
                or any(not alternate for alternate in alternates)
                or "." in alternates
            ):
                builder.issue(
                    "invalid_alternate",
                    IntakeSeverity.ERROR,
                    "VCF ALT list contains an empty or misplaced missing-value allele",
                    line_number=line_number,
                    raw_hash=raw_hash,
                )
                continue
            info_schema_issue = validate_info_values(
                info,
                info_definitions,
                invalid_info_definitions,
                len(alternates),
            )
            if info_schema_issue is not None:
                builder.issue(
                    info_schema_issue,
                    IntakeSeverity.ERROR,
                    "VCF INFO value disagrees with its declared schema",
                    line_number=line_number,
                    raw_hash=raw_hash,
                    remediation=(
                        "Check the INFO Type and Number declaration and make the record "
                        "values conform without changing their source meaning."
                    ),
                )
                continue
            if selected_sample_index is not None:
                format_values = sample_format_values(
                    format_keys, fields[9 + selected_sample_index]
                )
                format_schema_issue = validate_format_values(
                    format_values,
                    format_definitions,
                    invalid_format_definitions,
                    len(alternates),
                )
                if format_schema_issue is not None:
                    builder.issue(
                        format_schema_issue,
                        IntakeSeverity.ERROR,
                        "VCF FORMAT value disagrees with its declared schema",
                        line_number=line_number,
                        raw_hash=raw_hash,
                        remediation=(
                            "Check the selected sample's FORMAT Type and Number declarations "
                            "against its values and genotype ploidy."
                        ),
                    )
                    continue
            genotype = sample.get("GT")
            try:
                selected_alternates = called_alternate_indices(genotype, len(alternates))
            except ValidationError as exc:
                builder.issue(
                    "invalid_genotype",
                    IntakeSeverity.ERROR,
                    f"invalid selected-sample GT: {exc}",
                    line_number=line_number,
                    raw_hash=raw_hash,
                    remediation=(
                        "Correct the GT allele indices or retain only valid source records."
                    ),
                )
                continue
            try:
                block_span = (
                    _reference_block_length(
                        alternate=alternates[0],
                        position=position,
                        info=info,
                        sample_values=sample,
                    )
                    if len(alternates) == 1
                    else None
                )
            except ValidationError as exc:
                builder.issue(
                    "invalid_reference_block_span",
                    IntakeSeverity.ERROR,
                    str(exc),
                    line_number=line_number,
                    raw_hash=raw_hash,
                    remediation=(
                        "Use one positive per-sample FORMAT/LEN or a positive one-based "
                        "inclusive INFO/END for a <*> or <NON_REF> block."
                    ),
                )
                continue
            if block_span is not None:
                call_state = _reference_block_call_state(genotype)
                if call_state is not None:
                    block_length, span_source = block_span
                    block_start = position - 1
                    builder.add_reference_block(
                        ReferenceBlockRecord(
                            source_id=source_id,
                            record_id=(
                                record_id
                                if record_id not in {"", "."}
                                else f"{source_id}:{line_number}"
                            ),
                            source_line=line_number,
                            raw_hash=raw_hash,
                            genome_build=build,
                            chromosome=chromosome,
                            start=block_start,
                            end=block_start + block_length,
                            reference=reference,
                            alternate=alternates[0],
                            sample_id=selected_name,
                            genotype=genotype if isinstance(genotype, str) else None,
                            call_state=call_state,
                            span_source=span_source,
                            info=dict(info),
                            sample_values=dict(sample),
                            filter_value=filter_value,
                            quality=quality,
                        )
                    )
                    continue
            if no_alternate:
                builder.issue(
                    "no_alternate_allele",
                    IntakeSeverity.WARNING,
                    "VCF record has ALT='.' and is not emitted as a variant",
                    line_number=line_number,
                    raw_hash=raw_hash,
                )
                continue
            if sample and self._is_no_call(genotype) and not include_no_call:
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
            has_symbolic_alternate = any(
                alternate == "*"
                or alternate.startswith("<")
                or any(marker in alternate for marker in "[]")
                for alternate in alternates
            )
            if (
                genotype is not None
                and not self._is_no_call(genotype)
                and not selected_alternates
                and not has_symbolic_alternate
            ):
                builder.issue(
                    "reference_genotype",
                    IntakeSeverity.WARNING,
                    "record skipped because the selected genotype is reference-only",
                    line_number=line_number,
                    raw_hash=raw_hash,
                )
                continue
            for alternate_index, alternate in enumerate(alternates, start=1):
                if selected_alternates and alternate_index not in selected_alternates:
                    builder.issue(
                        "alternate_not_in_selected_genotype",
                        IntakeSeverity.WARNING,
                        f"ALT index {alternate_index} was not called in the selected genotype",
                        line_number=line_number,
                        raw_hash=raw_hash,
                        remediation=(
                            "Review the selected sample GT before using this alternate allele."
                        ),
                    )
                    continue
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
        if (
            alternate == "*"
            or alternate.startswith("<")
            or any(marker in alternate for marker in "[]")
        ):
            builder.defer(record)
            builder.issue(
                "unsupported_symbolic_allele",
                IntakeSeverity.WARNING,
                f"symbolic, breakend, or spanning-deletion allele deferred: {alternate}",
                line_number=record.source_line,
                raw_hash=record.raw_hash,
                remediation=(
                    "Route the allele to structural or overlap-aware handling; do not "
                    "treat it as a standalone SNV or indel."
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
    def _select_vcf_sample(
        fields: list[str],
        header_columns: list[str],
        selected_sample_index: int | None,
        requested_sample_id: str | None,
    ) -> tuple[dict[str, Any], str | None]:
        if len(fields) < 10 or len(header_columns) < 10:
            return {}, requested_sample_id
        sample_index = selected_sample_index or 0
        field_index = 9 + sample_index
        if field_index >= len(fields):
            return {}, requested_sample_id
        format_text = fields[8]
        if format_text in {"", "."}:
            return {}, header_columns[field_index]
        format_keys = format_text.split(":")
        sample_text = fields[field_index]
        values = ["."] * len(format_keys) if sample_text == "." else sample_text.split(":")
        return dict(zip(format_keys, values, strict=False)), header_columns[field_index]

    @staticmethod
    def _is_no_call(genotype: object) -> bool:
        return isinstance(genotype, str) and (genotype in {".", "./.", ".|."} or "." in genotype)

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


class ReferenceBlockIndex:
    """Bounded per-sample interval index for explicit gVCF confidence blocks.

    Query coordinates use zero-based half-open intervals. Genome build and sample
    are mandatory query dimensions; blocks are never pooled across either one.
    The sorted starts and prefix maximum ends bound candidate lookup without
    expanding intervals into per-base storage.
    """

    def __init__(
        self,
        blocks: Iterable[ReferenceBlockRecord],
        *,
        max_records: int = MAX_REFERENCE_BLOCK_INDEX_RECORDS,
    ) -> None:
        if (
            isinstance(max_records, bool)
            or not isinstance(max_records, int)
            or not 1 <= max_records <= MAX_REFERENCE_BLOCK_INDEX_RECORDS
        ):
            raise ValidationError(
                "max_records must be an integer between 1 and "
                f"MAX_REFERENCE_BLOCK_INDEX_RECORDS ({MAX_REFERENCE_BLOCK_INDEX_RECORDS})"
            )
        if isinstance(blocks, (str, bytes, bytearray, Mapping)):
            raise ValidationError("blocks must be an iterable of ReferenceBlockRecord objects")
        try:
            values = tuple(islice(iter(blocks), max_records + 1))
        except TypeError as exc:
            raise ValidationError("blocks must be iterable") from exc
        if len(values) > max_records:
            raise ValidationError(
                "reference_block_index_record_limit_exceeded: "
                f"reference-block index ceiling of {max_records} was exceeded"
            )
        if any(not isinstance(block, ReferenceBlockRecord) for block in values):
            raise ValidationError("blocks must contain only ReferenceBlockRecord objects")

        def sort_key(block: ReferenceBlockRecord) -> tuple[str, str, str, int, int, str]:
            return (
                block.genome_build.strip(),
                normalize_chromosome(block.chromosome),
                block.sample_id or "",
                block.start,
                block.end,
                block.content_address,
            )

        self._blocks = tuple(sorted(values, key=sort_key))
        grouped: dict[tuple[str, str, str | None], list[ReferenceBlockRecord]] = {}
        for block in self._blocks:
            key = (
                block.genome_build.strip(),
                normalize_chromosome(block.chromosome),
                block.sample_id,
            )
            grouped.setdefault(key, []).append(block)
        self._by_build_chromosome_sample = {
            key: tuple(group) for key, group in grouped.items()
        }
        self._starts: dict[tuple[str, str, str | None], tuple[int, ...]] = {}
        self._prefix_max_ends: dict[tuple[str, str, str | None], tuple[int, ...]] = {}
        for key, group in self._by_build_chromosome_sample.items():
            self._starts[key] = tuple(block.start for block in group)
            prefix_max_ends: list[int] = []
            max_end = 0
            for block in group:
                max_end = max(max_end, block.end)
                prefix_max_ends.append(max_end)
            self._prefix_max_ends[key] = tuple(prefix_max_ends)

    @staticmethod
    def _query_key(
        genome_build: str,
        chromosome: str,
        sample_id: str | None,
    ) -> tuple[str, str, str | None]:
        if not isinstance(genome_build, str) or not genome_build.strip():
            raise ValidationError("genome_build must be non-empty text")
        if not isinstance(chromosome, str) or not chromosome.strip():
            raise ValidationError("chromosome must be non-empty text")
        if sample_id is not None and (not isinstance(sample_id, str) or not sample_id.strip()):
            raise ValidationError("sample_id must be non-empty text when present")
        return (
            genome_build.strip(),
            normalize_chromosome(chromosome),
            sample_id.strip() if sample_id else None,
        )

    @staticmethod
    def _validate_interval(start: int, end: int) -> None:
        if type(start) is not int or type(end) is not int:
            raise ValidationError("reference-block query coordinates must be integers")
        if start < 0 or end <= start:
            raise ValidationError(
                "reference-block query must satisfy 0 <= start < end using half-open coordinates"
            )

    def _overlapping_blocks(
        self,
        key: tuple[str, str, str | None],
        start: int,
        end: int,
    ) -> tuple[ReferenceBlockRecord, ...]:
        group = self._by_build_chromosome_sample.get(key, ())
        if not group:
            return ()
        starts = self._starts[key]
        prefix_max_ends = self._prefix_max_ends[key]
        candidate_limit = bisect_left(starts, end)
        candidates: list[ReferenceBlockRecord] = []
        for index in range(candidate_limit - 1, -1, -1):
            if prefix_max_ends[index] <= start:
                break
            block = group[index]
            if block.end > start:
                candidates.append(block)
        candidates.sort(key=lambda item: (item.start, item.end, item.content_address))
        return tuple(candidates)

    def overlap(
        self,
        genome_build: str,
        chromosome: str,
        start: int,
        end: int,
        *,
        sample_id: str | None,
    ) -> tuple[ReferenceBlockRecord, ...]:
        """Return overlapping blocks for one explicit build and sample only."""

        self._validate_interval(start, end)
        key = self._query_key(genome_build, chromosome, sample_id)
        return self._overlapping_blocks(key, start, end)

    def coverage_for_variant(
        self,
        variant: VariantIdentity,
        *,
        sample_id: str | None,
    ) -> ReferenceCoverageResult:
        """Query the canonical reference span of a one-based closed variant.

        ``VariantIdentity`` coordinates are one-based and closed, while this
        index stores zero-based half-open intervals. The exact genome build and
        chromosome on the variant are used; no build conversion is attempted.
        The reference-block sample remains explicit so a variant's optional
        sample provenance is never used to select a different coverage record
        implicitly.
        """

        if not isinstance(variant, VariantIdentity):
            raise ValidationError("variant must be a VariantIdentity")
        return self.coverage(
            variant.genome_build,
            variant.chromosome,
            variant.start - 1,
            variant.end,
            sample_id=sample_id,
        )

    def coverage(
        self,
        genome_build: str,
        chromosome: str,
        start: int,
        end: int,
        *,
        sample_id: str | None,
    ) -> ReferenceCoverageResult:
        """Partition a query into reference, no-call, unknown, uncovered, or conflict."""

        self._validate_interval(start, end)
        key = self._query_key(genome_build, chromosome, sample_id)
        blocks = self._overlapping_blocks(key, start, end)
        starts_at: dict[int, list[int]] = {}
        ends_at: dict[int, list[int]] = {}
        for index, block in enumerate(blocks):
            clipped_start = max(start, block.start)
            clipped_end = min(end, block.end)
            starts_at.setdefault(clipped_start, []).append(index)
            ends_at.setdefault(clipped_end, []).append(index)

        boundaries = sorted({start, end, *starts_at, *ends_at})
        active: set[int] = set()
        segments: list[ReferenceCoverageSegment] = []
        provenance_reference_count = 0
        for boundary_index, boundary in enumerate(boundaries[:-1]):
            for index in ends_at.get(boundary, ()):
                active.discard(index)
            active.update(starts_at.get(boundary, ()))
            next_boundary = boundaries[boundary_index + 1]
            provenance_reference_count += len(active)
            if provenance_reference_count > MAX_REFERENCE_COVERAGE_PROVENANCE_REFERENCES:
                raise ValidationError(
                    "reference_coverage_provenance_limit_exceeded: "
                    "coverage query exceeds the bounded active-block provenance budget of "
                    f"{MAX_REFERENCE_COVERAGE_PROVENANCE_REFERENCES}"
                )
            active_blocks = tuple(blocks[index] for index in sorted(active))
            active_states = {block.call_state for block in active_blocks}
            if len(active_states) > 1:
                state = ReferenceCoverageState.CONFLICT
            elif not active_blocks:
                state = ReferenceCoverageState.UNCOVERED
            else:
                state = ReferenceCoverageState(next(iter(active_states)).value)
            addresses = tuple(sorted({block.content_address for block in active_blocks}))
            segment = ReferenceCoverageSegment(
                boundary,
                next_boundary,
                state,
                addresses,
            )
            if (
                segments
                and segments[-1].end == segment.start
                and segments[-1].state == segment.state
                and segments[-1].block_addresses == segment.block_addresses
            ):
                previous = segments.pop()
                segment = ReferenceCoverageSegment(
                    previous.start,
                    segment.end,
                    segment.state,
                    segment.block_addresses,
                )
            segments.append(segment)

        segment_values = tuple(segments)
        block_addresses = tuple(
            sorted({address for segment in segment_values for address in segment.block_addresses})
        )
        return ReferenceCoverageResult(
            genome_build=key[0],
            chromosome=key[1],
            start=start,
            end=end,
            sample_id=key[2],
            segments=segment_values,
            block_addresses=block_addresses,
        )

    def all(self) -> tuple[ReferenceBlockRecord, ...]:
        """Return all indexed records in deterministic query order."""

        return self._blocks

    @property
    def content_address(self) -> str:
        return content_hash(
            [block.content_address for block in self._blocks],
            prefix="intake-reference-block-index",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self._blocks),
            "coordinate_system": "zero_based_half_open",
            "blocks": [block.to_dict() for block in self._blocks],
            "content_address": self.content_address,
        }


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

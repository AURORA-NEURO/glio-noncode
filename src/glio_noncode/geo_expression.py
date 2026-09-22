"""Bounded GEO Series Matrix retrieval and exploratory expression contrasts.

Public-cohort comparisons stay separate from matched-sample RNA evidence. The
module supports single-feature outlier descriptions and explicitly filtered
two-group exploratory screens; neither creates patient-matched claims.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import heapq
import io
import math
import re
import zlib
from array import array
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Any

from . import _safe_persistence
from ._geo_statistics import (
    PreparedLinearModel,
    fit_linear_contrast,
    prepare_linear_model,
    student_t_critical_value,
)
from .data_sources import UrllibTransport
from .errors import SourceError, SourceNotFoundError, ValidationError
from .expression_evidence import (
    DispersionMethod,
    ExpressionBatch,
    ExpressionDirection,
    ExpressionObservation,
    ExpressionScale,
    RNAEvidenceState,
    RobustExpressionOutlierAnalyzer,
)
from .geo_platform_annotations import read_geo_platform_annotations
from .serialization import content_hash

GEO_FTP_ORIGIN = "https://ftp.ncbi.nlm.nih.gov"
GEO_RECORD_ORIGIN = "https://www.ncbi.nlm.nih.gov"
MAX_COMPRESSED_BYTES = 25_000_000
MAX_DECOMPRESSED_BYTES = 256_000_000
MAX_MATRIX_LINE_BYTES = 4_000_000
MAX_SAMPLE_COUNT = 2_000
MAX_FEATURE_COUNT = 1_000_000
MAX_MATRIX_CELLS = 5_000_000
MAX_CONTRAST_FEATURES = 100_000
MAX_FEATURE_ANNOTATION_BYTES = 2_000_000
MAX_FEATURE_ANNOTATION_ROWS = 100_000
GEO_COUNT_NORMALIZATION_METHODS = ("log2_cpm", "tmm_log2_cpm")
MAX_TRACKED_GEO_FEATURES = 500
MAX_EXACT_RANK_ASSIGNMENTS = 20_000
MAX_TOTAL_EXACT_RANK_SUMS = 100_000_000
MAX_GEO_COVARIATES = 16
MAX_GEO_MODEL_PARAMETERS = 24
MIN_GEO_COUNT_CONTRAST_PAIRS = 3
DEFAULT_GEO_CONFIDENCE_LEVEL = 0.95
MAX_METADATA_ROWS = 2_048
MAX_METADATA_VALUE_LENGTH = 8_192
DEFAULT_TIMEOUT_SECONDS = 30.0
_GSE_RE = re.compile(r"GSE[0-9]{1,10}\Z")
_GSM_RE = re.compile(r"GSM[0-9]{1,12}\Z")
_FEATURE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@|/+=_-]{0,255}\Z")
_SUPPLEMENTARY_FILE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}\Z")
_MISSING_MATRIX_VALUES = frozenset({"", "na", "null"})
_MONTH_ABBREVIATION = (
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
)
_DATE_LIKE_FEATURE_LABEL_RE = re.compile(
    rf"(?:[0-9]{{1,2}}-{_MONTH_ABBREVIATION}|{_MONTH_ABBREVIATION}-[0-9]{{1,2}})",
    re.IGNORECASE,
)
_MAX_REPORTED_DATE_LIKE_FEATURE_LABELS = 25


@dataclass(frozen=True, slots=True)
class GeoSample:
    accession: str
    title: str
    source_name: str
    platform_id: str
    characteristics: tuple[tuple[str, str], ...]

    def matches(self, filters: Sequence[tuple[str, str]]) -> bool:
        characteristics = tuple(
            (key.casefold(), value.casefold()) for key, value in self.characteristics
        )
        return all(
            (field.casefold(), expected.casefold()) in characteristics
            for field, expected in filters
        )

    def values_for(self, fields: Sequence[str]) -> dict[str, list[str]]:
        wanted = {field.casefold(): field for field in fields}
        values: dict[str, list[str]] = {field: [] for field in fields}
        for key, value in self.characteristics:
            requested = wanted.get(key.casefold())
            if requested is not None:
                values[requested].append(value)
        return values


@dataclass(frozen=True, slots=True)
class GeoSeriesMatrix:
    accession: str
    title: str
    series_types: tuple[str, ...]
    platform_ids: tuple[str, ...]
    samples: tuple[GeoSample, ...]
    processing_descriptions: tuple[str, ...]
    feature_count: int
    feature_id: str
    feature_values: tuple[float | None, ...]
    source_sha256: str
    source_url: str
    source_file_name: str | None
    compressed_bytes: int
    decompressed_bytes: int


@dataclass(frozen=True, slots=True)
class GeoMatrixFeature:
    feature_id: str
    values: tuple[float | None, ...]


@dataclass(frozen=True, slots=True)
class GeoFeatureMatrix:
    accession: str
    title: str
    series_types: tuple[str, ...]
    platform_ids: tuple[str, ...]
    samples: tuple[GeoSample, ...]
    processing_descriptions: tuple[str, ...]
    feature_count: int
    features: tuple[GeoMatrixFeature, ...]
    source_sha256: str
    source_url: str
    source_file_name: str | None
    compressed_bytes: int
    decompressed_bytes: int


@dataclass(frozen=True, slots=True)
class GeoMatrixMetadata:
    accession: str
    title: str
    series_types: tuple[str, ...]
    platform_ids: tuple[str, ...]
    samples: tuple[GeoSample, ...]
    processing_descriptions: tuple[str, ...]
    feature_count: int
    source_sha256: str
    source_url: str
    source_file_name: str | None
    compressed_bytes: int
    decompressed_bytes: int


@dataclass(frozen=True, slots=True)
class _PreparedGeoContrast:
    model: PreparedLinearModel
    sample_indices: tuple[int, ...]
    case_indices: tuple[int, ...]
    reference_indices: tuple[int, ...]
    parameter_names: tuple[str, ...]
    covariate_metadata: tuple[dict[str, Any], ...]
    excluded_case_indices: tuple[int, ...]
    excluded_reference_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _GeoCountMatrix:
    accession: str
    feature_id: str
    sample_ids: tuple[str, ...]
    feature_counts: tuple[int, ...]
    library_sizes: tuple[int, ...]
    feature_count: int
    duplicate_feature_label_count: int
    source_file_name: str
    source_url: str | None
    source_sha256: str
    compressed_bytes: int
    decompressed_bytes: int
    annotation_source_ids_found: tuple[str, ...]
    duplicate_annotation_source_ids: tuple[str, ...]
    normalization_factors: tuple[float, ...]


@dataclass(slots=True)
class _GeoCountTableSummary:
    sample_ids: tuple[str, ...] = ()
    library_sizes: list[int] = dataclass_field(default_factory=list)
    feature_count: int = 0
    duplicate_feature_label_count: int = 0
    duplicate_feature_ids: set[str] = dataclass_field(default_factory=set)
    date_like_feature_label_count: int = 0
    date_like_feature_labels: list[str] = dataclass_field(default_factory=list)
    decompressed_bytes: int = 0


def _date_like_feature_label_review(summary: _GeoCountTableSummary) -> dict[str, Any]:
    """Report bounded labels that resemble spreadsheet-coerced date tokens."""

    return {
        "possible_date_like_source_label_count": summary.date_like_feature_label_count,
        "reported_possible_date_like_source_labels": list(summary.date_like_feature_labels),
        "omitted_possible_date_like_source_label_count": max(
            0, summary.date_like_feature_label_count - len(summary.date_like_feature_labels)
        ),
        "automatic_normalization_performed": False,
        "manual_annotation_review_recommended": summary.date_like_feature_label_count > 0,
    }


def _feature_label_is_date_like(value: str) -> bool:
    return _DATE_LIKE_FEATURE_LABEL_RE.fullmatch(value) is not None


def _feature_label_review(value: str) -> dict[str, Any]:
    """Attach the date-like source-label warning directly to one result row."""

    is_date_like = _feature_label_is_date_like(value)
    return {
        "possible_date_like_source_label": is_date_like,
        "manual_annotation_review_recommended": is_date_like,
        "source_label_preserved": True,
        "automatic_normalization_performed": False,
    }


def _read_feature_annotation_file(
    annotation_file: str | Path | None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Read an explicit source-to-curated identifier map without altering source IDs."""

    if annotation_file is None:
        return {}, {
            "status": "not_provided",
            "format": "csv",
            "mapping_entry_count": 0,
            "source_sha256": None,
        }

    payload = _safe_persistence.read_bytes(
        annotation_file,
        field="GEO feature annotation map",
        max_bytes=MAX_FEATURE_ANNOTATION_BYTES,
    )
    try:
        text = payload.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader, None)
        if header != ["source_feature_id", "curated_feature_id"]:
            raise ValidationError(
                "GEO feature annotation map requires the exact header "
                "source_feature_id,curated_feature_id"
            )
        annotations: dict[str, str] = {}
        for row_number, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            if len(row) != 2:
                raise ValidationError(
                    f"GEO feature annotation row {row_number} must contain exactly two columns"
                )
            source_id = _required_text(
                row[0], "GEO source feature identifier", maximum=256
            )
            curated_id = _required_text(
                row[1], "GEO curated feature identifier", maximum=256
            )
            if _FEATURE_RE.fullmatch(source_id) is None:
                raise ValidationError("GEO source feature identifier is malformed")
            if _FEATURE_RE.fullmatch(curated_id) is None:
                raise ValidationError("GEO curated feature identifier is malformed")
            if source_id in annotations:
                raise ValidationError("GEO feature annotation map repeats a source identifier")
            annotations[source_id] = curated_id
            if len(annotations) > MAX_FEATURE_ANNOTATION_ROWS:
                raise ValidationError("GEO feature annotation map exceeds its row limit")
    except UnicodeDecodeError as error:
        raise ValidationError("GEO feature annotation map must be UTF-8 CSV") from error
    except csv.Error as error:
        raise ValidationError("GEO feature annotation map is malformed CSV") from error

    if not annotations:
        raise ValidationError("GEO feature annotation map must contain at least one mapping")
    return annotations, {
        "status": "provided",
        "format": "csv",
        "mapping_entry_count": len(annotations),
        "source_sha256": f"sha256:{hashlib.sha256(payload).hexdigest()}",
    }


def _required_text(value: object, label: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be text")
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > maximum
        or any(ord(character) < 32 for character in normalized)
    ):
        raise ValidationError(f"{label} must be bounded non-empty text")
    return normalized


def validate_accession(accession: str) -> str:
    value = _required_text(accession, "GEO series accession", maximum=16).upper()
    if not _GSE_RE.fullmatch(value):
        raise ValidationError("GEO series accession must use the GSE numeric format")
    return value


def series_matrix_url(accession: str) -> str:
    """Return the canonical public Series Matrix URL for a GEO series."""

    normalized = validate_accession(accession)
    digits = normalized[3:]
    series_range = f"GSE{digits[:-3]}nnn"
    return (
        f"{GEO_FTP_ORIGIN}/geo/series/{series_range}/{normalized}/matrix/"
        f"{normalized}_series_matrix.txt.gz"
    )


def _csv_row(line: str, label: str) -> list[str]:
    try:
        rows = csv.reader([line], delimiter="\t", quotechar='"', strict=True)
        row = next(rows)
    except (csv.Error, StopIteration) as error:
        raise ValidationError(f"GEO {label} is not a valid tab-delimited row") from error
    if any(len(item) > MAX_METADATA_VALUE_LENGTH for item in row):
        raise ValidationError(f"GEO {label} contains an oversized field")
    return row


def _decoded_lines(payload: bytes, *, label: str = "Series Matrix") -> Iterable[tuple[str, int]]:
    stream: io.BufferedIOBase
    if payload.startswith(b"\x1f\x8b"):
        stream = gzip.GzipFile(fileobj=io.BytesIO(payload))
    else:
        stream = io.BytesIO(payload)
    total = 0
    first_line = True
    try:
        with stream:
            while True:
                raw_line = stream.readline(MAX_MATRIX_LINE_BYTES + 1)
                if not raw_line:
                    break
                if len(raw_line) > MAX_MATRIX_LINE_BYTES:
                    raise ValidationError(f"GEO {label} line exceeds its byte bound")
                total += len(raw_line)
                if total > MAX_DECOMPRESSED_BYTES:
                    raise ValidationError(f"GEO {label} exceeds its decompressed byte bound")
                try:
                    line = raw_line.decode("utf-8-sig" if first_line else "utf-8")
                except UnicodeDecodeError as error:
                    raise ValidationError(f"GEO {label} must use UTF-8 encoding") from error
                first_line = False
                yield line.rstrip("\r\n"), total
    except (EOFError, OSError, gzip.BadGzipFile, zlib.error) as error:
        raise ValidationError(f"GEO {label} gzip payload is incomplete or invalid") from error


def _metadata_value(row: list[str], label: str, *, allow_blank_values: bool = False) -> list[str]:
    if not row or not row[0].startswith("!"):
        raise ValidationError(f"GEO {label} row is malformed")
    values: list[str] = []
    for value in row[1:]:
        if allow_blank_values and not value.strip():
            values.append("")
            continue
        values.append(
            _required_text(value, f"GEO {label} value", maximum=MAX_METADATA_VALUE_LENGTH)
        )
    return values


def _parse_characteristic(value: str) -> tuple[str, str] | None:
    if not value.strip():
        return None
    if ":" not in value:
        return "unstructured", _required_text(value, "GEO sample characteristic")
    key, content = value.split(":", 1)
    return (
        _required_text(key, "GEO sample characteristic key", maximum=256),
        _required_text(content, "GEO sample characteristic value"),
    )


def _matrix_number(value: str) -> float | None:
    normalized = value.strip()
    if normalized.casefold() in _MISSING_MATRIX_VALUES:
        return None
    try:
        number = float(normalized)
    except (ValueError, OverflowError) as error:
        raise ValidationError("GEO expression matrix contains a non-numeric cell") from error
    if not math.isfinite(number):
        raise ValidationError("GEO expression matrix contains a non-finite cell")
    return number


def _finite_mean(values: Sequence[float]) -> float:
    return math.fsum(value / len(values) for value in values)


def _finite_median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return ordered[middle - 1] / 2.0 + ordered[middle] / 2.0


def _finite_distribution_summary(values: Sequence[int | float]) -> dict[str, int | float]:
    """Return bounded descriptive statistics without retaining source records."""

    if not values or any(not math.isfinite(float(value)) for value in values):
        raise ValidationError("GEO count quality summaries require finite observations")
    ordered = sorted(values)
    return {
        "sample_count": len(ordered),
        "minimum": ordered[0],
        "median": _finite_median(tuple(float(value) for value in ordered)),
        "maximum": ordered[-1],
    }


def _finite_difference(left: float, right: float) -> float | None:
    difference = left - right
    return difference if math.isfinite(difference) else None


def _effect_direction(value: float, *, zero_label: str) -> str:
    if value > 0.0:
        return "case_higher"
    if value < 0.0:
        return "case_lower"
    return zero_label


def _parse_series_matrix_features(
    payload: bytes,
    *,
    accession: str,
    feature_ids: frozenset[str] | None,
    source_file_name: str | None = None,
    retain_features: bool = True,
    feature_consumer: Callable[[GeoMatrixFeature], None] | None = None,
) -> GeoFeatureMatrix:
    """Parse a bounded matrix, retaining selected features or every feature."""

    requested_accession = validate_accession(accession)
    if not isinstance(retain_features, bool):
        raise ValidationError("GEO feature-retention option must be boolean")
    if feature_consumer is not None and not callable(feature_consumer):
        raise ValidationError("GEO feature consumer must be callable")
    if retain_features and feature_consumer is not None:
        raise ValidationError("GEO feature retention and streaming are mutually exclusive")
    if not isinstance(payload, bytes):
        raise ValidationError("GEO Series Matrix payload must be bytes")
    if len(payload) > MAX_COMPRESSED_BYTES:
        raise ValidationError("GEO Series Matrix exceeds its compressed byte bound")
    if feature_ids is not None:
        feature_ids = frozenset(
            _required_text(feature_id, "GEO feature ID", maximum=256) for feature_id in feature_ids
        )
        if not feature_ids or any(not _FEATURE_RE.fullmatch(item) for item in feature_ids):
            raise ValidationError("GEO feature IDs are empty or contain unsupported characters")
    if source_file_name is not None:
        source_file_name = _required_text(source_file_name, "GEO source file name", maximum=255)
        if Path(source_file_name).name != source_file_name or "\\" in source_file_name:
            raise ValidationError("GEO source file name must not contain a directory path")
    if type(payload) is not bytes or not payload or len(payload) > MAX_COMPRESSED_BYTES:
        raise ValidationError("GEO Series Matrix payload is empty or exceeds its byte bound")

    series: dict[str, list[str]] = {}
    sample_rows: dict[str, list[str]] = {}
    sample_characteristics: list[list[tuple[str, str] | None]] = []
    sample_processing: list[list[str]] = []
    samples: tuple[GeoSample, ...] = ()
    retained_features: list[GeoMatrixFeature] = []
    retained_feature_ids: set[str] = set()
    feature_count = 0
    metadata_row_count = 0
    matrix_header_seen = False
    matrix_end_seen = False
    decompressed_bytes = 0

    lines = iter(_decoded_lines(payload))
    for line, total in lines:
        decompressed_bytes = total
        if not line:
            continue
        if line == "!series_matrix_table_begin":
            if matrix_header_seen:
                raise ValidationError("GEO Series Matrix contains multiple expression tables")
            matrix_header_seen = True
            try:
                header_line, total = next(lines)
            except StopIteration as error:
                raise ValidationError("GEO Series Matrix table header is missing") from error
            decompressed_bytes = total
            header = _csv_row(header_line, "matrix header")
            sample_accessions = sample_rows.get("Sample_geo_accession", [])
            if not sample_accessions or len(sample_accessions) > MAX_SAMPLE_COUNT:
                raise ValidationError("GEO sample accession row is missing or oversized")
            if len(set(sample_accessions)) != len(sample_accessions):
                raise ValidationError("GEO sample accessions are not unique")
            if len(header) != len(sample_accessions) + 1 or header[0] != "ID_REF":
                raise ValidationError("GEO matrix columns do not match the sample accession row")
            if tuple(header[1:]) != tuple(sample_accessions):
                raise ValidationError("GEO matrix column order differs from sample metadata")
            samples = _build_samples(
                sample_accessions,
                sample_rows,
                sample_characteristics,
                sample_processing,
            )
            while True:
                try:
                    matrix_line, total = next(lines)
                except StopIteration:
                    break
                decompressed_bytes = total
                if matrix_line == "!series_matrix_table_end":
                    matrix_end_seen = True
                    break
                if not matrix_line:
                    continue
                if matrix_line.startswith("!"):
                    raise ValidationError(
                        "GEO Series Matrix contains an unexpected table directive"
                    )
                row = _csv_row(matrix_line, "expression row")
                if len(row) != len(header):
                    raise ValidationError("GEO expression row width differs from its matrix header")
                feature_count += 1
                if (
                    feature_count > MAX_FEATURE_COUNT
                    or feature_count * (len(header) - 1) > MAX_MATRIX_CELLS
                ):
                    raise ValidationError("GEO expression matrix exceeds its feature/cell bound")
                row_feature = _required_text(row[0], "GEO matrix feature ID", maximum=256)
                if feature_ids is None and not _FEATURE_RE.fullmatch(row_feature):
                    raise ValidationError("GEO matrix feature ID contains unsupported characters")
                selected_feature = feature_ids is None or row_feature in feature_ids
                if retain_features and selected_feature:
                    values = tuple(_matrix_number(value) for value in row[1:])
                    if row_feature in retained_feature_ids:
                        raise ValidationError("GEO matrix repeats a retained feature ID")
                    if feature_ids is None and len(retained_features) >= MAX_CONTRAST_FEATURES:
                        raise ValidationError(
                            "GEO feature screen exceeds its retained-feature bound"
                        )
                    retained_feature_ids.add(row_feature)
                    retained_features.append(GeoMatrixFeature(row_feature, values))
                elif feature_consumer is not None and selected_feature:
                    if row_feature in retained_feature_ids:
                        raise ValidationError("GEO streaming feature IDs are not unique")
                    if len(retained_feature_ids) >= MAX_CONTRAST_FEATURES:
                        raise ValidationError("GEO feature scan exceeds its unique-feature bound")
                    retained_feature_ids.add(row_feature)
                    feature_consumer(
                        GeoMatrixFeature(
                            row_feature,
                            tuple(_matrix_number(value) for value in row[1:]),
                        )
                    )
                else:
                    for value in row[1:]:
                        _matrix_number(value)
            if not matrix_end_seen:
                raise ValidationError("GEO Series Matrix expression table is incomplete")
            # Drain the stream so gzip checksums and decompressed-byte ceilings are verified.
            for trailing_line, total in lines:
                decompressed_bytes = total
                if trailing_line:
                    raise ValidationError("GEO Series Matrix contains data after its table end")
            break

        if line.startswith("!") and (line.startswith("!Series_") or line.startswith("!Sample_")):
            row = _csv_row(line, "metadata")
            if len(row) < 2:
                raise ValidationError("GEO metadata row has no values")
            key = row[0][1:]
            if key.startswith("Series_"):
                if key in {
                    "Series_geo_accession",
                    "Series_title",
                    "Series_type",
                    "Series_platform_id",
                }:
                    series.setdefault(key, []).extend(_metadata_value(row, key))
            elif key in {
                "Sample_geo_accession",
                "Sample_title",
                "Sample_source_name_ch1",
                "Sample_platform_id",
                "Sample_characteristics_ch1",
                "Sample_data_processing",
            }:
                metadata_row_count += 1
                if metadata_row_count > MAX_METADATA_ROWS:
                    raise ValidationError("GEO metadata row count exceeds its bound")
                values = _metadata_value(
                    row,
                    key,
                    allow_blank_values=key == "Sample_characteristics_ch1",
                )
                if key == "Sample_characteristics_ch1":
                    sample_characteristics.append(
                        [_parse_characteristic(value) for value in values]
                    )
                elif key == "Sample_data_processing":
                    sample_processing.append(values)
                else:
                    sample_rows.setdefault(key, []).extend(values)

    if not matrix_header_seen or not matrix_end_seen:
        raise ValidationError("GEO Series Matrix expression table is incomplete")
    if series.get("Series_geo_accession", []) != [requested_accession]:
        raise ValidationError("GEO Series Matrix accession differs from the requested series")
    if feature_ids is not None and retained_feature_ids != feature_ids:
        raise ValidationError("GEO Series Matrix does not contain every selected feature ID")
    if retain_features and not retained_features:
        raise ValidationError("GEO Series Matrix contains no retained expression features")
    titles = series.get("Series_title", [])
    series_types = tuple(dict.fromkeys(series.get("Series_type", [])))
    platform_ids = tuple(dict.fromkeys(series.get("Series_platform_id", [])))
    if not platform_ids:
        platform_ids = tuple(
            dict.fromkeys(sample.platform_id for sample in samples if sample.platform_id)
        )
    processing = tuple(dict.fromkeys(value for row in sample_processing for value in row))
    return GeoFeatureMatrix(
        accession=requested_accession,
        title=titles[0] if titles else "",
        series_types=series_types,
        platform_ids=platform_ids,
        samples=samples,
        processing_descriptions=processing[:16],
        feature_count=feature_count,
        features=tuple(retained_features),
        source_sha256=hashlib.sha256(payload).hexdigest(),
        source_url=series_matrix_url(requested_accession),
        source_file_name=source_file_name,
        compressed_bytes=len(payload),
        decompressed_bytes=decompressed_bytes,
    )


def parse_series_matrix(
    payload: bytes,
    *,
    accession: str,
    feature_id: str,
    source_file_name: str | None = None,
) -> GeoSeriesMatrix:
    """Parse one bounded GEO matrix and retain values for exactly one feature."""

    selected_feature = _required_text(feature_id, "GEO feature ID", maximum=256)
    if not _FEATURE_RE.fullmatch(selected_feature):
        raise ValidationError("GEO feature ID contains unsupported characters")
    matrix = _parse_series_matrix_features(
        payload,
        accession=accession,
        feature_ids=frozenset({selected_feature}),
        source_file_name=source_file_name,
    )
    feature = matrix.features[0]
    return GeoSeriesMatrix(
        accession=matrix.accession,
        title=matrix.title,
        series_types=matrix.series_types,
        platform_ids=matrix.platform_ids,
        samples=matrix.samples,
        processing_descriptions=matrix.processing_descriptions,
        feature_count=matrix.feature_count,
        feature_id=feature.feature_id,
        feature_values=feature.values,
        source_sha256=matrix.source_sha256,
        source_url=matrix.source_url,
        source_file_name=matrix.source_file_name,
        compressed_bytes=matrix.compressed_bytes,
        decompressed_bytes=matrix.decompressed_bytes,
    )


def parse_series_matrix_features(
    payload: bytes,
    *,
    accession: str,
    source_file_name: str | None = None,
) -> GeoFeatureMatrix:
    """Parse a bounded GEO matrix while retaining its complete feature table."""

    return _parse_series_matrix_features(
        payload,
        accession=accession,
        feature_ids=None,
        source_file_name=source_file_name,
    )


def parse_series_matrix_metadata(
    payload: bytes,
    *,
    accession: str,
    source_file_name: str | None = None,
) -> GeoMatrixMetadata:
    """Validate a bounded Series Matrix while retaining metadata, not feature vectors."""

    matrix = _parse_series_matrix_features(
        payload,
        accession=accession,
        feature_ids=None,
        source_file_name=source_file_name,
        retain_features=False,
    )
    return _matrix_metadata(matrix)


def scan_series_matrix_features(
    payload: bytes,
    *,
    accession: str,
    feature_consumer: Callable[[GeoMatrixFeature], None],
    source_file_name: str | None = None,
) -> GeoMatrixMetadata:
    """Validate a matrix and deliver each feature row without retaining the table."""

    if not callable(feature_consumer):
        raise ValidationError("GEO feature consumer must be callable")
    matrix = _parse_series_matrix_features(
        payload,
        accession=accession,
        feature_ids=None,
        source_file_name=source_file_name,
        retain_features=False,
        feature_consumer=feature_consumer,
    )
    return _matrix_metadata(matrix)


def _matrix_metadata(matrix: GeoFeatureMatrix) -> GeoMatrixMetadata:
    return GeoMatrixMetadata(
        accession=matrix.accession,
        title=matrix.title,
        series_types=matrix.series_types,
        platform_ids=matrix.platform_ids,
        samples=matrix.samples,
        processing_descriptions=matrix.processing_descriptions,
        feature_count=matrix.feature_count,
        source_sha256=matrix.source_sha256,
        source_url=matrix.source_url,
        source_file_name=matrix.source_file_name,
        compressed_bytes=matrix.compressed_bytes,
        decompressed_bytes=matrix.decompressed_bytes,
    )


def _build_samples(
    accessions: Sequence[str],
    sample_rows: dict[str, list[str]],
    characteristic_rows: Sequence[Sequence[tuple[str, str] | None]],
    processing_rows: Sequence[Sequence[str]],
) -> tuple[GeoSample, ...]:
    count = len(accessions)
    if any(not _GSM_RE.fullmatch(sample_id) for sample_id in accessions):
        raise ValidationError("GEO sample accession row contains a non-GSM identifier")
    if any(len(values) != count for values in sample_rows.values()):
        raise ValidationError("GEO sample metadata count differs from sample accessions")
    if any(len(values) != count for values in characteristic_rows):
        raise ValidationError("GEO characteristic count differs from sample accessions")
    if any(len(values) != count for values in processing_rows):
        raise ValidationError("GEO processing metadata count differs from sample accessions")
    titles = sample_rows.get("Sample_title", list(accessions))
    sources = sample_rows.get("Sample_source_name_ch1", [""] * count)
    platforms = sample_rows.get("Sample_platform_id", [""] * count)
    characteristics: list[list[tuple[str, str]]] = [[] for _ in range(count)]
    for row in characteristic_rows:
        for index, pair in enumerate(row):
            if pair is not None:
                characteristics[index].append(pair)
    return tuple(
        GeoSample(
            accession=sample_id,
            title=titles[index],
            source_name=sources[index],
            platform_id=platforms[index],
            characteristics=tuple(characteristics[index]),
        )
        for index, sample_id in enumerate(accessions)
    )


def _read_matrix(
    accession: str,
    *,
    matrix_file: str | Path | None,
    timeout_seconds: float,
) -> tuple[bytes, str | None, str | None]:
    if matrix_file is not None:
        path = Path(matrix_file)
        payload = _safe_persistence.read_bytes(
            path,
            field="GEO matrix file",
            max_bytes=MAX_COMPRESSED_BYTES,
        )
        return payload, None, path.name
    url = series_matrix_url(accession)
    response = UrllibTransport(max_response_bytes=MAX_COMPRESSED_BYTES).request(
        "GET",
        url,
        {
            "Accept": "application/gzip, application/octet-stream;q=0.9",
            "User-Agent": "glio-noncode/0.1",
        },
        timeout_seconds,
    )
    if response.status == 404:
        raise SourceNotFoundError("canonical GEO Series Matrix file was not found")
    if response.status != 200:
        raise SourceError(f"NCBI GEO returned HTTP {response.status}")
    return response.body, response.url, None


def _supplementary_file_name(value: object, label: str) -> str:
    name = _required_text(value, label, maximum=255)
    if _SUPPLEMENTARY_FILE_NAME_RE.fullmatch(name) is None or name in {".", ".."}:
        raise ValidationError(f"{label} must be a simple file name, not a path")
    return name


def geo_series_supplementary_url(accession: str, file_name: str) -> str:
    """Return the canonical NCBI GEO URL for one series supplementary file."""

    normalized = validate_accession(accession)
    name = _supplementary_file_name(file_name, "GEO supplementary file name")
    digits = normalized[3:]
    series_range = f"GSE{digits[:-3]}nnn"
    return f"{GEO_FTP_ORIGIN}/geo/series/{series_range}/{normalized}/suppl/{name}"


def _read_supplementary_file(
    accession: str,
    *,
    label: str,
    file_name: str | None,
    local_file: str | Path | None,
    timeout_seconds: float,
) -> tuple[bytes, str, str | None, str | None]:
    if local_file is not None:
        path = Path(local_file)
        payload = _safe_persistence.read_bytes(
            path,
            field=f"GEO {label} file",
            max_bytes=MAX_COMPRESSED_BYTES,
        )
        local_name = _supplementary_file_name(path.name, f"GEO {label} file name")
        if (
            file_name is not None
            and _supplementary_file_name(file_name, f"GEO {label} file name") != local_name
        ):
            raise ValidationError(f"local GEO {label} file name does not match its declaration")
        return payload, local_name, None, None

    if file_name is None:
        raise ValidationError(f"GEO {label} requires a local file or supplementary file name")
    name = _supplementary_file_name(file_name, f"GEO {label} file name")
    url = geo_series_supplementary_url(accession, name)
    response = UrllibTransport(max_response_bytes=MAX_COMPRESSED_BYTES).request(
        "GET",
        url,
        {
            "Accept": "application/gzip, application/octet-stream;q=0.9",
            "User-Agent": "glio-noncode/0.1",
        },
        timeout_seconds,
    )
    if response.status == 404:
        raise SourceNotFoundError(f"GEO supplementary {label} file was not found")
    if response.status != 200:
        raise SourceError(f"NCBI GEO returned HTTP {response.status} for supplementary {label}")
    return response.body, name, response.url, response.url


def _normalize_delimiter(value: object, label: str) -> str:
    if not isinstance(value, str) or value not in {",", "\t"}:
        raise ValidationError(f"{label} must be comma or tab")
    return str(value)


def _iter_geo_supplementary_count_rows(
    payload: bytes,
    *,
    delimiter: str,
    summary: _GeoCountTableSummary,
) -> Iterator[tuple[str, tuple[int, ...]]]:
    if not isinstance(payload, bytes) or len(payload) > MAX_COMPRESSED_BYTES:
        raise ValidationError("GEO supplementary count matrix exceeds its compressed byte bound")
    normalized_delimiter = _normalize_delimiter(delimiter, "GEO count matrix delimiter")
    decompressed_bytes = 0

    def decoded_text_lines() -> Iterable[str]:
        nonlocal decompressed_bytes
        for line, total in _decoded_lines(payload, label="supplementary count matrix"):
            decompressed_bytes = total
            yield line

    reader = csv.reader(decoded_text_lines(), delimiter=normalized_delimiter, strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error) as error:
        raise ValidationError("GEO supplementary count matrix has no valid header") from error
    if len(header) < 2 or len(header) - 1 > MAX_SAMPLE_COUNT:
        raise ValidationError("GEO supplementary count matrix has an invalid sample count")
    sample_ids = tuple(
        _required_text(sample_id, "GEO count matrix sample key", maximum=256)
        for sample_id in header[1:]
    )
    if len(sample_ids) != len(set(sample_ids)):
        raise ValidationError("GEO count matrix contains duplicate sample keys")

    summary.sample_ids = sample_ids
    summary.library_sizes = [0] * len(sample_ids)
    seen_features: set[str] = set()
    try:
        for row in reader:
            if not row or len(row) != len(header):
                raise ValidationError("GEO supplementary count matrix contains a ragged row")
            current_feature = _required_text(
                row[0], "GEO count matrix feature identifier", maximum=256
            )
            if _FEATURE_RE.fullmatch(current_feature) is None:
                raise ValidationError("GEO count matrix feature identifier is malformed")
            summary.feature_count += 1
            if summary.feature_count > MAX_FEATURE_COUNT:
                raise ValidationError("GEO supplementary count matrix exceeds its feature limit")
            if summary.feature_count * len(sample_ids) > MAX_MATRIX_CELLS:
                raise ValidationError("GEO supplementary count matrix exceeds its cell limit")
            if current_feature in seen_features:
                summary.duplicate_feature_label_count += 1
                summary.duplicate_feature_ids.add(current_feature)
            else:
                if _feature_label_is_date_like(current_feature):
                    summary.date_like_feature_label_count += 1
                    if (
                        len(summary.date_like_feature_labels)
                        < _MAX_REPORTED_DATE_LIKE_FEATURE_LABELS
                    ):
                        summary.date_like_feature_labels.append(current_feature)
            seen_features.add(current_feature)

            counts: list[int] = []
            for raw_count in row[1:]:
                value = raw_count.strip()
                if len(value) > 19 or re.fullmatch(r"[0-9]{1,19}", value) is None:
                    raise ValidationError("GEO supplementary count matrix requires integer counts")
                count = int(value)
                if count > 9_223_372_036_854_775_807:
                    raise ValidationError("GEO supplementary count exceeds the signed 64-bit limit")
                counts.append(count)
            for index, count in enumerate(counts):
                summary.library_sizes[index] += count
            yield current_feature, tuple(counts)
    except csv.Error as error:
        raise ValidationError(
            "GEO supplementary count matrix is not valid delimited text"
        ) from error

    summary.decompressed_bytes = decompressed_bytes
    if summary.feature_count == 0 or decompressed_bytes == 0:
        raise ValidationError("GEO supplementary count matrix is empty")
    if any(total == 0 for total in summary.library_sizes):
        raise ValidationError("GEO count matrix contains a zero-size sample library")


def _normalize_count_normalization_method(value: object) -> str:
    if not isinstance(value, str) or value not in GEO_COUNT_NORMALIZATION_METHODS:
        accepted = ", ".join(GEO_COUNT_NORMALIZATION_METHODS)
        raise ValidationError(f"GEO count normalization method must be one of: {accepted}")
    return value


def _trimmed_tmm_value_bounds(
    ordered_values: Sequence[float], trim_fraction: float
) -> tuple[float, float] | None:
    """Return the inclusive value range retained by average-rank trimming."""

    observation_count = len(ordered_values)
    first_rank = math.floor(observation_count * trim_fraction) + 1
    last_rank = observation_count + 1 - first_rank
    lower_bound: float | None = None
    upper_bound: float | None = None
    index = 0
    while index < observation_count:
        end = index + 1
        while end < observation_count and ordered_values[end] == ordered_values[index]:
            end += 1
        average_rank = (index + 1 + end) / 2.0
        if first_rank <= average_rank <= last_rank:
            if lower_bound is None:
                lower_bound = ordered_values[index]
            upper_bound = ordered_values[index]
        index = end
    if lower_bound is None or upper_bound is None:
        return None
    return lower_bound, upper_bound


def _estimate_geo_tmm_factors(
    payload: bytes,
    *,
    delimiter: str,
    library_sizes: Sequence[int],
    duplicate_feature_ids: set[str] | frozenset[str],
) -> tuple[float, ...]:
    """Estimate edgeR-style TMM scaling factors from unique count rows.

    The matrix cell limit bounds the packed count storage. Repeated feature IDs
    are omitted from normalization because their biological identity is
    ambiguous; they remain included in the original library-size totals.
    """

    summary = _GeoCountTableSummary()
    columns: list[array[int]] | None = None
    for feature_id, counts in _iter_geo_supplementary_count_rows(
        payload, delimiter=delimiter, summary=summary
    ):
        if columns is None:
            columns = [array("Q") for _ in counts]
        if feature_id in duplicate_feature_ids or not any(counts):
            continue
        for index, count in enumerate(counts):
            columns[index].append(count)

    if tuple(summary.library_sizes) != tuple(library_sizes):
        raise ValidationError("GEO count matrix library totals changed during normalization")
    if columns is None or not columns[0]:
        raise ValidationError("TMM normalization has no uniquely identified features")
    sample_count = len(columns)
    if sample_count == 1:
        return (1.0,)

    # edgeR chooses the library whose CPM upper quartile is closest to the
    # cohort mean upper quartile. Use the standard type-7 interpolated quantile.
    upper_quartiles: list[float] = []
    for column, library_size in zip(columns, library_sizes, strict=True):
        ordered_counts = sorted(column)
        position = 0.75 * (len(ordered_counts) - 1)
        lower_index = math.floor(position)
        upper_index = math.ceil(position)
        fraction = position - lower_index
        quantile = ordered_counts[lower_index] * (1.0 - fraction)
        quantile += ordered_counts[upper_index] * fraction
        upper_quartiles.append(quantile / library_size * 1_000_000.0)
    mean_upper_quartile = math.fsum(upper_quartiles) / sample_count
    if _finite_median(upper_quartiles) < 1e-20:
        reference_index = max(
            range(sample_count),
            key=lambda index: math.fsum(math.sqrt(value) for value in columns[index]),
        )
    else:
        reference_index = min(
            range(sample_count),
            key=lambda index: abs(upper_quartiles[index] - mean_upper_quartile),
        )
    reference_library_size = library_sizes[reference_index]
    reference_counts = columns[reference_index]
    factors = [1.0] * sample_count

    for sample_index, (sample_counts, sample_library_size) in enumerate(
        zip(columns, library_sizes, strict=True)
    ):
        if sample_index == reference_index:
            continue
        records: list[tuple[float, float, float]] = []
        for sample_count_value, reference_count_value in zip(
            sample_counts, reference_counts, strict=True
        ):
            if sample_count_value == 0 or reference_count_value == 0:
                continue
            sample_proportion = sample_count_value / sample_library_size
            reference_proportion = reference_count_value / reference_library_size
            log_ratio = math.log2(sample_proportion / reference_proportion)
            average_log_expression = 0.5 * math.log2(
                sample_proportion * reference_proportion
            )
            variance = (
                1.0 / sample_count_value
                - 1.0 / sample_library_size
                + 1.0 / reference_count_value
                - 1.0 / reference_library_size
            )
            if variance > 0.0 and math.isfinite(variance):
                records.append((log_ratio, average_log_expression, 1.0 / variance))
        if not records:
            raise ValidationError("TMM normalization has no shared positive-count features")
        if max(abs(record[0]) for record in records) < 1e-6:
            factors[sample_index] = 1.0
            continue

        m_trim = math.floor(len(records) * 0.30)
        a_trim = math.floor(len(records) * 0.05)
        records.sort(key=lambda record: record[0])
        m_bounds = _trimmed_tmm_value_bounds(
            [record[0] for record in records], m_trim / len(records)
        )
        records.sort(key=lambda record: record[1])
        a_bounds = _trimmed_tmm_value_bounds(
            [record[1] for record in records], a_trim / len(records)
        )
        if m_bounds is None or a_bounds is None:
            raise ValidationError("TMM trimming left no features for a normalization factor")
        records = [
            record
            for record in records
            if m_bounds[0] <= record[0] <= m_bounds[1]
            and a_bounds[0] <= record[1] <= a_bounds[1]
        ]
        if not records:
            raise ValidationError("TMM trimming left no features for a normalization factor")
        weighted_mean = math.fsum(
            m_value * weight for m_value, _, weight in records
        ) / math.fsum(weight for _, _, weight in records)
        factors[sample_index] = 2.0**weighted_mean

    geometric_mean = math.exp(math.fsum(math.log(factor) for factor in factors) / sample_count)
    normalized_factors = tuple(factor / geometric_mean for factor in factors)
    if any(not math.isfinite(factor) or factor <= 0.0 for factor in normalized_factors):
        raise ValidationError("TMM normalization produced a non-finite factor")
    return normalized_factors


def _count_normalization_report(
    method: str, factors: Sequence[float]
) -> dict[str, Any]:
    tmm_used = method == "tmm_log2_cpm"
    return {
        "method": method,
        "expression_scale": "log2(count / effective_library_size * 1,000,000 + 1)",
        "effective_library_size": (
            "raw library size multiplied by a TMM normalization factor"
            if tmm_used
            else "raw library size"
        ),
        "normalization_factor_summary": _finite_distribution_summary(factors),
        "tmm_reference": (
            "sample whose CPM upper quartile is closest to the cohort mean"
            if tmm_used
            else None
        ),
        "tmm_trim": (
            {"log_ratio_each_tail": 0.30, "average_abundance_each_tail": 0.05}
            if tmm_used
            else None
        ),
        "duplicate_feature_policy": (
            "exclude duplicated feature IDs from factor estimation; retain all rows "
            "in raw library sizes"
            if tmm_used
            else "not applicable"
        ),
    }


def parse_geo_supplementary_count_matrix(
    payload: bytes,
    *,
    accession: str,
    feature_id: str,
    delimiter: str = ",",
    source_file_name: str = "count-matrix.csv.gz",
    source_url: str | None = None,
    annotation_source_ids: frozenset[str] = frozenset(),
    normalization_method: str = "log2_cpm",
) -> _GeoCountMatrix:
    """Parse one bounded gene-by-sample integer-count table for one feature.

    The parser retains only the requested row and per-sample library totals.
    Other repeated feature labels are counted but preserved in those totals.
    """

    normalized_accession = validate_accession(accession)
    normalized_normalization_method = _normalize_count_normalization_method(normalization_method)
    selected_feature = _required_text(feature_id, "GEO gene feature ID", maximum=256)
    if _FEATURE_RE.fullmatch(selected_feature) is None:
        raise ValidationError("GEO gene feature ID contains unsupported characters")
    file_name = _supplementary_file_name(source_file_name, "GEO count matrix file name")
    if source_url is not None:
        expected_url = geo_series_supplementary_url(normalized_accession, file_name)
        if source_url != expected_url:
            raise ValidationError("GEO count matrix source URL is not canonical")
    summary = _GeoCountTableSummary()
    selected_counts: tuple[int, ...] | None = None
    found_annotation_source_ids: set[str] = set()
    duplicate_annotation_source_ids: set[str] = set()
    for current_feature, counts in _iter_geo_supplementary_count_rows(
        payload, delimiter=delimiter, summary=summary
    ):
        if current_feature in annotation_source_ids:
            if current_feature in found_annotation_source_ids:
                duplicate_annotation_source_ids.add(current_feature)
            else:
                found_annotation_source_ids.add(current_feature)
        if current_feature == selected_feature:
            if selected_counts is not None:
                raise ValidationError("requested GEO feature appears more than once")
            selected_counts = counts

    if selected_counts is None:
        raise ValidationError("requested GEO feature is absent from the count matrix")
    normalization_factors = (
        _estimate_geo_tmm_factors(
            payload,
            delimiter=delimiter,
            library_sizes=summary.library_sizes,
            duplicate_feature_ids=summary.duplicate_feature_ids,
        )
        if normalized_normalization_method == "tmm_log2_cpm"
        else (1.0,) * len(summary.sample_ids)
    )
    return _GeoCountMatrix(
        accession=normalized_accession,
        feature_id=selected_feature,
        sample_ids=summary.sample_ids,
        feature_counts=selected_counts,
        library_sizes=tuple(summary.library_sizes),
        feature_count=summary.feature_count,
        duplicate_feature_label_count=summary.duplicate_feature_label_count,
        source_file_name=file_name,
        source_url=source_url,
        source_sha256=hashlib.sha256(payload).hexdigest(),
        compressed_bytes=len(payload),
        decompressed_bytes=summary.decompressed_bytes,
        annotation_source_ids_found=tuple(sorted(found_annotation_source_ids)),
        duplicate_annotation_source_ids=tuple(sorted(duplicate_annotation_source_ids)),
        normalization_factors=normalization_factors,
    )


def _parse_geo_count_metadata(
    payload: bytes,
    *,
    sample_ids: Sequence[str],
    sample_key_column: str,
    requested_fields: Sequence[str],
    delimiter: str,
    require_exact_sample_set: bool = True,
) -> tuple[dict[str, dict[str, str]], tuple[str, ...], int]:
    if type(require_exact_sample_set) is not bool:
        raise ValidationError("GEO exact sample-key join policy must be boolean")
    if not isinstance(sample_key_column, str) or len(sample_key_column) > 256:
        raise ValidationError("GEO metadata sample-key column must be a bounded string")
    if any(ord(character) < 32 for character in sample_key_column):
        raise ValidationError("GEO metadata sample-key column contains control characters")
    normalized_delimiter = _normalize_delimiter(delimiter, "GEO metadata delimiter")
    if not isinstance(payload, bytes) or len(payload) > MAX_COMPRESSED_BYTES:
        raise ValidationError("GEO supplementary metadata exceeds its compressed byte bound")

    decompressed_bytes = 0

    def decoded_text_lines() -> Iterable[str]:
        nonlocal decompressed_bytes
        for line, total in _decoded_lines(payload, label="supplementary sample metadata"):
            decompressed_bytes = total
            yield line

    reader = csv.reader(decoded_text_lines(), delimiter=normalized_delimiter, strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error) as error:
        raise ValidationError("GEO supplementary sample metadata has no valid header") from error
    if not header or len(header) > 256:
        raise ValidationError("GEO supplementary sample metadata has an invalid column count")
    if any(len(name) > 256 or any(ord(char) < 32 for char in name) for name in header):
        raise ValidationError("GEO supplementary sample metadata has an invalid column name")
    normalized_headers = [name.casefold() for name in header]
    if len(normalized_headers) != len(set(normalized_headers)):
        raise ValidationError("GEO supplementary sample metadata has duplicate columns")
    sample_key_indexes = [index for index, name in enumerate(header) if name == sample_key_column]
    if len(sample_key_indexes) != 1:
        raise ValidationError("GEO metadata sample-key column must match one exact header")
    sample_key_index = sample_key_indexes[0]
    field_indexes: dict[str, int] = {}
    for requested_field in requested_fields:
        matches = [
            index
            for index, name in enumerate(header)
            if name.casefold() == requested_field.casefold()
        ]
        if len(matches) != 1:
            raise ValidationError("one or more GEO sample filter fields are absent from metadata")
        field_indexes[header[matches[0]]] = matches[0]

    records: dict[str, dict[str, str]] = {}
    try:
        for row in reader:
            if not row or len(row) != len(header):
                raise ValidationError("GEO supplementary sample metadata contains a ragged row")
            sample_id = _required_text(
                row[sample_key_index], "GEO metadata sample key", maximum=256
            )
            if sample_id in records:
                raise ValidationError("GEO supplementary sample metadata has duplicate sample keys")
            if len(records) >= MAX_METADATA_ROWS:
                raise ValidationError("GEO supplementary sample metadata exceeds its row limit")
            if any(
                len(value) > MAX_METADATA_VALUE_LENGTH
                or any(ord(character) < 32 for character in value)
                for value in row
            ):
                raise ValidationError("GEO supplementary sample metadata contains invalid values")
            records[sample_id] = {header[index]: row[index] for index in field_indexes.values()}
    except csv.Error as error:
        raise ValidationError(
            "GEO supplementary sample metadata is not valid delimited text"
        ) from error

    if require_exact_sample_set and set(records) != set(sample_ids):
        raise ValidationError("GEO count matrix and sample metadata keys do not match exactly")
    if decompressed_bytes == 0:
        raise ValidationError("GEO supplementary sample metadata is empty")
    return records, tuple(header), decompressed_bytes


def _normalize_filters(value: object, label: str) -> list[tuple[str, str]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValidationError(f"{label} filters must be a sequence of field/value pairs")
    if not value or len(value) > 32:
        raise ValidationError(f"one to 32 explicit {label} filters are required")
    normalized: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, Sequence) or isinstance(item, (str, bytes)) or len(item) != 2:
            raise ValidationError(f"each {label} filter must contain one field and one value")
        field = _required_text(item[0], f"{label} characteristic field", maximum=256)
        expected = _required_text(item[1], f"{label} characteristic value", maximum=1024)
        if any(field.casefold() == prior[0].casefold() for prior in normalized):
            raise ValidationError(f"{label} characteristic fields must be unique")
        normalized.append((field, expected))
    return normalized


def _normalize_tracked_feature_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValidationError("tracked GEO feature IDs must be supplied as a sequence")
    if len(value) > MAX_TRACKED_GEO_FEATURES:
        raise ValidationError(
            f"at most {MAX_TRACKED_GEO_FEATURES} GEO feature IDs can be tracked per contrast"
        )
    normalized: list[str] = []
    for feature_id in value:
        if not isinstance(feature_id, str) or feature_id != feature_id.strip():
            raise ValidationError("tracked GEO feature ID uses an unsupported identifier format")
        text = _required_text(feature_id, "tracked GEO feature ID", maximum=256)
        if not _FEATURE_RE.fullmatch(text):
            raise ValidationError("tracked GEO feature ID uses an unsupported identifier format")
        normalized.append(text)
    if len(set(normalized)) != len(normalized):
        raise ValidationError("tracked GEO feature IDs must be unique")
    return tuple(normalized)


def _normalize_covariates(value: object) -> list[tuple[str, str]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValidationError("GEO covariates must be a sequence of field/type pairs")
    if len(value) > MAX_GEO_COVARIATES:
        raise ValidationError(f"at most {MAX_GEO_COVARIATES} GEO covariates are supported")
    normalized: list[tuple[str, str]] = []
    for item in value:
        if isinstance(item, (str, bytes)) or not isinstance(item, Sequence) or len(item) != 2:
            raise ValidationError("each GEO covariate must contain one field and one type")
        field = _required_text(item[0], "GEO covariate field", maximum=256)
        kind = _required_text(item[1], "GEO covariate type", maximum=32).casefold()
        if kind not in {"continuous", "categorical"}:
            raise ValidationError("GEO covariate type must be continuous or categorical")
        if any(field.casefold() == prior[0].casefold() for prior in normalized):
            raise ValidationError("GEO covariate fields must be unique")
        normalized.append((field, kind))
    return normalized


def _prepare_geo_contrast(
    matrix: GeoFeatureMatrix | GeoMatrixMetadata,
    *,
    case_indices: Sequence[int],
    reference_indices: Sequence[int],
    covariates: Sequence[tuple[str, str]],
) -> _PreparedGeoContrast:
    case_set = set(case_indices)
    reference_set = set(reference_indices)
    selected_indices = tuple(
        index for index in range(len(matrix.samples)) if index in case_set or index in reference_set
    )
    parsed: dict[int, dict[str, float | str]] = {}
    excluded: set[int] = set()
    missing_markers = _MISSING_MATRIX_VALUES | {"n/a", "none"}

    for sample_index in selected_indices:
        sample = matrix.samples[sample_index]
        sample_covariates: dict[str, float | str] = {}
        incomplete = False
        for field, kind in covariates:
            raw_values = sample.values_for((field,))[field]
            values = [
                candidate.strip()
                for candidate in raw_values
                if candidate.strip().casefold() not in missing_markers
            ]
            if not values:
                incomplete = True
                continue
            if kind == "continuous":
                try:
                    numeric_values = [float(raw_value) for raw_value in values]
                except ValueError as error:
                    raise ValidationError(
                        f"continuous GEO covariate {field} contains a non-numeric value"
                    ) from error
                if any(not math.isfinite(value) for value in numeric_values):
                    raise ValidationError(
                        f"continuous GEO covariate {field} contains a non-finite value"
                    )
                if len(set(numeric_values)) > 1:
                    raise ValidationError(
                        f"sample {sample.accession} has multiple values for GEO covariate {field}"
                    )
                sample_covariates[field] = numeric_values[0]
            else:
                distinct = {candidate.casefold() for candidate in values}
                if len(distinct) > 1:
                    raise ValidationError(
                        f"sample {sample.accession} has multiple values for GEO covariate {field}"
                    )
                sample_covariates[field] = values[0]
        if incomplete:
            excluded.add(sample_index)
        else:
            parsed[sample_index] = sample_covariates

    complete_indices = tuple(index for index in selected_indices if index not in excluded)
    complete_case_indices = tuple(index for index in complete_indices if index in case_set)
    complete_reference_indices = tuple(
        index for index in complete_indices if index in reference_set
    )
    if len(complete_case_indices) < 2 or len(complete_reference_indices) < 2:
        raise ValidationError("covariate-complete model needs at least two samples in each group")

    parameter_names = ["intercept", "group_case_minus_reference"]
    metadata: list[dict[str, Any]] = []
    encoded_covariates: dict[str, tuple[tuple[str, float], ...]] = {}
    for covariate_index, (field, kind) in enumerate(covariates):
        if kind == "continuous":
            values = [float(parsed[index][field]) for index in complete_indices]
            magnitude = max(abs(value) for value in values)
            if magnitude == 0.0:
                raise ValidationError(f"continuous GEO covariate {field} is constant")
            scaled_values = [value / magnitude for value in values]
            scaled_center = math.fsum(scaled_values) / len(scaled_values)
            centered = [value - scaled_center for value in scaled_values]
            scaled_standard_deviation = math.sqrt(
                math.fsum(value * value for value in centered) / len(centered)
            )
            if scaled_standard_deviation == 0.0:
                raise ValidationError(f"continuous GEO covariate {field} is constant")
            center = scaled_center * magnitude
            standard_deviation = scaled_standard_deviation * magnitude
            parameter_name = f"covariate_{covariate_index + 1}:{field}_standardized"
            encoded_covariates[field] = tuple(
                (
                    parameter_name,
                    (float(parsed[index][field]) / magnitude - scaled_center)
                    / scaled_standard_deviation,
                )
                for index in complete_indices
            )
            parameter_names.append(parameter_name)
            metadata.append(
                {
                    "field": field,
                    "type": kind,
                    "encoding": "centered_and_scaled_by_population_standard_deviation",
                    "center": center,
                    "scale": standard_deviation,
                    "parameter": parameter_name,
                }
            )
            continue

        level_by_key: dict[str, str] = {}
        for index in complete_indices:
            value = str(parsed[index][field])
            key = value.casefold()
            maximum_levels = MAX_GEO_MODEL_PARAMETERS - len(parameter_names) + 1
            if key not in level_by_key and len(level_by_key) >= maximum_levels:
                raise ValidationError(
                    f"GEO adjusted model exceeds {MAX_GEO_MODEL_PARAMETERS} parameters"
                )
            level_by_key.setdefault(key, value)
        levels = sorted(level_by_key.values(), key=lambda value: (value.casefold(), value))
        if len(levels) < 2:
            raise ValidationError(f"categorical GEO covariate {field} has fewer than two levels")
        reference_level = levels[0]
        categorical_parameters = [
            (level, f"covariate_{covariate_index + 1}:{field}[{level}]") for level in levels[1:]
        ]
        for _level, parameter in categorical_parameters:
            parameter_names.append(parameter)
        metadata.append(
            {
                "field": field,
                "type": kind,
                "encoding": "treatment_coded",
                "levels": levels,
                "reference_level": reference_level,
                "parameters": [parameter for _, parameter in categorical_parameters],
            }
        )

    if len(parameter_names) > MAX_GEO_MODEL_PARAMETERS:
        raise ValidationError(f"GEO adjusted model exceeds {MAX_GEO_MODEL_PARAMETERS} parameters")
    residual_degrees_of_freedom = len(complete_indices) - len(parameter_names)
    if residual_degrees_of_freedom < 3:
        raise ValidationError(
            "GEO adjusted model requires at least three residual degrees of freedom"
        )

    # Reconstruct columns in the declared parameter order, with treatment-coded levels.
    columns: list[tuple[float, ...]] = [
        tuple(1.0 for _ in complete_indices),
        tuple(1.0 if index in case_set else 0.0 for index in complete_indices),
    ]
    for field, kind in covariates:
        if kind == "continuous":
            columns.append(tuple(value for _, value in encoded_covariates[field]))
        else:
            covariate_info = next(item for item in metadata if item["field"] == field)
            for level in covariate_info["levels"][1:]:
                columns.append(
                    tuple(
                        1.0 if str(parsed[index][field]).casefold() == level.casefold() else 0.0
                        for index in complete_indices
                    )
                )
    design_rows = [
        tuple(column[row_index] for column in columns) for row_index in range(len(complete_indices))
    ]
    model = prepare_linear_model(design_rows, contrast_index=1)
    return _PreparedGeoContrast(
        model=model,
        sample_indices=complete_indices,
        case_indices=complete_case_indices,
        reference_indices=complete_reference_indices,
        parameter_names=tuple(parameter_names),
        covariate_metadata=tuple(metadata),
        excluded_case_indices=tuple(
            index for index in selected_indices if index in excluded and index in case_set
        ),
        excluded_reference_indices=tuple(
            index for index in selected_indices if index in excluded and index in reference_set
        ),
    )


def _mann_whitney_test(
    case_values: Sequence[float],
    reference_values: Sequence[float],
    *,
    assignment_limit: int,
) -> tuple[float, float, str]:
    """Return rank-biserial effect, two-sided p-value, and test method."""

    pooled = [(value, index) for index, value in enumerate((*case_values, *reference_values))]
    pooled.sort(key=lambda item: (item[0], item[1]))
    doubled_ranks = [0] * len(pooled)
    tie_sizes: list[int] = []
    start = 0
    while start < len(pooled):
        end = start + 1
        while end < len(pooled) and pooled[end][0] == pooled[start][0]:
            end += 1
        tie_sizes.append(end - start)
        # Twice the average 1-based rank is integral, including tied mid-ranks.
        doubled_rank = start + end + 1
        for sorted_index in range(start, end):
            original_index = pooled[sorted_index][1]
            doubled_ranks[original_index] = doubled_rank
        start = end

    case_count = len(case_values)
    reference_count = len(reference_values)
    total_count = case_count + reference_count
    doubled_rank_sum = sum(doubled_ranks[:case_count])
    doubled_u = doubled_rank_sum - case_count * (case_count + 1)
    center_u = case_count * reference_count
    rank_biserial = (doubled_u - center_u) / (case_count * reference_count)
    assignments = math.comb(total_count, case_count)

    if assignments <= assignment_limit:
        if case_count <= reference_count:
            permutation_size = case_count
            observed_sum = doubled_rank_sum
        else:
            permutation_size = reference_count
            observed_sum = sum(doubled_ranks[case_count:])
        expected_sum = permutation_size * (total_count + 1)
        distance = abs(observed_sum - expected_sum)
        extreme = 0
        for indices in combinations(range(total_count), permutation_size):
            permuted_sum = sum(doubled_ranks[index] for index in indices)
            if abs(permuted_sum - expected_sum) >= distance:
                extreme += 1
        return rank_biserial, extreme / assignments, "exact_label_permutation"

    tie_adjustment = sum(size**3 - size for size in tie_sizes)
    variance = (
        case_count
        * reference_count
        / 12.0
        * (total_count + 1 - tie_adjustment / (total_count * (total_count - 1)))
    )
    if variance <= 0:
        p_value = 1.0
    else:
        deviation = abs(doubled_u / 2.0 - center_u / 2.0)
        z_score = max(0.0, (deviation - 0.5) / math.sqrt(variance))
        p_value = min(1.0, math.erfc(z_score / math.sqrt(2.0)))
    return rank_biserial, p_value, "tie_corrected_normal_approximation"


MAX_EXACT_SIGNED_RANK_PAIRS = 32
MAX_EXACT_SIGN_TEST_PAIRS = 128


@lru_cache(maxsize=256)
def _signed_rank_null_distribution(rank_weights: tuple[int, ...]) -> tuple[int, ...]:
    """Count exact signed-rank assignments for one tied-rank pattern."""

    assignment_counts = [1]
    for rank_weight in rank_weights:
        expanded = assignment_counts + [0] * rank_weight
        for score in range(len(expanded) - 1, rank_weight - 1, -1):
            expanded[score] += expanded[score - rank_weight]
        assignment_counts = expanded
    return tuple(assignment_counts)


def _paired_signed_rank_test(
    differences: Sequence[float],
) -> tuple[float, float, str, int]:
    """Return matched rank-biserial effect, two-sided p, method, and nonzero-pair count."""

    nonzero = tuple(value for value in differences if value != 0.0)
    if not nonzero:
        return 0.0, 1.0, "exact_paired_signed_rank", 0
    if any(not math.isfinite(value) for value in nonzero):
        raise ValidationError("paired GEO expression differences must be finite")

    ordered = sorted((abs(value), value > 0.0) for value in nonzero)
    rank_weights = [0] * len(ordered)
    positive_rank_sum = 0
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][0] == ordered[start][0]:
            end += 1
        doubled_rank = start + end + 1
        for index in range(start, end):
            rank_weights[index] = doubled_rank
            if ordered[index][1]:
                positive_rank_sum += doubled_rank
        start = end

    total_rank_sum = sum(rank_weights)
    rank_biserial = (2 * positive_rank_sum - total_rank_sum) / total_rank_sum
    nonzero_pair_count = len(nonzero)
    center = total_rank_sum / 2.0
    observed_distance = abs(positive_rank_sum - center)
    if nonzero_pair_count <= MAX_EXACT_SIGNED_RANK_PAIRS:
        distribution = _signed_rank_null_distribution(tuple(rank_weights))
        extreme_assignments = sum(
            assignments
            for score, assignments in enumerate(distribution)
            if abs(score - center) >= observed_distance
        )
        p_value = extreme_assignments / (2**nonzero_pair_count)
        return rank_biserial, p_value, "exact_paired_signed_rank", nonzero_pair_count

    variance = math.fsum(weight * weight for weight in rank_weights) / 4.0
    z_score = max(0.0, observed_distance - 1.0) / math.sqrt(variance) if variance > 0.0 else 0.0
    p_value = min(1.0, math.erfc(z_score / math.sqrt(2.0)))
    return rank_biserial, p_value, "normal_approximation_paired_signed_rank", nonzero_pair_count


@lru_cache(maxsize=8_192)
def _exact_two_sided_sign_pvalue(positive_count: int, negative_count: int) -> float:
    nonzero_pair_count = positive_count + negative_count
    if nonzero_pair_count == 0:
        return 1.0
    lower_tail_count = min(positive_count, negative_count)
    lower_tail_assignments = sum(
        math.comb(nonzero_pair_count, count) for count in range(lower_tail_count + 1)
    )
    return min(1.0, 2.0 * lower_tail_assignments / (2**nonzero_pair_count))


def _paired_sign_test(
    differences: Sequence[float],
) -> tuple[int, int, int, float, str]:
    """Return positive, negative, tied pairs and a two-sided paired sign-test p-value."""

    if any(not math.isfinite(value) for value in differences):
        raise ValidationError("paired GEO expression differences must be finite")
    positive_count = sum(value > 0.0 for value in differences)
    negative_count = sum(value < 0.0 for value in differences)
    tied_pair_count = len(differences) - positive_count - negative_count
    nonzero_pair_count = positive_count + negative_count
    if nonzero_pair_count <= MAX_EXACT_SIGN_TEST_PAIRS:
        p_value = _exact_two_sided_sign_pvalue(positive_count, negative_count)
        return (
            positive_count,
            negative_count,
            tied_pair_count,
            p_value,
            "exact_paired_sign_test",
        )

    observed_distance = abs(positive_count - nonzero_pair_count / 2.0)
    standard_deviation = math.sqrt(nonzero_pair_count / 4.0)
    z_score = max(0.0, observed_distance - 0.5) / standard_deviation
    p_value = min(1.0, math.erfc(z_score / math.sqrt(2.0)))
    return (
        positive_count,
        negative_count,
        tied_pair_count,
        p_value,
        "normal_approximation_paired_sign_test",
    )


def _leave_one_out_medians(values: Sequence[float]) -> tuple[float, ...]:
    """Return every one-observation-deleted median using sorted order statistics."""

    if len(values) < 3:
        raise ValidationError("leave-one-out median sensitivity requires at least three values")
    if any(not math.isfinite(value) for value in values):
        raise ValidationError("GEO expression values for leave-one-out sensitivity must be finite")

    ordered = sorted(values)
    retained_count = len(ordered) - 1
    lower_rank = (retained_count - 1) // 2
    upper_rank = retained_count // 2
    return tuple(
        ordered[lower_rank + (lower_rank >= omitted_rank)] / 2.0
        + ordered[upper_rank + (upper_rank >= omitted_rank)] / 2.0
        for omitted_rank in range(len(ordered))
    )


def _paired_leave_one_out_median_sensitivity(differences: Sequence[float]) -> dict[str, Any]:
    """Describe how the paired median changes when each matched pair is omitted.

    The sorted-order-statistic implementation evaluates every omission in
    O(n log n) total time rather than re-sorting once per pair. These are
    descriptive influence diagnostics; no inferential test is refit.
    """

    if len(differences) < 3:
        raise ValidationError("leave-one-pair-out sensitivity requires at least three pairs")
    if any(not math.isfinite(value) for value in differences):
        raise ValidationError("paired GEO expression differences must be finite")
    omitted_medians = _leave_one_out_medians(differences)

    def direction(value: float) -> str:
        return "case_higher" if value > 0.0 else "case_lower" if value < 0.0 else "tied"

    full_direction = direction(_finite_median(differences))
    direction_counts = Counter(direction(value) for value in omitted_medians)
    return {
        "omitted_pair_count": len(differences),
        "median_difference_range_log2_cpm": [min(omitted_medians), max(omitted_medians)],
        "direction_counts": {
            key: direction_counts[key] for key in ("case_higher", "case_lower", "tied")
        },
        "direction_stable": all(direction(value) == full_direction for value in omitted_medians),
    }


def _unpaired_leave_one_out_median_sensitivity(
    case_values: Sequence[float], reference_values: Sequence[float]
) -> dict[str, Any]:
    """Summarize median-direction stability across eligible single-sample deletions.

    Deletions are evaluated separately within each group and are eligible only
    when at least two observations remain in both groups. The result describes
    raw, unadjusted group medians; no rank test, model, or p-value is refit.
    """

    if any(not math.isfinite(value) for value in (*case_values, *reference_values)):
        raise ValidationError("GEO expression values for leave-one-out sensitivity must be finite")

    observed_sample_count = len(case_values) + len(reference_values)
    if len(case_values) < 2 or len(reference_values) < 2:
        return {
            "basis": "unadjusted_group_medians",
            "status": "unavailable",
            "reason": "fewer_than_two_nonmissing_observations_in_a_group",
            "full_data_median_direction": None,
            "omitted_case_sample_count": 0,
            "omitted_reference_sample_count": 0,
            "eligible_omission_count": 0,
            "observed_sample_count": observed_sample_count,
            "eligible_omission_coverage": 0.0,
            "direction_counts": {
                "case_higher": 0,
                "case_lower": 0,
                "no_median_difference": 0,
            },
            "direction_stable": None,
            "median_difference_range": None,
        }

    case_median = _finite_median(case_values)
    reference_median = _finite_median(reference_values)

    def direction(case_center: float, reference_center: float) -> str:
        if case_center > reference_center:
            return "case_higher"
        if case_center < reference_center:
            return "case_lower"
        return "no_median_difference"

    full_direction = direction(case_median, reference_median)
    omitted_case_medians = _leave_one_out_medians(case_values) if len(case_values) >= 3 else ()
    omitted_reference_medians = (
        _leave_one_out_medians(reference_values) if len(reference_values) >= 3 else ()
    )
    direction_counts = Counter()
    minimum_difference: float | None = None
    maximum_difference: float | None = None
    representable_differences = 0

    for omitted_case_median in omitted_case_medians:
        direction_counts[direction(omitted_case_median, reference_median)] += 1
        difference = _finite_difference(omitted_case_median, reference_median)
        if difference is not None:
            minimum_difference = (
                difference if minimum_difference is None else min(minimum_difference, difference)
            )
            maximum_difference = (
                difference if maximum_difference is None else max(maximum_difference, difference)
            )
            representable_differences += 1
    for omitted_reference_median in omitted_reference_medians:
        direction_counts[direction(case_median, omitted_reference_median)] += 1
        difference = _finite_difference(case_median, omitted_reference_median)
        if difference is not None:
            minimum_difference = (
                difference if minimum_difference is None else min(minimum_difference, difference)
            )
            maximum_difference = (
                difference if maximum_difference is None else max(maximum_difference, difference)
            )
            representable_differences += 1

    omitted_case_count = len(omitted_case_medians)
    omitted_reference_count = len(omitted_reference_medians)
    eligible_omission_count = omitted_case_count + omitted_reference_count
    if omitted_case_count and omitted_reference_count:
        status = "complete"
        reason = None
    elif eligible_omission_count:
        status = "partial"
        reason = "a_group_has_only_two_observed_values"
    else:
        status = "unavailable"
        reason = "no_eligible_single_sample_deletions"

    return {
        "basis": "unadjusted_group_medians",
        "status": status,
        "reason": reason,
        "full_data_median_direction": full_direction,
        "omitted_case_sample_count": omitted_case_count,
        "omitted_reference_sample_count": omitted_reference_count,
        "eligible_omission_count": eligible_omission_count,
        "observed_sample_count": observed_sample_count,
        "eligible_omission_coverage": (
            eligible_omission_count / observed_sample_count if observed_sample_count else 0.0
        ),
        "direction_counts": {
            key: direction_counts[key]
            for key in ("case_higher", "case_lower", "no_median_difference")
        },
        "direction_stable": (
            all(
                key == full_direction
                for key, count in direction_counts.items()
                if count > 0
            )
            if eligible_omission_count
            else None
        ),
        "median_difference_range": (
            [minimum_difference, maximum_difference]
            if representable_differences == eligible_omission_count
            and minimum_difference is not None
            and maximum_difference is not None
            else None
        ),
    }


@lru_cache(maxsize=128)
def _paired_median_sign_interval_critical_values(
    pair_count: int, confidence_level: float
) -> tuple[int | None, float | None, float]:
    """Cache exact central sign-test ranks shared by every feature in a contrast."""

    denominator = 2**pair_count
    confidence_numerator, confidence_denominator = confidence_level.as_integer_ratio()
    lower_tail_assignments = 0
    binomial_coefficient = 1
    selected_rank: int | None = None
    achieved_level: float | None = None
    maximum_finite_level = 0.0
    for rank in range((pair_count + 1) // 2):
        if rank:
            binomial_coefficient = binomial_coefficient * (pair_count - rank + 1) // rank
        lower_tail_assignments += binomial_coefficient
        coverage_numerator = denominator - 2 * lower_tail_assignments
        if rank == 0:
            maximum_finite_level = float(Fraction(coverage_numerator, denominator))
        if coverage_numerator * confidence_denominator >= confidence_numerator * denominator:
            selected_rank = rank
            achieved_level = float(Fraction(coverage_numerator, denominator))
        else:
            break
    return selected_rank, achieved_level, maximum_finite_level


def _paired_median_sign_interval(
    differences: Sequence[float], *, confidence_level: float
) -> dict[str, Any]:
    """Invert the exact sign test to form a conservative median interval.

    The central order-statistic interval has binomial coverage. If the pair
    count cannot attain the requested level with finite endpoints, no interval
    is emitted rather than silently reporting a lower-coverage range.
    """

    if (
        isinstance(confidence_level, bool)
        or not isinstance(confidence_level, (int, float))
        or not math.isfinite(confidence_level)
        or not 0.0 < confidence_level < 1.0
    ):
        raise ValidationError("confidence level must be finite and strictly between zero and one")
    if not differences or any(not math.isfinite(value) for value in differences):
        raise ValidationError("paired GEO expression differences must be finite and non-empty")

    ordered = sorted(differences)
    pair_count = len(ordered)
    selected_rank, achieved_level, maximum_finite_level = (
        _paired_median_sign_interval_critical_values(pair_count, float(confidence_level))
    )

    if selected_rank is None:
        return {
            "method": "exact_sign_order_statistics",
            "requested_confidence_level": float(confidence_level),
            "achieved_confidence_level": None,
            "maximum_finite_interval_confidence_level": maximum_finite_level,
            "bounds_log2_cpm": None,
            "lower_order_statistic_rank": None,
            "upper_order_statistic_rank": None,
            "status": "no_finite_interval_at_requested_confidence",
        }

    return {
        "method": "exact_sign_order_statistics",
        "requested_confidence_level": float(confidence_level),
        "achieved_confidence_level": achieved_level,
        "maximum_finite_interval_confidence_level": maximum_finite_level,
        "bounds_log2_cpm": [ordered[selected_rank], ordered[pair_count - selected_rank - 1]],
        "lower_order_statistic_rank": selected_rank + 1,
        "upper_order_statistic_rank": pair_count - selected_rank,
        "status": "bounded",
    }


def _adjust_p_values(p_values: Sequence[float], *, method: str) -> list[float]:
    """Compute deterministic monotone BH or BY adjusted p-values."""

    if method not in {"bh", "by"}:
        raise ValidationError("FDR method must be 'bh' or 'by'")
    values = tuple(float(value) for value in p_values)
    if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in values):
        raise ValidationError("FDR adjustment requires finite p-values in [0, 1]")
    ordered = sorted(enumerate(values), key=lambda item: (item[1], item[0]))
    adjusted = [1.0] * len(ordered)
    running_minimum = 1.0
    count = len(ordered)
    dependence_factor = (
        math.fsum(1.0 / rank for rank in range(1, count + 1)) if method == "by" else 1.0
    )
    for index in range(count - 1, -1, -1):
        original_index, p_value = ordered[index]
        rank = index + 1
        running_minimum = min(running_minimum, p_value * count * dependence_factor / rank)
        adjusted[original_index] = min(1.0, running_minimum)
    return adjusted


def _benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """Compute deterministic monotone Benjamini-Hochberg adjusted p-values."""

    return _adjust_p_values(p_values, method="bh")


def build_expression_contrast_report(
    accession: str,
    *,
    case_filters: Sequence[tuple[str, str]],
    reference_filters: Sequence[tuple[str, str]],
    scale: ExpressionScale | str,
    matrix_file: str | Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    fdr_threshold: float = 0.05,
    fdr_method: str = "bh",
    confidence_level: float = DEFAULT_GEO_CONFIDENCE_LEVEL,
    top: int = 1_000,
    track_feature_ids: Sequence[str] = (),
    covariates: Sequence[tuple[str, str]] = (),
    platform_annotation_file: str | Path | None = None,
    annotation_id_column: str = "ID",
    annotation_columns: Sequence[str] = (),
) -> dict[str, Any]:
    """Screen all retained features with rank tests or an additive adjusted model."""

    normalized_accession = validate_accession(accession)
    normalized_case = _normalize_filters(case_filters, "case")
    normalized_reference = _normalize_filters(reference_filters, "reference")
    normalized_covariates = _normalize_covariates(covariates)
    normalized_tracked_features = _normalize_tracked_feature_ids(track_feature_ids)
    if not isinstance(fdr_method, str):
        raise ValidationError("FDR method must be 'bh' or 'by'")
    normalized_fdr_method = fdr_method.strip().casefold()
    if normalized_fdr_method not in {"bh", "by"}:
        raise ValidationError("FDR method must be 'bh' or 'by'")
    normalized_annotation_columns = tuple(annotation_columns)
    if platform_annotation_file is None and (
        normalized_annotation_columns or annotation_id_column != "ID"
    ):
        raise ValidationError("GEO platform annotation columns require a platform annotation file")
    group_fields = {field.casefold() for field, _ in (*normalized_case, *normalized_reference)}
    if any(field.casefold() in group_fields for field, _ in normalized_covariates):
        raise ValidationError("GEO covariates cannot reuse sample fields that define group labels")
    if isinstance(fdr_threshold, bool) or not isinstance(fdr_threshold, (int, float)):
        raise ValidationError("FDR threshold must be numeric")
    fdr_threshold = float(fdr_threshold)
    if not math.isfinite(fdr_threshold) or not 0.0 < fdr_threshold <= 1.0:
        raise ValidationError("FDR threshold must be greater than zero and at most one")
    if isinstance(top, bool) or not isinstance(top, int) or not 1 <= top <= MAX_CONTRAST_FEATURES:
        raise ValidationError("top result limit must be an integer within the feature bound")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (float, int))
        or not 0.1 <= float(timeout_seconds) <= 120.0
    ):
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")
    try:
        expression_scale = ExpressionScale(scale)
    except (ValueError, TypeError) as error:
        raise ValidationError("expression scale is not supported") from error
    if not expression_scale.cohort_comparable:
        raise ValidationError("raw counts are not supported for this cohort comparison")

    payload, response_url, source_file_name = _read_matrix(
        normalized_accession,
        matrix_file=matrix_file,
        timeout_seconds=float(timeout_seconds),
    )
    matrix = parse_series_matrix_metadata(
        payload,
        accession=normalized_accession,
        source_file_name=source_file_name,
    )
    if len(matrix.platform_ids) != 1:
        raise ValidationError("two-group screening requires exactly one GEO platform")
    platform_annotations = (
        read_geo_platform_annotations(
            platform_annotation_file,
            expected_platform_id=matrix.platform_ids[0],
            annotation_columns=normalized_annotation_columns,
            id_column=annotation_id_column,
        )
        if platform_annotation_file is not None
        else None
    )

    case_samples = tuple(sample for sample in matrix.samples if sample.matches(normalized_case))
    reference_samples = tuple(
        sample for sample in matrix.samples if sample.matches(normalized_reference)
    )
    case_ids = {sample.accession for sample in case_samples}
    reference_ids = {sample.accession for sample in reference_samples}
    if case_ids & reference_ids:
        raise ValidationError("case and reference sample filters select overlapping samples")
    if len(case_samples) < 2 or len(reference_samples) < 2:
        raise ValidationError("each group must select at least two GEO samples")
    case_indices = tuple(
        index for index, sample in enumerate(matrix.samples) if sample.accession in case_ids
    )
    reference_indices = tuple(
        index for index, sample in enumerate(matrix.samples) if sample.accession in reference_ids
    )
    adjusted_contrast = (
        _prepare_geo_contrast(
            matrix,
            case_indices=case_indices,
            reference_indices=reference_indices,
            covariates=normalized_covariates,
        )
        if normalized_covariates
        else None
    )
    confidence_critical_value = (
        student_t_critical_value(
            DEFAULT_GEO_CONFIDENCE_LEVEL,
            adjusted_contrast.model.degrees_of_freedom,
        )
        if adjusted_contrast is not None
        else None
    )
    analysis_case_indices = (
        adjusted_contrast.case_indices if adjusted_contrast is not None else case_indices
    )
    analysis_reference_indices = (
        adjusted_contrast.reference_indices if adjusted_contrast is not None else reference_indices
    )

    preliminary_rows: list[dict[str, Any]] = []
    p_values: list[float] = []
    tested_rows: list[int] = []
    method_counts = (
        {"covariate_adjusted_ols_t_test": 0}
        if adjusted_contrast is not None
        else {"exact_label_permutation": 0, "tie_corrected_normal_approximation": 0}
    )
    def process_feature(feature: GeoMatrixFeature) -> None:
        case_values = tuple(
            feature.values[index]
            for index in analysis_case_indices
            if feature.values[index] is not None
        )
        reference_values = tuple(
            feature.values[index]
            for index in analysis_reference_indices
            if feature.values[index] is not None
        )
        case_median = _finite_median(case_values) if case_values else None
        reference_median = _finite_median(reference_values) if reference_values else None
        case_mean = _finite_mean(case_values) if case_values else None
        reference_mean = _finite_mean(reference_values) if reference_values else None
        row: dict[str, Any] = {
            "feature_id": feature.feature_id,
            "case_n": len(case_values),
            "reference_n": len(reference_values),
            "case_median": case_median,
            "reference_median": reference_median,
            "median_difference": (
                _finite_difference(case_median, reference_median)
                if case_median is not None and reference_median is not None
                else None
            ),
            "mean_difference": (
                _finite_difference(case_mean, reference_mean)
                if case_mean is not None and reference_mean is not None
                else None
            ),
            "rank_biserial_correlation": None,
            "effect_direction": None,
            "p_value": None,
            "q_value": None,
            "test_method": None,
            "fdr_significant": False,
            "reason": None,
            "leave_one_sample_out_median_sensitivity": (
                _unpaired_leave_one_out_median_sensitivity(case_values, reference_values)
                if adjusted_contrast is None
                else {
                    "basis": "unadjusted_group_medians",
                    "status": "not_calculated",
                    "reason": "covariate_adjusted_contrast",
                    "full_data_median_direction": None,
                    "omitted_case_sample_count": 0,
                    "omitted_reference_sample_count": 0,
                    "eligible_omission_count": 0,
                    "observed_sample_count": len(case_values) + len(reference_values),
                    "eligible_omission_coverage": 0.0,
                    "direction_counts": {
                        "case_higher": 0,
                        "case_lower": 0,
                        "no_median_difference": 0,
                    },
                    "direction_stable": None,
                    "median_difference_range": None,
                }
            ),
        }
        if adjusted_contrast is not None:
            row.update(
                {
                    "adjusted_mean_difference": None,
                    "adjusted_mean_difference_ci_low": None,
                    "adjusted_mean_difference_ci_high": None,
                    "residual_standard_error": None,
                    "adjusted_r_squared": None,
                    "t_statistic": None,
                    "degrees_of_freedom": None,
                    "model_sample_count": len(adjusted_contrast.sample_indices),
                }
            )
            model_values = tuple(
                feature.values[index] for index in adjusted_contrast.sample_indices
            )
            if any(value is None for value in model_values):
                row["reason"] = "missing_expression_in_covariate_complete_samples"
            else:
                fit = fit_linear_contrast(
                    adjusted_contrast.model,
                    tuple(float(value) for value in model_values if value is not None),
                )
                if fit is None:
                    row["reason"] = "zero_residual_variance"
                elif fit.coefficient is None:
                    row["reason"] = "nonfinite_adjusted_group_effect"
                else:
                    if confidence_critical_value is None:
                        raise ArithmeticError("adjusted model confidence limit is unavailable")
                    confidence_margin = confidence_critical_value * fit.standard_error
                    confidence_low = fit.coefficient - confidence_margin
                    confidence_high = fit.coefficient + confidence_margin
                    if not math.isfinite(confidence_low) or not math.isfinite(confidence_high):
                        raise ArithmeticError(
                            "adjusted model confidence interval is not representable"
                        )
                    row["adjusted_mean_difference"] = fit.coefficient
                    row["adjusted_mean_difference_ci_low"] = confidence_low
                    row["adjusted_mean_difference_ci_high"] = confidence_high
                    row["residual_standard_error"] = fit.residual_standard_error
                    row["adjusted_r_squared"] = fit.adjusted_r_squared
                    row["t_statistic"] = fit.statistic
                    row["degrees_of_freedom"] = fit.degrees_of_freedom
                    row["effect_direction"] = (
                        "case_higher"
                        if fit.coefficient > 0
                        else "case_lower"
                        if fit.coefficient < 0
                        else "no_adjusted_group_effect"
                    )
                    row["p_value"] = fit.p_value
                    row["test_method"] = "covariate_adjusted_ols_t_test"
                    row["reason"] = None
                    tested_rows.append(len(preliminary_rows))
                    p_values.append(fit.p_value)
                    method_counts["covariate_adjusted_ols_t_test"] += 1
        elif len(case_values) < 2 or len(reference_values) < 2:
            row["reason"] = "fewer_than_two_nonmissing_observations_in_a_group"
        else:
            assignment_limit = max(
                1,
                min(
                    MAX_EXACT_RANK_ASSIGNMENTS,
                    MAX_TOTAL_EXACT_RANK_SUMS
                    // max(1, matrix.feature_count * min(len(case_values), len(reference_values))),
                ),
            )
            effect, p_value, method = _mann_whitney_test(
                case_values,
                reference_values,
                assignment_limit=assignment_limit,
            )
            row["rank_biserial_correlation"] = effect
            row["effect_direction"] = (
                "case_higher" if effect > 0 else "case_lower" if effect < 0 else "no_rank_shift"
            )
            row["p_value"] = p_value
            row["test_method"] = method
            row["reason"] = None
            method_counts[method] += 1
            tested_rows.append(len(preliminary_rows))
            p_values.append(p_value)
        preliminary_rows.append(row)

    scanned_matrix = scan_series_matrix_features(
        payload,
        accession=normalized_accession,
        feature_consumer=process_feature,
        source_file_name=source_file_name,
    )
    if scanned_matrix != matrix:
        raise ValidationError("GEO Series Matrix metadata changed between contrast passes")
    matrix = scanned_matrix

    adjusted_values = _adjust_p_values(p_values, method=normalized_fdr_method)
    for row_index, q_value in zip(tested_rows, adjusted_values, strict=True):
        preliminary_rows[row_index]["q_value"] = q_value
        preliminary_rows[row_index]["fdr_significant"] = q_value <= fdr_threshold
    annotation_match_count = 0
    if platform_annotations is not None:
        annotation_rows = dict(platform_annotations.records)
        for row in preliminary_rows:
            values = annotation_rows.get(row["feature_id"])
            row["platform_annotation_status"] = "matched" if values is not None else "not_found"
            row["platform_annotation"] = (
                dict(zip(platform_annotations.annotation_columns, values, strict=True))
                if values is not None
                else None
            )
            annotation_match_count += values is not None
    preliminary_rows.sort(
        key=lambda row: (
            row["q_value"] is None,
            row["q_value"] if row["q_value"] is not None else 1.0,
            row["p_value"] if row["p_value"] is not None else 1.0,
            row["feature_id"],
        )
    )
    ranked_rows = preliminary_rows[:top]
    ranked_feature_ids = {row["feature_id"] for row in ranked_rows}
    rows_by_feature_id = {row["feature_id"]: row for row in preliminary_rows}
    missing_tracked_features = [
        feature_id
        for feature_id in normalized_tracked_features
        if feature_id not in rows_by_feature_id
    ]
    if missing_tracked_features:
        raise ValidationError(
            f"{len(missing_tracked_features)} requested tracked GEO feature ID(s) were not "
            "present in the Series Matrix"
        )
    additional_feature_rows = [
        rows_by_feature_id[feature_id]
        for feature_id in normalized_tracked_features
        if feature_id not in ranked_feature_ids
    ]

    source_version = f"sha256:{matrix.source_sha256}"

    def filter_context(filters: Sequence[tuple[str, str]]) -> str:
        return ",".join(
            f"{field.casefold()}={value.casefold()}"
            for field, value in sorted(filters, key=lambda item: item[0].casefold())
        )

    test_description = (
        "additive ordinary least squares adjusted group coefficient with two-sided Student t test"
        if adjusted_contrast is not None
        else "two-sided Mann-Whitney U with exact label permutations when bounded"
    )
    dependence_limitation = (
        "Benjamini-Yekutieli adjustment controls false discovery rate under arbitrary dependence "
        "among valid feature-level p-values, but can be conservative and does not repair invalid "
        "tests or post-selection."
        if normalized_fdr_method == "by"
        else (
            "Nominal FDR control depends on assumptions about test dependence; correlated platform "
            "features may affect it."
        )
    )
    exact_test_feature_count = 0
    assignment_count_minimum: int | None = None
    assignment_count_maximum: int | None = None
    no_tie_p_floor_minimum: float | None = None
    no_tie_p_floor_maximum: float | None = None
    smallest_exact_p_value: float | None = None
    feature_count_at_smallest_exact_p_value = 0
    for row in preliminary_rows:
        if row["test_method"] != "exact_label_permutation":
            continue
        exact_test_feature_count += 1
        assignment_count = math.comb(row["case_n"] + row["reference_n"], row["case_n"])
        no_tie_p_floor = 2 / assignment_count
        assignment_count_minimum = (
            assignment_count
            if assignment_count_minimum is None
            else min(assignment_count_minimum, assignment_count)
        )
        assignment_count_maximum = (
            assignment_count
            if assignment_count_maximum is None
            else max(assignment_count_maximum, assignment_count)
        )
        no_tie_p_floor_minimum = (
            no_tie_p_floor
            if no_tie_p_floor_minimum is None
            else min(no_tie_p_floor_minimum, no_tie_p_floor)
        )
        no_tie_p_floor_maximum = (
            no_tie_p_floor
            if no_tie_p_floor_maximum is None
            else max(no_tie_p_floor_maximum, no_tie_p_floor)
        )
        exact_p_value = float(row["p_value"])
        if smallest_exact_p_value is None or exact_p_value < smallest_exact_p_value:
            smallest_exact_p_value = exact_p_value
            feature_count_at_smallest_exact_p_value = 1
        elif exact_p_value == smallest_exact_p_value:
            feature_count_at_smallest_exact_p_value += 1
    finite_sample_resolution = {
        "exact_test_feature_count": exact_test_feature_count,
        "label_assignment_count_range": (
            {
                "minimum": assignment_count_minimum,
                "maximum": assignment_count_maximum,
            }
            if assignment_count_minimum is not None
            else None
        ),
        "no_tie_minimum_two_sided_p_range": (
            {
                "minimum": no_tie_p_floor_minimum,
                "maximum": no_tie_p_floor_maximum,
            }
            if no_tie_p_floor_minimum is not None
            else None
        ),
        "smallest_observed_exact_p_value": smallest_exact_p_value,
        "feature_count_at_smallest_observed_exact_p_value": feature_count_at_smallest_exact_p_value,
    }
    limitations = (
        [
            "Exploratory public-cohort group comparison; it is not matched-case RNA evidence.",
            (
                "Only explicitly declared covariates are adjusted; unmeasured confounding and "
                "unmodeled batch effects remain."
            ),
            (
                "The additive ordinary least squares model assumes independent samples, a linear "
                "continuous-covariate effect, and approximately normal homoscedastic residuals."
            ),
            (
                "Samples missing any declared covariate are excluded listwise; a feature missing "
                "in any analyzed sample is untestable in the adjusted model."
            ),
            (
                "Paired or repeated measures, interactions, and nonlinear covariate effects "
                "are not modeled."
            ),
            (
                "FDR adjustment covers testable rows in this matrix, not analyses selected after "
                "inspecting results."
            ),
            dependence_limitation,
            (
                "Leave-one-sample-out median sensitivity is not calculated for covariate-adjusted "
                "contrasts; the unadjusted median difference is descriptive and distinct from the "
                "adjusted model coefficient."
            ),
            (
                "Feature identifiers remain platform identifiers; transcript or gene identity "
                "was not inferred."
            ),
            "Results do not support diagnosis or treatment decisions.",
        ]
        if adjusted_contrast is not None
        else [
            "Exploratory public-cohort group comparison; it is not matched-case RNA evidence.",
            (
                "Group labels use submitted sample characteristics; covariates and batch effects "
                "are not modeled."
            ),
            (
                "The test assumes exchangeable independent samples; paired or repeated measures "
                "are not modeled."
            ),
            (
                "FDR adjustment covers testable rows in this matrix, not analyses selected after "
                "inspecting results."
            ),
            dependence_limitation,
            (
                "Leave-one-sample-out sensitivity is based on unadjusted group medians and is a "
                "descriptive influence check; it does not refit the rank test or change p-values."
            ),
            (
                "Per-feature missingness is reported but not modeled; informative missingness "
                "may bias a comparison."
            ),
            (
                "Feature identifiers remain platform identifiers; transcript or gene identity "
                "was not inferred."
            ),
            "Results do not support diagnosis or treatment decisions.",
        ]
    )
    if exact_test_feature_count:
        limitations.append(
            "Exact two-sided permutation p-values are discrete. For each exact-tested feature, "
            "2 / choose(n_case + n_reference, n_case) is the no-tie lower bound on an attainable "
            "two-sided p-value; feature-specific missingness changes that bound, and tied "
            "observations can make the actual p-value support coarser. See "
            "comparison.finite_sample_resolution."
        )
    body: dict[str, Any] = {
        "schema": "glio-noncode.geo-expression-contrast.v1",
        "status": "completed",
        "source": {
            "database": "NCBI GEO",
            "accession": matrix.accession,
            "series_url": f"{GEO_RECORD_ORIGIN}/geo/query/acc.cgi?acc={matrix.accession}",
            "matrix_url": matrix.source_url,
            "retrieval": "local_file" if source_file_name is not None else "https",
            "response_url": response_url,
            "source_file_name": source_file_name,
            "source_sha256": source_version,
            "compressed_bytes": matrix.compressed_bytes,
            "decompressed_bytes": matrix.decompressed_bytes,
            "series_title": matrix.title,
            "series_types": list(matrix.series_types),
            "platform_ids": list(matrix.platform_ids),
            "processing_descriptions": list(matrix.processing_descriptions),
            "sample_count": len(matrix.samples),
            "feature_count": matrix.feature_count,
        },
        "comparison": {
            "case_filters": [{"field": field, "equals": value} for field, value in normalized_case],
            "reference_filters": [
                {"field": field, "equals": value} for field, value in normalized_reference
            ],
            "case_sample_ids": [sample.accession for sample in case_samples],
            "reference_sample_ids": [sample.accession for sample in reference_samples],
            "unassigned_sample_count": (
                len(matrix.samples) - len(case_samples) - len(reference_samples)
            ),
            "scale": expression_scale.value,
            "test": test_description,
            "multiple_testing_adjustment": (
                "Benjamini-Yekutieli" if normalized_fdr_method == "by" else "Benjamini-Hochberg"
            )
            + " over all testable matrix features",
            "fdr_method": normalized_fdr_method,
            "fdr_threshold": fdr_threshold,
            "matched_to_case_sample": False,
            "population_generalization": False,
            "tracked_feature_ids": list(normalized_tracked_features),
            "finite_sample_resolution": finite_sample_resolution,
        },
        "summary": {
            "matrix_feature_count": matrix.feature_count,
            "tested_feature_count": len(tested_rows),
            "untestable_feature_count": matrix.feature_count - len(tested_rows),
            "fdr_significant_feature_count": sum(
                bool(row["fdr_significant"]) for row in preliminary_rows
            ),
            "fdr_significant_case_higher_count": sum(
                row["fdr_significant"] and row["effect_direction"] == "case_higher"
                for row in preliminary_rows
            ),
            "fdr_significant_case_lower_count": sum(
                row["fdr_significant"] and row["effect_direction"] == "case_lower"
                for row in preliminary_rows
            ),
            "test_method_counts": method_counts,
            "median_sensitivity_status_counts": {
                status: sum(
                    row["leave_one_sample_out_median_sensitivity"]["status"] == status
                    for row in preliminary_rows
                )
                for status in ("complete", "partial", "unavailable", "not_calculated")
            },
            "median_sensitivity_direction_unstable_feature_count": sum(
                row["leave_one_sample_out_median_sensitivity"]["direction_stable"] is False
                for row in preliminary_rows
            ),
            "reported_feature_count": min(top, len(preliminary_rows)),
            "additional_feature_result_count": len(additional_feature_rows),
            "result_limit": top,
            "fdr_family_size": len(tested_rows),
        },
        "analysis_limits": {
            "max_retained_features": MAX_CONTRAST_FEATURES,
            "max_exact_assignments_per_feature": MAX_EXACT_RANK_ASSIGNMENTS,
            "max_exact_rank_sums_per_screen": MAX_TOTAL_EXACT_RANK_SUMS,
            "max_matrix_cells": MAX_MATRIX_CELLS,
            "matrix_scan_passes": 2,
            "retains_feature_vectors": False,
        },
        "results": ranked_rows,
        "additional_feature_results": additional_feature_rows,
        "limitations": limitations,
    }
    if platform_annotations is not None:
        body["source"]["platform_annotation"] = {
            "platform_accession": platform_annotations.platform_id,
            "platform_url": (
                f"{GEO_RECORD_ORIGIN}/geo/query/acc.cgi?acc={platform_annotations.platform_id}"
            ),
            "retrieval": "local_file",
            "source_file_name": platform_annotations.source_file_name,
            "source_sha256": f"sha256:{platform_annotations.source_sha256}",
            "source_bytes": platform_annotations.source_bytes,
            "decompressed_bytes": platform_annotations.decompressed_bytes,
            "record_count": len(platform_annotations.records),
            "id_column": platform_annotations.id_column,
            "annotation_columns": list(platform_annotations.annotation_columns),
            "feature_ids_matched_exactly": True,
        }
        body["summary"]["platform_annotation_matched_feature_count"] = annotation_match_count
        body["summary"]["platform_annotation_unmatched_feature_count"] = (
            matrix.feature_count - annotation_match_count
        )
        body["limitations"].append(
            "Platform annotation cells are retained verbatim; multi-valued cells are not split, "
            "deduplicated, or interpreted as gene identity."
        )
    if adjusted_contrast is not None:
        body["comparison"]["model"] = {
            "type": "additive_ordinary_least_squares",
            "group_effect": "case_minus_reference_adjusted_for_declared_covariates",
            "confidence_level": DEFAULT_GEO_CONFIDENCE_LEVEL,
            "parameter_names": list(adjusted_contrast.parameter_names),
            "residual_degrees_of_freedom": adjusted_contrast.model.degrees_of_freedom,
            "covariates": list(adjusted_contrast.covariate_metadata),
        }
        body["comparison"]["analysis_case_sample_ids"] = [
            matrix.samples[index].accession for index in adjusted_contrast.case_indices
        ]
        body["comparison"]["analysis_reference_sample_ids"] = [
            matrix.samples[index].accession for index in adjusted_contrast.reference_indices
        ]
        body["comparison"]["covariate_excluded_case_sample_ids"] = [
            matrix.samples[index].accession for index in adjusted_contrast.excluded_case_indices
        ]
        body["comparison"]["covariate_excluded_reference_sample_ids"] = [
            matrix.samples[index].accession
            for index in adjusted_contrast.excluded_reference_indices
        ]
        body["summary"]["covariate_complete_sample_count"] = len(adjusted_contrast.sample_indices)
        body["summary"]["covariate_excluded_sample_count"] = len(
            adjusted_contrast.excluded_case_indices
        ) + len(adjusted_contrast.excluded_reference_indices)
        body["analysis_limits"]["max_covariates"] = MAX_GEO_COVARIATES
        body["analysis_limits"]["max_model_parameters"] = MAX_GEO_MODEL_PARAMETERS
        body["analysis_limits"]["minimum_residual_degrees_of_freedom"] = 3
    body["comparison"]["context_key"] = (
        f"geo-contrast:{normalized_accession}:{matrix.platform_ids[0]}:"
        f"case[{filter_context(normalized_case)}]:reference[{filter_context(normalized_reference)}]"
    )
    if adjusted_contrast is not None:
        covariate_context = ",".join(
            f"{field.casefold()}:{kind}" for field, kind in normalized_covariates
        )
        body["comparison"]["context_key"] += f":covariates[{covariate_context}]"
    return body | {"content_address": content_hash(body, prefix="geo-expression-contrast")}


def build_expression_outlier_report(
    accession: str,
    *,
    feature_id: str,
    target_sample_id: str,
    reference_filters: Sequence[tuple[str, str]],
    scale: ExpressionScale | str,
    matrix_file: str | Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Build a descriptive public-cohort outlier report for one selected feature."""

    normalized_accession = validate_accession(accession)
    target_id = _required_text(target_sample_id, "target GEO sample accession", maximum=20).upper()
    if not _GSM_RE.fullmatch(target_id):
        raise ValidationError("target GEO sample accession must use the GSM numeric format")
    normalized_filters = _normalize_filters(reference_filters, "reference")
    try:
        expression_scale = ExpressionScale(scale)
    except (ValueError, TypeError) as error:
        raise ValidationError("expression scale is not supported") from error
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (float, int))
        or not 0.1 <= float(timeout_seconds) <= 120.0
    ):
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")

    payload, response_url, source_file_name = _read_matrix(
        normalized_accession,
        matrix_file=matrix_file,
        timeout_seconds=float(timeout_seconds),
    )
    matrix = parse_series_matrix(
        payload,
        accession=normalized_accession,
        feature_id=feature_id,
        source_file_name=source_file_name,
    )
    sample_by_id = {
        sample.accession: (index, sample) for index, sample in enumerate(matrix.samples)
    }
    target_entry = sample_by_id.get(target_id)
    if target_entry is None:
        raise ValidationError("target sample is not present in the GEO Series Matrix")
    target_index, target_sample = target_entry
    reference_samples = tuple(
        (index, sample)
        for index, sample in enumerate(matrix.samples)
        if sample.matches(normalized_filters)
    )
    if any(sample.accession == target_id for _, sample in reference_samples):
        raise ValidationError("target sample also matches the selected reference filters")

    source_id = f"GEO:{normalized_accession}"
    source_version = f"sha256:{matrix.source_sha256}"
    platform_key = "+".join(matrix.platform_ids) if matrix.platform_ids else "unannotated"
    filter_key = ",".join(
        f"{field.casefold()}={value.casefold()}"
        for field, value in sorted(normalized_filters, key=lambda pair: pair[0].casefold())
    )
    context_key = f"geo-cohort:{normalized_accession}:{platform_key}:{filter_key}"
    target_value = matrix.feature_values[target_index]
    available_references = tuple(
        (index, sample, matrix.feature_values[index])
        for index, sample in reference_samples
        if matrix.feature_values[index] is not None
    )
    missing_reference_ids = [
        sample.accession
        for index, sample in reference_samples
        if matrix.feature_values[index] is None
    ]

    if target_value is None:
        comparison_result = _unresolved_result("target_value_missing")
    elif not available_references:
        comparison_result = _unresolved_result("reference_group_has_no_feature_values")
    else:
        target = ExpressionObservation(
            feature_id=matrix.feature_id,
            sample_key=target_sample.accession,
            value=target_value,
            scale=expression_scale,
            context_key=context_key,
            source_id=source_id,
            source_version=source_version,
        )
        references = ExpressionBatch.from_observations(
            ExpressionObservation(
                feature_id=matrix.feature_id,
                sample_key=sample.accession,
                value=value,
                scale=expression_scale,
                context_key=context_key,
                source_id=source_id,
                source_version=source_version,
            )
            for _, sample, value in available_references
            if value is not None
        )
        result = RobustExpressionOutlierAnalyzer().analyze(target, references)
        if result.state is RNAEvidenceState.SUPPORTED:
            call = "descriptive_outlier"
        elif result.state is RNAEvidenceState.MEASURED_NEGATIVE:
            call = "no_descriptive_outlier"
        else:
            call = "unresolved"
        comparison_result = {
            "call": call,
            "direction": result.direction.value,
            "target_value": result.target_value,
            "reference_median": result.reference_median,
            "reference_count": result.reference_count,
            "missing_reference_count": len(missing_reference_ids),
            "dispersion": result.dispersion,
            "dispersion_method": result.dispersion_method.value,
            "robust_z": result.robust_z,
            "z_threshold": result.z_threshold,
            "reason_codes": list(result.reason_codes),
        }

    body: dict[str, Any] = {
        "schema": "glio-noncode.geo-expression-outlier.v1",
        "status": "completed",
        "source": {
            "database": "NCBI GEO",
            "accession": matrix.accession,
            "series_url": f"{GEO_RECORD_ORIGIN}/geo/query/acc.cgi?acc={matrix.accession}",
            "matrix_url": matrix.source_url,
            "retrieval": "local_file" if source_file_name is not None else "https",
            "response_url": response_url,
            "source_file_name": source_file_name,
            "source_sha256": source_version,
            "compressed_bytes": matrix.compressed_bytes,
            "decompressed_bytes": matrix.decompressed_bytes,
            "series_title": matrix.title,
            "series_types": list(matrix.series_types),
            "platform_ids": list(matrix.platform_ids),
            "processing_descriptions": list(matrix.processing_descriptions),
            "sample_count": len(matrix.samples),
            "feature_count": matrix.feature_count,
        },
        "comparison": {
            "feature_id": matrix.feature_id,
            "feature_identity_scope": "source-platform identifier; no gene annotation inferred",
            "target_sample_id": target_sample.accession,
            "target_sample_title": target_sample.title,
            "target_characteristics": target_sample.values_for(
                tuple(field for field, _ in normalized_filters)
            ),
            "reference_filters": [
                {"field": field, "equals": value} for field, value in normalized_filters
            ],
            "reference_sample_ids": [sample.accession for _, sample in reference_samples],
            "missing_reference_sample_ids": missing_reference_ids,
            "scale": expression_scale.value,
            "context_key": context_key,
            "method": "single-target median/MAD robust outlier with IQR fallback",
            "multiple_testing_adjustment": (
                "none; only the explicitly selected feature was analyzed"
            ),
            "matched_to_case_sample": False,
            "population_level_test": False,
        },
        "result": comparison_result,
        "limitations": [
            (
                "This is a descriptive single-sample public-cohort comparison, "
                "not matched case RNA evidence."
            ),
            (
                "This is not a population-level differential-expression test; "
                "no p-value is calculated."
            ),
            (
                "The feature remains a platform identifier; transcript or gene "
                "identity was not inferred."
            ),
            "Research use only; this result does not support diagnosis or treatment decisions.",
        ],
    }
    return body | {"content_address": content_hash(body, prefix="geo-expression-outlier")}


def build_geo_count_outlier_report(
    accession: str,
    *,
    feature_id: str,
    sample_key_column: str,
    sample_filters: Sequence[tuple[str, str]],
    counts_file_name: str | None = None,
    metadata_file_name: str | None = None,
    counts_file: str | Path | None = None,
    metadata_file: str | Path | None = None,
    counts_delimiter: str = ",",
    metadata_delimiter: str = ",",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    feature_annotation_file: str | Path | None = None,
    normalization_method: str = "log2_cpm",
) -> dict[str, Any]:
    """Build an aggregate leave-one-out expression report from GEO count files.

    This bounded adapter handles one-feature queries over an explicitly selected
    gene-by-sample non-negative integer count matrix and a sample metadata table.
    It computes log2(CPM + 1), optionally using TMM effective library sizes,
    then compares each selected sample with the remaining selected samples
    using the existing robust expression analyzer. Source sample keys and
    individual values are deliberately omitted from the returned aggregate.
    """

    normalized_accession = validate_accession(accession)
    normalized_normalization_method = _normalize_count_normalization_method(normalization_method)
    selected_feature = _required_text(feature_id, "GEO gene feature ID", maximum=256)
    if _FEATURE_RE.fullmatch(selected_feature) is None:
        raise ValidationError("GEO gene feature ID contains unsupported characters")
    if not isinstance(timeout_seconds, (float, int)) or isinstance(timeout_seconds, bool):
        raise ValidationError("GEO request timeout must be numeric")
    if not 0.1 <= float(timeout_seconds) <= 120.0:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")
    normalized_filters = _normalize_filters(sample_filters, "sample")
    count_delimiter = _normalize_delimiter(counts_delimiter, "GEO count matrix delimiter")
    metadata_separator = _normalize_delimiter(metadata_delimiter, "GEO metadata delimiter")
    feature_annotations, feature_annotation_provenance = _read_feature_annotation_file(
        feature_annotation_file
    )
    if not isinstance(sample_key_column, str) or len(sample_key_column) > 256:
        raise ValidationError("GEO metadata sample-key column must be a bounded string")

    count_payload, count_name, count_response_url, count_source_url = _read_supplementary_file(
        normalized_accession,
        label="count matrix",
        file_name=counts_file_name,
        local_file=counts_file,
        timeout_seconds=float(timeout_seconds),
    )
    metadata_payload, metadata_name, metadata_response_url, metadata_source_url = (
        _read_supplementary_file(
            normalized_accession,
            label="sample metadata",
            file_name=metadata_file_name,
            local_file=metadata_file,
            timeout_seconds=float(timeout_seconds),
        )
    )
    matrix = parse_geo_supplementary_count_matrix(
        count_payload,
        accession=normalized_accession,
        feature_id=selected_feature,
        delimiter=count_delimiter,
        source_file_name=count_name,
        source_url=count_source_url,
        annotation_source_ids=frozenset(feature_annotations),
        normalization_method=normalized_normalization_method,
    )
    duplicate_annotation_count = len(matrix.duplicate_annotation_source_ids)
    missing_annotation_count = len(
        set(feature_annotations) - set(matrix.annotation_source_ids_found)
    )
    if duplicate_annotation_count or missing_annotation_count:
        raise ValidationError(
            "GEO feature annotation map must reference existing unique source rows "
            f"(missing={missing_annotation_count}; duplicated={duplicate_annotation_count})"
        )
    metadata, metadata_headers, metadata_decompressed_bytes = _parse_geo_count_metadata(
        metadata_payload,
        sample_ids=matrix.sample_ids,
        sample_key_column=sample_key_column,
        requested_fields=tuple(field for field, _ in normalized_filters),
        delimiter=metadata_separator,
    )
    fields_by_casefold = {name.casefold(): name for name in metadata_headers}
    missing_filter_fields = [
        field for field, _ in normalized_filters if field.casefold() not in fields_by_casefold
    ]
    if missing_filter_fields:
        raise ValidationError("one or more GEO sample filter fields are absent from metadata")

    cohort_sample_ids = tuple(
        sample_id
        for sample_id in matrix.sample_ids
        if all(
            metadata[sample_id][fields_by_casefold[field.casefold()]].casefold()
            == expected.casefold()
            for field, expected in normalized_filters
        )
    )
    filter_records = [
        {"field": field, "equals": expected} for field, expected in normalized_filters
    ]
    filter_address = content_hash(
        {
            "accession": normalized_accession,
            "filters": filter_records,
            "normalization_method": normalized_normalization_method,
        },
        prefix="geo-count-cohort",
    )
    source_version_inputs = {
        "counts_sha256": matrix.source_sha256,
        "metadata_sha256": hashlib.sha256(metadata_payload).hexdigest(),
    }
    annotation_sha256 = feature_annotation_provenance["source_sha256"]
    if annotation_sha256 is not None:
        source_version_inputs["feature_annotation_map_sha256"] = str(
            annotation_sha256
        ).removeprefix("sha256:")
    source_version = content_hash(source_version_inputs, prefix="geo-count-inputs")
    cohort_sample_set = set(cohort_sample_ids)
    observations: tuple[ExpressionObservation, ...] = tuple(
        ExpressionObservation(
            feature_id=selected_feature,
            sample_key=f"private:geo:{sample_id}",
            value=math.log2(
                matrix.feature_counts[index]
                / (matrix.library_sizes[index] * matrix.normalization_factors[index])
                * 1_000_000
                + 1
            ),
            scale=ExpressionScale.LOG2_CPM,
            context_key=filter_address,
            source_id=f"GEO:{normalized_accession}",
            source_version=source_version,
        )
        for index, sample_id in enumerate(matrix.sample_ids)
        if sample_id in cohort_sample_set
    )

    states: Counter[str] = Counter()
    calls: Counter[str] = Counter()
    directions: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    robust_scores: list[float] = []
    reference_counts: list[int] = []
    if observations:
        reference_batch = ExpressionBatch.from_observations(observations)
        analyzer = RobustExpressionOutlierAnalyzer()
        for target in observations:
            result = analyzer.analyze(
                target,
                reference_batch,
                expected_context_key=filter_address,
            )
            states[result.state.value] += 1
            directions[result.direction.value] += 1
            reasons.update(result.reason_codes)
            reference_counts.append(result.reference_count)
            if result.robust_z is not None:
                robust_scores.append(result.robust_z)
            if result.state is RNAEvidenceState.SUPPORTED:
                calls["descriptive_outlier"] += 1
            elif result.state is RNAEvidenceState.MEASURED_NEGATIVE:
                calls["no_descriptive_outlier"] += 1
            else:
                calls["unresolved"] += 1
    else:
        reasons["no_samples_match_metadata_filters"] = 1

    report_body: dict[str, Any] = {
        "schema": "glio-noncode.geo-count-expression-outlier.v1",
        "status": "completed" if observations else "unresolved",
        "source": {
            "database": "NCBI GEO",
            "accession": normalized_accession,
            "series_url": f"{GEO_RECORD_ORIGIN}/geo/query/acc.cgi?acc={normalized_accession}",
            "retrieval": (
                "https"
                if count_response_url is not None or metadata_response_url is not None
                else "local_file"
            ),
            "count_matrix": {
                "file_name": matrix.source_file_name,
                "response_url": count_response_url,
                "source_sha256": f"sha256:{matrix.source_sha256}",
                "compressed_bytes": matrix.compressed_bytes,
                "decompressed_bytes": matrix.decompressed_bytes,
            },
            "sample_metadata": {
                "file_name": metadata_name,
                "response_url": metadata_response_url,
                "source_sha256": f"sha256:{hashlib.sha256(metadata_payload).hexdigest()}",
                "compressed_bytes": len(metadata_payload),
                "decompressed_bytes": metadata_decompressed_bytes,
            },
            "feature_annotation_map": feature_annotation_provenance,
        },
        "matrix": {
            "feature_id": selected_feature,
            "feature_count": matrix.feature_count,
            "duplicate_feature_label_count": matrix.duplicate_feature_label_count,
            "sample_count": len(matrix.sample_ids),
            "library_size_method": "sum of all non-negative integer count rows per sample",
            "feature_label_review": {
                "selected_label_matches_date_like_pattern": _feature_label_is_date_like(
                    selected_feature
                ),
                "automatic_normalization_performed": False,
                "manual_annotation_review_recommended": _feature_label_is_date_like(
                    selected_feature
                ),
            },
            "feature_annotation": {
                "status": "mapped"
                if selected_feature in feature_annotations
                else "unmapped",
                "curated_feature_id": feature_annotations.get(selected_feature),
            },
        },
        "comparison": {
            "selection_filters": filter_records,
            "comparison_mode": "symmetric_leave_one_out",
            "feature_id": selected_feature,
            "feature_identity_scope": (
                "exact source-matrix row label; optional user-supplied curation is separate"
            ),
            "normalization": (
                "log2(counts per million + 1)"
                if normalized_normalization_method == "log2_cpm"
                else "TMM-adjusted log2(counts per million + 1)"
            ),
            "normalization_details": _count_normalization_report(
                normalized_normalization_method, matrix.normalization_factors
            ),
            "scale": ExpressionScale.LOG2_CPM.value,
            "context_key": filter_address,
            "source_version": source_version,
            "method": "median/MAD robust outlier with IQR fallback",
            "selected_sample_count": len(cohort_sample_ids),
            "comparison_count": len(observations),
            "reference_count_range": (
                [min(reference_counts), max(reference_counts)] if reference_counts else []
            ),
            "matched_to_case_sample": False,
            "population_level_test": False,
            "multiple_testing_adjustment": "none; one explicitly selected feature was analyzed",
        },
        "result": {
            "call_counts": {
                "descriptive_outlier": calls["descriptive_outlier"],
                "no_descriptive_outlier": calls["no_descriptive_outlier"],
                "unresolved": calls["unresolved"],
            },
            "evidence_state_counts": dict(sorted(states.items())),
            "direction_counts": dict(sorted(directions.items())),
            "reason_code_counts": dict(sorted(reasons.items())),
            "robust_z_range": (
                [round(min(robust_scores), 6), round(max(robust_scores), 6)]
                if robust_scores
                else None
            ),
        },
        "limitations": [
            (
                "Supplementary count-table layouts are not standardized; this importer requires "
                "an explicit delimiter, sample-key column, and matrix row-label contract."
            ),
            (
                "CPM is a library-size transform for descriptive comparison, not a count-model "
                "differential-expression analysis."
            ),
            (
                "TMM normalization is optional and assumes most uniquely identified features "
                "are not differentially expressed; it does not fit a count model."
            ),
            (
                "Each selected observation is compared with the other selected observations; "
                "repeated specimens may not be independent."
            ),
            "Date-shaped feature labels are only flagged for review; no gene identity is "
            "inferred and no source label is normalized.",
            "This is not matched-case evidence, a population-level test, or clinical guidance.",
        ],
    }
    return report_body | {
        "content_address": content_hash(report_body, prefix="geo-count-expression-outlier")
    }


def build_geo_count_contrast_report(
    accession: str,
    *,
    case_filters: Sequence[tuple[str, str]],
    reference_filters: Sequence[tuple[str, str]],
    sample_key_column: str,
    pair_key_column: str,
    counts_file_name: str | None = None,
    metadata_file_name: str | None = None,
    counts_file: str | Path | None = None,
    metadata_file: str | Path | None = None,
    counts_delimiter: str = ",",
    metadata_delimiter: str = ",",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    fdr_threshold: float = 0.05,
    confidence_level: float = DEFAULT_GEO_CONFIDENCE_LEVEL,
    fdr_method: str = "bh",
    top: int = 1_000,
    feature_annotation_file: str | Path | None = None,
    normalization_method: str = "log2_cpm",
) -> dict[str, Any]:
    """Run a paired signed-rank screen over a bounded GEO integer-count matrix.

    The feature table is validated once to compute library sizes and duplicate
    labels, then streamed for per-feature paired tests. Normalization defaults
    to raw-library CPM and can optionally use TMM effective library sizes.
    Exact duplicate feature identifiers are excluded from the testing family;
    their counts still contribute to library sizes.
    A separately adjusted paired sign test and pair-direction counts complement
    the magnitude-sensitive signed-rank result.
    """

    normalized_accession = validate_accession(accession)
    normalized_normalization_method = _normalize_count_normalization_method(normalization_method)
    normalized_case = sorted(
        _normalize_filters(case_filters, "case"),
        key=lambda item: (item[0].casefold(), item[1].casefold()),
    )
    normalized_reference = sorted(
        _normalize_filters(reference_filters, "reference"),
        key=lambda item: (item[0].casefold(), item[1].casefold()),
    )
    pair_field = _required_text(pair_key_column, "GEO pair-key column", maximum=256)
    if not isinstance(sample_key_column, str) or len(sample_key_column) > 256:
        raise ValidationError("GEO metadata sample-key column must be a bounded string")
    if any(ord(character) < 32 for character in sample_key_column):
        raise ValidationError("GEO metadata sample-key column contains control characters")
    if pair_field.casefold() == sample_key_column.casefold():
        raise ValidationError("GEO pair-key and sample-key columns must be different")
    grouping_fields = {field.casefold() for field, _ in (*normalized_case, *normalized_reference)}
    if pair_field.casefold() in grouping_fields:
        raise ValidationError("GEO pair-key column cannot also define a comparison group")
    if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool):
        raise ValidationError("GEO request timeout must be numeric")
    if not 0.1 <= float(timeout_seconds) <= 120.0:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")
    if isinstance(fdr_threshold, bool) or not isinstance(fdr_threshold, (int, float)):
        raise ValidationError("FDR threshold must be numeric")
    fdr_threshold = float(fdr_threshold)
    if not math.isfinite(fdr_threshold) or not 0.0 < fdr_threshold <= 1.0:
        raise ValidationError("FDR threshold must be greater than zero and at most one")
    if (
        isinstance(confidence_level, bool)
        or not isinstance(confidence_level, (int, float))
        or not math.isfinite(confidence_level)
        or not 0.0 < confidence_level < 1.0
    ):
        raise ValidationError("confidence level must be finite and strictly between zero and one")
    confidence_level = float(confidence_level)
    if not isinstance(fdr_method, str) or fdr_method.strip().casefold() not in {"bh", "by"}:
        raise ValidationError("FDR method must be 'bh' or 'by'")
    normalized_fdr_method = fdr_method.strip().casefold()
    if isinstance(top, bool) or not isinstance(top, int) or not 1 <= top <= MAX_CONTRAST_FEATURES:
        raise ValidationError("top result limit must be an integer within the feature bound")
    normalized_count_delimiter = _normalize_delimiter(
        counts_delimiter, "GEO count matrix delimiter"
    )
    normalized_metadata_delimiter = _normalize_delimiter(
        metadata_delimiter, "GEO metadata delimiter"
    )
    feature_annotations, feature_annotation_provenance = _read_feature_annotation_file(
        feature_annotation_file
    )

    count_payload, count_name, count_response_url, count_source_url = _read_supplementary_file(
        normalized_accession,
        label="count matrix",
        file_name=counts_file_name,
        local_file=counts_file,
        timeout_seconds=float(timeout_seconds),
    )
    metadata_payload, metadata_name, metadata_response_url, _ = _read_supplementary_file(
        normalized_accession,
        label="sample metadata",
        file_name=metadata_file_name,
        local_file=metadata_file,
        timeout_seconds=float(timeout_seconds),
    )

    matrix_summary = _GeoCountTableSummary()
    found_annotation_sources: set[str] = set()
    for row in _iter_geo_supplementary_count_rows(
        count_payload,
        delimiter=normalized_count_delimiter,
        summary=matrix_summary,
    ):
        if row[0] in feature_annotations:
            found_annotation_sources.add(row[0])
    if matrix_summary.feature_count > MAX_CONTRAST_FEATURES:
        raise ValidationError(
            f"GEO paired count contrast is limited to {MAX_CONTRAST_FEATURES} feature rows"
        )
    duplicate_feature_row_count = matrix_summary.duplicate_feature_label_count + len(
        matrix_summary.duplicate_feature_ids
    )
    duplicate_annotation_count = len(
        set(feature_annotations).intersection(matrix_summary.duplicate_feature_ids)
    )
    missing_annotation_count = len(set(feature_annotations) - found_annotation_sources)
    if duplicate_annotation_count or missing_annotation_count:
        raise ValidationError(
            "GEO feature annotation map must reference existing unique source rows "
            f"(missing={missing_annotation_count}; duplicated={duplicate_annotation_count})"
        )
    analyzable_feature_count = matrix_summary.feature_count - duplicate_feature_row_count
    if analyzable_feature_count < 1:
        raise ValidationError("GEO count matrix has no uniquely identified features to test")

    requested_fields_by_casefold = {
        field.casefold(): field for field, _ in (*normalized_case, *normalized_reference)
    }
    requested_fields_by_casefold[pair_field.casefold()] = pair_field
    metadata, metadata_headers, metadata_decompressed_bytes = _parse_geo_count_metadata(
        metadata_payload,
        sample_ids=matrix_summary.sample_ids,
        sample_key_column=sample_key_column,
        requested_fields=tuple(requested_fields_by_casefold.values()),
        delimiter=normalized_metadata_delimiter,
    )
    fields_by_casefold = {name.casefold(): name for name in metadata_headers}
    pair_header = fields_by_casefold[pair_field.casefold()]
    pair_field = pair_header

    def selected_samples(filters: Sequence[tuple[str, str]]) -> tuple[str, ...]:
        return tuple(
            sample_id
            for sample_id in matrix_summary.sample_ids
            if all(
                metadata[sample_id][fields_by_casefold[field.casefold()]].casefold()
                == expected.casefold()
                for field, expected in filters
            )
        )

    case_sample_ids = selected_samples(normalized_case)
    reference_sample_ids = selected_samples(normalized_reference)
    if set(case_sample_ids) & set(reference_sample_ids):
        raise ValidationError("GEO case and reference filters select overlapping samples")
    sample_index = {sample_id: index for index, sample_id in enumerate(matrix_summary.sample_ids)}

    def samples_by_pair(sample_ids: Sequence[str], label: str) -> dict[str, str]:
        by_pair: dict[str, str] = {}
        for sample_id in sample_ids:
            pair_value = metadata[sample_id][pair_header].strip()
            if not pair_value:
                raise ValidationError(f"selected GEO {label} sample has a blank pair key")
            if pair_value in by_pair:
                raise ValidationError(f"GEO {label} group has more than one sample per pair key")
            by_pair[pair_value] = sample_id
        return by_pair

    case_by_pair = samples_by_pair(case_sample_ids, "case")
    reference_by_pair = samples_by_pair(reference_sample_ids, "reference")
    matched_pair_keys = tuple(sorted(case_by_pair.keys() & reference_by_pair.keys()))
    if len(matched_pair_keys) < MIN_GEO_COUNT_CONTRAST_PAIRS:
        raise ValidationError("GEO paired count contrast requires at least three complete pairs")

    case_indices = tuple(sample_index[case_by_pair[key]] for key in matched_pair_keys)
    reference_indices = tuple(sample_index[reference_by_pair[key]] for key in matched_pair_keys)
    library_sizes = tuple(matrix_summary.library_sizes)
    normalization_factors = (
        _estimate_geo_tmm_factors(
            count_payload,
            delimiter=normalized_count_delimiter,
            library_sizes=library_sizes,
            duplicate_feature_ids=matrix_summary.duplicate_feature_ids,
        )
        if normalized_normalization_method == "tmm_log2_cpm"
        else (1.0,) * len(library_sizes)
    )
    effective_library_sizes = tuple(
        size * factor for size, factor in zip(library_sizes, normalization_factors, strict=True)
    )
    count_source_sha256 = hashlib.sha256(count_payload).hexdigest()
    metadata_source_sha256 = hashlib.sha256(metadata_payload).hexdigest()
    source_version_inputs = {
        "counts_sha256": count_source_sha256,
        "metadata_sha256": metadata_source_sha256,
    }
    annotation_sha256 = feature_annotation_provenance["source_sha256"]
    if annotation_sha256 is not None:
        annotation_hash_value = str(annotation_sha256).removeprefix("sha256:")
        source_version_inputs["feature_annotation_map_sha256"] = annotation_hash_value
    source_version = content_hash(source_version_inputs, prefix="geo-count-inputs")
    normalized_case_records = [
        {"field": field, "equals": expected} for field, expected in normalized_case
    ]
    normalized_reference_records = [
        {"field": field, "equals": expected} for field, expected in normalized_reference
    ]
    context_key = content_hash(
        {
            "accession": normalized_accession,
            "case_filters": normalized_case_records,
            "reference_filters": normalized_reference_records,
            "pair_key_column": pair_field,
            "normalization_method": normalized_normalization_method,
        },
        prefix="geo-paired-count-contrast",
    )
    rows: list[dict[str, Any]] = []
    tested_rows: list[int] = []
    p_values: list[float] = []
    sign_test_p_values: list[float] = []
    method_counts: Counter[str] = Counter()
    sign_test_method_counts: Counter[str] = Counter()
    detection_thresholds = (1, 5, 10)
    detected_unique_feature_counts = {
        threshold: [0] * len(matrix_summary.sample_ids) for threshold in detection_thresholds
    }
    top_unique_feature_counts = [[] for _ in matrix_summary.sample_ids]
    second_summary = _GeoCountTableSummary()
    for feature_id, counts in _iter_geo_supplementary_count_rows(
        count_payload,
        delimiter=normalized_count_delimiter,
        summary=second_summary,
    ):
        if feature_id in matrix_summary.duplicate_feature_ids:
            continue
        for sample_index, count in enumerate(counts):
            for threshold in detection_thresholds:
                if count >= threshold:
                    detected_unique_feature_counts[threshold][sample_index] += 1
            sample_top_counts = top_unique_feature_counts[sample_index]
            if len(sample_top_counts) < 10:
                heapq.heappush(sample_top_counts, count)
            elif count > sample_top_counts[0]:
                heapq.heapreplace(sample_top_counts, count)
        case_values = tuple(
            math.log2(counts[index] / effective_library_sizes[index] * 1_000_000 + 1)
            for index in case_indices
        )
        reference_values = tuple(
            math.log2(counts[index] / effective_library_sizes[index] * 1_000_000 + 1)
            for index in reference_indices
        )
        differences = tuple(
            case_value - reference_value
            for case_value, reference_value in zip(case_values, reference_values, strict=True)
        )
        rank_biserial, p_value, method, nonzero_pair_count = _paired_signed_rank_test(differences)
        positive_pair_count, negative_pair_count, tied_pair_count, sign_p_value, sign_method = (
            _paired_sign_test(differences)
        )
        mean_difference = _finite_mean(differences)
        median_difference = _finite_median(differences)
        median_difference_interval = _paired_median_sign_interval(
            differences, confidence_level=confidence_level
        )
        pair_deletion_sensitivity = _paired_leave_one_out_median_sensitivity(differences)
        curated_feature_id = feature_annotations.get(feature_id)
        row = {
            "feature_id": feature_id,
            "feature_label_review": _feature_label_review(feature_id),
            "feature_annotation": {
                "status": "mapped" if curated_feature_id is not None else "unmapped",
                "curated_feature_id": curated_feature_id,
            },
            "paired_sample_count": len(matched_pair_keys),
            "nonzero_pair_count": nonzero_pair_count,
            "case_higher_pair_count": positive_pair_count,
            "case_lower_pair_count": negative_pair_count,
            "tied_pair_count": tied_pair_count,
            "case_median_log2_cpm": _finite_median(case_values),
            "reference_median_log2_cpm": _finite_median(reference_values),
            "mean_paired_difference_log2_cpm": mean_difference,
            "median_paired_difference_log2_cpm": median_difference,
            "median_paired_difference_confidence_interval_log2_cpm": median_difference_interval,
            "leave_one_pair_out_median_sensitivity": pair_deletion_sensitivity,
            "matched_pairs_rank_biserial_correlation": rank_biserial,
            "effect_direction": _effect_direction(
                mean_difference, zero_label="no_mean_difference"
            ),
            "mean_effect_direction": _effect_direction(
                mean_difference, zero_label="no_mean_difference"
            ),
            "median_effect_direction": _effect_direction(
                median_difference, zero_label="no_median_difference"
            ),
            "rank_biserial_effect_direction": _effect_direction(
                rank_biserial, zero_label="no_rank_shift"
            ),
            "p_value": p_value,
            "q_value": None,
            "test_method": method,
            "fdr_significant": False,
            "sign_test_p_value": sign_p_value,
            "sign_test_q_value": None,
            "sign_test_method": sign_method,
            "sign_test_fdr_significant": False,
        }
        tested_rows.append(len(rows))
        p_values.append(p_value)
        sign_test_p_values.append(sign_p_value)
        method_counts[method] += 1
        sign_test_method_counts[sign_method] += 1
        rows.append(row)

    if (
        second_summary.sample_ids != matrix_summary.sample_ids
        or second_summary.library_sizes != matrix_summary.library_sizes
        or second_summary.feature_count != matrix_summary.feature_count
        or second_summary.duplicate_feature_label_count
        != matrix_summary.duplicate_feature_label_count
        or second_summary.duplicate_feature_ids != matrix_summary.duplicate_feature_ids
        or second_summary.decompressed_bytes != matrix_summary.decompressed_bytes
    ):
        raise ValidationError("GEO count matrix changed during paired contrast processing")

    def sample_quality_summary(sample_indices: Sequence[int]) -> dict[str, Any]:
        return {
            "sample_count": len(sample_indices),
            "library_size": _finite_distribution_summary(
                [library_sizes[index] for index in sample_indices]
            ),
            "effective_library_size": _finite_distribution_summary(
                [effective_library_sizes[index] for index in sample_indices]
            ),
            "unique_features_detected_by_minimum_count": {
                str(threshold): _finite_distribution_summary(
                    [detected_unique_feature_counts[threshold][index] for index in sample_indices]
                )
                for threshold in detection_thresholds
            },
            "top_unique_feature_share_of_full_library": {
                "top_one": _finite_distribution_summary(
                    [
                        max(top_unique_feature_counts[index], default=0)
                        / library_sizes[index]
                        for index in sample_indices
                    ]
                ),
                "top_ten": _finite_distribution_summary(
                    [
                        math.fsum(top_unique_feature_counts[index]) / library_sizes[index]
                        for index in sample_indices
                    ]
                ),
            },
        }

    case_library_sizes = [library_sizes[index] for index in case_indices]
    reference_library_sizes = [library_sizes[index] for index in reference_indices]
    paired_library_imbalance = [
        max(case_size, reference_size) / min(case_size, reference_size)
        for case_size, reference_size in zip(
            case_library_sizes, reference_library_sizes, strict=True
        )
    ]
    adjusted_p_values = _adjust_p_values(p_values, method=normalized_fdr_method)
    adjusted_sign_test_p_values = _adjust_p_values(sign_test_p_values, method=normalized_fdr_method)
    for row_index, q_value, sign_test_q_value in zip(
        tested_rows, adjusted_p_values, adjusted_sign_test_p_values, strict=True
    ):
        rows[row_index]["q_value"] = q_value
        rows[row_index]["fdr_significant"] = q_value <= fdr_threshold
        rows[row_index]["sign_test_q_value"] = sign_test_q_value
        rows[row_index]["sign_test_fdr_significant"] = sign_test_q_value <= fdr_threshold
    rows.sort(
        key=lambda row: (
            row["q_value"] is None,
            row["q_value"] if row["q_value"] is not None else 1.0,
            row["p_value"],
            row["feature_id"],
        )
    )
    reported_rows = rows[:top]
    significant_count = sum(bool(row["fdr_significant"]) for row in rows)
    sign_test_significant_count = sum(bool(row["sign_test_fdr_significant"]) for row in rows)
    pair_deletion_direction_change_count = sum(
        not row["leave_one_pair_out_median_sensitivity"]["direction_stable"] for row in rows
    )
    significant_pair_deletion_direction_change_count = sum(
        bool(row["fdr_significant"])
        and not row["leave_one_pair_out_median_sensitivity"]["direction_stable"]
        for row in rows
    )
    result_body: dict[str, Any] = {
        "schema": "glio-noncode.geo-paired-count-contrast.v1",
        "status": "completed",
        "source": {
            "database": "NCBI GEO",
            "accession": normalized_accession,
            "series_url": f"{GEO_RECORD_ORIGIN}/geo/query/acc.cgi?acc={normalized_accession}",
            "retrieval": (
                "https"
                if count_response_url is not None or metadata_response_url is not None
                else "local_file"
            ),
            "count_matrix": {
                "file_name": count_name,
                "response_url": count_response_url,
                "source_sha256": f"sha256:{count_source_sha256}",
                "compressed_bytes": len(count_payload),
                "decompressed_bytes": matrix_summary.decompressed_bytes,
            },
            "sample_metadata": {
                "file_name": metadata_name,
                "response_url": metadata_response_url,
                "source_sha256": f"sha256:{metadata_source_sha256}",
                "compressed_bytes": len(metadata_payload),
                "decompressed_bytes": metadata_decompressed_bytes,
            },
            "feature_annotation_map": feature_annotation_provenance,
        },
        "matrix": {
            "feature_row_count": matrix_summary.feature_count,
            "duplicate_feature_label_count": matrix_summary.duplicate_feature_label_count,
            "duplicate_feature_id_count_excluded": len(matrix_summary.duplicate_feature_ids),
            "duplicate_feature_row_count_excluded": duplicate_feature_row_count,
            "uniquely_identified_feature_count_tested": len(rows),
            "sample_count": len(matrix_summary.sample_ids),
            "library_size_method": "sum of all non-negative integer count rows per sample",
            "feature_label_review": _date_like_feature_label_review(matrix_summary),
        },
        "comparison": {
            "case_filters": normalized_case_records,
            "reference_filters": normalized_reference_records,
            "pair_key_column": pair_field,
            "design": "one case and one reference sample per matched pair",
            "matched_pair_count": len(matched_pair_keys),
            "case_sample_count_selected": len(case_sample_ids),
            "reference_sample_count_selected": len(reference_sample_ids),
            "case_sample_count_unmatched": len(case_sample_ids) - len(matched_pair_keys),
            "reference_sample_count_unmatched": len(reference_sample_ids) - len(matched_pair_keys),
            "normalization": (
                "log2(counts per million + 1)"
                if normalized_normalization_method == "log2_cpm"
                else "TMM-adjusted log2(counts per million + 1)"
            ),
            "normalization_details": _count_normalization_report(
                normalized_normalization_method, normalization_factors
            ),
            "effect_size": "matched-pairs rank-biserial correlation",
            "effect_direction_basis": "sign of mean paired difference (compatibility field)",
            "rank_biserial_effect_direction_basis": (
                "sign of matched-pairs rank-biserial correlation"
            ),
            "test": "two-sided paired Wilcoxon signed-rank test on log2-CPM differences",
            "effect_sensitivity": (
                "leave-one-pair-out range and direction of the median paired difference; "
                "descriptive only, with no inferential test refit"
            ),
            "median_difference_interval_method": (
                "central exact sign-order-statistic interval; ties retained; "
                "pointwise and not adjusted across features"
            ),
            "median_difference_interval_confidence_level": confidence_level,
            "exact_test_maximum_nonzero_pairs": MAX_EXACT_SIGNED_RANK_PAIRS,
            "sensitivity_test": (
                "two-sided paired sign test on nonzero log2-CPM differences; ties excluded"
            ),
            "exact_sign_test_maximum_nonzero_pairs": MAX_EXACT_SIGN_TEST_PAIRS,
            "fdr_method": normalized_fdr_method,
            "fdr_threshold": fdr_threshold,
            "multiple_testing_family_count": len(rows),
            "context_key": context_key,
            "source_version": source_version,
            "individual_sample_and_pair_keys_emitted": False,
        },
        "quality_control": {
            "scope": "matched case/reference samples only; unmatched selected samples are excluded",
            "library_size_basis": "all count-matrix rows, including duplicated feature identifiers",
            "feature_detection_basis": (
                "uniquely identified feature rows; duplicated identifiers are excluded"
            ),
            "case": sample_quality_summary(case_indices),
            "reference": sample_quality_summary(reference_indices),
            "paired_library_size_imbalance_fold": _finite_distribution_summary(
                paired_library_imbalance
            ),
            "automatic_sample_exclusion": False,
        },
        "summary": {
            "tested_feature_count": len(rows),
            "fdr_significant_feature_count": significant_count,
            "not_fdr_significant_feature_count": len(rows) - significant_count,
            "test_method_counts": dict(sorted(method_counts.items())),
            "sign_test_fdr_significant_feature_count": sign_test_significant_count,
            "not_sign_test_fdr_significant_feature_count": len(rows) - sign_test_significant_count,
            "sign_test_method_counts": dict(sorted(sign_test_method_counts.items())),
            "pair_deletion_sensitivity": {
                "feature_count": len(rows),
                "features_with_direction_change_count": pair_deletion_direction_change_count,
                "fdr_significant_features_with_direction_change_count": (
                    significant_pair_deletion_direction_change_count
                ),
            },
            "reported_feature_count": len(reported_rows),
            "reported_date_like_feature_label_count": sum(
                _feature_label_is_date_like(str(row["feature_id"])) for row in reported_rows
            ),
            "reported_curated_feature_count": sum(
                row["feature_annotation"]["status"] == "mapped" for row in reported_rows
            ),
        },
        "analysis_limits": {
            "max_compressed_bytes_per_file": MAX_COMPRESSED_BYTES,
            "max_decompressed_bytes_per_file": MAX_DECOMPRESSED_BYTES,
            "max_matrix_line_bytes": MAX_MATRIX_LINE_BYTES,
            "max_samples": MAX_SAMPLE_COUNT,
            "max_feature_rows": MAX_CONTRAST_FEATURES,
            "max_matrix_cells": MAX_MATRIX_CELLS,
            "minimum_complete_pairs": MIN_GEO_COUNT_CONTRAST_PAIRS,
        },
        "results": reported_rows,
        "limitations": [
            (
                "The paired signed-rank test assumes independent pairs and exchangeable signs of "
                "within-pair differences under the null; it is not a negative-binomial count "
                "model or a voom/precision-weighted analysis."
            ),
            (
                "The paired sign-test sensitivity uses only the direction of nonzero differences, "
                "excludes ties, and has lower power when difference magnitudes are informative."
            ),
            (
                "log2(CPM + 1) is a simple library-size transform; gene-specific mean-variance, "
                "batch, purity, and other nuisance effects are not modeled. Optional TMM adjusts "
                "composition under a majority-stable-features assumption but does not fit "
                "a count model."
            ),
            (
                "Rows with repeated exact feature identifiers are excluded from testing to avoid "
                "ambiguous multiple-testing units; all their counts remain in library-size totals."
            ),
            (
                "Date-shaped feature labels are flagged for manual review only; no source label "
                "is normalized and no gene identity is inferred."
            ),
            (
                "Curated feature identifiers, when supplied, are user annotations only; they are "
                "not validated against an external authority, merged, or used in statistical tests."
            ),
            (
                "The result is a cohort-level exploratory association, not a patient-matched "
                "variant claim, causal conclusion, diagnosis, or treatment recommendation."
            ),
        ],
    }
    return result_body | {
        "content_address": content_hash(result_body, prefix="geo-paired-count-contrast")
    }


def _unresolved_result(reason: str) -> dict[str, Any]:
    return {
        "call": "unresolved",
        "direction": ExpressionDirection.UNKNOWN.value,
        "target_value": None,
        "reference_median": None,
        "reference_count": 0,
        "missing_reference_count": 0,
        "dispersion": None,
        "dispersion_method": DispersionMethod.NONE.value,
        "robust_z": None,
        "z_threshold": 3.5,
        "reason_codes": [reason],
    }

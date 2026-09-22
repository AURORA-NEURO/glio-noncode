"""Bounded GEO Series Matrix retrieval and exploratory expression contrasts.

Public-cohort comparisons stay separate from matched-sample RNA evidence. The
module supports single-feature outlier descriptions and explicitly filtered
two-group exploratory screens; neither creates patient-matched claims.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import math
import re
import zlib
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
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
MAX_EXACT_RANK_ASSIGNMENTS = 20_000
MAX_TOTAL_EXACT_RANK_SUMS = 100_000_000
MAX_GEO_COVARIATES = 16
MAX_GEO_MODEL_PARAMETERS = 24
DEFAULT_GEO_CONFIDENCE_LEVEL = 0.95
MAX_METADATA_ROWS = 2_048
MAX_METADATA_VALUE_LENGTH = 8_192
DEFAULT_TIMEOUT_SECONDS = 30.0
_GSE_RE = re.compile(r"GSE[0-9]{1,10}\Z")
_GSM_RE = re.compile(r"GSM[0-9]{1,12}\Z")
_FEATURE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@|/+=_-]{0,255}\Z")
_MISSING_MATRIX_VALUES = frozenset({"", "na", "null"})


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


def _decoded_lines(payload: bytes) -> Iterable[tuple[str, int]]:
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
                    raise ValidationError("GEO Series Matrix line exceeds its byte bound")
                total += len(raw_line)
                if total > MAX_DECOMPRESSED_BYTES:
                    raise ValidationError("GEO Series Matrix exceeds its decompressed byte bound")
                try:
                    line = raw_line.decode("utf-8-sig" if first_line else "utf-8")
                except UnicodeDecodeError as error:
                    raise ValidationError("GEO Series Matrix must use UTF-8 encoding") from error
                first_line = False
                yield line.rstrip("\r\n"), total
    except (EOFError, OSError, gzip.BadGzipFile, zlib.error) as error:
        raise ValidationError("GEO Series Matrix gzip payload is incomplete or invalid") from error


def _metadata_value(
    row: list[str], label: str, *, allow_blank_values: bool = False
) -> list[str]:
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


def _finite_difference(left: float, right: float) -> float | None:
    difference = left - right
    return difference if math.isfinite(difference) else None


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
    top: int = 1_000,
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
    if not isinstance(fdr_method, str):
        raise ValidationError("FDR method must be 'bh' or 'by'")
    normalized_fdr_method = fdr_method.strip().casefold()
    if normalized_fdr_method not in {"bh", "by"}:
        raise ValidationError("FDR method must be 'bh' or 'by'")
    normalized_annotation_columns = tuple(annotation_columns)
    if platform_annotation_file is None and (
        normalized_annotation_columns or annotation_id_column != "ID"
    ):
        raise ValidationError(
            "GEO platform annotation columns require a platform annotation file"
        )
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
    matrix = parse_series_matrix_features(
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
    for feature in matrix.features:
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
                    // max(1, len(matrix.features) * min(len(case_values), len(reference_values))),
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
                "Benjamini-Yekutieli"
                if normalized_fdr_method == "by"
                else "Benjamini-Hochberg"
            )
            + " over all testable matrix features",
            "fdr_method": normalized_fdr_method,
            "fdr_threshold": fdr_threshold,
            "matched_to_case_sample": False,
            "population_generalization": False,
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
            "reported_feature_count": min(top, len(preliminary_rows)),
            "result_limit": top,
            "fdr_family_size": len(tested_rows),
        },
        "analysis_limits": {
            "max_retained_features": MAX_CONTRAST_FEATURES,
            "max_exact_assignments_per_feature": MAX_EXACT_RANK_ASSIGNMENTS,
            "max_exact_rank_sums_per_screen": MAX_TOTAL_EXACT_RANK_SUMS,
            "max_matrix_cells": MAX_MATRIX_CELLS,
        },
        "results": preliminary_rows[:top],
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

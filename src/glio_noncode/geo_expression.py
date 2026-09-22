"""Bounded GEO Series Matrix retrieval and exploratory expression contrasts.

Public-cohort comparisons stay separate from matched-sample RNA evidence. This
module reports one descriptive outlier against an explicit reference group; it
does not create patient-matched claims or population-level tests.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import math
import re
import zlib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import _safe_persistence
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
from .serialization import content_hash

GEO_FTP_ORIGIN = "https://ftp.ncbi.nlm.nih.gov"
GEO_RECORD_ORIGIN = "https://www.ncbi.nlm.nih.gov"
MAX_COMPRESSED_BYTES = 25_000_000
MAX_DECOMPRESSED_BYTES = 256_000_000
MAX_MATRIX_LINE_BYTES = 4_000_000
MAX_SAMPLE_COUNT = 2_000
MAX_FEATURE_COUNT = 1_000_000
MAX_MATRIX_CELLS = 5_000_000
MAX_METADATA_ROWS = 2_048
MAX_METADATA_VALUE_LENGTH = 8_192
DEFAULT_TIMEOUT_SECONDS = 30.0
_GSE_RE = re.compile(r"GSE[0-9]{1,10}\Z")
_GSM_RE = re.compile(r"GSM[0-9]{1,12}\Z")
_FEATURE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@|/+=-]{0,255}\Z")
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


def _metadata_value(row: list[str], label: str) -> list[str]:
    if not row or not row[0].startswith("!"):
        raise ValidationError(f"GEO {label} row is malformed")
    return [
        _required_text(value, f"GEO {label} value", maximum=MAX_METADATA_VALUE_LENGTH)
        for value in row[1:]
    ]


def _parse_characteristic(value: str) -> tuple[str, str]:
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


def parse_series_matrix(
    payload: bytes,
    *,
    accession: str,
    feature_id: str,
    source_file_name: str | None = None,
) -> GeoSeriesMatrix:
    """Parse one bounded GEO matrix and retain values for exactly one feature."""

    requested_accession = validate_accession(accession)
    if not isinstance(payload, bytes):
        raise ValidationError("GEO Series Matrix payload must be bytes")
    if len(payload) > MAX_COMPRESSED_BYTES:
        raise ValidationError("GEO Series Matrix exceeds its compressed byte bound")
    selected_feature = _required_text(feature_id, "GEO feature ID", maximum=256)
    if not _FEATURE_RE.fullmatch(selected_feature):
        raise ValidationError("GEO feature ID contains unsupported characters")
    if source_file_name is not None:
        source_file_name = _required_text(source_file_name, "GEO source file name", maximum=255)
        if Path(source_file_name).name != source_file_name or "\\" in source_file_name:
            raise ValidationError("GEO source file name must not contain a directory path")
    if type(payload) is not bytes or not payload or len(payload) > MAX_COMPRESSED_BYTES:
        raise ValidationError("GEO Series Matrix payload is empty or exceeds its byte bound")

    series: dict[str, list[str]] = {}
    sample_rows: dict[str, list[str]] = {}
    sample_characteristics: list[list[tuple[str, str]]] = []
    sample_processing: list[list[str]] = []
    samples: tuple[GeoSample, ...] = ()
    matrix_values: tuple[float | None, ...] | None = None
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
                values = tuple(_matrix_number(value) for value in row[1:])
                if row_feature == selected_feature:
                    if matrix_values is not None:
                        raise ValidationError("GEO matrix repeats the selected feature ID")
                    matrix_values = values
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
                values = _metadata_value(row, key)
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
    if matrix_values is None:
        raise ValidationError("GEO Series Matrix does not contain the selected feature ID")
    titles = series.get("Series_title", [])
    series_types = tuple(dict.fromkeys(series.get("Series_type", [])))
    platform_ids = tuple(dict.fromkeys(series.get("Series_platform_id", [])))
    if not platform_ids:
        platform_ids = tuple(
            dict.fromkeys(sample.platform_id for sample in samples if sample.platform_id)
        )
    processing = tuple(dict.fromkeys(value for row in sample_processing for value in row))
    return GeoSeriesMatrix(
        accession=requested_accession,
        title=titles[0] if titles else "",
        series_types=series_types,
        platform_ids=platform_ids,
        samples=samples,
        processing_descriptions=processing[:16],
        feature_count=feature_count,
        feature_id=selected_feature,
        feature_values=matrix_values,
        source_sha256=hashlib.sha256(payload).hexdigest(),
        source_url=series_matrix_url(requested_accession),
        source_file_name=source_file_name,
        compressed_bytes=len(payload),
        decompressed_bytes=decompressed_bytes,
    )


def _build_samples(
    accessions: Sequence[str],
    sample_rows: dict[str, list[str]],
    characteristic_rows: Sequence[Sequence[tuple[str, str]]],
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
    if isinstance(reference_filters, (str, bytes)) or not isinstance(reference_filters, Sequence):
        raise ValidationError("reference filters must be a sequence of field/value pairs")
    if not reference_filters or len(reference_filters) > 32:
        raise ValidationError("one to 32 explicit reference filters are required")
    normalized_filters: list[tuple[str, str]] = []
    for item in reference_filters:
        if not isinstance(item, Sequence) or isinstance(item, (str, bytes)) or len(item) != 2:
            raise ValidationError("each reference filter must contain one field and one value")
        field = _required_text(item[0], "reference characteristic field", maximum=256)
        expected = _required_text(item[1], "reference characteristic value", maximum=1024)
        if any(field.casefold() == prior[0].casefold() for prior in normalized_filters):
            raise ValidationError("reference characteristic fields must be unique")
        normalized_filters.append((field, expected))
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

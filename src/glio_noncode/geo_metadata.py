"""Bounded GEO Series Matrix sample-characteristic and design summaries."""

from __future__ import annotations

import csv
import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .geo_expression import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_COMPRESSED_BYTES,
    MAX_CONTRAST_FEATURES,
    MAX_DECOMPRESSED_BYTES,
    MAX_METADATA_ROWS,
    MAX_METADATA_VALUE_LENGTH,
    MAX_SAMPLE_COUNT,
    MIN_GEO_COUNT_CONTRAST_PAIRS,
    _date_like_feature_label_review,
    _decoded_lines,
    _GeoCountTableSummary,
    _iter_geo_supplementary_count_rows,
    _normalize_delimiter,
    _normalize_filters,
    _parse_geo_count_metadata,
    _read_matrix,
    _read_supplementary_file,
    _required_text,
    parse_series_matrix_metadata,
    validate_accession,
)
from .serialization import content_hash

MAX_CATEGORY_KEYS = 50_000
MAX_REPORTED_CATEGORIES_PER_FIELD = 100
MAX_REPORTED_COUNT_METADATA_CATEGORIES = 25
MAX_COUNT_METADATA_CATEGORY_VALUE_LENGTH = 1_024


def build_geo_sample_metadata_report(
    accession: str,
    *,
    matrix_file: str | Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Summarize sample annotations without retaining expression feature vectors."""

    normalized_accession = validate_accession(accession)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")
    try:
        timeout = float(timeout_seconds)
    except OverflowError as error:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds") from error
    if not math.isfinite(timeout) or not 0.1 <= timeout <= 120.0:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")

    payload, response_url, source_file_name = _read_matrix(
        normalized_accession,
        matrix_file=matrix_file,
        timeout_seconds=timeout,
    )
    matrix = parse_series_matrix_metadata(
        payload,
        accession=normalized_accession,
        source_file_name=source_file_name,
    )
    sample_count = len(matrix.samples)
    if not 1 <= sample_count <= MAX_SAMPLE_COUNT:
        raise ValidationError("GEO metadata summary requires at least one bounded sample")
    if matrix.feature_count < 1:
        raise ValidationError("GEO metadata summary requires at least one matrix feature")

    fields: dict[str, dict[str, Any]] = {}
    distinct_annotation_count = 0
    annotation_entry_count = 0
    duplicate_annotation_count = 0

    for sample in matrix.samples:
        values_by_field: dict[str, set[str]] = {}
        field_display: dict[str, str] = {}
        sample_pairs: set[tuple[str, str]] = set()
        for field_name, value in sample.characteristics:
            annotation_entry_count += 1
            field_key = field_name.casefold()
            value_key = value.casefold()
            field_display.setdefault(field_key, field_name)
            pair = (field_key, value_key)
            if pair in sample_pairs:
                duplicate_annotation_count += 1
                continue
            sample_pairs.add(pair)
            values_by_field.setdefault(field_key, set()).add(value_key)
            state = fields.setdefault(
                field_key,
                {
                    "field": field_display[field_key],
                    "sample_count": 0,
                    "multiple_value_sample_count": 0,
                    "categories": {},
                },
            )
            categories = state["categories"]
            category = categories.get(value_key)
            if category is None:
                if distinct_annotation_count >= MAX_CATEGORY_KEYS:
                    raise ValidationError(
                        "GEO sample metadata exceeds the distinct field/value category bound"
                    )
                category = {"value": value, "sample_count": 0}
                categories[value_key] = category
                distinct_annotation_count += 1
            category["sample_count"] += 1

        for field_key, category_values in values_by_field.items():
            state = fields[field_key]
            state["sample_count"] += 1
            if len(category_values) > 1:
                state["multiple_value_sample_count"] += 1

    field_rows: list[dict[str, Any]] = []
    reported_category_count = 0
    omitted_category_count = 0
    omitted_category_sample_memberships = 0
    for field_key in sorted(fields):
        state = fields[field_key]
        categories = sorted(
            state["categories"].values(),
            key=lambda item: (-item["sample_count"], item["value"].casefold(), item["value"]),
        )
        reported_categories = categories[:MAX_REPORTED_CATEGORIES_PER_FIELD]
        omitted_categories = categories[MAX_REPORTED_CATEGORIES_PER_FIELD:]
        omitted_category_count += len(omitted_categories)
        omitted_category_sample_memberships += sum(
            item["sample_count"] for item in omitted_categories
        )
        reported_category_count += len(reported_categories)
        field_rows.append(
            {
                "field": state["field"],
                "sample_count": state["sample_count"],
                "missing_sample_count": sample_count - state["sample_count"],
                "coverage_fraction": state["sample_count"] / sample_count,
                "multiple_value_sample_count": state["multiple_value_sample_count"],
                "distinct_value_count": len(categories),
                "reported_value_count": len(reported_categories),
                "values_truncated": bool(omitted_categories),
                "omitted_value_count": len(omitted_categories),
                "omitted_value_sample_memberships": sum(
                    item["sample_count"] for item in omitted_categories
                ),
                "values": reported_categories,
            }
        )

    samples = [
        {
            "sample_accession": sample.accession,
            "title": sample.title,
            "source_name": sample.source_name,
            "platform_id": sample.platform_id,
        }
        for sample in matrix.samples
    ]
    body: dict[str, Any] = {
        "schema": "glio-noncode.geo-sample-metadata.v1",
        "status": "completed",
        "source": {
            "database": "NCBI GEO",
            "accession": matrix.accession,
            "series_url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={matrix.accession}",
            "matrix_url": matrix.source_url,
            "retrieval": "local_file" if source_file_name is not None else "https",
            "response_url": response_url,
            "source_file_name": source_file_name,
            "source_sha256": f"sha256:{matrix.source_sha256}",
            "compressed_bytes": matrix.compressed_bytes,
            "decompressed_bytes": matrix.decompressed_bytes,
            "series_title": matrix.title,
            "series_types": list(matrix.series_types),
            "platform_ids": list(matrix.platform_ids),
            "processing_descriptions": list(matrix.processing_descriptions),
            "sample_count": sample_count,
            "feature_count": matrix.feature_count,
        },
        "analysis": {
            "expression_values_retained": False,
            "expression_values_validated": True,
            "field_value_matching": "case-insensitive Unicode casefold",
            "display_spelling": "first observed source spelling",
            "automatic_sample_classification": False,
            "automatic_group_assignment": False,
        },
        "summary": {
            "sample_count": sample_count,
            "samples_with_characteristics_count": sum(
                bool(sample.characteristics) for sample in matrix.samples
            ),
            "samples_without_characteristics_count": sum(
                not sample.characteristics for sample in matrix.samples
            ),
            "characteristic_field_count": len(field_rows),
            "characteristic_annotation_entry_count": annotation_entry_count,
            "distinct_characteristic_entry_count": (
                annotation_entry_count - duplicate_annotation_count
            ),
            "duplicate_characteristic_entry_count": duplicate_annotation_count,
            "distinct_field_value_category_count": distinct_annotation_count,
            "reported_category_count": reported_category_count,
            "omitted_category_count": omitted_category_count,
            "omitted_category_sample_memberships": omitted_category_sample_memberships,
        },
        "samples": samples,
        "characteristics": field_rows,
        "limitations": [
            "This report inventories GEO sample annotations; it does not decide which values "
            "represent cases, controls, or clinically meaningful groups.",
            "Category counts are sample counts after duplicate annotations within a sample "
            "are collapsed.",
            "Field labels and category values are aggregated case-insensitively; the first "
            "observed source spelling is shown.",
            "At most 100 category values per field are listed; omitted-category counts and "
            "sample memberships remain explicit.",
            "Expression values are validated but not retained, transformed, or analyzed.",
            "GEO metadata are submitter supplied and may be incomplete, inconsistent, or "
            "ambiguous.",
            "Research use only; this report does not support diagnosis or treatment decisions.",
        ],
    }
    return body | {"content_address": content_hash(body, prefix="geo-sample-metadata")}


def _identifier_like_metadata_field(field_name: str) -> bool:
    tokens = set(re.split(r"[^a-z0-9]+", field_name.casefold()))
    return bool(
        tokens
        & {
            "accession",
            "barcode",
            "donor",
            "identifier",
            "id",
            "key",
            "participant",
            "patient",
            "sample",
            "subject",
        }
    )


def build_geo_count_metadata_report(
    accession: str,
    *,
    sample_key_column: str,
    pair_key_column: str | None = None,
    metadata_file_name: str | None = None,
    metadata_file: str | Path | None = None,
    metadata_delimiter: str = ",",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Inventory supplementary count-matrix metadata without emitting row keys.

    This report exposes bounded category frequencies for cohort-filter discovery,
    verifies metadata sample-key uniqueness, and optionally summarizes repeated
    pair-key coverage. Count-matrix joins and group assignments remain the
    responsibility of the downstream contrast command.
    """

    normalized_accession = validate_accession(accession)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")
    try:
        timeout = float(timeout_seconds)
    except OverflowError as error:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds") from error
    if not math.isfinite(timeout) or not 0.1 <= timeout <= 120.0:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")
    if not isinstance(sample_key_column, str) or len(sample_key_column) > 256:
        raise ValidationError("GEO metadata sample-key column must be a bounded string")
    if any(ord(character) < 32 for character in sample_key_column):
        raise ValidationError("GEO metadata sample-key column contains control characters")
    if pair_key_column is not None:
        pair_key_column = _required_text(
            pair_key_column, "GEO metadata pair-key column", maximum=256
        )
        if pair_key_column.casefold() == sample_key_column.casefold():
            raise ValidationError("GEO metadata pair-key and sample-key columns must differ")
    delimiter = _normalize_delimiter(metadata_delimiter, "GEO metadata delimiter")
    payload, file_name, response_url, source_url = _read_supplementary_file(
        normalized_accession,
        label="sample metadata",
        file_name=metadata_file_name,
        local_file=metadata_file,
        timeout_seconds=timeout,
    )
    if len(payload) > MAX_COMPRESSED_BYTES:
        raise ValidationError("GEO supplementary metadata exceeds its compressed byte bound")

    decompressed_bytes = 0

    def decoded_text_lines() -> Iterator[str]:
        nonlocal decompressed_bytes
        for line, total in _decoded_lines(payload, label="supplementary sample metadata"):
            decompressed_bytes = total
            yield line

    reader = csv.reader(decoded_text_lines(), delimiter=delimiter, strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error) as error:
        raise ValidationError("GEO supplementary sample metadata has no valid header") from error
    if not header or len(header) > 256:
        raise ValidationError("GEO supplementary sample metadata has an invalid column count")
    if any(len(name) > 256 or any(ord(char) < 32 for char in name) for name in header):
        raise ValidationError("GEO supplementary sample metadata has an invalid column name")
    header_keys = [name.casefold() for name in header]
    if len(header_keys) != len(set(header_keys)):
        raise ValidationError("GEO supplementary sample metadata has duplicate columns")
    sample_key_matches = [index for index, name in enumerate(header) if name == sample_key_column]
    if len(sample_key_matches) != 1:
        raise ValidationError("GEO metadata sample-key column must match one exact header")
    sample_key_index = sample_key_matches[0]
    header_by_key = {name.casefold(): name for name in header}
    pair_header = None
    pair_key_index = None
    if pair_key_column is not None:
        pair_header = header_by_key.get(pair_key_column.casefold())
        if pair_header is None:
            raise ValidationError("GEO metadata pair-key column is absent from the header")
        pair_key_index = header.index(pair_header)

    columns: list[dict[str, Any]] = [
        {
            "field": name,
            "column_index": index,
            "blank_value_count": 0,
            "whitespace_only_value_count": 0,
            "nonblank_value_count": 0,
            "categories": {},
            "category_overflow": False,
        }
        for index, name in enumerate(header)
    ]
    sample_ids: set[str] = set()
    pair_counts: dict[str, int] = {}
    metadata_row_count = 0
    try:
        for row in reader:
            if not row or len(row) != len(header):
                raise ValidationError("GEO supplementary sample metadata contains a ragged row")
            metadata_row_count += 1
            if metadata_row_count > MAX_METADATA_ROWS:
                raise ValidationError("GEO supplementary sample metadata exceeds its row limit")
            if any(
                len(value) > MAX_METADATA_VALUE_LENGTH
                or any(ord(character) < 32 for character in value)
                for value in row
            ):
                raise ValidationError("GEO supplementary sample metadata contains invalid values")
            sample_id = _required_text(
                row[sample_key_index], "GEO metadata sample key", maximum=256
            )
            if sample_id in sample_ids:
                raise ValidationError("GEO supplementary sample metadata has duplicate sample keys")
            sample_ids.add(sample_id)

            for index, value in enumerate(row):
                state = columns[index]
                if value == "":
                    state["blank_value_count"] += 1
                    continue
                if not value.strip():
                    state["whitespace_only_value_count"] += 1
                    continue
                state["nonblank_value_count"] += 1
                if index == sample_key_index or index == pair_key_index:
                    continue
                if state["category_overflow"]:
                    continue
                normalized_value = value.casefold()
                category = state["categories"].get(normalized_value)
                if category is None:
                    if len(state["categories"]) >= MAX_REPORTED_COUNT_METADATA_CATEGORIES:
                        state["categories"].clear()
                        state["category_overflow"] = True
                        continue
                    category = {"value": value, "sample_count": 0}
                    state["categories"][normalized_value] = category
                category["sample_count"] += 1

            if pair_key_index is not None:
                pair_value = row[pair_key_index].strip()
                if pair_value:
                    pair_counts[pair_value] = pair_counts.get(pair_value, 0) + 1
    except csv.Error as error:
        raise ValidationError(
            "GEO supplementary sample metadata is not valid delimited text"
        ) from error

    if metadata_row_count < 1 or decompressed_bytes < 1:
        raise ValidationError("GEO supplementary sample metadata is empty")
    if decompressed_bytes > MAX_DECOMPRESSED_BYTES:
        raise ValidationError(
            "GEO supplementary sample metadata exceeds its decompressed byte bound"
        )
    if len(sample_ids) > MAX_SAMPLE_COUNT:
        raise ValidationError("GEO supplementary sample metadata exceeds its sample limit")

    field_rows: list[dict[str, Any]] = []
    distinct_category_count_lower_bound = 0
    suppressed_field_count = 0
    for index, state in enumerate(columns):
        field = state["field"]
        is_sample_key = index == sample_key_index
        is_pair_key = index == pair_key_index
        category_overflow = state["category_overflow"]
        categories = state["categories"]
        if is_sample_key:
            distinct_count = metadata_row_count
            distinct_count_is_lower_bound = False
        elif is_pair_key:
            distinct_count = len(pair_counts)
            distinct_count_is_lower_bound = False
        else:
            distinct_count = (
                MAX_REPORTED_COUNT_METADATA_CATEGORIES + 1
                if category_overflow
                else len(categories)
            )
            distinct_count_is_lower_bound = category_overflow
            distinct_category_count_lower_bound += distinct_count
        identifier_like = _identifier_like_metadata_field(field)
        if is_sample_key:
            suppression_reason = "sample_key"
        elif is_pair_key:
            suppression_reason = "pair_key"
        elif identifier_like:
            suppression_reason = "identifier_like_field_name"
        elif category_overflow:
            suppression_reason = "category_limit_exceeded"
        else:
            suppression_reason = None
        values_suppressed = suppression_reason is not None
        if values_suppressed:
            suppressed_field_count += 1
            values: list[dict[str, Any]] = []
        else:
            ordered_categories = sorted(
                categories.values(),
                key=lambda item: (
                    -item["sample_count"],
                    item["value"].casefold(),
                    item["value"],
                ),
            )
            values = [
                {
                    "value": item["value"][:MAX_COUNT_METADATA_CATEGORY_VALUE_LENGTH],
                    "sample_count": item["sample_count"],
                    "value_truncated": (
                        len(item["value"]) > MAX_COUNT_METADATA_CATEGORY_VALUE_LENGTH
                    ),
                    "filter_value_round_trippable": (
                        item["value"] == item["value"].strip()
                        and len(item["value"]) <= MAX_COUNT_METADATA_CATEGORY_VALUE_LENGTH
                    ),
                }
                for item in ordered_categories
            ]
        field_rows.append(
            {
                "field": field,
                "column_index": index,
                "filter_field_round_trippable": bool(field)
                and field == field.strip()
                and not is_sample_key
                and not is_pair_key,
                "sample_count": metadata_row_count,
                "blank_value_count": state["blank_value_count"],
                "whitespace_only_value_count": state["whitespace_only_value_count"],
                "nonblank_value_count": state["nonblank_value_count"],
                "distinct_value_count": distinct_count,
                "distinct_value_count_is_lower_bound": distinct_count_is_lower_bound,
                "reported_value_count": len(values),
                "values_suppressed": values_suppressed,
                "values_suppression_reason": suppression_reason,
                "values": values,
            }
        )

    pair_summary = None
    if pair_key_index is not None and pair_header is not None:
        pair_row_count = sum(pair_counts.values())
        repeated_key_counts = [count for count in pair_counts.values() if count > 1]
        pair_summary = {
            "field": pair_header,
            "nonblank_pair_key_row_count": pair_row_count,
            "blank_pair_key_row_count": metadata_row_count - pair_row_count,
            "nonblank_pair_key_coverage_fraction": pair_row_count / metadata_row_count,
            "distinct_pair_key_count": len(pair_counts),
            "repeated_pair_key_count": len(repeated_key_counts),
            "rows_beyond_first_per_pair_key_count": sum(
                count - 1 for count in pair_counts.values()
            ),
            "rows_with_repeated_pair_key_count": sum(repeated_key_counts),
            "maximum_rows_per_pair_key": max(pair_counts.values(), default=0),
            "pair_key_values_emitted": False,
        }

    metadata_sha256 = hashlib.sha256(payload).hexdigest()
    report_body: dict[str, Any] = {
        "schema": "glio-noncode.geo-count-metadata.v1",
        "status": "completed",
        "source": {
            "database": "NCBI GEO",
            "accession": normalized_accession,
            "series_url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={normalized_accession}",
            "file_name": file_name,
            "response_url": response_url,
            "source_url": source_url,
            "retrieval": "https" if source_url is not None else "local_file",
            "source_sha256": f"sha256:{metadata_sha256}",
            "compressed_bytes": len(payload),
            "decompressed_bytes": decompressed_bytes,
        },
        "analysis": {
            "metadata_row_count": metadata_row_count,
            "column_count": len(header),
            "sample_key_column": sample_key_column,
            "sample_key_unique": True,
            "pair_key_column": pair_header,
            "sample_key_values_emitted": False,
            "pair_key_values_emitted": False,
            "automatic_group_assignment": False,
            "filter_matching": (
                "field names are case-insensitive and CLI-trimmed; values are "
                "case-insensitive and metadata whitespace is preserved"
            ),
            "maximum_reported_categories_per_field": MAX_REPORTED_COUNT_METADATA_CATEGORIES,
            "maximum_reported_category_value_length": MAX_COUNT_METADATA_CATEGORY_VALUE_LENGTH,
        },
        "summary": {
            "sample_count": metadata_row_count,
            "column_count": len(header),
            "distinct_non_key_category_count_lower_bound": distinct_category_count_lower_bound,
            "fields_with_suppressed_values_count": suppressed_field_count,
            "pair_key": pair_summary,
        },
        "columns": field_rows,
        "limitations": [
            (
                "This report inventories only the supplementary sample-metadata table; "
                "it does not validate a join to a count matrix."
            ),
            (
                "The downstream count analysis validates exact metadata/count-matrix "
                "sample-key equality."
            ),
            (
                "Cohort groups are not inferred; choose exact fields and values explicitly "
                "from the report."
            ),
            (
                "Sample and pair-key values are never emitted. Identifier-like columns "
                "suppress category labels."
            ),
            (
                "Fields with more than the reported category bound show a distinct-value "
                "lower bound and no values."
            ),
            (
                "Filter field names are trimmed by the CLI. Metadata values are not "
                "trimmed; leading or trailing whitespace can make a listed value "
                "unusable in the CLI."
            ),
            (
                "GEO metadata are submitter supplied and may be incomplete, inconsistent, "
                "or ambiguous."
            ),
            "Research use only; this report does not support diagnosis or treatment decisions.",
        ],
    }
    return report_body | {
        "content_address": content_hash(report_body, prefix="geo-count-metadata")
    }


def build_geo_count_contrast_design_report(
    accession: str,
    *,
    case_filters: tuple[tuple[str, str], ...] | list[tuple[str, str]],
    reference_filters: tuple[tuple[str, str], ...] | list[tuple[str, str]],
    sample_key_column: str,
    pair_key_column: str,
    counts_file_name: str | None = None,
    metadata_file_name: str | None = None,
    counts_file: str | Path | None = None,
    metadata_file: str | Path | None = None,
    counts_delimiter: str = ",",
    metadata_delimiter: str = ",",
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Validate a supplementary-count contrast design without feature tests.

    The bounded count matrix is fully scanned for structural and integer-count
    validity, then its sample keys are joined exactly to the metadata table.
    Only aggregate group and pair-key counts are returned; sample and pair IDs
    remain internal to the join.
    """

    normalized_accession = validate_accession(accession)
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
    grouping_fields = {
        field.casefold() for field, _ in (*normalized_case, *normalized_reference)
    }
    if pair_field.casefold() in grouping_fields:
        raise ValidationError("GEO pair-key column cannot also define a comparison group")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise ValidationError("GEO request timeout must be numeric")
    try:
        timeout = float(timeout_seconds)
    except OverflowError as error:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds") from error
    if not math.isfinite(timeout) or not 0.1 <= timeout <= 120.0:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")

    count_delimiter = _normalize_delimiter(counts_delimiter, "GEO count matrix delimiter")
    metadata_delimiter = _normalize_delimiter(metadata_delimiter, "GEO metadata delimiter")
    count_payload, count_name, count_response_url, count_source_url = _read_supplementary_file(
        normalized_accession,
        label="count matrix",
        file_name=counts_file_name,
        local_file=counts_file,
        timeout_seconds=timeout,
    )
    metadata_payload, metadata_name, metadata_response_url, metadata_source_url = (
        _read_supplementary_file(
            normalized_accession,
            label="sample metadata",
            file_name=metadata_file_name,
            local_file=metadata_file,
            timeout_seconds=timeout,
        )
    )

    matrix_summary = _GeoCountTableSummary()
    for _ in _iter_geo_supplementary_count_rows(
        count_payload,
        delimiter=count_delimiter,
        summary=matrix_summary,
    ):
        pass
    requested_fields = {
        field.casefold(): field
        for field, _ in (*normalized_case, *normalized_reference)
    }
    requested_fields[pair_field.casefold()] = pair_field
    metadata, metadata_headers, metadata_decompressed_bytes = _parse_geo_count_metadata(
        metadata_payload,
        sample_ids=matrix_summary.sample_ids,
        sample_key_column=sample_key_column,
        requested_fields=tuple(requested_fields.values()),
        delimiter=metadata_delimiter,
        require_exact_sample_set=False,
    )
    fields_by_casefold = {name.casefold(): name for name in metadata_headers}
    pair_header = fields_by_casefold[pair_field.casefold()]
    matrix_sample_keys = set(matrix_summary.sample_ids)
    metadata_sample_keys = set(metadata)
    joined_sample_ids = tuple(
        sample_id for sample_id in matrix_summary.sample_ids if sample_id in metadata_sample_keys
    )
    count_sample_keys_without_metadata_count = len(matrix_sample_keys - metadata_sample_keys)
    metadata_sample_keys_without_count_count = len(metadata_sample_keys - matrix_sample_keys)
    exact_sample_key_join = not (
        count_sample_keys_without_metadata_count or metadata_sample_keys_without_count_count
    )

    def select_samples(filters: tuple[tuple[str, str], ...]) -> tuple[str, ...]:
        return tuple(
            sample_id
            for sample_id in joined_sample_ids
            if all(
                metadata[sample_id][fields_by_casefold[field.casefold()]].casefold()
                == expected.casefold()
                for field, expected in filters
            )
        )

    case_sample_ids = select_samples(normalized_case)
    reference_sample_ids = select_samples(normalized_reference)
    case_ids = set(case_sample_ids)
    reference_ids = set(reference_sample_ids)
    overlap_count = len(case_ids & reference_ids)
    selected_ids = case_ids | reference_ids

    def pair_counts(sample_ids: tuple[str, ...]) -> tuple[Counter[str], int]:
        counts: Counter[str] = Counter()
        blank_count = 0
        for sample_id in sample_ids:
            pair_value = metadata[sample_id][pair_header].strip()
            if pair_value:
                counts[pair_value] += 1
            else:
                blank_count += 1
        return counts, blank_count

    case_pair_counts, case_blank_pair_count = pair_counts(case_sample_ids)
    reference_pair_counts, reference_blank_pair_count = pair_counts(reference_sample_ids)
    case_unique_pair_keys = {
        pair_key for pair_key, count in case_pair_counts.items() if count == 1
    }
    reference_unique_pair_keys = {
        pair_key for pair_key, count in reference_pair_counts.items() if count == 1
    }
    matched_pair_count = len(case_unique_pair_keys & reference_unique_pair_keys)
    case_duplicate_pair_key_count = sum(count > 1 for count in case_pair_counts.values())
    reference_duplicate_pair_key_count = sum(
        count > 1 for count in reference_pair_counts.values()
    )
    case_duplicate_extra_sample_count = sum(
        count - 1 for count in case_pair_counts.values() if count > 1
    )
    reference_duplicate_extra_sample_count = sum(
        count - 1 for count in reference_pair_counts.values() if count > 1
    )

    duplicate_feature_row_count = matrix_summary.duplicate_feature_label_count + len(
        matrix_summary.duplicate_feature_ids
    )
    unique_feature_count = matrix_summary.feature_count - duplicate_feature_row_count
    reasons: list[str] = []
    if not exact_sample_key_join:
        reasons.append("count matrix and metadata sample keys do not match exactly")
    if overlap_count:
        reasons.append("case and reference filters select overlapping samples")
    if case_blank_pair_count or reference_blank_pair_count:
        reasons.append("one or more selected samples have a blank pair key")
    if case_duplicate_pair_key_count or reference_duplicate_pair_key_count:
        reasons.append("a selected group has more than one sample for a pair key")
    if matched_pair_count < MIN_GEO_COUNT_CONTRAST_PAIRS:
        reasons.append(
            f"fewer than {MIN_GEO_COUNT_CONTRAST_PAIRS} complete unique pairs are available"
        )
    if matrix_summary.feature_count > MAX_CONTRAST_FEATURES:
        reasons.append(
            f"feature rows exceed the contrast limit of {MAX_CONTRAST_FEATURES}"
        )
    if unique_feature_count < 1:
        reasons.append("the count matrix has no uniquely labeled features to test")

    source_body = {
        "database": "NCBI GEO",
        "accession": normalized_accession,
        "series_url": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={normalized_accession}",
        "retrieval": (
            "https"
            if count_source_url is not None or metadata_source_url is not None
            else "local_file"
        ),
        "count_matrix": {
            "file_name": count_name,
            "retrieval": "https" if count_source_url is not None else "local_file",
            "response_url": count_response_url,
            "source_sha256": f"sha256:{hashlib.sha256(count_payload).hexdigest()}",
            "compressed_bytes": len(count_payload),
            "decompressed_bytes": matrix_summary.decompressed_bytes,
        },
        "sample_metadata": {
            "file_name": metadata_name,
            "retrieval": "https" if metadata_source_url is not None else "local_file",
            "response_url": metadata_response_url,
            "source_sha256": f"sha256:{hashlib.sha256(metadata_payload).hexdigest()}",
            "compressed_bytes": len(metadata_payload),
            "decompressed_bytes": metadata_decompressed_bytes,
        },
    }
    report_body: dict[str, Any] = {
        "schema": "glio-noncode.geo-count-contrast-design.v1",
        "status": "completed",
        "source": source_body,
        "analysis": {
            "count_values_validated": True,
            "count_rows_fully_scanned": True,
            "metadata_sample_keys_joined_exactly": exact_sample_key_join,
            "sample_and_pair_ids_emitted": False,
            "expression_values_retained": False,
            "effect_sizes_calculated": False,
            "p_values_calculated": False,
            "filter_matching": (
                "field names are case-insensitive; values are case-insensitive and "
                "metadata whitespace is preserved"
            ),
        },
        "matrix": {
            "sample_count": len(matrix_summary.sample_ids),
            "feature_row_count": matrix_summary.feature_count,
            "duplicate_feature_label_count": matrix_summary.duplicate_feature_label_count,
            "duplicate_feature_id_count_excluded": len(matrix_summary.duplicate_feature_ids),
            "duplicate_feature_row_count_excluded": duplicate_feature_row_count,
            "uniquely_labeled_feature_count": unique_feature_count,
            "feature_label_review": _date_like_feature_label_review(matrix_summary),
        },
        "comparison": {
            "sample_key_join": {
                "exact_match": exact_sample_key_join,
                "count_matrix_sample_key_count": len(matrix_sample_keys),
                "metadata_sample_key_count": len(metadata_sample_keys),
                "joined_sample_key_count": len(joined_sample_ids),
                "count_matrix_sample_key_without_metadata_count": (
                    count_sample_keys_without_metadata_count
                ),
                "metadata_sample_key_without_count_matrix_count": (
                    metadata_sample_keys_without_count_count
                ),
                "sample_key_values_emitted": False,
            },
            "group_selection_basis": (
                "metadata rows whose sample keys exactly match count-matrix sample keys"
            ),
            "case_filters": [
                {"field": field, "equals": expected} for field, expected in normalized_case
            ],
            "reference_filters": [
                {"field": field, "equals": expected}
                for field, expected in normalized_reference
            ],
            "pair_key_column": pair_header,
            "case_sample_count_selected": len(case_sample_ids),
            "reference_sample_count_selected": len(reference_sample_ids),
            "overlap_sample_count": overlap_count,
            "unassigned_sample_count": len(matrix_summary.sample_ids) - len(selected_ids),
            "case_blank_pair_key_sample_count": case_blank_pair_count,
            "reference_blank_pair_key_sample_count": reference_blank_pair_count,
            "case_duplicate_pair_key_count": case_duplicate_pair_key_count,
            "reference_duplicate_pair_key_count": reference_duplicate_pair_key_count,
            "case_duplicate_extra_sample_count": case_duplicate_extra_sample_count,
            "reference_duplicate_extra_sample_count": reference_duplicate_extra_sample_count,
            "matched_pair_count": matched_pair_count,
            "case_sample_count_unmatched": len(case_sample_ids) - matched_pair_count,
            "reference_sample_count_unmatched": len(reference_sample_ids) - matched_pair_count,
            "sample_and_pair_ids_emitted": False,
        },
        "design": {
            "state": "estimable" if not reasons else "not_estimable",
            "estimable": not reasons,
            "method": "one case and one reference sample per unique matched pair",
            "minimum_complete_pairs": MIN_GEO_COUNT_CONTRAST_PAIRS,
            "complete_pair_count": matched_pair_count,
            "reasons": reasons,
        },
        "summary": {
            "design_estimable": not reasons,
            "case_sample_count": len(case_sample_ids),
            "reference_sample_count": len(reference_sample_ids),
            "overlap_sample_count": overlap_count,
            "matched_pair_count": matched_pair_count,
            "feature_row_count": matrix_summary.feature_count,
            "uniquely_labeled_feature_count": unique_feature_count,
        },
        "limitations": [
            "This is a structural preflight; it calculates no effects, p-values, or q-values.",
            "A valid join and pair design do not establish that selected metadata values "
            "are biologically appropriate.",
            "Date-shaped feature labels are only flagged for review; no gene identity is "
            "inferred and no source label is normalized.",
            "The paired count contrast uses exploratory log2-CPM signed-rank tests and "
            "does not fit a negative-binomial or precision-weighted count model.",
            "GEO metadata are submitter supplied and may be incomplete, inconsistent, "
            "or ambiguous.",
            "Research use only; this report does not support diagnosis or treatment decisions.",
        ],
    }
    return report_body | {
        "content_address": content_hash(report_body, prefix="geo-count-contrast-design")
    }


__all__ = [
    "build_geo_count_contrast_design_report",
    "build_geo_count_metadata_report",
    "build_geo_sample_metadata_report",
]

"""Bounded GEO Series Matrix sample-characteristic and design summaries."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .geo_expression import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_SAMPLE_COUNT,
    _read_matrix,
    parse_series_matrix_metadata,
    validate_accession,
)
from .serialization import content_hash

MAX_CATEGORY_KEYS = 50_000
MAX_REPORTED_CATEGORIES_PER_FIELD = 100


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


__all__ = ["build_geo_sample_metadata_report"]

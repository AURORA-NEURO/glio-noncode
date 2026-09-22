"""Descriptive, non-destructive quality summaries for GEO Series Matrices."""

from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .expression_evidence import ExpressionScale
from .geo_expression import (
    DEFAULT_TIMEOUT_SECONDS,
    GeoMatrixFeature,
    _read_matrix,
    scan_series_matrix_features,
    validate_accession,
)
from .serialization import content_hash


def build_expression_quality_report(
    accession: str,
    *,
    scale: ExpressionScale | str,
    matrix_file: str | Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Summarize per-sample matrix coverage and descriptive expression statistics."""

    normalized_accession = validate_accession(accession)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")
    try:
        normalized_timeout = float(timeout_seconds)
    except OverflowError as error:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds") from error
    if not math.isfinite(normalized_timeout) or not 0.1 <= normalized_timeout <= 120.0:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")
    try:
        expression_scale = ExpressionScale(scale)
    except (TypeError, ValueError) as error:
        raise ValidationError("expression scale is not supported") from error

    payload, response_url, source_file_name = _read_matrix(
        normalized_accession,
        matrix_file=matrix_file,
        timeout_seconds=normalized_timeout,
    )
    statistics: dict[str, Any] | None = None

    def consume_feature(feature: GeoMatrixFeature) -> None:
        nonlocal statistics
        if statistics is None:
            sample_count = len(feature.values)
            statistics = {
                "feature_count": 0,
                "observed_counts": [0] * sample_count,
                "missing_counts": [0] * sample_count,
                "magnitude_scales": [0.0] * sample_count,
                "scaled_means": [0.0] * sample_count,
                "scaled_sum_squares": [0.0] * sample_count,
                "minima": [None] * sample_count,
                "maxima": [None] * sample_count,
                "features_by_missing_sample_count": [0] * (sample_count + 1),
                "profile_digests": [
                    hashlib.sha256(b"glio-geo-profile-v1\0") for _ in range(sample_count)
                ],
            }
        state = statistics
        feature_missing_count = 0
        for sample_index, value in enumerate(feature.values):
            profile_digest = state["profile_digests"][sample_index]
            if value is None:
                profile_digest.update(b"\x00")
                state["missing_counts"][sample_index] += 1
                feature_missing_count += 1
                continue

            profile_digest.update(b"\x01")
            profile_digest.update(struct.pack("!d", 0.0 if value == 0.0 else value))

            scale_value = state["magnitude_scales"][sample_index]
            value_magnitude = abs(value)
            if value_magnitude > scale_value:
                rescale = scale_value / value_magnitude if scale_value else 0.0
                state["scaled_means"][sample_index] *= rescale
                state["scaled_sum_squares"][sample_index] *= rescale * rescale
                scale_value = value_magnitude
                state["magnitude_scales"][sample_index] = scale_value

            scaled_value = value / scale_value if scale_value else 0.0
            observed = state["observed_counts"][sample_index] + 1
            delta = scaled_value - state["scaled_means"][sample_index]
            updated_mean = state["scaled_means"][sample_index] + delta / observed
            state["scaled_sum_squares"][sample_index] += delta * (scaled_value - updated_mean)
            state["scaled_means"][sample_index] = updated_mean
            state["observed_counts"][sample_index] = observed

            minimum = state["minima"][sample_index]
            maximum = state["maxima"][sample_index]
            state["minima"][sample_index] = value if minimum is None else min(minimum, value)
            state["maxima"][sample_index] = value if maximum is None else max(maximum, value)

        state["feature_count"] += 1
        state["features_by_missing_sample_count"][feature_missing_count] += 1

    matrix = scan_series_matrix_features(
        payload,
        accession=normalized_accession,
        source_file_name=source_file_name,
        feature_consumer=consume_feature,
    )
    if len(matrix.platform_ids) != 1:
        raise ValidationError("GEO quality summaries require exactly one platform")
    sample_count = len(matrix.samples)
    feature_count = matrix.feature_count
    if feature_count < 1:
        raise ValidationError("GEO quality summary requires at least one matrix feature")
    if statistics is None or statistics["feature_count"] != feature_count:
        raise ValidationError("GEO quality scan did not consume the complete feature table")

    observed_counts = statistics["observed_counts"]
    missing_counts = statistics["missing_counts"]
    magnitude_scales = statistics["magnitude_scales"]
    scaled_means = statistics["scaled_means"]
    scaled_sum_squares = statistics["scaled_sum_squares"]
    minima = statistics["minima"]
    maxima = statistics["maxima"]
    features_by_missing_sample_count = statistics["features_by_missing_sample_count"]
    profile_groups: dict[str, list[int]] = {}
    for index, observed in enumerate(observed_counts):
        if observed:
            digest = statistics["profile_digests"][index].hexdigest()
            profile_groups.setdefault(digest, []).append(index)
    profile_group_sizes: list[int | None] = [None] * sample_count
    duplicate_group_size_counts: dict[int, int] = {}
    for members in profile_groups.values():
        group_size = len(members)
        for index in members:
            profile_group_sizes[index] = group_size
        if group_size > 1:
            duplicate_group_size_counts[group_size] = (
                duplicate_group_size_counts.get(group_size, 0) + 1
            )

    sample_summaries: list[dict[str, Any]] = []
    for index, sample in enumerate(matrix.samples):
        observed = observed_counts[index]
        scale_value = magnitude_scales[index]
        scaled_mean = scaled_means[index]
        mean: float | None = None
        if observed:
            mean = scaled_mean * scale_value if scale_value else 0.0
        standard_deviation: float | None = None
        if observed >= 2:
            scaled_variance = max(0.0, scaled_sum_squares[index]) / (observed - 1)
            candidate = math.sqrt(scaled_variance) * scale_value
            standard_deviation = candidate if math.isfinite(candidate) else None
        sample_summaries.append(
            {
                "sample_accession": sample.accession,
                "observed_feature_count": observed,
                "missing_feature_count": missing_counts[index],
                "missing_fraction": missing_counts[index] / feature_count,
                "mean": mean if mean is not None and math.isfinite(mean) else None,
                "sample_standard_deviation": standard_deviation,
                "minimum": minima[index],
                "maximum": maxima[index],
                "exact_profile_group_size": profile_group_sizes[index],
            }
        )

    total_cells = feature_count * sample_count
    total_missing = sum(missing_counts)
    duplicate_profile_group_count = sum(duplicate_group_size_counts.values())
    samples_in_duplicate_profile_groups = sum(
        group_size * group_count
        for group_size, group_count in duplicate_group_size_counts.items()
    )
    body: dict[str, Any] = {
        "schema": "glio-noncode.geo-expression-quality.v1",
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
            "feature_count": feature_count,
        },
        "analysis": {
            "scale": expression_scale.value,
            "transformed_values": False,
            "feature_vectors_retained": False,
            "streaming_summary_passes": 1,
            "automatic_sample_exclusion": False,
            "automatic_quality_classification": False,
            "exact_profile_match_basis": "parsed measurements and missingness in matrix row order",
            "profile_fingerprints_emitted": False,
        },
        "summary": {
            "sample_count": sample_count,
            "feature_count": feature_count,
            "measurement_count": total_cells,
            "observed_measurement_count": total_cells - total_missing,
            "missing_measurement_count": total_missing,
            "overall_missing_fraction": total_missing / total_cells,
            "complete_feature_count": features_by_missing_sample_count[0],
            "feature_with_missing_measurement_count": (
                feature_count - features_by_missing_sample_count[0]
            ),
            "sample_count_without_observed_values": sum(
                observed == 0 for observed in observed_counts
            ),
            "exact_duplicate_profile_group_count": duplicate_profile_group_count,
            "samples_in_exact_duplicate_profile_groups": samples_in_duplicate_profile_groups,
            "exact_duplicate_profile_groups_by_size": [
                {"group_size": group_size, "group_count": group_count}
                for group_size, group_count in sorted(duplicate_group_size_counts.items())
            ],
            "features_by_missing_sample_count": [
                {"missing_sample_count": missing_sample_count, "feature_count": count}
                for missing_sample_count, count in enumerate(
                    features_by_missing_sample_count
                )
            ],
        },
        "samples": sample_summaries,
        "limitations": [
            "This report is descriptive QC only; it does not transform or normalize "
            "expression values.",
            "No sample is automatically excluded, ranked as bad, or declared suitable for "
            "analysis.",
            "Means, ranges, and standard deviations are scale-dependent and may be "
            "outlier-sensitive.",
            "Missingness patterns are summarized but their cause and informativeness are not "
            "inferred.",
            "Exact profile groups compare all parsed values and missingness positions; near-"
            "duplicate profiles are not detected, and samples with no observed values are not "
            "matched.",
            "Profile fingerprints are used internally for exact matching and are not emitted.",
            "A single-platform matrix is required; cross-platform harmonization is not performed.",
        ],
    }
    return body | {"content_address": content_hash(body, prefix="geo-expression-quality")}


__all__ = ["build_expression_quality_report"]

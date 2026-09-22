"""Metadata-only preflight for explicit GEO two-group contrast designs."""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .geo_expression import (
    _MISSING_MATRIX_VALUES,
    DEFAULT_TIMEOUT_SECONDS,
    GeoSample,
    _normalize_covariates,
    _normalize_filters,
    _prepare_geo_contrast,
    _read_matrix,
    parse_series_matrix_metadata,
    validate_accession,
)
from .serialization import content_hash

_MISSING_COVARIATE_VALUES = _MISSING_MATRIX_VALUES | {"n/a", "none"}


def build_geo_contrast_design_report(
    accession: str,
    *,
    case_filters: Sequence[tuple[str, str]],
    reference_filters: Sequence[tuple[str, str]],
    covariates: Sequence[tuple[str, str]] = (),
    matrix_file: str | Path | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Audit group selection and model estimability without retaining expression rows."""

    normalized_accession = validate_accession(accession)
    normalized_case = _normalize_filters(case_filters, "case")
    normalized_reference = _normalize_filters(reference_filters, "reference")
    normalized_covariates = _normalize_covariates(covariates)
    timeout = _validated_timeout(timeout_seconds)
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

    case_indices = tuple(
        index for index, sample in enumerate(matrix.samples) if sample.matches(normalized_case)
    )
    reference_indices = tuple(
        index
        for index, sample in enumerate(matrix.samples)
        if sample.matches(normalized_reference)
    )
    case_set = set(case_indices)
    reference_set = set(reference_indices)
    overlap_indices = tuple(sorted(case_set & reference_set))
    selected_indices = tuple(sorted(case_set | reference_set))
    unassigned_indices = tuple(
        index for index in range(len(matrix.samples)) if index not in case_set | reference_set
    )

    missing_by_sample = {
        index: _missing_covariate_fields(matrix.samples[index], normalized_covariates)
        for index in selected_indices
    }
    missing_excluded_indices = tuple(
        index for index in selected_indices if missing_by_sample[index]
    )
    design_state = "not_estimable"
    design_reason: str | None = None
    complete_indices: tuple[int, ...] = ()
    complete_case_indices: tuple[int, ...] = ()
    complete_reference_indices: tuple[int, ...] = ()
    parameter_names: tuple[str, ...] = ()
    covariate_metadata: tuple[dict[str, Any], ...] = ()
    residual_degrees_of_freedom: int | None = None
    design_method: str | None = None

    if len(matrix.platform_ids) != 1:
        design_reason = "the GEO contrast workflow requires exactly one platform"
    elif overlap_indices:
        design_reason = "case and reference filters select overlapping samples"
    elif len(case_indices) < 2 or len(reference_indices) < 2:
        design_reason = "each contrast group must select at least two samples"
    elif len(matrix.platform_ids) == 1 and matrix.feature_count < 1:
        design_reason = "the Series Matrix contains no expression features"
    elif normalized_covariates:
        try:
            prepared = _prepare_geo_contrast(
                matrix,
                case_indices=case_indices,
                reference_indices=reference_indices,
                covariates=normalized_covariates,
            )
        except ValidationError as error:
            design_reason = str(error)
        else:
            design_state = "estimable"
            design_method = "additive_ordinary_least_squares"
            complete_indices = prepared.sample_indices
            complete_case_indices = prepared.case_indices
            complete_reference_indices = prepared.reference_indices
            parameter_names = prepared.parameter_names
            covariate_metadata = prepared.covariate_metadata
            residual_degrees_of_freedom = prepared.model.degrees_of_freedom
    else:
        design_state = "estimable"
        design_method = "two_group_difference"
        complete_indices = selected_indices
        complete_case_indices = case_indices
        complete_reference_indices = reference_indices
        parameter_names = ("intercept", "group_case_minus_reference")
        residual_degrees_of_freedom = len(complete_indices) - len(parameter_names)

    balance = (
        _covariate_balance(
            matrix.samples,
            normalized_covariates,
            complete_indices,
            set(complete_case_indices),
            set(complete_reference_indices),
            covariate_metadata,
        )
        if design_state == "estimable" and normalized_covariates
        else []
    )
    sample_lookup = matrix.samples
    content_body: dict[str, Any] = {
        "schema": "glio-noncode.geo-contrast-design.v1",
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
            "feature_count": matrix.feature_count,
            "sample_count": len(matrix.samples),
        },
        "analysis": {
            "expression_values_retained": False,
            "expression_values_validated": True,
            "effect_sizes_calculated": False,
            "p_values_calculated": False,
            "automatic_group_assignment": False,
        },
        "comparison": {
            "case_filters": [{"field": field, "equals": value} for field, value in normalized_case],
            "reference_filters": [
                {"field": field, "equals": value} for field, value in normalized_reference
            ],
            "case_sample_ids": [sample_lookup[index].accession for index in case_indices],
            "reference_sample_ids": [
                sample_lookup[index].accession for index in reference_indices
            ],
            "overlapping_sample_ids": [
                sample_lookup[index].accession for index in overlap_indices
            ],
            "unassigned_sample_ids": [
                sample_lookup[index].accession for index in unassigned_indices
            ],
            "covariates": [
                {"field": field, "type": kind} for field, kind in normalized_covariates
            ],
        },
        "design": {
            "state": design_state,
            "reason": design_reason,
            "method": design_method,
            "rank": len(parameter_names) if design_state == "estimable" else None,
            "parameter_count": len(parameter_names) if design_state == "estimable" else None,
            "parameter_names": list(parameter_names),
            "residual_degrees_of_freedom": residual_degrees_of_freedom,
            "covariate_terms": list(covariate_metadata),
            "complete_case_sample_ids": [
                sample_lookup[index].accession for index in complete_indices
            ],
            "complete_case_group_counts": {
                "case": len(complete_case_indices),
                "reference": len(complete_reference_indices),
            },
            "excluded_for_missing_covariates": [
                {
                    "sample_accession": sample_lookup[index].accession,
                    "group": "case" if index in case_set else "reference",
                    "missing_fields": missing_by_sample[index],
                }
                for index in missing_excluded_indices
            ],
            "covariate_balance": balance,
        },
        "summary": {
            "sample_count": len(matrix.samples),
            "selected_case_count": len(case_indices),
            "selected_reference_count": len(reference_indices),
            "overlap_count": len(overlap_indices),
            "unassigned_count": len(unassigned_indices),
            "missing_covariate_exclusion_count": len(missing_excluded_indices),
            "complete_case_count": len(complete_indices),
            "design_estimable": design_state == "estimable",
        },
        "limitations": [
            "This is a metadata-only design preflight; it does not calculate expression effects, "
            "test statistics, p-values, or FDR-adjusted values.",
            "Group membership comes only from the explicit characteristic filters supplied by "
            "the user.",
            "Covariate balance summaries are descriptive and do not establish exchangeability, "
            "causal identification, or absence of unmeasured confounding.",
            "The preflight uses the same additive model encoding and missing-covariate rules as "
            "geo-contrast; feature-level missingness may still make individual features "
            "untestable.",
            "GEO annotations are submitter supplied and may be incomplete, inconsistent, or "
            "ambiguous.",
            "Research use only; this report does not support diagnosis or treatment decisions.",
        ],
    }
    return content_body | {
        "content_address": content_hash(content_body, prefix="geo-contrast-design")
    }


def _validated_timeout(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")
    try:
        timeout = float(value)
    except OverflowError as error:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds") from error
    if not math.isfinite(timeout) or not 0.1 <= timeout <= 120.0:
        raise ValidationError("GEO request timeout must be between 0.1 and 120 seconds")
    return timeout


def _missing_covariate_fields(
    sample: GeoSample,
    covariates: Sequence[tuple[str, str]],
) -> list[str]:
    missing: list[str] = []
    for field, _kind in covariates:
        values = sample.values_for((field,))[field]
        if not any(value.strip().casefold() not in _MISSING_COVARIATE_VALUES for value in values):
            missing.append(field)
    return missing


def _covariate_balance(
    samples: Sequence[GeoSample],
    covariates: Sequence[tuple[str, str]],
    complete_indices: Sequence[int],
    case_indices: set[int],
    reference_indices: set[int],
    covariate_metadata: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    metadata_by_field = {str(item["field"]).casefold(): item for item in covariate_metadata}
    summaries: list[dict[str, Any]] = []
    for field, kind in covariates:
        values_by_group: dict[str, list[str]] = {"case": [], "reference": []}
        for index in complete_indices:
            group = "case" if index in case_indices else "reference"
            raw_values = samples[index].values_for((field,))[field]
            values = [
                value
                for value in raw_values
                if value.strip().casefold() not in _MISSING_COVARIATE_VALUES
            ]
            values_by_group[group].append(values[0])

        if kind == "categorical":
            term = metadata_by_field[field.casefold()]
            levels = list(term["levels"])
            level_counts: dict[str, dict[str, int]] = {
                level.casefold(): {"case": 0, "reference": 0} for level in levels
            }
            for group, values in values_by_group.items():
                for value in values:
                    level_counts[value.casefold()][group] += 1
            case_count = len(values_by_group["case"])
            reference_count = len(values_by_group["reference"])
            summarized_levels = []
            for level in levels:
                counts = level_counts[level.casefold()]
                case_fraction = counts["case"] / case_count
                reference_fraction = counts["reference"] / reference_count
                summarized_levels.append(
                    {
                        "value": level,
                        "case_count": counts["case"],
                        "reference_count": counts["reference"],
                        "case_fraction": case_fraction,
                        "reference_fraction": reference_fraction,
                        "absolute_fraction_difference": abs(
                            case_fraction - reference_fraction
                        ),
                    }
                )
            case_only_levels = [
                item["value"]
                for item in summarized_levels
                if item["case_count"] > 0 and item["reference_count"] == 0
            ]
            reference_only_levels = [
                item["value"]
                for item in summarized_levels
                if item["reference_count"] > 0 and item["case_count"] == 0
            ]
            summaries.append(
                {
                    "field": field,
                    "type": kind,
                    "case_sample_count": case_count,
                    "reference_sample_count": reference_count,
                    "shared_level_count": len(levels)
                    - len(case_only_levels)
                    - len(reference_only_levels),
                    "case_only_levels": case_only_levels,
                    "reference_only_levels": reference_only_levels,
                    "maximum_absolute_level_fraction_difference": max(
                        item["absolute_fraction_difference"] for item in summarized_levels
                    ),
                    "levels": summarized_levels,
                }
            )
            continue

        case_values = [float(value) for value in values_by_group["case"]]
        reference_values = [float(value) for value in values_by_group["reference"]]
        case_minimum = min(case_values)
        reference_minimum = min(reference_values)
        overlap_minimum = max(case_minimum, reference_minimum)
        overlap_maximum = min(max(case_values), max(reference_values))
        has_range_overlap = overlap_minimum <= overlap_maximum
        standardized_mean_difference, standardized_mean_difference_status = (
            _standardized_mean_difference(case_values, reference_values)
        )
        summaries.append(
            {
                "field": field,
                "type": kind,
                "case": _continuous_summary(case_values),
                "reference": _continuous_summary(reference_values),
                "standardized_mean_difference": standardized_mean_difference,
                "standardized_mean_difference_status": standardized_mean_difference_status,
                "range_overlap": {
                    "overlaps": has_range_overlap,
                    "minimum": overlap_minimum if has_range_overlap else None,
                    "maximum": overlap_maximum if has_range_overlap else None,
                },
            }
        )
    return summaries


def _continuous_summary(values: Sequence[float]) -> dict[str, Any]:
    magnitude = max((abs(value) for value in values), default=0.0)
    scaled_mean = (
        math.fsum(value / magnitude for value in values) / len(values) if magnitude else 0.0
    )
    mean = scaled_mean * magnitude if magnitude else 0.0
    sample_standard_deviation = _sample_standard_deviation(values, magnitude=magnitude)
    return {
        "sample_count": len(values),
        "mean": mean if math.isfinite(mean) else None,
        "sample_standard_deviation": sample_standard_deviation,
        "minimum": min(values) if values else None,
        "maximum": max(values) if values else None,
    }


def _sample_standard_deviation(
    values: Sequence[float], *, magnitude: float | None = None
) -> float | None:
    if len(values) < 2:
        return None
    value_magnitude = (
        max(abs(value) for value in values) if magnitude is None and values else magnitude
    )
    if not value_magnitude:
        return 0.0
    scaled_values = [value / value_magnitude for value in values]
    scaled_mean = math.fsum(scaled_values) / len(scaled_values)
    scaled_sum_squares = math.fsum((value - scaled_mean) ** 2 for value in scaled_values)
    standard_deviation = (
        math.sqrt(scaled_sum_squares / (len(scaled_values) - 1)) * value_magnitude
    )
    return standard_deviation if math.isfinite(standard_deviation) else None


def _standardized_mean_difference(
    case_values: Sequence[float], reference_values: Sequence[float]
) -> tuple[float | None, str]:
    case_count = len(case_values)
    reference_count = len(reference_values)
    if case_count < 2 or reference_count < 2:
        return None, "insufficient_group_variance_degrees_of_freedom"

    magnitude = max(
        max(abs(value) for value in case_values),
        max(abs(value) for value in reference_values),
    )
    if magnitude == 0.0:
        return None, "zero_pooled_standard_deviation"

    scaled_case = [value / magnitude for value in case_values]
    scaled_reference = [value / magnitude for value in reference_values]
    case_mean = math.fsum(scaled_case) / case_count
    reference_mean = math.fsum(scaled_reference) / reference_count
    within_group_sum_squares = math.fsum(
        (value - case_mean) ** 2 for value in scaled_case
    ) + math.fsum((value - reference_mean) ** 2 for value in scaled_reference)
    pooled_standard_deviation = math.sqrt(
        within_group_sum_squares / (case_count + reference_count - 2)
    )
    if pooled_standard_deviation == 0.0:
        return None, "zero_pooled_standard_deviation"

    result = (case_mean - reference_mean) / pooled_standard_deviation
    if not math.isfinite(result):
        return None, "non_finite_standardized_mean_difference"
    return result, "available"


__all__ = ["build_geo_contrast_design_report"]

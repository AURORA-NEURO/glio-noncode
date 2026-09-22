"""Normalization-sensitivity comparisons for saved paired GEO count reports.

This module is deliberately separate from cross-Series consistency.  A
consistency comparison asks whether an effect direction repeats in distinct
Series accessions and therefore requires distinct source studies.  A
sensitivity comparison asks whether the same source study remains stable when
the declared expression normalization changes.  It accepts exactly two
completed reports, requires the same source files and declared design, and
emits only bounded aggregate observations for explicitly requested feature
labels.

The comparison never recomputes a statistic, pools p-values, or treats a
missing bounded result as a zero.  It is a reproducible review artifact for
normalization robustness, not a second inferential analysis.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import ValidationError
from .geo_analysis_store import validate_geo_count_contrast_report
from .serialization import canonical_json, content_hash

GEO_COUNT_SENSITIVITY_SCHEMA = "glio-noncode.geo-count-sensitivity.v1"
MAX_COUNT_SENSITIVITY_FEATURES = 500
_FEATURE_ID_MAX_LENGTH = 256
_FEATURE_ID_ALLOWED = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-+|/()[]"
)


class CountSensitivityCompatibilityError(ValidationError):
    """Raised when two saved runs cannot be interpreted as one sensitivity pair."""


def _finite(value: object, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValidationError(f"GEO count sensitivity {label} must be finite numeric data")
    return float(value)


def _normalize_feature_ids(feature_ids: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(feature_ids, Sequence) or isinstance(feature_ids, (str, bytes, bytearray)):
        raise ValidationError("GEO count sensitivity feature IDs must be a sequence")
    if not 1 <= len(feature_ids) <= MAX_COUNT_SENSITIVITY_FEATURES:
        raise ValidationError(
            "GEO count sensitivity requires between 1 and "
            f"{MAX_COUNT_SENSITIVITY_FEATURES} feature IDs"
        )
    normalized: list[str] = []
    for feature_id in feature_ids:
        if (
            not isinstance(feature_id, str)
            or not feature_id
            or len(feature_id) > _FEATURE_ID_MAX_LENGTH
            or any(character not in _FEATURE_ID_ALLOWED for character in feature_id)
        ):
            raise ValidationError(
                "GEO count sensitivity feature IDs use an invalid source-label format"
            )
        normalized.append(feature_id)
    if len(set(normalized)) != len(normalized):
        raise ValidationError("GEO count sensitivity feature IDs must be unique")
    return tuple(normalized)


def _validated_report(report: object) -> dict[str, Any]:
    try:
        validated = validate_geo_count_contrast_report(report)
    except ValidationError as error:
        raise ValidationError(
            "GEO paired-count sensitivity input failed independent validation"
        ) from error
    if validated.get("status") != "completed":
        raise ValidationError("GEO count sensitivity cannot use an incomplete report")
    expected = content_hash(
        {key: value for key, value in validated.items() if key != "content_address"},
        prefix="geo-paired-count-contrast",
    )
    if validated.get("content_address") != expected:
        raise ValidationError("GEO paired-count sensitivity input has an invalid report address")
    return validated


def _comparison_signature(report: Mapping[str, Any]) -> tuple[str, ...]:
    comparison = report["comparison"]
    normalization = comparison["normalization_details"]
    return (
        canonical_json(comparison["case_filters"]),
        canonical_json(comparison["reference_filters"]),
        str(comparison["pair_key_column"]),
        str(comparison["design"]),
        str(comparison["effect_size"]),
        str(comparison["effect_direction_basis"]),
        str(comparison["rank_biserial_effect_direction_basis"]),
        str(comparison["test"]),
        str(comparison["fdr_method"]),
        str(comparison["fdr_threshold"]),
        str(normalization["method"]),
        str(normalization["expression_scale"]),
    )


def _validate_compatibility(reports: Sequence[Mapping[str, Any]]) -> None:
    if len(reports) != 2:
        raise ValidationError("GEO count sensitivity requires exactly two paired-count reports")
    left, right = reports
    left_source = left["source"]
    right_source = right["source"]
    if left["content_address"] == right["content_address"]:
        raise CountSensitivityCompatibilityError(
            "GEO count sensitivity requires two distinct saved analysis reports"
        )
    if left_source["accession"] != right_source["accession"]:
        raise CountSensitivityCompatibilityError(
            "GEO count sensitivity requires the same Series accession"
        )
    for source_key, label in (
        ("count_matrix", "count-matrix"),
        ("sample_metadata", "sample-metadata"),
    ):
        if left_source[source_key]["source_sha256"] != right_source[source_key]["source_sha256"]:
            raise CountSensitivityCompatibilityError(
                f"GEO count sensitivity requires identical source digests for the {label}"
            )
    left_signature = _comparison_signature(left)
    right_signature = _comparison_signature(right)
    if left_signature[:-2] != right_signature[:-2]:
        raise CountSensitivityCompatibilityError(
            "GEO count sensitivity requires the same case/reference filters, pairing "
            "design, effect basis, test, and FDR settings"
        )
    if left_signature[-2:] == right_signature[-2:]:
        raise CountSensitivityCompatibilityError(
            "GEO count sensitivity requires different normalization methods or expression scales"
        )


def _rows_by_feature(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row["feature_id"]): row for row in report["results"]}


def _aggregate_result(row: Mapping[str, Any], report: Mapping[str, Any]) -> dict[str, Any]:
    comparison = report["comparison"]
    review = row["feature_label_review"]
    annotation = row["feature_annotation"]
    normalization = comparison["normalization_details"]
    return {
        "normalization": comparison["normalization"],
        "normalization_method": normalization["method"],
        "expression_scale": normalization["expression_scale"],
        "result_state": "tested" if row["p_value"] is not None else "reported_but_untestable",
        "feature_label_review": {
            "possible_date_like_source_label": review["possible_date_like_source_label"],
            "manual_annotation_review_recommended": review["manual_annotation_review_recommended"],
        },
        "feature_annotation": {
            "status": annotation["status"],
            "curated_feature_id": annotation["curated_feature_id"],
        },
        "paired_sample_count": row["paired_sample_count"],
        "nonzero_pair_count": row["nonzero_pair_count"],
        "case_higher_pair_count": row["case_higher_pair_count"],
        "case_lower_pair_count": row["case_lower_pair_count"],
        "tied_pair_count": row["tied_pair_count"],
        "mean_paired_difference_log2_cpm": row["mean_paired_difference_log2_cpm"],
        "median_paired_difference_log2_cpm": row["median_paired_difference_log2_cpm"],
        "matched_pairs_rank_biserial_correlation": row["matched_pairs_rank_biserial_correlation"],
        "effect_direction": row["effect_direction"],
        "mean_effect_direction": row["mean_effect_direction"],
        "median_effect_direction": row["median_effect_direction"],
        "p_value": row["p_value"],
        "q_value": row["q_value"],
        "test_method": row["test_method"],
        "fdr_significant": row["fdr_significant"],
        "sign_test_p_value": row["sign_test_p_value"],
        "sign_test_q_value": row["sign_test_q_value"],
        "sign_test_method": row["sign_test_method"],
        "sign_test_fdr_significant": row["sign_test_fdr_significant"],
    }


def _binary_state(
    left: Mapping[str, Any] | None,
    right: Mapping[str, Any] | None,
    key: str,
    *,
    stable: str,
    changed: str,
    insufficient: str,
) -> str:
    if left is None or right is None:
        return "not_reported_in_bounded_results"
    if left["p_value"] is None or right["p_value"] is None:
        return insufficient
    return stable if left[key] == right[key] else changed


def _run_summary(report: Mapping[str, Any], role: str) -> dict[str, Any]:
    source = report["source"]
    comparison = report["comparison"]
    summary = report["summary"]
    normalization = comparison["normalization_details"]
    return {
        "role": role,
        "accession": source["accession"],
        "count_matrix_source_sha256": source["count_matrix"]["source_sha256"],
        "metadata_source_sha256": source["sample_metadata"]["source_sha256"],
        "report_content_address": report["content_address"],
        "case_filters": comparison["case_filters"],
        "reference_filters": comparison["reference_filters"],
        "pair_key_column": comparison["pair_key_column"],
        "matched_pair_count": comparison["matched_pair_count"],
        "case_sample_count_selected": comparison["case_sample_count_selected"],
        "reference_sample_count_selected": comparison["reference_sample_count_selected"],
        "normalization": comparison["normalization"],
        "normalization_method": normalization["method"],
        "expression_scale": normalization["expression_scale"],
        "fdr_method": comparison["fdr_method"],
        "fdr_threshold": comparison["fdr_threshold"],
        "tested_feature_count": summary["tested_feature_count"],
        "reported_feature_count": summary["reported_feature_count"],
        "fdr_significant_feature_count": summary["fdr_significant_feature_count"],
        "sign_test_fdr_significant_feature_count": summary[
            "sign_test_fdr_significant_feature_count"
        ],
    }


def build_geo_count_sensitivity_report(
    reports: Sequence[Mapping[str, Any]], *, feature_ids: Sequence[str]
) -> dict[str, Any]:
    """Build a deterministic same-source normalization sensitivity report."""

    if not isinstance(reports, Sequence) or isinstance(reports, (str, bytes, bytearray)):
        raise ValidationError("GEO count sensitivity reports must be a sequence")
    if len(reports) != 2:
        raise ValidationError("GEO count sensitivity requires exactly two reports")
    normalized_features = _normalize_feature_ids(feature_ids)
    validated = tuple(_validated_report(report) for report in reports)
    _validate_compatibility(validated)
    left, right = validated
    left_rows = _rows_by_feature(left)
    right_rows = _rows_by_feature(right)
    features: list[dict[str, Any]] = []
    counts = {
        "direction": {
            "stable_direction": 0,
            "changed_direction": 0,
            "insufficient_direction_evidence": 0,
            "not_reported_in_bounded_results": 0,
        },
        "fdr": {
            "stable_fdr_significance": 0,
            "changed_fdr_significance": 0,
            "insufficient_fdr_evidence": 0,
            "not_reported_in_bounded_results": 0,
        },
        "sign": {
            "stable_sign_test_fdr_significance": 0,
            "changed_sign_test_fdr_significance": 0,
            "insufficient_sign_test_fdr_evidence": 0,
            "not_reported_in_bounded_results": 0,
        },
    }
    for feature_id in normalized_features:
        left_row = left_rows.get(feature_id)
        right_row = right_rows.get(feature_id)
        direction_state = _binary_state(
            left_row,
            right_row,
            "effect_direction",
            stable="stable_direction",
            changed="changed_direction",
            insufficient="insufficient_direction_evidence",
        )
        fdr_state = _binary_state(
            left_row,
            right_row,
            "fdr_significant",
            stable="stable_fdr_significance",
            changed="changed_fdr_significance",
            insufficient="insufficient_fdr_evidence",
        )
        sign_state = _binary_state(
            left_row,
            right_row,
            "sign_test_fdr_significant",
            stable="stable_sign_test_fdr_significance",
            changed="changed_sign_test_fdr_significance",
            insufficient="insufficient_sign_test_fdr_evidence",
        )
        counts["direction"][direction_state] += 1
        counts["fdr"][fdr_state] += 1
        counts["sign"][sign_state] += 1
        left_aggregate = _aggregate_result(left_row, left) if left_row is not None else None
        right_aggregate = _aggregate_result(right_row, right) if right_row is not None else None
        median_delta = None
        mean_delta = None
        if left_aggregate is not None and right_aggregate is not None:
            median_delta = _finite(
                right_aggregate["median_paired_difference_log2_cpm"],
                "median paired difference",
            ) - _finite(
                left_aggregate["median_paired_difference_log2_cpm"],
                "median paired difference",
            )
            mean_delta = _finite(
                right_aggregate["mean_paired_difference_log2_cpm"],
                "mean paired difference",
            ) - _finite(
                left_aggregate["mean_paired_difference_log2_cpm"],
                "mean paired difference",
            )
        features.append(
            {
                "feature_id": feature_id,
                "runs": [
                    {
                        "role": "left",
                        "result_state": "reported"
                        if left_row is not None
                        else "not_reported_in_bounded_results",
                        "aggregate_result": left_aggregate,
                    },
                    {
                        "role": "right",
                        "result_state": "reported"
                        if right_row is not None
                        else "not_reported_in_bounded_results",
                        "aggregate_result": right_aggregate,
                    },
                ],
                "summary": {
                    "direction_sensitivity": direction_state,
                    "fdr_sensitivity": fdr_state,
                    "sign_test_fdr_sensitivity": sign_state,
                    "median_effect_delta_right_minus_left": median_delta,
                    "mean_effect_delta_right_minus_left": mean_delta,
                },
            }
        )

    left_comparison = left["comparison"]
    right_comparison = right["comparison"]
    left_normalization = left_comparison["normalization_details"]
    right_normalization = right_comparison["normalization_details"]
    content_body: dict[str, Any] = {
        "schema": GEO_COUNT_SENSITIVITY_SCHEMA,
        "status": "completed",
        "comparison": {
            "feature_identity": "exact_case_sensitive_source_feature_id",
            "sensitivity_dimension": "normalization_and_expression_scale",
            "accession": left["source"]["accession"],
            "count_matrix_source_sha256": left["source"]["count_matrix"]["source_sha256"],
            "metadata_source_sha256": left["source"]["sample_metadata"]["source_sha256"],
            "left_normalization": left_comparison["normalization"],
            "left_normalization_method": left_normalization["method"],
            "left_expression_scale": left_normalization["expression_scale"],
            "right_normalization": right_comparison["normalization"],
            "right_normalization_method": right_normalization["method"],
            "right_expression_scale": right_normalization["expression_scale"],
            "case_filters": left_comparison["case_filters"],
            "reference_filters": left_comparison["reference_filters"],
            "pair_key_column": left_comparison["pair_key_column"],
            "design": left_comparison["design"],
            "group_orientation": "case relative to reference in each saved run",
            "effect_direction_basis": left_comparison["effect_direction_basis"],
            "rank_biserial_effect_direction_basis": left_comparison[
                "rank_biserial_effect_direction_basis"
            ],
            "fdr_method": left_comparison["fdr_method"],
            "fdr_threshold": left_comparison["fdr_threshold"],
        },
        "runs": [_run_summary(left, "left"), _run_summary(right, "right")],
        "features": features,
        "summary": {
            "run_count": 2,
            "feature_count": len(features),
            "stable_direction_feature_count": counts["direction"]["stable_direction"],
            "changed_direction_feature_count": counts["direction"]["changed_direction"],
            "insufficient_direction_feature_count": counts["direction"][
                "insufficient_direction_evidence"
            ],
            "not_reported_direction_feature_count": counts["direction"][
                "not_reported_in_bounded_results"
            ],
            "stable_fdr_significance_feature_count": counts["fdr"]["stable_fdr_significance"],
            "changed_fdr_significance_feature_count": counts["fdr"]["changed_fdr_significance"],
            "insufficient_fdr_feature_count": counts["fdr"]["insufficient_fdr_evidence"],
            "not_reported_fdr_feature_count": counts["fdr"]["not_reported_in_bounded_results"],
            "stable_sign_test_fdr_significance_feature_count": counts["sign"][
                "stable_sign_test_fdr_significance"
            ],
            "changed_sign_test_fdr_significance_feature_count": counts["sign"][
                "changed_sign_test_fdr_significance"
            ],
            "insufficient_sign_test_fdr_feature_count": counts["sign"][
                "insufficient_sign_test_fdr_evidence"
            ],
            "not_reported_sign_test_fdr_feature_count": counts["sign"][
                "not_reported_in_bounded_results"
            ],
        },
        "analysis": {
            "effect_sizes_pooled": False,
            "p_values_combined": False,
            "fdr_values_recomputed": False,
            "normalization_reestimated": False,
            "missing_report_rows_treated_as_negative": False,
            "individual_sample_and_pair_keys_emitted": False,
        },
        "limitations": [
            (
                "This is a same-source normalization sensitivity review. It compares "
                "stored aggregate directions and significance flags; it does not pool "
                "effect sizes, p-values, or q-values."
            ),
            (
                "Only the explicitly requested source feature labels are compared. A "
                "feature absent from either bounded result table is not treated as zero, "
                "negative, or non-significant evidence."
            ),
            (
                "A stable direction across transforms is descriptive robustness evidence, "
                "not proof of biological validity, cohort independence, causality, diagnosis, "
                "prognosis, or treatment response."
            ),
            (
                "Sample, subject, pair, and raw matrix identifiers remain withheld from "
                "the public aggregate projection."
            ),
        ],
    }
    return content_body | {
        "content_address": content_hash(content_body, prefix="geo-count-sensitivity")
    }


def summarize_geo_count_sensitivity_report(report: Mapping[str, Any]) -> dict[str, Any]:
    comparison = report["comparison"]
    summary = report["summary"]
    return {
        "content_address": report["content_address"],
        "accession": comparison["accession"],
        "run_count": summary["run_count"],
        "feature_count": summary["feature_count"],
        "left_normalization_method": comparison["left_normalization_method"],
        "right_normalization_method": comparison["right_normalization_method"],
        "fdr_method": comparison["fdr_method"],
        "fdr_threshold": comparison["fdr_threshold"],
        **{
            key: summary[key]
            for key in (
                "stable_direction_feature_count",
                "changed_direction_feature_count",
                "insufficient_direction_feature_count",
                "not_reported_direction_feature_count",
                "stable_fdr_significance_feature_count",
                "changed_fdr_significance_feature_count",
                "insufficient_fdr_feature_count",
                "not_reported_fdr_feature_count",
                "stable_sign_test_fdr_significance_feature_count",
                "changed_sign_test_fdr_significance_feature_count",
                "insufficient_sign_test_fdr_feature_count",
                "not_reported_sign_test_fdr_feature_count",
            )
        },
    }


__all__ = [
    "CountSensitivityCompatibilityError",
    "GEO_COUNT_SENSITIVITY_SCHEMA",
    "MAX_COUNT_SENSITIVITY_FEATURES",
    "build_geo_count_sensitivity_report",
    "summarize_geo_count_sensitivity_report",
]

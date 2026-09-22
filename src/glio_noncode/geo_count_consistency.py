"""Cross-series direction consistency for saved paired GEO count reports.

The paired-count contrast is deliberately kept separate from the classic GEO
expression contrast.  Count reports contain a different result contract
(matched-pair effects, sign-test sensitivity, and optional curated labels), so
joining them through the generic expression-consistency path would silently
discard useful diagnostics.  This module compares already-completed aggregate
reports only.  It does not pool effect sizes, combine p-values, or establish
that public cohorts are independent.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .errors import ValidationError
from .geo_analysis_store import validate_geo_count_contrast_report
from .serialization import canonical_json, content_hash

MAX_COUNT_CONTRAST_REPORTS = 8
MAX_COUNT_CONSISTENCY_FEATURES = 500
_FEATURE_ID_MAX_LENGTH = 256
_FEATURE_ID_ALLOWED = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:@|/+=-_"
)
_MISSING = object()


class CountContrastCompatibilityError(ValidationError):
    """Raised when valid paired-count reports are not safely comparable."""

    code = "incompatible_count_contrast_reports"


def build_geo_count_consistency_report(
    contrast_reports: Sequence[Mapping[str, Any]],
    *,
    feature_ids: Sequence[str],
) -> dict[str, Any]:
    """Compare exact source feature directions across paired-count reports.

    A feature absent from a report's bounded ``results`` list is explicitly
    represented as ``not_reported_in_bounded_results``.  It is never treated as
    a zero effect, a non-significant result, or an opposite-direction result.
    Every input is independently validated before any comparison is made.
    """

    if not isinstance(contrast_reports, Sequence) or isinstance(
        contrast_reports, (str, bytes, bytearray)
    ):
        raise ValidationError("GEO paired-count reports must be a sequence of report objects")
    if not 2 <= len(contrast_reports) <= MAX_COUNT_CONTRAST_REPORTS:
        raise ValidationError(
            "GEO count consistency requires between "
            f"2 and {MAX_COUNT_CONTRAST_REPORTS} paired-count reports"
        )
    normalized_features = _normalize_feature_ids(feature_ids)
    reports = tuple(_validate_report(report) for report in contrast_reports)
    _validate_distinct_sources(reports)
    _validate_compatibility(reports)

    feature_rows = tuple(_rows_by_feature(report) for report in reports)
    output_features: list[dict[str, Any]] = []
    concordant_count = 0
    discordant_count = 0
    insufficient_count = 0
    fdr_concordant_count = 0
    fdr_discordant_count = 0
    fdr_insufficient_count = 0
    sign_concordant_count = 0
    sign_discordant_count = 0
    sign_insufficient_count = 0

    for feature_id in normalized_features:
        observations: list[dict[str, Any]] = []
        directions: list[str] = []
        fdr_directions: list[str] = []
        sign_directions: list[str] = []
        reported_count = 0
        tested_count = 0
        untestable_count = 0
        not_reported_count = 0
        fdr_significant_count = 0
        sign_fdr_significant_count = 0

        for report, rows in zip(reports, feature_rows, strict=True):
            row = rows.get(feature_id)
            accession = report["source"]["accession"]
            if row is None:
                not_reported_count += 1
                observations.append(
                    {
                        "accession": accession,
                        "count_matrix_source_sha256": report["source"]["count_matrix"][
                            "source_sha256"
                        ],
                        "metadata_source_sha256": report["source"]["sample_metadata"][
                            "source_sha256"
                        ],
                        "report_content_address": report["content_address"],
                        "matched_pair_count": report["comparison"]["matched_pair_count"],
                        "result_state": "not_reported_in_bounded_results",
                        "aggregate_result": None,
                    }
                )
                continue

            reported_count += 1
            p_value = row["p_value"]
            if p_value is None:
                result_state = "reported_but_untestable"
                untestable_count += 1
            else:
                result_state = "tested"
                tested_count += 1
                direction = row["effect_direction"]
                directions.append(direction)
                if row["fdr_significant"]:
                    fdr_significant_count += 1
                    fdr_directions.append(direction)
                if row["sign_test_fdr_significant"]:
                    sign_fdr_significant_count += 1
                    sign_directions.append(direction)
            observations.append(
                {
                    "accession": accession,
                    "count_matrix_source_sha256": report["source"]["count_matrix"][
                        "source_sha256"
                    ],
                    "metadata_source_sha256": report["source"]["sample_metadata"][
                        "source_sha256"
                    ],
                    "report_content_address": report["content_address"],
                    "matched_pair_count": report["comparison"]["matched_pair_count"],
                    "result_state": result_state,
                    "aggregate_result": _aggregate_result(row),
                }
            )

        direction_consistency = _consistency_label(
            directions,
            insufficient_label="insufficient_tested_reports",
            concordant_label="concordant_among_tested",
            discordant_label="discordant_among_tested",
        )
        if direction_consistency == "insufficient_tested_reports":
            insufficient_count += 1
        elif direction_consistency == "concordant_among_tested":
            concordant_count += 1
        else:
            discordant_count += 1

        fdr_consistency = _consistency_label(
            fdr_directions,
            insufficient_label="insufficient_fdr_significant_reports",
            concordant_label="concordant_among_fdr_significant",
            discordant_label="discordant_among_fdr_significant",
        )
        if fdr_consistency == "insufficient_fdr_significant_reports":
            fdr_insufficient_count += 1
        elif fdr_consistency == "concordant_among_fdr_significant":
            fdr_concordant_count += 1
        else:
            fdr_discordant_count += 1

        sign_consistency = _consistency_label(
            sign_directions,
            insufficient_label="insufficient_sign_test_fdr_significant_reports",
            concordant_label="concordant_among_sign_test_fdr_significant",
            discordant_label="discordant_among_sign_test_fdr_significant",
        )
        if sign_consistency == "insufficient_sign_test_fdr_significant_reports":
            sign_insufficient_count += 1
        elif sign_consistency == "concordant_among_sign_test_fdr_significant":
            sign_concordant_count += 1
        else:
            sign_discordant_count += 1

        output_features.append(
            {
                "feature_id": feature_id,
                "studies": observations,
                "summary": {
                    "series_count": len(reports),
                    "reported_count": reported_count,
                    "tested_count": tested_count,
                    "untestable_count": untestable_count,
                    "not_reported_count": not_reported_count,
                    "direction_observation_count": len(directions),
                    "distinct_directions": sorted(set(directions)),
                    "direction_consistency": direction_consistency,
                    "fdr_significant_count": fdr_significant_count,
                    "fdr_significant_direction_observation_count": len(fdr_directions),
                    "distinct_fdr_significant_directions": sorted(set(fdr_directions)),
                    "fdr_significant_direction_consistency": fdr_consistency,
                    "sign_test_fdr_significant_count": sign_fdr_significant_count,
                    "sign_test_fdr_significant_direction_observation_count": len(sign_directions),
                    "distinct_sign_test_fdr_significant_directions": sorted(set(sign_directions)),
                    "sign_test_fdr_significant_direction_consistency": sign_consistency,
                },
            }
        )

    first_comparison = reports[0]["comparison"]
    first_normalization = first_comparison["normalization_details"]
    content_body: dict[str, Any] = {
        "schema": "glio-noncode.geo-count-consistency.v1",
        "status": "completed",
        "comparison": {
            "feature_identity": "exact_case_sensitive_source_feature_id",
            "normalization": first_comparison["normalization"],
            "normalization_method": first_normalization["method"],
            "expression_scale": first_normalization["expression_scale"],
            "fdr_method": first_comparison["fdr_method"],
            "fdr_threshold": first_comparison["fdr_threshold"],
            "case_filters": first_comparison["case_filters"],
            "reference_filters": first_comparison["reference_filters"],
            "pair_key_column": first_comparison["pair_key_column"],
            "design": first_comparison["design"],
            "group_orientation": "case relative to reference in each source report",
            "effect_direction_basis": first_comparison["effect_direction_basis"],
            "rank_biserial_effect_direction_basis": first_comparison[
                "rank_biserial_effect_direction_basis"
            ],
        },
        "studies": [_study_summary(report) for report in reports],
        "features": output_features,
        "summary": {
            "study_count": len(reports),
            "feature_count": len(output_features),
            "concordant_feature_count": concordant_count,
            "discordant_feature_count": discordant_count,
            "insufficient_feature_count": insufficient_count,
            "fdr_significant_concordant_feature_count": fdr_concordant_count,
            "fdr_significant_discordant_feature_count": fdr_discordant_count,
            "fdr_significant_insufficient_feature_count": fdr_insufficient_count,
            "sign_test_fdr_significant_concordant_feature_count": sign_concordant_count,
            "sign_test_fdr_significant_discordant_feature_count": sign_discordant_count,
            "sign_test_fdr_significant_insufficient_feature_count": sign_insufficient_count,
        },
        "analysis": {
            "effect_sizes_pooled": False,
            "p_values_combined": False,
            "fdr_values_recomputed": False,
            "curated_feature_aliases_joined": False,
            "cohort_independence_verified": False,
            "missing_report_rows_treated_as_negative": False,
            "individual_sample_and_pair_keys_emitted": False,
        },
        "limitations": [
            (
                "This report compares aggregate paired-count directions and separately "
                "summarizes agreement among signed-rank and sign-test FDR-significant "
                "reports. Effect sizes, p-values, and q-values remain per-study values; "
                "no meta-analysis or pooled estimate is calculated."
            ),
            (
                "Feature identity is exact and case-sensitive on the preserved source "
                "feature label. Curated feature IDs are displayed as per-study annotations "
                "and are never used to merge rows across studies."
            ),
            (
                "A feature absent from a bounded report result table is not reported here "
                "and is not interpreted as negative, neutral, or non-significant evidence."
            ),
            (
                "Distinct Series accessions and source digests do not establish independent "
                "participants or non-overlapping cohorts. Individual sample and pair keys "
                "are intentionally withheld."
            ),
            (
                "Public-cohort comparisons are exploratory research evidence and do not "
                "support diagnosis, prognosis, or treatment decisions."
            ),
        ],
    }
    return content_body | {
        "content_address": content_hash(content_body, prefix="geo-count-consistency")
    }


def _validate_report(report: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(report, Mapping):
        raise ValidationError("each GEO paired-count report must be an object")
    try:
        validated = validate_geo_count_contrast_report(report)
    except ValidationError as error:
        raise ValidationError("GEO paired-count report failed independent validation") from error
    if validated.get("status") != "completed":
        raise ValidationError("GEO count consistency cannot use an incomplete report")
    expected = content_hash(
        {key: value for key, value in validated.items() if key != "content_address"},
        prefix="geo-paired-count-contrast",
    )
    if validated.get("content_address") != expected:
        raise ValidationError("GEO paired-count report content address does not match its contents")
    return validated


def _validate_distinct_sources(reports: Sequence[Mapping[str, Any]]) -> None:
    accessions = [report["source"]["accession"] for report in reports]
    if len(set(accessions)) != len(accessions):
        raise ValidationError("GEO count consistency reports must use distinct Series accessions")
    count_addresses = [
        report["source"]["count_matrix"]["source_sha256"] for report in reports
    ]
    if len(set(count_addresses)) != len(count_addresses):
        raise ValidationError(
            "GEO count consistency reports must use distinct count-matrix source digests"
        )
    report_addresses = [report["content_address"] for report in reports]
    if len(set(report_addresses)) != len(report_addresses):
        raise ValidationError("GEO count consistency reports must be distinct reports")


def _validate_compatibility(reports: Sequence[Mapping[str, Any]]) -> None:
    first = reports[0]["comparison"]
    first_normalization = first["normalization_details"]
    first_signature = (
        canonical_json(first["case_filters"]),
        canonical_json(first["reference_filters"]),
        first["pair_key_column"],
        first["design"],
        first["normalization"],
        first_normalization["method"],
        first_normalization["expression_scale"],
        first["effect_size"],
        first["effect_direction_basis"],
        first["rank_biserial_effect_direction_basis"],
        first["test"],
        first["fdr_method"],
        first["fdr_threshold"],
    )
    for report in reports[1:]:
        comparison = report["comparison"]
        normalization = comparison["normalization_details"]
        signature = (
            canonical_json(comparison["case_filters"]),
            canonical_json(comparison["reference_filters"]),
            comparison["pair_key_column"],
            comparison["design"],
            comparison["normalization"],
            normalization["method"],
            normalization["expression_scale"],
            comparison["effect_size"],
            comparison["effect_direction_basis"],
            comparison["rank_biserial_effect_direction_basis"],
            comparison["test"],
            comparison["fdr_method"],
            comparison["fdr_threshold"],
        )
        if signature != first_signature:
            raise CountContrastCompatibilityError(
                "GEO paired-count reports must use the same case/reference filters, "
                "pairing design, normalization, effect-direction basis, test, and FDR settings"
            )


def _normalize_feature_ids(feature_ids: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(feature_ids, Sequence) or isinstance(feature_ids, (str, bytes, bytearray)):
        raise ValidationError("feature IDs must be supplied as a sequence")
    if not 1 <= len(feature_ids) <= MAX_COUNT_CONSISTENCY_FEATURES:
        raise ValidationError(
            "GEO count consistency requires between 1 and "
            f"{MAX_COUNT_CONSISTENCY_FEATURES} feature IDs"
        )
    normalized: list[str] = []
    for feature_id in feature_ids:
        if (
            not isinstance(feature_id, str)
            or not feature_id
            or len(feature_id) > _FEATURE_ID_MAX_LENGTH
            or any(character not in _FEATURE_ID_ALLOWED for character in feature_id)
        ):
            raise ValidationError("feature IDs use an invalid bounded source-label format")
        normalized.append(feature_id)
    if len(set(normalized)) != len(normalized):
        raise ValidationError("feature IDs must be unique")
    return tuple(normalized)


def _rows_by_feature(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row["feature_id"]): row for row in report["results"]}


def _aggregate_result(row: Mapping[str, Any]) -> dict[str, Any]:
    review = row["feature_label_review"]
    annotation = row["feature_annotation"]
    return {
        "feature_label_review": {
            "possible_date_like_source_label": review["possible_date_like_source_label"],
            "manual_annotation_review_recommended": review[
                "manual_annotation_review_recommended"
            ],
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
        "matched_pairs_rank_biserial_correlation": row[
            "matched_pairs_rank_biserial_correlation"
        ],
        "effect_direction": row["effect_direction"],
        "mean_effect_direction": row["mean_effect_direction"],
        "median_effect_direction": row["median_effect_direction"],
        "rank_biserial_effect_direction": row["rank_biserial_effect_direction"],
        "p_value": row["p_value"],
        "q_value": row["q_value"],
        "test_method": row["test_method"],
        "fdr_significant": row["fdr_significant"],
        "sign_test_p_value": row["sign_test_p_value"],
        "sign_test_q_value": row["sign_test_q_value"],
        "sign_test_method": row["sign_test_method"],
        "sign_test_fdr_significant": row["sign_test_fdr_significant"],
    }


def _study_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    source = report["source"]
    comparison = report["comparison"]
    summary = report["summary"]
    normalization = comparison["normalization_details"]
    return {
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
        "ranked_feature_count": summary.get(
            "ranked_feature_count", summary["reported_feature_count"]
        ),
        "additional_tracked_feature_count": summary.get(
            "additional_tracked_feature_count", 0
        ),
        "tracked_feature_ids": comparison.get("tracked_feature_ids", []),
        "fdr_significant_feature_count": summary["fdr_significant_feature_count"],
        "sign_test_fdr_significant_feature_count": summary[
            "sign_test_fdr_significant_feature_count"
        ],
    }


def _consistency_label(
    directions: Sequence[str],
    *,
    insufficient_label: str,
    concordant_label: str,
    discordant_label: str,
) -> str:
    if len(directions) < 2:
        return insufficient_label
    return concordant_label if len(set(directions)) == 1 else discordant_label


__all__ = [
    "CountContrastCompatibilityError",
    "MAX_COUNT_CONSISTENCY_FEATURES",
    "MAX_COUNT_CONTRAST_REPORTS",
    "build_geo_count_consistency_report",
]

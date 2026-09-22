"""Immutable persistence for aggregate GEO count-contrast reports.

Study-level cohort analyses remain distinct from patient-specific case runs.
"""

from __future__ import annotations

import csv
import io
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, overload
from urllib.parse import urlsplit

from ._safe_persistence import atomic_write_text, read_bytes
from .errors import StoreError, ValidationError
from .serialization import _strict_json_loads, canonical_bytes, canonical_json, content_hash
from .storage import ObjectStore, _filesystem_lock, _run_lock, _validate_storage_parent

GEO_ANALYSIS_RECORD_SCHEMA = "glio-noncode.geo-analysis-record.v1"
GEO_ANALYSIS_CATALOG_SCHEMA = "glio-noncode.geo-analysis-catalog.v1"
MAX_GEO_ANALYSIS_REPORT_BYTES = 32 * 1024 * 1024
MAX_GEO_ANALYSIS_RECORD_BYTES = 256 * 1024
MAX_GEO_ANALYSIS_RECORDS = 10_000
MAX_GEO_ANALYSIS_PAGE_SIZE = 50
MAX_GEO_ANALYSIS_OFFSET = 10_000
MAX_GEO_RESULT_FEATURE_QUERY_LENGTH = 256
MAX_GEO_RESULT_EXPORT_BYTES = 8 * 1024 * 1024

_ANALYSIS_ID_RE = re.compile(r"geo-[0-9a-f]{64}\Z")
_ACCESSION_RE = re.compile(r"GSE[0-9]{1,12}\Z")
_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SUPPLEMENTARY_FILE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,254}\Z")
_GEO_SUPPLEMENTARY_HOST = "ftp.ncbi.nlm.nih.gov"
_REPORT_FIELDS = frozenset(
    {
        "schema", "status", "source", "matrix", "comparison", "quality_control",
        "summary", "analysis_limits", "results", "limitations", "content_address",
    }
)
_REPORT_SUMMARY_FIELDS = frozenset(
    {
        "tested_feature_count", "fdr_significant_feature_count",
        "not_fdr_significant_feature_count", "test_method_counts",
        "sign_test_fdr_significant_feature_count",
        "not_sign_test_fdr_significant_feature_count", "sign_test_method_counts",
        "pair_deletion_sensitivity", "reported_feature_count",
        "ranked_feature_count", "additional_tracked_feature_count",
        "reported_date_like_feature_label_count", "reported_curated_feature_count",
    }
)
_LEGACY_REPORT_SUMMARY_FIELDS = _REPORT_SUMMARY_FIELDS - frozenset(
    {"ranked_feature_count", "additional_tracked_feature_count"}
)
_CATALOG_SUMMARY_FIELDS = frozenset(
    {
        "accession", "series_url", "content_address", "counts_source_sha256",
        "metadata_source_sha256", "feature_row_count", "tested_feature_count",
        "reported_feature_count", "sample_count", "pair_key_column", "case_filters",
        "reference_filters", "matched_pair_count", "case_sample_count_selected",
        "reference_sample_count_selected", "case_sample_count_unmatched",
        "reference_sample_count_unmatched", "normalization", "fdr_method",
        "fdr_threshold", "fdr_significant_feature_count",
        "sign_test_fdr_significant_feature_count",
        "ranked_feature_count", "additional_tracked_feature_count",
        "tracked_feature_ids",
        "reported_date_like_feature_label_count", "reported_curated_feature_count",
    }
)
_LEGACY_CATALOG_SUMMARY_FIELDS = _CATALOG_SUMMARY_FIELDS - frozenset(
    {"ranked_feature_count", "additional_tracked_feature_count", "tracked_feature_ids"}
)
_SOURCE_FIELDS = frozenset(
    {
        "database", "accession", "series_url", "retrieval", "count_matrix",
        "sample_metadata", "feature_annotation_map",
    }
)
_SOURCE_FILE_FIELDS = frozenset(
    {"file_name", "response_url", "source_sha256", "compressed_bytes", "decompressed_bytes"}
)
_ANNOTATION_MAP_FIELDS = frozenset(
    {"status", "format", "mapping_entry_count", "source_sha256"}
)
_MATRIX_FIELDS = frozenset(
    {
        "feature_row_count", "duplicate_feature_label_count",
        "duplicate_feature_id_count_excluded", "duplicate_feature_row_count_excluded",
        "uniquely_identified_feature_count_tested", "sample_count", "library_size_method",
        "feature_label_review",
    }
)
_MATRIX_LABEL_REVIEW_FIELDS = frozenset(
    {
        "possible_date_like_source_label_count", "reported_possible_date_like_source_labels",
        "omitted_possible_date_like_source_label_count", "automatic_normalization_performed",
        "manual_annotation_review_recommended",
    }
)
_COMPARISON_FIELDS = frozenset(
    {
        "case_filters", "reference_filters", "pair_key_column", "design",
        "matched_pair_count", "case_sample_count_selected", "reference_sample_count_selected",
        "case_sample_count_unmatched", "reference_sample_count_unmatched", "normalization",
        "normalization_details", "effect_size", "effect_direction_basis",
        "rank_biserial_effect_direction_basis", "test", "effect_sensitivity",
        "median_difference_interval_method", "median_difference_interval_confidence_level",
        "exact_test_maximum_nonzero_pairs", "sensitivity_test",
        "exact_sign_test_maximum_nonzero_pairs", "fdr_method", "fdr_threshold",
        "multiple_testing_family_count", "context_key", "source_version",
        "individual_sample_and_pair_keys_emitted",
        "tracked_feature_ids",
    }
)
_LEGACY_COMPARISON_FIELDS = _COMPARISON_FIELDS - frozenset({"tracked_feature_ids"})
_NORMALIZATION_FIELDS = frozenset(
    {
        "method", "expression_scale", "effective_library_size",
        "normalization_factor_summary", "tmm_reference", "tmm_trim",
        "duplicate_feature_policy",
    }
)
_DESCRIPTIVE_SUMMARY_FIELDS = frozenset(
    {"sample_count", "minimum", "median", "maximum"}
)
_NORMALIZATION_FACTOR_FIELDS = _DESCRIPTIVE_SUMMARY_FIELDS
_QUALITY_CONTROL_FIELDS = frozenset(
    {
        "scope", "library_size_basis", "feature_detection_basis", "case", "reference",
        "paired_library_size_imbalance_fold", "automatic_sample_exclusion",
    }
)
_QUALITY_GROUP_FIELDS = frozenset(
    {
        "sample_count", "library_size", "effective_library_size",
        "unique_features_detected_by_minimum_count", "top_unique_feature_share_of_full_library",
    }
)
_ANALYSIS_LIMIT_FIELDS = frozenset(
    {
        "max_compressed_bytes_per_file", "max_decompressed_bytes_per_file",
        "max_matrix_line_bytes", "max_samples", "max_feature_rows", "max_matrix_cells",
        "minimum_complete_pairs",
    }
)
_FILTER_FIELDS = frozenset({"field", "equals"})
_FEATURE_LABEL_REVIEW_FIELDS = frozenset(
    {
        "possible_date_like_source_label", "manual_annotation_review_recommended",
        "source_label_preserved", "automatic_normalization_performed",
    }
)
_FEATURE_ANNOTATION_FIELDS = frozenset({"status", "curated_feature_id"})
_RESULT_FIELDS = frozenset(
    {
        "feature_id", "feature_label_review", "feature_annotation", "paired_sample_count",
        "nonzero_pair_count", "case_higher_pair_count", "case_lower_pair_count",
        "tied_pair_count", "case_median_log2_cpm", "reference_median_log2_cpm",
        "mean_paired_difference_log2_cpm", "median_paired_difference_log2_cpm",
        "median_paired_difference_confidence_interval_log2_cpm",
        "leave_one_pair_out_median_sensitivity", "matched_pairs_rank_biserial_correlation",
        "effect_direction", "mean_effect_direction", "median_effect_direction",
        "rank_biserial_effect_direction", "p_value", "q_value", "test_method",
        "fdr_significant", "sign_test_p_value", "sign_test_q_value", "sign_test_method",
        "sign_test_fdr_significant",
    }
)
_CONFIDENCE_INTERVAL_FIELDS = frozenset(
    {
        "method", "requested_confidence_level", "achieved_confidence_level",
        "maximum_finite_interval_confidence_level", "bounds_log2_cpm",
        "lower_order_statistic_rank", "upper_order_statistic_rank", "status",
    }
)
_SENSITIVITY_FIELDS = frozenset(
    {
        "omitted_pair_count", "median_difference_range_log2_cpm", "direction_counts",
        "direction_stable",
    }
)
_DIRECTION_COUNT_FIELDS = frozenset({"case_higher", "case_lower", "tied"})
_SENSITIVE_KEYS = frozenset(
    {
        "gsm_id", "gsm_ids", "pair_id", "pair_ids", "patient_id", "patient_ids",
        "sample_id", "sample_ids", "subject_id", "subject_ids",
        "agent", "language",
    }
)


def _check_no_individual_keys(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is str and key.casefold() in _SENSITIVE_KEYS:
                raise ValidationError("GEO report contains an individual sample or pair key")
            _check_no_individual_keys(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_no_individual_keys(item)


def _object(value: object, fields: frozenset[str], label: str) -> dict[str, Any]:
    if type(value) is not dict or frozenset(value) != fields:
        raise ValidationError(f"GEO {label} has an invalid v1 shape")
    return value


def _comparison_object(value: object) -> dict[str, Any]:
    """Accept pre-tracking v1 reports while exposing an empty tracking set to validators."""

    if type(value) is not dict:
        raise ValidationError("GEO comparison design must be an object")
    if frozenset(value) == _COMPARISON_FIELDS:
        return _object(value, _COMPARISON_FIELDS, "comparison design")
    if frozenset(value) == _LEGACY_COMPARISON_FIELDS:
        return value | {"tracked_feature_ids": []}
    raise ValidationError("comparison design has an invalid shape")


def _summary_object(value: object) -> dict[str, Any]:
    """Accept pre-tracking v1 summaries and derive their zero-extra-row fields."""

    if type(value) is not dict:
        raise ValidationError("GEO summary must be an object")
    if frozenset(value) == _REPORT_SUMMARY_FIELDS:
        return _object(value, _REPORT_SUMMARY_FIELDS, "summary")
    if frozenset(value) == _LEGACY_REPORT_SUMMARY_FIELDS:
        return value | {
            "ranked_feature_count": value["reported_feature_count"],
            "additional_tracked_feature_count": 0,
        }
    raise ValidationError("summary has an invalid shape")


def _count(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValidationError(f"GEO {label} must be an integer of at least {minimum}")
    return value


@overload
def _finite_number(
    value: object,
    label: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    nullable: Literal[False] = False,
) -> float | int: ...


@overload
def _finite_number(
    value: object,
    label: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    nullable: Literal[True],
) -> float | int | None: ...


def _finite_number(
    value: object,
    label: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    nullable: bool = False,
) -> float | int | None:
    if value is None and nullable:
        return None
    try:
        is_finite = type(value) in (int, float) and math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        is_finite = False
    if not is_finite:
        raise ValidationError(f"GEO {label} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValidationError(f"GEO {label} is below its supported range")
    if maximum is not None and value > maximum:
        raise ValidationError(f"GEO {label} is above its supported range")
    return value


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValidationError(f"GEO {label} must be non-empty text")
    return value


def _validate_stat_summary(
    value: object,
    label: str,
    *,
    fraction: bool = False,
    expected_sample_count: int | None = None,
) -> None:
    stat = _object(value, _DESCRIPTIVE_SUMMARY_FIELDS, label)
    sample_count = _count(stat["sample_count"], f"{label} sample count", minimum=1)
    if expected_sample_count is not None and sample_count != expected_sample_count:
        raise ValidationError(f"GEO {label} sample count does not match its group")
    for key in ("minimum", "median", "maximum"):
        _finite_number(
            stat[key],
            f"{label} {key}",
            minimum=0.0 if fraction else 0.0,
            maximum=1.0 if fraction else None,
        )
    if stat["minimum"] > stat["median"] or stat["median"] > stat["maximum"]:
        raise ValidationError(f"GEO {label} values are not ordered")


def _validate_contrast_report_sections(report: dict[str, Any]) -> None:
    source = _object(report["source"], _SOURCE_FIELDS, "source provenance")
    if (
        source["database"] != "NCBI GEO"
        or type(source["retrieval"]) is not str
        or source["retrieval"] not in {"https", "local_file"}
    ):
        raise ValidationError("GEO source provenance has an unsupported origin")
    accession = _text(source["accession"], "accession")
    if _ACCESSION_RE.fullmatch(accession) is None:
        raise ValidationError("GEO analysis report accession is invalid")
    if source["series_url"] != (
        f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={accession}"
    ):
        raise ValidationError("GEO analysis series URL does not match its accession")
    response_url_count = 0
    for label in ("count_matrix", "sample_metadata"):
        artifact = _object(source[label], _SOURCE_FILE_FIELDS, f"{label} provenance")
        file_name = _text(artifact["file_name"], f"{label} filename")
        if (
            len(file_name) > 255
            or file_name in {".", ".."}
            or _SUPPLEMENTARY_FILE_NAME_RE.fullmatch(file_name) is None
        ):
            raise ValidationError(f"GEO {label} filename must be a simple file name")
        if _ADDRESS_RE.fullmatch(str(artifact["source_sha256"])) is None:
            raise ValidationError(f"GEO {label} digest is invalid")
        if artifact["response_url"] is not None:
            response_url = _text(artifact["response_url"], f"{label} response URL")
            try:
                parsed_url = urlsplit(response_url)
            except ValueError as exc:
                raise ValidationError(f"GEO {label} response URL is invalid") from exc
            digits = accession[3:]
            series_directory = f"GSE{digits[:-3]}nnn"
            expected_path = f"/geo/series/{series_directory}/{accession}/suppl/{file_name}"
            if (
                parsed_url.scheme != "https"
                or parsed_url.netloc.casefold() != _GEO_SUPPLEMENTARY_HOST
                or parsed_url.path != expected_path
                or parsed_url.query
                or parsed_url.fragment
            ):
                raise ValidationError(
                    f"GEO {label} response URL must identify its canonical NCBI GEO file"
                )
            response_url_count += 1
        for key in ("compressed_bytes", "decompressed_bytes"):
            _count(artifact[key], f"{label} {key}", minimum=1)
    if (
        source["retrieval"] == "local_file" and response_url_count
        or source["retrieval"] == "https" and response_url_count == 0
    ):
        raise ValidationError("GEO retrieval mode does not match its response provenance")
    annotation_map = _object(
        source["feature_annotation_map"], _ANNOTATION_MAP_FIELDS, "feature annotation map"
    )
    if (
        type(annotation_map["status"]) is not str
        or annotation_map["status"] not in {"provided", "not_provided"}
    ):
        raise ValidationError("GEO feature annotation map status is invalid")
    if annotation_map["format"] != "csv":
        raise ValidationError("GEO feature annotation map format is invalid")
    _count(annotation_map["mapping_entry_count"], "annotation mapping entry count")
    if annotation_map["source_sha256"] is not None and _ADDRESS_RE.fullmatch(
        str(annotation_map["source_sha256"])
    ) is None:
        raise ValidationError("GEO annotation-map digest is invalid")
    if annotation_map["status"] == "not_provided" and (
        annotation_map["mapping_entry_count"] != 0 or annotation_map["source_sha256"] is not None
    ):
        raise ValidationError("GEO unprovided annotation map has source data")
    if annotation_map["status"] == "provided" and annotation_map["source_sha256"] is None:
        raise ValidationError("GEO provided annotation map has no source digest")

    matrix = _object(report["matrix"], _MATRIX_FIELDS, "matrix summary")
    matrix_rows = _count(matrix["feature_row_count"], "matrix feature row count", minimum=1)
    matrix_samples = _count(matrix["sample_count"], "matrix sample count", minimum=1)
    duplicate_rows = _count(
        matrix["duplicate_feature_row_count_excluded"], "excluded duplicate feature rows"
    )
    tested_features = _count(
        matrix["uniquely_identified_feature_count_tested"], "tested matrix features", minimum=1
    )
    if matrix_rows - duplicate_rows != tested_features:
        raise ValidationError("GEO matrix row and tested-feature counts do not reconcile")
    for key in ("duplicate_feature_label_count", "duplicate_feature_id_count_excluded"):
        _count(matrix[key], f"matrix {key}")
    if type(matrix["library_size_method"]) is not str:
        raise ValidationError("GEO matrix library-size method is invalid")
    label_review = _object(
        matrix["feature_label_review"], _MATRIX_LABEL_REVIEW_FIELDS, "matrix label review"
    )
    date_like_count = _count(
        label_review["possible_date_like_source_label_count"], "date-like source label count"
    )
    reported_labels = label_review["reported_possible_date_like_source_labels"]
    if type(reported_labels) is not list or any(type(item) is not str for item in reported_labels):
        raise ValidationError("GEO reported date-like source labels are invalid")
    omitted_labels = _count(
        label_review["omitted_possible_date_like_source_label_count"], "omitted date-like labels"
    )
    if len(reported_labels) + omitted_labels != date_like_count:
        raise ValidationError("GEO date-like label counts do not reconcile")
    if any(
        type(label_review[key]) is not bool
        for key in ("automatic_normalization_performed", "manual_annotation_review_recommended")
    ):
        raise ValidationError("GEO matrix label review flags must be boolean")
    if label_review["automatic_normalization_performed"]:
        raise ValidationError("GEO source feature labels must not be normalized automatically")

    comparison = _comparison_object(report["comparison"])
    if comparison["individual_sample_and_pair_keys_emitted"] is not False:
        raise ValidationError("GEO report must withhold individual sample and pair keys")
    if (
        type(comparison["fdr_method"]) is not str
        or comparison["fdr_method"] not in {"bh", "by"}
    ):
        raise ValidationError("GEO FDR method is unsupported")
    threshold = _finite_number(
        comparison["fdr_threshold"], "FDR threshold", minimum=0.0, maximum=1.0
    )
    if threshold == 0:
        raise ValidationError("GEO FDR threshold must be greater than zero")
    matched_pairs = _count(comparison["matched_pair_count"], "matched pair count", minimum=1)
    case_selected = _count(
        comparison["case_sample_count_selected"], "selected case sample count", minimum=1
    )
    reference_selected = _count(
        comparison["reference_sample_count_selected"], "selected reference sample count", minimum=1
    )
    case_unmatched = _count(comparison["case_sample_count_unmatched"], "unmatched case samples")
    reference_unmatched = _count(
        comparison["reference_sample_count_unmatched"], "unmatched reference samples"
    )
    if (
        case_selected != matched_pairs + case_unmatched
        or reference_selected != matched_pairs + reference_unmatched
    ):
        raise ValidationError("GEO selected-sample and matched-pair counts do not reconcile")
    if matrix_samples < case_selected + reference_selected:
        raise ValidationError("GEO matrix has fewer samples than the selected groups")
    family_count = _count(comparison["multiple_testing_family_count"], "multiple-testing family")
    if family_count != tested_features:
        raise ValidationError("GEO testing family does not match the number of tested features")
    for key in (
        "pair_key_column", "design", "normalization", "effect_size", "effect_direction_basis",
        "rank_biserial_effect_direction_basis", "test", "effect_sensitivity",
        "median_difference_interval_method", "sensitivity_test", "context_key", "source_version",
    ):
        _text(comparison[key], f"comparison {key}")
    for key in ("case_filters", "reference_filters"):
        filters = comparison[key]
        if type(filters) is not list or not filters:
            raise ValidationError(f"GEO {key} must contain at least one filter")
        for item in filters:
            condition = _object(item, _FILTER_FIELDS, f"{key} entry")
            _text(condition["field"], f"{key} field")
            _text(condition["equals"], f"{key} value")
    normalization = _object(
        comparison["normalization_details"], _NORMALIZATION_FIELDS, "normalization details"
    )
    _text(normalization["method"], "normalization method")
    _text(normalization["expression_scale"], "normalization expression scale")
    _text(normalization["effective_library_size"], "effective library-size method")
    _text(normalization["duplicate_feature_policy"], "duplicate feature policy")
    factor_summary = _object(
        normalization["normalization_factor_summary"],
        _NORMALIZATION_FACTOR_FIELDS,
        "normalization factor summary",
    )
    factor_sample_count = _count(
        factor_summary["sample_count"], "normalization factor sample count", minimum=1
    )
    if factor_sample_count != matrix_samples:
        raise ValidationError("GEO normalization factors do not cover every matrix sample")
    factor_values = [
        _finite_number(factor_summary[key], f"normalization factor {key}", minimum=0.0)
        for key in ("minimum", "median", "maximum")
    ]
    if factor_values[0] > factor_values[1] or factor_values[1] > factor_values[2]:
        raise ValidationError("GEO normalization factor summary is not ordered")

    quality = _object(report["quality_control"], _QUALITY_CONTROL_FIELDS, "quality control")
    if (
        type(quality["automatic_sample_exclusion"]) is not bool
        or quality["automatic_sample_exclusion"]
    ):
        raise ValidationError("GEO quality control must not automatically exclude samples")
    for key in ("scope", "library_size_basis", "feature_detection_basis"):
        _text(quality[key], f"quality-control {key}")
    for key in ("case", "reference"):
        group = _object(quality[key], _QUALITY_GROUP_FIELDS, f"{key} quality summary")
        if _count(group["sample_count"], f"{key} quality sample count", minimum=1) != matched_pairs:
            raise ValidationError(f"GEO {key} quality summary does not match complete pairs")
        _validate_stat_summary(
            group["library_size"],
            f"{key} library size",
            expected_sample_count=matched_pairs,
        )
        _validate_stat_summary(
            group["effective_library_size"],
            f"{key} effective library size",
            expected_sample_count=matched_pairs,
        )
        detected = group["unique_features_detected_by_minimum_count"]
        if type(detected) is not dict or frozenset(detected) != {"1", "5", "10"}:
            raise ValidationError(f"GEO {key} feature-detection thresholds are invalid")
        for cutoff, values in detected.items():
            _validate_stat_summary(
                values,
                f"{key} features detected at count {cutoff}",
                expected_sample_count=matched_pairs,
            )
        shares = group["top_unique_feature_share_of_full_library"]
        if type(shares) is not dict or frozenset(shares) != {"top_one", "top_ten"}:
            raise ValidationError(f"GEO {key} top-feature share summary is invalid")
        for label, values in shares.items():
            _validate_stat_summary(
                values,
                f"{key} {label} share",
                fraction=True,
                expected_sample_count=matched_pairs,
            )
    _validate_stat_summary(
        quality["paired_library_size_imbalance_fold"],
        "paired library-size imbalance",
        expected_sample_count=matched_pairs,
    )

    limits = _object(report["analysis_limits"], _ANALYSIS_LIMIT_FIELDS, "analysis limits")
    for key in _ANALYSIS_LIMIT_FIELDS:
        _count(limits[key], f"analysis limit {key}", minimum=1)


def validate_geo_count_contrast_report(report: object) -> dict[str, Any]:
    """Require a complete, address-valid, aggregate-only v1 report."""

    if type(report) is not dict or frozenset(report) != _REPORT_FIELDS:
        raise ValidationError("GEO analysis must be a complete paired-count contrast report")
    try:
        encoded = canonical_bytes(report)
    except (TypeError, ValueError, UnicodeError) as exc:
        raise ValidationError("GEO analysis report must be canonical JSON data") from exc
    if len(encoded) > MAX_GEO_ANALYSIS_REPORT_BYTES:
        raise ValidationError("GEO analysis report exceeds the storage byte limit")
    if (
        report["schema"] != "glio-noncode.geo-paired-count-contrast.v1"
        or report["status"] != "completed"
    ):
        raise ValidationError("only completed v1 paired-count contrast reports can be saved")
    body = {key: value for key, value in report.items() if key != "content_address"}
    if report["content_address"] != content_hash(body, prefix="geo-paired-count-contrast"):
        raise ValidationError("GEO analysis report content address does not verify")

    _check_no_individual_keys(report)
    _validate_contrast_report_sections(report)
    matrix = report["matrix"]
    comparison = _comparison_object(report["comparison"])
    summary = _summary_object(report["summary"])
    results = report["results"]
    if type(results) is not list:
        raise ValidationError("GEO analysis results must be a list")
    tested_features = matrix["uniquely_identified_feature_count_tested"]
    summary_tested = _count(summary["tested_feature_count"], "tested feature count", minimum=1)
    if summary_tested != tested_features:
        raise ValidationError("GEO summary tested-feature count does not match the matrix")
    reported_count = _count(summary["reported_feature_count"], "reported feature count")
    if len(results) != reported_count or reported_count > tested_features:
        raise ValidationError("GEO result count does not match its summary")
    ranked_count = _count(summary["ranked_feature_count"], "ranked feature count", minimum=1)
    additional_tracked_count = _count(
        summary["additional_tracked_feature_count"],
        "additional tracked feature count",
    )
    if ranked_count + additional_tracked_count != reported_count:
        raise ValidationError("GEO ranked and tracked result counts do not reconcile")
    tracked_feature_ids = comparison["tracked_feature_ids"]
    if type(tracked_feature_ids) is not list or any(
        type(feature_id) is not str or not feature_id.strip()
        for feature_id in tracked_feature_ids
    ) or len(set(tracked_feature_ids)) != len(tracked_feature_ids):
        raise ValidationError("GEO tracked feature IDs must be a unique list of text")
    if additional_tracked_count > len(tracked_feature_ids):
        raise ValidationError("GEO additional tracked feature count exceeds tracked IDs")
    fdr_count = _count(summary["fdr_significant_feature_count"], "FDR-significant feature count")
    not_fdr_count = _count(
        summary["not_fdr_significant_feature_count"], "not-FDR-significant feature count"
    )
    sign_count = _count(
        summary["sign_test_fdr_significant_feature_count"],
        "sign-test FDR-significant feature count",
    )
    not_sign_count = _count(
        summary["not_sign_test_fdr_significant_feature_count"],
        "not-sign-test-FDR-significant feature count",
    )
    if (
        fdr_count + not_fdr_count != tested_features
        or sign_count + not_sign_count != tested_features
    ):
        raise ValidationError("GEO FDR summary counts do not cover the tested feature family")
    if fdr_count > tested_features or sign_count > tested_features:
        raise ValidationError("GEO significant feature count exceeds the tested family")
    if _count(
        summary["reported_date_like_feature_label_count"], "reported date-like feature count"
    ) > reported_count:
        raise ValidationError("GEO reported date-like feature count exceeds reported rows")
    curated_count = _count(
        summary["reported_curated_feature_count"], "reported curated feature count"
    )
    if curated_count > reported_count:
        raise ValidationError("GEO curated feature count exceeds reported rows")
    for key in ("test_method_counts", "sign_test_method_counts"):
        counts = summary[key]
        if type(counts) is not dict or not counts:
            raise ValidationError(f"GEO {key} must be a non-empty object")
        if any(type(method) is not str or not method for method in counts):
            raise ValidationError(f"GEO {key} contains an invalid method name")
        if sum(_count(count, f"{key} value") for count in counts.values()) != tested_features:
            raise ValidationError(f"GEO {key} does not cover the tested feature family")
    pair_sensitivity = _object(
        summary["pair_deletion_sensitivity"],
        frozenset(
            {
                "feature_count", "features_with_direction_change_count",
                "fdr_significant_features_with_direction_change_count",
            }
        ),
        "pair-deletion sensitivity summary",
    )
    if _count(pair_sensitivity["feature_count"], "pair-deletion feature count") != tested_features:
        raise ValidationError("GEO pair-deletion summary does not cover the tested family")
    changed_count = _count(
        pair_sensitivity["features_with_direction_change_count"],
        "pair-deletion direction-change count",
    )
    changed_significant = _count(
        pair_sensitivity["fdr_significant_features_with_direction_change_count"],
        "significant pair-deletion direction-change count",
    )
    if changed_count > tested_features or changed_significant > min(changed_count, fdr_count):
        raise ValidationError("GEO pair-deletion sensitivity counts are inconsistent")

    threshold = comparison["fdr_threshold"]
    matched_pairs = comparison["matched_pair_count"]
    feature_ids: set[str] = set()
    reported_date_like_count = 0
    reported_curated_count = 0
    reported_fdr_count = 0
    reported_sign_count = 0
    test_methods = summary["test_method_counts"]
    sign_test_methods = summary["sign_test_method_counts"]
    for row in results:
        result = _object(row, _RESULT_FIELDS, "feature result")
        feature_id = _text(result["feature_id"], "feature identifier")
        if feature_id in feature_ids:
            raise ValidationError("GEO analysis report repeats a feature identifier")
        feature_ids.add(feature_id)
        review = _object(
            result["feature_label_review"], _FEATURE_LABEL_REVIEW_FIELDS, "result label review"
        )
        if any(type(value) is not bool for value in review.values()):
            raise ValidationError("GEO result label-review flags must be boolean")
        if (
            review["source_label_preserved"] is not True
            or review["automatic_normalization_performed"]
        ):
            raise ValidationError(
                "GEO result source labels must be preserved without normalization"
            )
        reported_date_like_count += review["possible_date_like_source_label"]
        annotation = _object(
            result["feature_annotation"], _FEATURE_ANNOTATION_FIELDS, "feature annotation"
        )
        curated_id = annotation["curated_feature_id"]
        if annotation["status"] == "mapped":
            _text(curated_id, "curated feature identifier")
            reported_curated_count += 1
        elif annotation["status"] == "unmapped":
            if curated_id is not None:
                raise ValidationError("unmapped GEO feature has a curated identifier")
        else:
            raise ValidationError("GEO feature annotation status is invalid")

        paired_count = _count(
            result["paired_sample_count"], "paired feature sample count", minimum=1
        )
        higher = _count(result["case_higher_pair_count"], "case-higher pair count")
        lower = _count(result["case_lower_pair_count"], "case-lower pair count")
        ties = _count(result["tied_pair_count"], "tied pair count")
        nonzero = _count(result["nonzero_pair_count"], "nonzero pair count")
        if paired_count != matched_pairs or higher + lower + ties != matched_pairs:
            raise ValidationError("GEO feature pair counts do not match the comparison design")
        if nonzero != higher + lower:
            raise ValidationError("GEO nonzero-pair count does not match direction counts")
        for key in (
            "case_median_log2_cpm", "reference_median_log2_cpm",
            "mean_paired_difference_log2_cpm", "median_paired_difference_log2_cpm",
        ):
            _finite_number(result[key], f"feature {key}")
        correlation = _finite_number(
            result["matched_pairs_rank_biserial_correlation"],
            "matched-pairs rank-biserial correlation",
            minimum=-1.0,
            maximum=1.0,
        )
        mean_difference = result["mean_paired_difference_log2_cpm"]
        median_difference = result["median_paired_difference_log2_cpm"]
        mean_direction = (
            "case_higher" if mean_difference > 0 else "case_lower" if mean_difference < 0
            else "no_mean_difference"
        )
        median_direction = (
            "case_higher" if median_difference > 0 else "case_lower" if median_difference < 0
            else "no_median_difference"
        )
        rank_direction = (
            "case_higher" if correlation > 0 else "case_lower" if correlation < 0
            else "no_rank_shift"
        )
        direction_values = {
            "effect_direction": {"case_higher", "case_lower", "no_mean_difference"},
            "mean_effect_direction": {"case_higher", "case_lower", "no_mean_difference"},
            "median_effect_direction": {"case_higher", "case_lower", "no_median_difference"},
            "rank_biserial_effect_direction": {"case_higher", "case_lower", "no_rank_shift"},
        }
        for key, allowed in direction_values.items():
            if type(result[key]) is not str or result[key] not in allowed:
                raise ValidationError(f"GEO feature {key} is invalid")
        if (
            result["effect_direction"] != mean_direction
            or result["mean_effect_direction"] != mean_direction
            or result["median_effect_direction"] != median_direction
            or result["rank_biserial_effect_direction"] != rank_direction
        ):
            raise ValidationError("GEO feature effect directions do not match their estimates")
        for key in ("p_value", "q_value", "sign_test_p_value", "sign_test_q_value"):
            _finite_number(result[key], f"feature {key}", minimum=0.0, maximum=1.0)
        for key in ("fdr_significant", "sign_test_fdr_significant"):
            if type(result[key]) is not bool:
                raise ValidationError(f"GEO feature {key} must be boolean")
        if result["fdr_significant"] != (result["q_value"] <= threshold):
            raise ValidationError("GEO feature FDR flag does not match its q-value")
        if result["sign_test_fdr_significant"] != (result["sign_test_q_value"] <= threshold):
            raise ValidationError("GEO feature sign-test FDR flag does not match its q-value")
        reported_fdr_count += result["fdr_significant"]
        reported_sign_count += result["sign_test_fdr_significant"]
        for key in ("test_method", "sign_test_method"):
            _text(result[key], f"feature {key}")
        if result["test_method"] not in test_methods:
            raise ValidationError("GEO reported feature test method is absent from its summary")
        if result["sign_test_method"] not in sign_test_methods:
            raise ValidationError("GEO reported sign-test method is absent from its summary")

        interval = _object(
            result["median_paired_difference_confidence_interval_log2_cpm"],
            _CONFIDENCE_INTERVAL_FIELDS,
            "median-difference confidence interval",
        )
        _text(interval["method"], "confidence-interval method")
        _text(interval["status"], "confidence-interval status")
        requested_interval_level = _finite_number(
            interval["requested_confidence_level"],
            "requested confidence level",
            minimum=0.0,
            maximum=1.0,
        )
        if not 0.0 < requested_interval_level < 1.0:
            raise ValidationError(
                "GEO requested confidence level must be strictly between zero and one"
            )
        if requested_interval_level != comparison["median_difference_interval_confidence_level"]:
            raise ValidationError("GEO feature confidence level differs from its design")
        achieved_level = interval["achieved_confidence_level"]
        for key in ("achieved_confidence_level", "maximum_finite_interval_confidence_level"):
            _finite_number(interval[key], key, minimum=0.0, maximum=1.0, nullable=True)
        bounds = interval["bounds_log2_cpm"]
        if bounds is None:
            if interval["status"] != "no_finite_interval_at_requested_confidence":
                raise ValidationError("GEO confidence interval status does not match its bounds")
            if achieved_level is not None:
                raise ValidationError("unbounded GEO confidence interval has an achieved level")
        else:
            if type(bounds) is not list or len(bounds) != 2:
                raise ValidationError("GEO confidence interval bounds must contain two values")
            lower_bound = _finite_number(bounds[0], "confidence-interval lower bound")
            upper_bound = _finite_number(bounds[1], "confidence-interval upper bound")
            if (
                lower_bound > upper_bound
                or interval["status"] != "bounded"
                or achieved_level is None
                or achieved_level < requested_interval_level
            ):
                raise ValidationError("GEO confidence-interval bounds are inconsistent")
        for key in ("lower_order_statistic_rank", "upper_order_statistic_rank"):
            if interval[key] is not None:
                _count(interval[key], f"confidence interval {key}", minimum=1)

        sensitivity = _object(
            result["leave_one_pair_out_median_sensitivity"], _SENSITIVITY_FIELDS,
            "leave-one-pair-out sensitivity",
        )
        if type(sensitivity["direction_stable"]) is not bool:
            raise ValidationError("GEO direction-stability flag must be boolean")
        omitted_pairs = _count(sensitivity["omitted_pair_count"], "omitted pair count")
        if omitted_pairs != matched_pairs:
            raise ValidationError("GEO leave-one-pair-out sensitivity does not cover every pair")
        sensitivity_range = sensitivity["median_difference_range_log2_cpm"]
        if type(sensitivity_range) is not list or len(sensitivity_range) != 2:
            raise ValidationError("GEO leave-one-pair-out range must contain two values")
        range_min = _finite_number(sensitivity_range[0], "leave-one-pair-out range minimum")
        range_max = _finite_number(sensitivity_range[1], "leave-one-pair-out range maximum")
        if range_min > range_max:
            raise ValidationError("GEO leave-one-pair-out range is not ordered")
        direction_counts = _object(
            sensitivity["direction_counts"], _DIRECTION_COUNT_FIELDS,
            "leave-one-pair-out direction counts",
        )
        direction_total = sum(
            _count(direction_counts[key], f"leave-one-pair-out {key} count")
            for key in _DIRECTION_COUNT_FIELDS
        )
        if direction_total != omitted_pairs:
            raise ValidationError("GEO leave-one-pair-out direction counts do not reconcile")
    if reported_date_like_count != summary["reported_date_like_feature_label_count"]:
        raise ValidationError("GEO reported date-like label count does not match feature rows")
    if reported_curated_count != curated_count:
        raise ValidationError("GEO curated feature count does not match feature rows")
    if reported_fdr_count > fdr_count or reported_sign_count > sign_count:
        raise ValidationError("GEO reported significant rows exceed the tested-family summary")
    if type(report["limitations"]) is not list or any(
        type(item) is not str or not item.strip() for item in report["limitations"]
    ):
        raise ValidationError("GEO report limitations must be non-empty text entries")
    return report


def summarize_geo_count_contrast_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Build a bounded catalog row without result feature values."""

    source, matrix = report["source"], report["matrix"]
    comparison, summary = report["comparison"], report["summary"]
    return {
        "accession": source["accession"],
        "series_url": source["series_url"],
        "content_address": report["content_address"],
        "counts_source_sha256": source["count_matrix"]["source_sha256"],
        "metadata_source_sha256": source["sample_metadata"]["source_sha256"],
        "feature_row_count": matrix["feature_row_count"],
        "tested_feature_count": summary["tested_feature_count"],
        "reported_feature_count": summary["reported_feature_count"],
        "ranked_feature_count": summary.get(
            "ranked_feature_count", summary["reported_feature_count"]
        ),
        "additional_tracked_feature_count": summary.get(
            "additional_tracked_feature_count", 0
        ),
        "sample_count": matrix["sample_count"],
        "pair_key_column": comparison["pair_key_column"],
        "case_filters": comparison["case_filters"],
        "reference_filters": comparison["reference_filters"],
        "matched_pair_count": comparison["matched_pair_count"],
        "case_sample_count_selected": comparison["case_sample_count_selected"],
        "reference_sample_count_selected": comparison["reference_sample_count_selected"],
        "case_sample_count_unmatched": comparison["case_sample_count_unmatched"],
        "reference_sample_count_unmatched": comparison["reference_sample_count_unmatched"],
        "normalization": comparison["normalization"],
        "tracked_feature_ids": comparison.get("tracked_feature_ids", []),
        "fdr_method": comparison["fdr_method"],
        "fdr_threshold": comparison["fdr_threshold"],
        "fdr_significant_feature_count": summary["fdr_significant_feature_count"],
        "sign_test_fdr_significant_feature_count": summary[
            "sign_test_fdr_significant_feature_count"
        ],
        "reported_date_like_feature_label_count": summary[
            "reported_date_like_feature_label_count"
        ],
        "reported_curated_feature_count": summary["reported_curated_feature_count"],
    }


class GeoAnalysisStore:
    """Immutable content-addressed reports colocated with a local data root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = ObjectStore(self.root)
        self.records = self.root / "geo-analyses"
        self.locks = self.root / ".locks" / "geo-analyses"
        try:
            _validate_storage_parent(self.records, "GEO analysis store")
            if self.records.is_symlink():
                raise StoreError("GEO analysis store must be a regular directory")
            self.records.mkdir(parents=True, exist_ok=True)
            if self.records.is_symlink() or not self.records.is_dir():
                raise StoreError("GEO analysis store must be a regular directory")
            _validate_storage_parent(self.locks, "GEO analysis lock directory")
            if self.locks.is_symlink():
                raise StoreError("GEO analysis lock directory must be regular")
            self.locks.mkdir(parents=True, exist_ok=True)
            if self.locks.is_symlink() or not self.locks.is_dir():
                raise StoreError("GEO analysis lock directory must be regular")
        except StoreError:
            raise
        except OSError as exc:
            raise StoreError("GEO analysis store could not be initialized") from exc
        self._lock = _run_lock(self.records)

    @staticmethod
    def _analysis_id(body: Mapping[str, Any]) -> str:
        return f"geo-{content_hash(body).split(':', 1)[1]}"

    def _record_path(self, analysis_id: str) -> Path:
        if type(analysis_id) is not str or _ANALYSIS_ID_RE.fullmatch(analysis_id) is None:
            raise ValidationError("GEO analysis identifier is invalid")
        return self.records / f"{analysis_id}.json"

    def _decode_record(self, path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise StoreError("GEO analysis catalog contains an unsafe record")
        try:
            payload = read_bytes(
                path,
                field="GEO analysis catalog record",
                max_bytes=MAX_GEO_ANALYSIS_RECORD_BYTES,
            )
            raw = _strict_json_loads(payload)
        except (OSError, UnicodeError, ValueError, ValidationError) as exc:
            raise StoreError("GEO analysis catalog record could not be verified") from exc
        if type(raw) is not dict or frozenset(raw) != frozenset(
            {"schema", "analysis_id", "report_address", "summary"}
        ):
            raise StoreError("GEO analysis catalog record has an invalid shape")
        if raw.get("schema") != GEO_ANALYSIS_RECORD_SCHEMA:
            raise StoreError("GEO analysis catalog record schema is unsupported")
        analysis_id = raw.get("analysis_id")
        if type(analysis_id) is not str or path.stem != analysis_id:
            raise StoreError("GEO analysis identifier does not match its filename")
        if _ANALYSIS_ID_RE.fullmatch(analysis_id) is None:
            raise StoreError("GEO analysis catalog identifier is invalid")
        address = raw.get("report_address")
        if type(address) is not str or _ADDRESS_RE.fullmatch(address) is None:
            raise StoreError("GEO report address is invalid")
        summary = raw.get("summary")
        if type(summary) is not dict or frozenset(summary) not in {
            _CATALOG_SUMMARY_FIELDS,
            _LEGACY_CATALOG_SUMMARY_FIELDS,
        }:
            raise StoreError("GEO analysis catalog summary has an invalid shape")
        body = {key: value for key, value in raw.items() if key != "analysis_id"}
        if self._analysis_id(body) != analysis_id:
            raise StoreError("GEO analysis catalog address does not verify")
        return raw

    def save(self, report: object) -> dict[str, Any]:
        """Persist one complete report and return its deterministic catalog row."""

        validated = validate_geo_count_contrast_report(report)
        report_address = self.objects.put(validated)
        body = {
            "schema": GEO_ANALYSIS_RECORD_SCHEMA,
            "report_address": report_address,
            "summary": summarize_geo_count_contrast_report(validated),
        }
        analysis_id = self._analysis_id(body)
        record = body | {"analysis_id": analysis_id}
        path = self._record_path(analysis_id)
        try:
            with self._lock, _filesystem_lock(self.locks / f"{analysis_id}.lock"):
                if path.is_symlink():
                    raise StoreError("GEO analysis catalog record path is unsafe")
                if path.exists():
                    current = self._decode_record(path)
                    if canonical_json(current) != canonical_json(record):
                        raise StoreError("GEO analysis record differs at an immutable identifier")
                else:
                    atomic_write_text(
                        path,
                        canonical_json(record),
                        field="GEO analysis catalog record",
                    )
        except (OSError, ValidationError) as exc:
            raise StoreError("GEO analysis record could not be saved") from exc
        return record

    def list_reports(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        """Return a deterministic bounded page of aggregate report summaries."""

        if type(offset) is not int or not 0 <= offset <= MAX_GEO_ANALYSIS_OFFSET:
            raise ValidationError("GEO analysis offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_GEO_ANALYSIS_PAGE_SIZE:
            raise ValidationError("GEO analysis limit is outside the supported range")
        paths = sorted(self.records.glob("geo-*.json"), key=lambda item: item.name)
        if len(paths) > MAX_GEO_ANALYSIS_RECORDS:
            raise StoreError("GEO analysis catalog exceeds its record limit")
        records = [self._decode_record(path) for path in paths]
        rows = [
            {"analysis_id": item["analysis_id"], **item["summary"]}
            for item in records[offset : offset + limit]
        ]
        return {
            "schema": GEO_ANALYSIS_CATALOG_SCHEMA,
            "offset": offset,
            "limit": limit,
            "total_count": len(records),
            "has_more": offset + len(rows) < len(records),
            "rows": rows,
        }

    def get_report(self, analysis_id: str) -> dict[str, Any]:
        """Load and independently revalidate one complete stored report."""

        path = self._record_path(analysis_id)
        if not path.exists():
            raise KeyError(analysis_id)
        record = self._decode_record(path)
        report = self.objects.get(record["report_address"])
        validated = validate_geo_count_contrast_report(report)
        computed_summary = summarize_geo_count_contrast_report(validated)
        if frozenset(record["summary"]) == _LEGACY_CATALOG_SUMMARY_FIELDS:
            computed_summary = {
                key: value for key, value in computed_summary.items()
                if key in _LEGACY_CATALOG_SUMMARY_FIELDS
            }
        if computed_summary != record["summary"]:
            raise StoreError("GEO analysis catalog summary does not match its report")
        return {
            "schema": GEO_ANALYSIS_RECORD_SCHEMA,
            "analysis_id": analysis_id,
            "report_address": record["report_address"],
            "summary": record["summary"],
            "report": validated,
        }

    def compare_consistency(
        self,
        analysis_ids: Sequence[str],
        *,
        feature_ids: Sequence[str],
    ) -> dict[str, Any]:
        """Compare selected saved paired-count reports by exact source feature ID.

        The selected reports are reopened through the immutable catalog before
        comparison.  The returned consistency report contains only aggregate
        study and feature observations; individual sample and pair keys remain
        outside the store's public projection.
        """

        if not isinstance(analysis_ids, Sequence) or isinstance(
            analysis_ids, (str, bytes, bytearray)
        ):
            raise ValidationError("GEO consistency analysis IDs must be a sequence")
        from .geo_count_consistency import build_geo_count_consistency_report

        reports = tuple(self.get_report(analysis_id)["report"] for analysis_id in analysis_ids)
        return build_geo_count_consistency_report(reports, feature_ids=feature_ids)

    @staticmethod
    def _filter_results(
        results: list[dict[str, Any]],
        *,
        feature_contains: str | None,
        effect_direction: str | None,
        fdr_significant: bool | None,
        sign_test_fdr_significant: bool | None,
        min_abs_median_effect: float | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if feature_contains is not None:
            if (
                type(feature_contains) is not str
                or not feature_contains.strip()
                or len(feature_contains) > MAX_GEO_RESULT_FEATURE_QUERY_LENGTH
                or any(
                    ord(character) < 32 or ord(character) == 127
                    for character in feature_contains
                )
            ):
                raise ValidationError("GEO feature query is outside the supported range")
            feature_contains = feature_contains.casefold()
        if effect_direction is not None and effect_direction not in {
            "case_higher",
            "case_lower",
            "no_mean_difference",
        }:
            raise ValidationError("GEO effect direction is unsupported")
        if min_abs_median_effect is not None:
            _finite_number(
                min_abs_median_effect,
                "minimum absolute median effect",
                minimum=0.0,
            )
        filtered = [
            result
            for result in results
            if (
                feature_contains is None
                or feature_contains in result["feature_id"].casefold()
            )
            and (
                effect_direction is None
                or result["effect_direction"] == effect_direction
            )
            and (
                fdr_significant is None
                or result["fdr_significant"] is fdr_significant
            )
            and (
                sign_test_fdr_significant is None
                or result["sign_test_fdr_significant"] is sign_test_fdr_significant
            )
            and (
                min_abs_median_effect is None
                or abs(result["median_paired_difference_log2_cpm"]) >= min_abs_median_effect
            )
        ]
        return filtered, {
            "feature_contains": feature_contains,
            "effect_direction": effect_direction,
            "fdr_significant": fdr_significant,
            "sign_test_fdr_significant": sign_test_fdr_significant,
            "min_abs_median_effect": min_abs_median_effect,
        }

    @staticmethod
    def _filtered_result_summary(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Summarize a filtered aggregate result set without reopening or rescanning pages."""

        directions = {"case_higher": 0, "case_lower": 0, "no_mean_difference": 0}
        for result in results:
            direction = result["effect_direction"]
            if direction in directions:
                directions[direction] += 1
        return {
            "result_count": len(results),
            "effect_direction_counts": directions,
            "fdr_significant_count": sum(
                result["fdr_significant"] is True for result in results
            ),
            "sign_test_fdr_significant_count": sum(
                result["sign_test_fdr_significant"] is True for result in results
            ),
            "manual_annotation_review_recommended_count": sum(
                result["feature_label_review"]["manual_annotation_review_recommended"] is True
                for result in results
            ),
            "possible_date_like_source_label_count": sum(
                result["feature_label_review"]["possible_date_like_source_label"] is True
                for result in results
            ),
        }

    def page_results(
        self,
        analysis_id: str,
        *,
        offset: int = 0,
        limit: int = 25,
        feature_contains: str | None = None,
        effect_direction: str | None = None,
        fdr_significant: bool | None = None,
        sign_test_fdr_significant: bool | None = None,
        min_abs_median_effect: float | None = None,
    ) -> dict[str, Any]:
        """Return one filtered feature-result page with its study-level context.

        Filtering is applied to already validated aggregate rows before
        pagination. It does not change the immutable stored report or expose
        sample-level data.
        """

        if type(offset) is not int or not 0 <= offset <= MAX_GEO_ANALYSIS_OFFSET:
            raise ValidationError("GEO result offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_GEO_ANALYSIS_PAGE_SIZE:
            raise ValidationError("GEO result limit is outside the supported range")
        saved = self.get_report(analysis_id)
        report = saved["report"]
        all_results = report["results"]
        results, filters = self._filter_results(
            all_results,
            feature_contains=feature_contains,
            effect_direction=effect_direction,
            fdr_significant=fdr_significant,
            sign_test_fdr_significant=sign_test_fdr_significant,
            min_abs_median_effect=min_abs_median_effect,
        )
        page = results[offset : offset + limit]
        return {
            "schema": "glio-noncode.geo-analysis-page.v1",
            "analysis_id": analysis_id,
            "report_address": saved["report_address"],
            "summary": saved["summary"],
            "provenance": report["source"],
            "matrix": report["matrix"],
            "comparison": report["comparison"],
            "quality_control": report["quality_control"],
            "analysis_limits": report["analysis_limits"],
            "limitations": report["limitations"],
            "results": page,
            "offset": offset,
            "limit": limit,
            "total_results": len(results),
            "unfiltered_result_count": len(all_results),
            "filters": filters,
            "filtered_result_summary": self._filtered_result_summary(results),
            "has_more": offset + len(page) < len(results),
        }

    def results_csv(
        self,
        analysis_id: str,
        *,
        feature_contains: str | None = None,
        effect_direction: str | None = None,
        fdr_significant: bool | None = None,
        sign_test_fdr_significant: bool | None = None,
        min_abs_median_effect: float | None = None,
    ) -> str:
        """Export filtered aggregate result rows without individual identifiers."""

        saved = self.get_report(analysis_id)
        results, _filters = self._filter_results(
            saved["report"]["results"],
            feature_contains=feature_contains,
            effect_direction=effect_direction,
            fdr_significant=fdr_significant,
            sign_test_fdr_significant=sign_test_fdr_significant,
            min_abs_median_effect=min_abs_median_effect,
        )
        fields = (
            "feature_id",
            "possible_date_like_source_label",
            "manual_annotation_review_recommended",
            "curated_feature_id",
            "paired_sample_count",
            "case_higher_pair_count",
            "case_lower_pair_count",
            "tied_pair_count",
            "mean_paired_difference_log2_cpm",
            "median_paired_difference_log2_cpm",
            "effect_direction",
            "p_value",
            "q_value",
            "sign_test_p_value",
            "sign_test_q_value",
            "fdr_significant",
            "sign_test_fdr_significant",
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(fields)
        for result in results:
            review = result["feature_label_review"]
            annotation = result["feature_annotation"]
            writer.writerow(
                (
                    result["feature_id"],
                    review["possible_date_like_source_label"],
                    review["manual_annotation_review_recommended"],
                    annotation["curated_feature_id"],
                    result["paired_sample_count"],
                    result["case_higher_pair_count"],
                    result["case_lower_pair_count"],
                    result["tied_pair_count"],
                    result["mean_paired_difference_log2_cpm"],
                    result["median_paired_difference_log2_cpm"],
                    result["effect_direction"],
                    result["p_value"],
                    result["q_value"],
                    result["sign_test_p_value"],
                    result["sign_test_q_value"],
                    result["fdr_significant"],
                    result["sign_test_fdr_significant"],
                )
            )
        rendered = output.getvalue()
        if len(rendered.encode("utf-8")) > MAX_GEO_RESULT_EXPORT_BYTES:
            raise StoreError("GEO result CSV exceeds the export byte limit")
        return rendered

"""Cross-series direction consistency for bounded GEO contrast reports.

This module compares user-selected exact feature IDs across already completed
single-series reports. It intentionally does not combine effect sizes or
inferential statistics, resolve platform aliases, or claim cohort independence.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import ValidationError
from .geo_expression import validate_accession
from .serialization import canonical_json, content_hash

MAX_CONTRAST_REPORTS = 8
MAX_CONSISTENCY_FEATURES = 500
_FEATURE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@|/+=_-]{0,255}\Z")
_SOURCE_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DIRECTIONS = frozenset(
    {
        "case_higher",
        "case_lower",
        "no_rank_shift",
        "no_adjusted_group_effect",
    }
)


class ContrastCompatibilityError(ValidationError):
    """Raised when individually valid GEO contrasts cannot be compared directly."""

    code = "incompatible_contrast_reports"


def build_geo_contrast_consistency_report(
    contrast_reports: Sequence[Mapping[str, Any]],
    *,
    feature_ids: Sequence[str],
) -> dict[str, Any]:
    """Compare reported directions for exact feature IDs across distinct GEO matrices.

    A feature omitted from a source report's bounded result table is recorded as
    not reported; it is never treated as a negative or non-significant result.
    Content addresses are verified for integrity, but are not signatures of the
    upstream GEO source or proof that cohorts contain independent participants.
    """

    if not isinstance(contrast_reports, Sequence) or isinstance(
        contrast_reports, (str, bytes, bytearray)
    ):
        raise ValidationError("GEO contrast reports must be a sequence of report objects")
    if not 2 <= len(contrast_reports) <= MAX_CONTRAST_REPORTS:
        raise ValidationError(
            f"GEO consistency requires between 2 and {MAX_CONTRAST_REPORTS} contrast reports"
        )
    normalized_features = _normalize_feature_ids(feature_ids)
    studies = tuple(_validate_contrast_report(report) for report in contrast_reports)

    accessions = [study["source"]["accession"] for study in studies]
    if len(set(accessions)) != len(accessions):
        raise ValidationError("GEO consistency reports must use distinct Series accessions")
    source_addresses = [study["source"]["source_sha256"] for study in studies]
    if len(set(source_addresses)) != len(source_addresses):
        raise ValidationError("GEO consistency reports must use distinct matrix source digests")
    report_addresses = [study["report_content_address"] for study in studies]
    if len(set(report_addresses)) != len(report_addresses):
        raise ValidationError("GEO consistency reports must be distinct content-addressed reports")
    platform_ids = {study["source"]["platform_id"] for study in studies}
    if len(platform_ids) != 1:
        raise ContrastCompatibilityError(
            "GEO consistency requires the same platform accession; exact feature IDs do not "
            "resolve cross-platform identity"
        )

    compatibility = {
        (
            study["comparison"]["scale"],
            study["comparison"]["fdr_method"],
            study["comparison"]["fdr_threshold"],
            canonical_json(study["model_signature"]),
        )
        for study in studies
    }
    if len(compatibility) != 1:
        raise ContrastCompatibilityError(
            "GEO consistency reports must use the same scale, FDR method and threshold, "
            "and adjusted-model covariate specification"
        )

    contrast_compatibility = {
        (
            _filter_signature(study["comparison"]["case_filters"]),
            _filter_signature(study["comparison"]["reference_filters"]),
        )
        for study in studies
    }
    if len(contrast_compatibility) != 1:
        raise ContrastCompatibilityError(
            "GEO consistency reports must use identical case and reference filter definitions "
            "in the same roles"
        )

    sample_occurrences: dict[str, dict[str, Any]] = {}
    for study in studies:
        for group, sample_ids in study["sample_group_ids"].items():
            for sample_id in sample_ids:
                occurrence = sample_occurrences.setdefault(
                    sample_id, {"series": set(), "groups": set()}
                )
                occurrence["series"].add(study["source"]["accession"])
                occurrence["groups"].add(group)
    shared_sample_id_count = sum(
        len(occurrence["series"]) > 1 for occurrence in sample_occurrences.values()
    )
    cross_role_sample_id_count = sum(
        len(occurrence["groups"]) > 1 for occurrence in sample_occurrences.values()
    )

    output_features: list[dict[str, Any]] = []
    concordant_feature_count = 0
    discordant_feature_count = 0
    insufficient_feature_count = 0
    for feature_id in normalized_features:
        study_observations: list[dict[str, Any]] = []
        directions: list[str] = []
        tested_count = 0
        untestable_count = 0
        fdr_significant_count = 0
        not_reported_count = 0
        for study in studies:
            row = study["results_by_feature"].get(feature_id)
            if row is None:
                not_reported_count += 1
                study_observations.append(
                    {
                        "accession": study["source"]["accession"],
                        "platform_id": study["source"]["platform_id"],
                        "matrix_source_sha256": study["source"]["source_sha256"],
                        "contrast_report_address": study["report_content_address"],
                        "case_sample_count": study["case_sample_count"],
                        "reference_sample_count": study["reference_sample_count"],
                        "result_state": "not_reported_in_bounded_or_tracked_results",
                        "effect_direction": None,
                        "p_value": None,
                        "q_value": None,
                        "fdr_significant": None,
                        "test_method": None,
                    }
                )
                continue

            if row["p_value"] is None:
                untestable_count += 1
                result_state = "reported_but_untestable"
                direction = None
            else:
                tested_count += 1
                result_state = "tested"
                direction = _direction_category(row["effect_direction"])
                directions.append(direction)
                fdr_significant_count += int(row["fdr_significant"])
            study_observations.append(
                {
                    "accession": study["source"]["accession"],
                    "platform_id": study["source"]["platform_id"],
                    "matrix_source_sha256": study["source"]["source_sha256"],
                    "contrast_report_address": study["report_content_address"],
                    "case_sample_count": study["case_sample_count"],
                    "reference_sample_count": study["reference_sample_count"],
                    "result_state": result_state,
                    "effect_direction": direction,
                    "p_value": row["p_value"],
                    "q_value": row["q_value"],
                    "fdr_significant": (
                        row["fdr_significant"] if row["p_value"] is not None else None
                    ),
                    "test_method": row["test_method"],
                }
            )

        distinct_directions = sorted(set(directions))
        if tested_count < 2:
            direction_consistency = "insufficient_tested_reports"
            insufficient_feature_count += 1
        elif len(distinct_directions) == 1:
            direction_consistency = "concordant_among_reported"
            concordant_feature_count += 1
        else:
            direction_consistency = "discordant_among_reported"
            discordant_feature_count += 1
        output_features.append(
            {
                "feature_id": feature_id,
                "studies": study_observations,
                "summary": {
                    "series_count": len(studies),
                    "reported_count": len(studies) - not_reported_count,
                    "tested_count": tested_count,
                    "untestable_count": untestable_count,
                    "not_reported_count": not_reported_count,
                    "direction_observation_count": len(directions),
                    "distinct_directions": distinct_directions,
                    "direction_consistency": direction_consistency,
                    "fdr_significant_count": fdr_significant_count,
                },
            }
        )

    first_comparison = studies[0]["comparison"]
    content_body: dict[str, Any] = {
        "schema": "glio-noncode.geo-contrast-consistency.v1",
        "status": "completed",
        "comparison": {
            "feature_identity": "exact_case_sensitive_feature_id",
            "scale": first_comparison["scale"],
            "fdr_method": first_comparison["fdr_method"],
            "fdr_threshold": first_comparison["fdr_threshold"],
            "case_filters": first_comparison["case_filters"],
            "reference_filters": first_comparison["reference_filters"],
            "group_orientation": "case relative to reference in each source report",
            "model_signature": studies[0]["model_signature"],
        },
        "studies": [
            {
                "accession": study["source"]["accession"],
                "platform_id": study["source"]["platform_id"],
                "matrix_source_sha256": study["source"]["source_sha256"],
                "contrast_report_address": study["report_content_address"],
                "case_filters": study["comparison"]["case_filters"],
                "reference_filters": study["comparison"]["reference_filters"],
                "tracked_feature_ids": study["comparison"]["tracked_feature_ids"],
                "case_sample_count": study["case_sample_count"],
                "reference_sample_count": study["reference_sample_count"],
                "matrix_feature_count": study["summary"]["matrix_feature_count"],
                "tested_feature_count": study["summary"]["tested_feature_count"],
                "reported_feature_count": study["summary"]["reported_feature_count"],
                "additional_feature_result_count": study["summary"][
                    "additional_feature_result_count"
                ],
                "result_limit": study["summary"]["result_limit"],
            }
            for study in studies
        ],
        "features": output_features,
        "summary": {
            "study_count": len(studies),
            "feature_count": len(output_features),
            "concordant_feature_count": concordant_feature_count,
            "discordant_feature_count": discordant_feature_count,
            "insufficient_feature_count": insufficient_feature_count,
            "shared_sample_id_count_across_series": shared_sample_id_count,
            "sample_ids_assigned_to_different_groups": cross_role_sample_id_count,
        },
        "analysis": {
            "effect_sizes_pooled": False,
            "p_values_combined": False,
            "gene_aliases_resolved": False,
            "cohort_independence_verified": False,
            "shared_sample_ids_detected": shared_sample_id_count > 0,
            "cross_series_group_conflict_detected": cross_role_sample_id_count > 0,
            "missing_report_rows_treated_as_negative": False,
        },
        "limitations": [
            "This report compares directions only; it does not pool effect sizes, p-values, "
            "or false-discovery estimates.",
            "Feature identity is exact and case-sensitive. Matching IDs do not prove that "
            "different platforms measured the same transcript or gene.",
            "Studies must declare identical case and reference filter definitions; matching "
            "labels do not independently establish biological equivalence across studies.",
            "A feature absent from the ranked and explicitly tracked result tables is not "
            "reported here and is not "
            "interpreted as negative or non-significant evidence.",
            "Distinct Series accessions and matrix digests do not establish independent "
            "participants or non-overlapping cohorts.",
            "Content addresses detect report-content changes but do not authenticate GEO "
            "source data or the report producer.",
            "Public-cohort comparisons are not matched-case evidence and do not support "
            "diagnosis or treatment decisions.",
        ],
    }
    return content_body | {
        "content_address": content_hash(content_body, prefix="geo-contrast-consistency")
    }


def _normalize_feature_ids(feature_ids: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(feature_ids, Sequence) or isinstance(feature_ids, (str, bytes, bytearray)):
        raise ValidationError("feature IDs must be supplied as a sequence")
    if not 1 <= len(feature_ids) <= MAX_CONSISTENCY_FEATURES:
        raise ValidationError(
            f"GEO consistency requires between 1 and {MAX_CONSISTENCY_FEATURES} feature IDs"
        )
    normalized: list[str] = []
    for feature_id in feature_ids:
        if not isinstance(feature_id, str) or not _FEATURE_ID_RE.fullmatch(feature_id):
            raise ValidationError("feature IDs must use the bounded GEO feature identifier format")
        normalized.append(feature_id)
    if len(set(normalized)) != len(normalized):
        raise ValidationError("feature IDs must be unique")
    return tuple(normalized)


def _validate_contrast_report(report: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(report, Mapping):
        raise ValidationError("each GEO contrast report must be an object")
    if report.get("schema") != "glio-noncode.geo-expression-contrast.v1":
        raise ValidationError("GEO consistency accepts only completed GEO contrast v1 reports")
    if report.get("status") != "completed":
        raise ValidationError("GEO consistency cannot use an incomplete GEO contrast report")
    address = report.get("content_address")
    if not isinstance(address, str):
        raise ValidationError("GEO contrast report is missing its content address")
    body = {key: value for key, value in report.items() if key != "content_address"}
    try:
        expected_address = content_hash(body, prefix="geo-expression-contrast")
    except (TypeError, ValueError, UnicodeError) as error:
        raise ValidationError("GEO contrast report is not canonical JSON data") from error
    if address != expected_address:
        raise ValidationError("GEO contrast report content address does not match its contents")

    source = report.get("source")
    comparison = report.get("comparison")
    summary = report.get("summary")
    results = report.get("results")
    additional_results = report.get("additional_feature_results", [])
    if not all(isinstance(value, Mapping) for value in (source, comparison, summary)):
        raise ValidationError("GEO contrast report is missing source, comparison, or summary data")
    if not isinstance(results, list) or not isinstance(additional_results, list):
        raise ValidationError("GEO contrast ranked and tracked results must be lists")
    tracked_feature_ids = comparison.get("tracked_feature_ids", [])
    if (
        not isinstance(tracked_feature_ids, list)
        or len(tracked_feature_ids) > 500
        or any(
            not isinstance(feature_id, str) or not _FEATURE_ID_RE.fullmatch(feature_id)
            for feature_id in tracked_feature_ids
        )
        or len(set(tracked_feature_ids)) != len(tracked_feature_ids)
    ):
        raise ValidationError("GEO contrast tracked feature IDs are invalid")

    accession = validate_accession(source.get("accession"))
    source_address = source.get("source_sha256")
    if not isinstance(source_address, str) or not _SOURCE_ADDRESS_RE.fullmatch(source_address):
        raise ValidationError(
            "GEO contrast source matrix address must be a SHA-256 content address"
        )
    platform_ids = source.get("platform_ids")
    if not isinstance(platform_ids, list) or len(platform_ids) != 1:
        raise ValidationError("GEO contrast report must identify exactly one platform")
    platform_id = platform_ids[0]
    if not isinstance(platform_id, str) or not platform_id:
        raise ValidationError("GEO contrast report platform ID must be non-empty text")

    case_ids = _sample_ids(comparison.get("case_sample_ids"), "case")
    reference_ids = _sample_ids(comparison.get("reference_sample_ids"), "reference")
    if len(case_ids) < 2 or len(reference_ids) < 2:
        raise ValidationError("GEO contrast report must contain at least two samples per group")
    if set(case_ids) & set(reference_ids):
        raise ValidationError("GEO contrast report contains overlapping case and reference samples")

    scale = comparison.get("scale")
    fdr_method = comparison.get("fdr_method")
    fdr_threshold = comparison.get("fdr_threshold")
    if not isinstance(scale, str) or not scale:
        raise ValidationError("GEO contrast report scale must be non-empty text")
    if not isinstance(fdr_method, str) or fdr_method not in {"bh", "by"}:
        raise ValidationError("GEO contrast report FDR method must be bh or by")
    if (
        isinstance(fdr_threshold, bool)
        or not isinstance(fdr_threshold, (int, float))
        or not math.isfinite(float(fdr_threshold))
        or not 0.0 < float(fdr_threshold) <= 1.0
    ):
        raise ValidationError("GEO contrast report FDR threshold must be in (0, 1]")

    model_signature = _model_signature(comparison.get("model"))
    matrix_feature_count = _count(summary.get("matrix_feature_count"), "matrix feature count")
    tested_feature_count = _count(summary.get("tested_feature_count"), "tested feature count")
    reported_feature_count = _count(summary.get("reported_feature_count"), "reported feature count")
    additional_feature_result_count = _count(
        summary.get("additional_feature_result_count", len(additional_results)),
        "additional feature result count",
    )
    result_limit = _count(summary.get("result_limit"), "result limit")
    if tested_feature_count > matrix_feature_count:
        raise ValidationError("GEO contrast report tests more features than its matrix contains")
    if (
        reported_feature_count > 100_000
        or len(results) > 100_000
        or len(additional_results) > 500
        or result_limit > 100_000
        or reported_feature_count != len(results)
        or additional_feature_result_count != len(additional_results)
        or reported_feature_count > result_limit
    ):
        raise ValidationError("GEO contrast report counts do not match its ranked or tracked rows")
    if _count(source.get("feature_count"), "source feature count") != matrix_feature_count:
        raise ValidationError("GEO contrast report matrix feature counts are inconsistent")
    untestable_feature_count = _count(
        summary.get("untestable_feature_count"), "untestable feature count"
    )
    fdr_family_size = _count(summary.get("fdr_family_size"), "FDR family size")
    if (
        tested_feature_count + untestable_feature_count != matrix_feature_count
        or fdr_family_size != tested_feature_count
        or result_limit < 1
        or reported_feature_count > matrix_feature_count
    ):
        raise ValidationError("GEO contrast report feature-family counts are inconsistent")

    rows_by_feature: dict[str, dict[str, Any]] = {}
    for raw_row in (*results, *additional_results):
        if not isinstance(raw_row, Mapping):
            raise ValidationError("GEO contrast result rows must be objects")
        feature_id = raw_row.get("feature_id")
        if not isinstance(feature_id, str) or not _FEATURE_ID_RE.fullmatch(feature_id):
            raise ValidationError("GEO contrast result has an invalid feature ID")
        if feature_id in rows_by_feature:
            raise ValidationError("GEO contrast result contains duplicate feature IDs")
        p_value = _probability(raw_row.get("p_value"), "feature p-value")
        q_value = _probability(raw_row.get("q_value"), "feature q-value")
        if (p_value is None) != (q_value is None):
            raise ValidationError(
                "GEO contrast feature p-value and q-value must both be present or absent"
            )
        effect_direction = raw_row.get("effect_direction")
        if effect_direction is not None and (
            not isinstance(effect_direction, str) or effect_direction not in _DIRECTIONS
        ):
            raise ValidationError("GEO contrast feature has an unsupported effect direction")
        significant = raw_row.get("fdr_significant")
        if not isinstance(significant, bool):
            raise ValidationError("GEO contrast feature FDR status must be boolean")
        if p_value is None:
            if significant:
                raise ValidationError("untestable GEO contrast feature cannot be FDR significant")
        elif significant != (q_value <= float(fdr_threshold)):
            raise ValidationError("GEO contrast feature FDR status does not match its q-value")
        if p_value is not None and effect_direction is None:
            raise ValidationError("tested GEO contrast feature must provide an effect direction")
        test_method = raw_row.get("test_method")
        if p_value is not None and (not isinstance(test_method, str) or not test_method):
            raise ValidationError("tested GEO contrast feature must provide its test method")
        rows_by_feature[feature_id] = {
            "p_value": p_value,
            "q_value": q_value,
            "effect_direction": effect_direction,
            "fdr_significant": significant,
            "test_method": test_method,
        }
    result_feature_ids = set(rows_by_feature)
    additional_feature_ids = {row["feature_id"] for row in additional_results}
    if not additional_feature_ids.issubset(tracked_feature_ids) or not set(
        tracked_feature_ids
    ).issubset(result_feature_ids):
        raise ValidationError("GEO contrast tracked feature IDs do not match reported rows")

    source_sample_count = _count(source.get("sample_count"), "source sample count")
    if source_sample_count < len(case_ids) + len(reference_ids):
        raise ValidationError("GEO contrast group sample counts exceed the source sample count")
    return {
        "report_content_address": address,
        "source": {
            "accession": accession,
            "platform_id": platform_id,
            "source_sha256": source_address,
            "feature_count": matrix_feature_count,
        },
        "comparison": {
            "scale": scale,
            "fdr_method": fdr_method,
            "fdr_threshold": float(fdr_threshold),
            "tracked_feature_ids": tracked_feature_ids,
            "case_filters": _filter_list(comparison.get("case_filters"), "case"),
            "reference_filters": _filter_list(comparison.get("reference_filters"), "reference"),
        },
        "case_sample_count": len(case_ids),
        "reference_sample_count": len(reference_ids),
        "sample_group_ids": {"case": case_ids, "reference": reference_ids},
        "summary": {
            "matrix_feature_count": matrix_feature_count,
            "tested_feature_count": tested_feature_count,
            "reported_feature_count": reported_feature_count,
            "additional_feature_result_count": additional_feature_result_count,
            "result_limit": result_limit,
        },
        "model_signature": model_signature,
        "results_by_feature": rows_by_feature,
    }


def _sample_ids(value: object, group: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValidationError(f"GEO contrast {group} sample IDs must be a list of non-empty text")
    if len(set(value)) != len(value):
        raise ValidationError(f"GEO contrast {group} sample IDs must be unique")
    return tuple(value)


def _filter_list(value: object, group: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or not 1 <= len(value) <= 32:
        raise ValidationError(f"GEO contrast {group} filters must be a non-empty list")
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValidationError(f"GEO contrast {group} filters must contain objects")
        field = item.get("field")
        expected = item.get("equals")
        if (
            not isinstance(field, str)
            or not 1 <= len(field) <= 128
            or not isinstance(expected, str)
            or not 1 <= len(expected) <= 512
        ):
            raise ValidationError(f"GEO contrast {group} filter fields must be non-empty text")
        normalized.append({"field": field, "equals": expected})
    return normalized


def _filter_signature(filters: Sequence[Mapping[str, str]]) -> tuple[tuple[str, str], ...]:
    """Canonicalize an AND-filter set using the case-insensitive GEO matcher semantics."""

    pairs = (
        (item["field"].strip().casefold(), item["equals"].strip().casefold())
        for item in filters
    )
    return tuple(sorted(pairs))


def _model_signature(value: object) -> dict[str, Any]:
    if value is None:
        return {"type": "unadjusted", "covariates": []}
    if not isinstance(value, Mapping) or value.get("type") != "additive_ordinary_least_squares":
        raise ValidationError("GEO contrast report has an unsupported adjusted model")
    covariates = value.get("covariates")
    if not isinstance(covariates, list) or len(covariates) > 16:
        raise ValidationError("GEO adjusted model covariates must be a list")
    signature: list[dict[str, str]] = []
    for item in covariates:
        if not isinstance(item, Mapping):
            raise ValidationError("GEO adjusted model covariates must be objects")
        field = item.get("field")
        kind = item.get("type")
        if (
            not isinstance(field, str)
            or not field
            or not isinstance(kind, str)
            or kind not in {"continuous", "categorical"}
        ):
            raise ValidationError("GEO adjusted model covariate specification is invalid")
        signature.append({"field": field, "type": kind})
    return {"type": "additive_ordinary_least_squares", "covariates": signature}


def _count(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"GEO contrast {label} must be a non-negative integer")
    return value


def _probability(value: object, label: str) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        or not 0.0 <= float(value) <= 1.0
    ):
        raise ValidationError(f"GEO contrast {label} must be a finite probability or null")
    return float(value)


def _direction_category(value: str) -> str:
    if value in {"case_higher", "case_lower"}:
        return value
    if value in {"no_rank_shift", "no_adjusted_group_effect"}:
        return "neutral"
    raise ValidationError("tested GEO contrast feature has no comparable effect direction")


__all__ = [
    "MAX_CONSISTENCY_FEATURES",
    "MAX_CONTRAST_REPORTS",
    "build_geo_contrast_consistency_report",
]

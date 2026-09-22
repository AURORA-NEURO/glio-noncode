"""Immutable persistence and review projections for GEO expression contrasts.

Expression contrast reports contain selected GEO sample accessions so that a
researcher can reproduce the exact cohort selection.  Those identifiers are
kept inside the content-addressed report object.  The catalog, paged results,
and CSV export deliberately expose only aggregate cohort counts and feature
statistics.
"""

from __future__ import annotations

import csv
import io
import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import atomic_write_text, read_bytes
from .errors import StoreError, ValidationError
from .geo_consistency import _validate_contrast_report
from .serialization import _strict_json_loads, canonical_json, content_hash
from .storage import ObjectStore, _filesystem_lock, _run_lock, _validate_storage_parent

GEO_EXPRESSION_RECORD_SCHEMA = "glio-noncode.geo-expression-analysis-record.v1"
GEO_EXPRESSION_CATALOG_SCHEMA = "glio-noncode.geo-expression-analysis-catalog.v1"
GEO_EXPRESSION_PAGE_SCHEMA = "glio-noncode.geo-expression-analysis-page.v1"
MAX_GEO_EXPRESSION_REPORT_BYTES = 64 * 1024 * 1024
MAX_GEO_EXPRESSION_RECORD_BYTES = 256 * 1024
MAX_GEO_EXPRESSION_RECORDS = 10_000
MAX_GEO_EXPRESSION_PAGE_SIZE = 100
MAX_GEO_EXPRESSION_OFFSET = 100_000
MAX_GEO_EXPRESSION_QUERY_LENGTH = 256
MAX_GEO_EXPRESSION_EXPORT_BYTES = 16 * 1024 * 1024

_ANALYSIS_ID_RE = re.compile(r"geo-expression-[0-9a-f]{64}\Z")
_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SOURCE_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DIRECTIONS = frozenset(
    {
        "case_higher",
        "case_lower",
        "no_adjusted_group_effect",
        "no_rank_shift",
    }
)
_BASE_SUMMARY_FIELDS = frozenset(
    {
        "accession",
        "series_url",
        "content_address",
        "source_sha256",
        "platform_id",
        "source_file_name",
        "sample_count",
        "feature_count",
        "case_sample_count",
        "reference_sample_count",
        "scale",
        "fdr_method",
        "fdr_threshold",
        "tested_feature_count",
        "reported_feature_count",
        "additional_feature_result_count",
        "fdr_significant_feature_count",
        "fdr_significant_case_higher_count",
        "fdr_significant_case_lower_count",
        "result_limit",
        "model_type",
    }
)
_COVERAGE_SUMMARY_FIELDS = frozenset(
    {
        "ranked_feature_count_total",
        "additional_tracked_feature_count_total",
        "tracked_feature_id_count_total",
    }
)
_SUMMARY_FIELDS = _BASE_SUMMARY_FIELDS | _COVERAGE_SUMMARY_FIELDS
_SAFE_RESULT_FIELDS = (
    "feature_id",
    "case_n",
    "reference_n",
    "case_median",
    "reference_median",
    "median_difference",
    "mean_difference",
    "rank_biserial_correlation",
    "adjusted_mean_difference",
    "adjusted_mean_difference_ci_low",
    "adjusted_mean_difference_ci_high",
    "residual_standard_error",
    "adjusted_r_squared",
    "t_statistic",
    "degrees_of_freedom",
    "model_sample_count",
    "effect_direction",
    "p_value",
    "q_value",
    "test_method",
    "fdr_significant",
    "reason",
    "leave_one_sample_out_median_sensitivity",
    "platform_annotation_status",
)


def _finite(value: object, label: str, *, nullable: bool = False) -> float | int | None:
    if value is None and nullable:
        return None
    if type(value) not in (int, float):
        raise ValidationError(f"GEO expression {label} must be numeric")
    try:
        if not math.isfinite(value):
            raise ValidationError(f"GEO expression {label} must be finite")
    except (OverflowError, TypeError, ValueError) as error:
        raise ValidationError(f"GEO expression {label} must be finite") from error
    return value


def _count(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValidationError(f"GEO expression {label} must be an integer of at least {minimum}")
    return value


def _query_text(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > MAX_GEO_EXPRESSION_QUERY_LENGTH
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValidationError(f"GEO expression {label} is outside the supported range")
    return value.casefold()


def validate_geo_expression_contrast_report(report: object) -> dict[str, Any]:
    """Validate one completed expression report and its content address."""

    if type(report) is not dict:
        raise ValidationError("GEO expression contrast report must be an object")
    if report.get("schema") != "glio-noncode.geo-expression-contrast.v1":
        raise ValidationError("unsupported GEO expression contrast schema")
    if report.get("status") != "completed":
        raise ValidationError("only completed GEO expression reports can be saved")
    address = report.get("content_address")
    if type(address) is not str:
        raise ValidationError("GEO expression contrast report is missing its content address")
    body = {key: value for key, value in report.items() if key != "content_address"}
    if address != content_hash(body, prefix="geo-expression-contrast"):
        raise ValidationError("GEO expression contrast content address does not match contents")
    # The consistency validator owns the detailed report contract, including
    # feature statistics, source digests, sample-group disjointness, and FDR.
    _validate_contrast_report(report)
    source = report["source"]
    if source.get("retrieval") not in {"https", "local_file"}:
        raise ValidationError("GEO expression source retrieval mode is unsupported")
    if not _SOURCE_ADDRESS_RE.fullmatch(str(source.get("source_sha256", ""))):
        raise ValidationError("GEO expression source digest is invalid")
    return report


def summarize_geo_expression_contrast_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Create a bounded catalog row without selected sample identifiers."""

    source = report["source"]
    comparison = report["comparison"]
    summary = report["summary"]
    model = comparison.get("model")
    return {
        "accession": source["accession"],
        "series_url": source["series_url"],
        "content_address": report["content_address"],
        "source_sha256": source["source_sha256"],
        "platform_id": source["platform_ids"][0],
        "source_file_name": source.get("source_file_name"),
        "sample_count": source["sample_count"],
        "feature_count": source["feature_count"],
        "case_sample_count": len(comparison["case_sample_ids"]),
        "reference_sample_count": len(comparison["reference_sample_ids"]),
        "scale": comparison["scale"],
        "fdr_method": comparison["fdr_method"],
        "fdr_threshold": comparison["fdr_threshold"],
        "tested_feature_count": summary["tested_feature_count"],
        "reported_feature_count": summary["reported_feature_count"],
        "additional_feature_result_count": summary["additional_feature_result_count"],
        "ranked_feature_count_total": (
            summary["reported_feature_count"] - summary["additional_feature_result_count"]
        ),
        "additional_tracked_feature_count_total": summary[
            "additional_feature_result_count"
        ],
        "tracked_feature_id_count_total": len(
            comparison.get("tracked_feature_ids", [])
        ),
        "fdr_significant_feature_count": summary["fdr_significant_feature_count"],
        "fdr_significant_case_higher_count": summary["fdr_significant_case_higher_count"],
        "fdr_significant_case_lower_count": summary["fdr_significant_case_lower_count"],
        "result_limit": summary["result_limit"],
        "model_type": model.get("type") if isinstance(model, Mapping) else "unadjusted",
    }


def _public_result(row: Mapping[str, Any]) -> dict[str, Any]:
    """Strip sample-bearing and arbitrary annotation fields from one result."""

    return {key: row[key] for key in _SAFE_RESULT_FIELDS if key in row}


class GeoExpressionAnalysisStore:
    """Immutable content-addressed GEO expression reports and review pages."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = ObjectStore(self.root)
        self.records = self.root / "geo-expression-analyses"
        self.locks = self.root / ".locks" / "geo-expression-analyses"
        try:
            _validate_storage_parent(self.records, "GEO expression analysis store")
            if self.records.is_symlink():
                raise StoreError("GEO expression analysis store must be a regular directory")
            self.records.mkdir(parents=True, exist_ok=True)
            if self.records.is_symlink() or not self.records.is_dir():
                raise StoreError("GEO expression analysis store must be a regular directory")
            _validate_storage_parent(self.locks, "GEO expression analysis lock directory")
            if self.locks.is_symlink():
                raise StoreError("GEO expression analysis lock directory must be regular")
            self.locks.mkdir(parents=True, exist_ok=True)
            if self.locks.is_symlink() or not self.locks.is_dir():
                raise StoreError("GEO expression analysis lock directory must be regular")
        except StoreError:
            raise
        except OSError as error:
            raise StoreError("GEO expression analysis store could not be initialized") from error
        self._lock = _run_lock(self.records)

    @staticmethod
    def _analysis_id(body: Mapping[str, Any]) -> str:
        return f"geo-expression-{content_hash(body).split(':', 1)[1]}"

    def _record_path(self, analysis_id: str) -> Path:
        if type(analysis_id) is not str or _ANALYSIS_ID_RE.fullmatch(analysis_id) is None:
            raise ValidationError("GEO expression analysis identifier is invalid")
        return self.records / f"{analysis_id}.json"

    def _decode_record(self, path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise StoreError("GEO expression catalog contains an unsafe record")
        try:
            raw = _strict_json_loads(
                read_bytes(
                    path,
                    field="GEO expression catalog record",
                    max_bytes=MAX_GEO_EXPRESSION_RECORD_BYTES,
                )
            )
        except (OSError, UnicodeError, ValueError, ValidationError) as error:
            raise StoreError("GEO expression catalog record could not be verified") from error
        if type(raw) is not dict or frozenset(raw) != frozenset(
            {"schema", "analysis_id", "report_address", "summary"}
        ):
            raise StoreError("GEO expression catalog record has an invalid shape")
        if raw["schema"] != GEO_EXPRESSION_RECORD_SCHEMA:
            raise StoreError("GEO expression catalog record schema is unsupported")
        if type(raw["analysis_id"]) is not str or path.stem != raw["analysis_id"]:
            raise StoreError("GEO expression analysis identifier does not match filename")
        if _ANALYSIS_ID_RE.fullmatch(raw["analysis_id"]) is None:
            raise StoreError("GEO expression analysis identifier is invalid")
        if _ADDRESS_RE.fullmatch(str(raw["report_address"])) is None:
            raise StoreError("GEO expression report address is invalid")
        summary_keys = frozenset(raw["summary"]) if type(raw["summary"]) is dict else frozenset()
        if summary_keys not in {_BASE_SUMMARY_FIELDS, _SUMMARY_FIELDS}:
            raise StoreError("GEO expression catalog summary has an invalid shape")
        body = {key: value for key, value in raw.items() if key != "analysis_id"}
        if self._analysis_id(body) != raw["analysis_id"]:
            raise StoreError("GEO expression catalog record address does not verify")
        return raw

    def save(self, report: object) -> dict[str, Any]:
        """Persist one completed report and return its deterministic catalog record."""

        validated = validate_geo_expression_contrast_report(report)
        if len(canonical_json(validated).encode("utf-8")) > MAX_GEO_EXPRESSION_REPORT_BYTES:
            raise StoreError("GEO expression contrast report exceeds the storage byte limit")
        report_address = self.objects.put(validated)
        body = {
            "schema": GEO_EXPRESSION_RECORD_SCHEMA,
            "report_address": report_address,
            "summary": summarize_geo_expression_contrast_report(validated),
        }
        analysis_id = self._analysis_id(body)
        record = body | {"analysis_id": analysis_id}
        path = self._record_path(analysis_id)
        try:
            with self._lock, _filesystem_lock(self.locks / f"{analysis_id}.lock"):
                if path.is_symlink():
                    raise StoreError("GEO expression catalog record path is unsafe")
                if path.exists():
                    if canonical_json(self._decode_record(path)) != canonical_json(record):
                        raise StoreError("GEO expression record differs at immutable identifier")
                else:
                    atomic_write_text(
                        path,
                        canonical_json(record),
                        field="GEO expression catalog record",
                    )
        except (OSError, ValidationError) as error:
            raise StoreError("GEO expression analysis record could not be saved") from error
        return record

    def list_reports(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= MAX_GEO_EXPRESSION_OFFSET:
            raise ValidationError("GEO expression offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_GEO_EXPRESSION_PAGE_SIZE:
            raise ValidationError("GEO expression limit is outside the supported range")
        paths = sorted(self.records.glob("geo-expression-*.json"), key=lambda item: item.name)
        if len(paths) > MAX_GEO_EXPRESSION_RECORDS:
            raise StoreError("GEO expression catalog exceeds its record limit")
        records = [self._decode_record(path) for path in paths]
        rows = [{"analysis_id": item["analysis_id"], **item["summary"]} for item in records]
        page = rows[offset : offset + limit]
        return {
            "schema": GEO_EXPRESSION_CATALOG_SCHEMA,
            "offset": offset,
            "limit": limit,
            "total_count": len(rows),
            "has_more": offset + len(page) < len(rows),
            "rows": page,
        }

    def get_report(self, analysis_id: str) -> dict[str, Any]:
        path = self._record_path(analysis_id)
        if not path.exists():
            raise KeyError(analysis_id)
        record = self._decode_record(path)
        report = self.objects.get(record["report_address"])
        validated = validate_geo_expression_contrast_report(report)
        expected_summary = summarize_geo_expression_contrast_report(validated)
        if expected_summary != record["summary"] and {
            key: expected_summary[key] for key in _BASE_SUMMARY_FIELDS
        } != record["summary"]:
            raise StoreError("GEO expression catalog summary does not match its report")
        return {
            "schema": GEO_EXPRESSION_RECORD_SCHEMA,
            "analysis_id": analysis_id,
            "report_address": record["report_address"],
            "summary": record["summary"],
            "report": validated,
        }

    @staticmethod
    def _filter_results(
        results: list[Mapping[str, Any]],
        *,
        feature_contains: str | None,
        effect_direction: str | None,
        fdr_significant: bool | None,
        min_abs_effect: float | None,
    ) -> tuple[list[Mapping[str, Any]], dict[str, Any]]:
        feature_contains = _query_text(feature_contains, "feature query")
        if effect_direction is not None and effect_direction not in _DIRECTIONS:
            raise ValidationError("GEO expression effect direction is unsupported")
        if min_abs_effect is not None:
            _finite(min_abs_effect, "minimum absolute effect")
            if min_abs_effect < 0:
                raise ValidationError("minimum absolute effect cannot be negative")
        filtered = []
        for result in results:
            effect = result.get("adjusted_mean_difference")
            if effect is None:
                effect = result.get("mean_difference")
            if effect is None:
                effect = result.get("median_difference")
            if (
                (feature_contains is None or feature_contains in str(result["feature_id"]).casefold())
                and (effect_direction is None or result.get("effect_direction") == effect_direction)
                and (fdr_significant is None or result.get("fdr_significant") is fdr_significant)
                and (min_abs_effect is None or (effect is not None and abs(effect) >= min_abs_effect))
            ):
                filtered.append(result)
        return filtered, {
            "feature_contains": feature_contains,
            "effect_direction": effect_direction,
            "fdr_significant": fdr_significant,
            "min_abs_effect": min_abs_effect,
        }

    def _all_results(self, analysis_id: str) -> tuple[dict[str, Any], list[Mapping[str, Any]]]:
        saved = self.get_report(analysis_id)
        report = saved["report"]
        return saved, [*report["results"], *report.get("additional_feature_results", [])]

    def page_results(
        self,
        analysis_id: str,
        *,
        offset: int = 0,
        limit: int = 25,
        feature_contains: str | None = None,
        effect_direction: str | None = None,
        fdr_significant: bool | None = None,
        min_abs_effect: float | None = None,
    ) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= MAX_GEO_EXPRESSION_OFFSET:
            raise ValidationError("GEO expression result offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_GEO_EXPRESSION_PAGE_SIZE:
            raise ValidationError("GEO expression result limit is outside the supported range")
        saved, all_results = self._all_results(analysis_id)
        results, filters = self._filter_results(
            all_results,
            feature_contains=feature_contains,
            effect_direction=effect_direction,
            fdr_significant=fdr_significant,
            min_abs_effect=min_abs_effect,
        )
        page = [_public_result(result) for result in results[offset : offset + limit]]
        report = saved["report"]
        return {
            "schema": GEO_EXPRESSION_PAGE_SCHEMA,
            "analysis_id": analysis_id,
            "report_address": saved["report_address"],
            "summary": saved["summary"],
            "provenance": {
                key: report["source"][key]
                for key in (
                    "database", "accession", "series_url", "matrix_url", "retrieval",
                    "response_url", "source_file_name", "source_sha256", "sample_count",
                    "feature_count", "platform_ids", "series_title", "series_types",
                )
                if key in report["source"]
            },
            "comparison": {
                key: report["comparison"][key]
                for key in (
                    "case_filters", "reference_filters", "unassigned_sample_count", "scale",
                    "fdr_method", "fdr_threshold", "matched_to_case_sample",
                    "population_generalization", "tracked_feature_ids", "context_key", "model",
                )
                if key in report["comparison"]
            },
            "analysis_limits": report["analysis_limits"],
            "limitations": report["limitations"],
            "results": page,
            "offset": offset,
            "limit": limit,
            "total_results": len(results),
            "unfiltered_result_count": len(all_results),
            "filters": filters,
            "has_more": offset + len(page) < len(results),
        }

    def results_csv(
        self,
        analysis_id: str,
        *,
        feature_contains: str | None = None,
        effect_direction: str | None = None,
        fdr_significant: bool | None = None,
        min_abs_effect: float | None = None,
    ) -> str:
        _saved, all_results = self._all_results(analysis_id)
        results, _filters = self._filter_results(
            all_results,
            feature_contains=feature_contains,
            effect_direction=effect_direction,
            fdr_significant=fdr_significant,
            min_abs_effect=min_abs_effect,
        )
        fields = (
            "feature_id", "case_n", "reference_n", "case_median", "reference_median",
            "median_difference", "mean_difference", "adjusted_mean_difference",
            "adjusted_mean_difference_ci_low", "adjusted_mean_difference_ci_high",
            "rank_biserial_correlation", "effect_direction", "p_value", "q_value",
            "test_method", "fdr_significant", "reason",
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(fields)
        for raw in results:
            row = _public_result(raw)
            writer.writerow(tuple(row.get(field) for field in fields))
        rendered = output.getvalue()
        if len(rendered.encode("utf-8")) > MAX_GEO_EXPRESSION_EXPORT_BYTES:
            raise StoreError("GEO expression result CSV exceeds the export byte limit")
        return rendered

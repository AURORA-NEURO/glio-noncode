"""Immutable storage and bounded projections for GEO count sensitivity reports."""

from __future__ import annotations

import csv
import io
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ._safe_persistence import atomic_write_text, read_bytes
from .errors import StoreError, ValidationError
from .geo_count_sensitivity import (
    GEO_COUNT_SENSITIVITY_SCHEMA,
    build_geo_count_sensitivity_report,
    summarize_geo_count_sensitivity_report,
)
from .serialization import _strict_json_loads, canonical_json, content_hash
from .storage import ObjectStore, _filesystem_lock, _run_lock, _validate_storage_parent

GEO_COUNT_SENSITIVITY_RECORD_SCHEMA = "glio-noncode.geo-count-sensitivity-record.v1"
GEO_COUNT_SENSITIVITY_CATALOG_SCHEMA = "glio-noncode.geo-count-sensitivity-catalog.v1"
GEO_COUNT_SENSITIVITY_PAGE_SCHEMA = "glio-noncode.geo-count-sensitivity-page.v1"
MAX_COUNT_SENSITIVITY_REPORT_BYTES = 32 * 1024 * 1024
MAX_COUNT_SENSITIVITY_RECORD_BYTES = 256 * 1024
MAX_COUNT_SENSITIVITY_RECORDS = 10_000
MAX_COUNT_SENSITIVITY_PAGE_SIZE = 100
MAX_COUNT_SENSITIVITY_OFFSET = 100_000
MAX_COUNT_SENSITIVITY_QUERY_LENGTH = 256
MAX_COUNT_SENSITIVITY_EXPORT_BYTES = 16 * 1024 * 1024

_COMPARISON_ID_RE = re.compile(r"geo-count-sensitivity-[0-9a-f]{64}\Z")
_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CONTENT_ADDRESS_RE = re.compile(r"geo-count-sensitivity:[0-9a-f]{64}\Z")
_REPORT_ADDRESS_RE = re.compile(r"geo-paired-count-contrast:[0-9a-f]{64}\Z")
_DIRECTION_STATES = frozenset(
    {
        "stable_direction",
        "changed_direction",
        "insufficient_direction_evidence",
        "not_reported_in_bounded_results",
    }
)
_FDR_STATES = frozenset(
    {
        "stable_fdr_significance",
        "changed_fdr_significance",
        "insufficient_fdr_evidence",
        "not_reported_in_bounded_results",
    }
)
_SIGN_STATES = frozenset(
    {
        "stable_sign_test_fdr_significance",
        "changed_sign_test_fdr_significance",
        "insufficient_sign_test_fdr_evidence",
        "not_reported_in_bounded_results",
    }
)
_BASE_SUMMARY_FIELDS = frozenset(
    {
        "content_address",
        "accession",
        "run_count",
        "feature_count",
        "left_normalization_method",
        "right_normalization_method",
        "fdr_method",
        "fdr_threshold",
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
    }
)
_COVERAGE_SUMMARY_FIELDS = frozenset(
    {
        "reported_feature_count_total",
        "ranked_feature_count_total",
        "additional_tracked_feature_count_total",
        "tracked_feature_id_count_total",
    }
)
_SUMMARY_FIELDS = _BASE_SUMMARY_FIELDS | _COVERAGE_SUMMARY_FIELDS
_REPORT_SUMMARY_FIELDS = frozenset(
    {
        "run_count",
        "feature_count",
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
    }
)


def _count(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValidationError(
            f"GEO count sensitivity {label} must be an integer of at least {minimum}"
        )
    return value


def _finite(value: object, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValidationError(f"GEO count sensitivity {label} must be finite numeric data")
    return float(value)


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValidationError(f"GEO count sensitivity {label} must be non-empty text")
    return value


def _query_text(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > MAX_COUNT_SENSITIVITY_QUERY_LENGTH
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValidationError(f"GEO count sensitivity {label} is outside the supported range")
    return value.casefold()


def _check_no_identifiers(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is str and key.casefold() in {
                "gsm_id",
                "gsm_ids",
                "sample_id",
                "sample_ids",
                "subject_id",
                "subject_ids",
                "patient_id",
                "patient_ids",
                "pair_id",
                "pair_ids",
                "agent",
                "language",
            }:
                raise ValidationError(
                    "GEO count sensitivity contains a forbidden identifier or metadata field"
                )
            _check_no_identifiers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_no_identifiers(item)


def validate_geo_count_sensitivity_report(report: object) -> dict[str, Any]:
    """Validate the complete sensitivity artifact and all aggregate projections."""

    if type(report) is not dict:
        raise ValidationError("GEO count sensitivity report must be an object")
    required = {
        "schema",
        "status",
        "comparison",
        "runs",
        "features",
        "summary",
        "analysis",
        "limitations",
        "content_address",
    }
    if frozenset(report) != frozenset(required):
        raise ValidationError("GEO count sensitivity report has an invalid top-level shape")
    if report["schema"] != GEO_COUNT_SENSITIVITY_SCHEMA or report["status"] != "completed":
        raise ValidationError("only completed GEO count sensitivity reports can be saved")
    address = report["content_address"]
    if type(address) is not str or _CONTENT_ADDRESS_RE.fullmatch(address) is None:
        raise ValidationError("GEO count sensitivity content address is invalid")
    body = {key: value for key, value in report.items() if key != "content_address"}
    if address != content_hash(body, prefix="geo-count-sensitivity"):
        raise ValidationError("GEO count sensitivity content address does not match contents")
    _check_no_identifiers(report)

    comparison = report["comparison"]
    if type(comparison) is not dict:
        raise ValidationError("GEO count sensitivity comparison must be an object")
    required_comparison = {
        "feature_identity",
        "sensitivity_dimension",
        "accession",
        "count_matrix_source_sha256",
        "metadata_source_sha256",
        "left_normalization",
        "left_normalization_method",
        "left_expression_scale",
        "right_normalization",
        "right_normalization_method",
        "right_expression_scale",
        "case_filters",
        "reference_filters",
        "pair_key_column",
        "design",
        "group_orientation",
        "effect_direction_basis",
        "rank_biserial_effect_direction_basis",
        "fdr_method",
        "fdr_threshold",
    }
    if frozenset(comparison) != frozenset(required_comparison):
        raise ValidationError("GEO count sensitivity comparison has an invalid shape")
    if comparison["feature_identity"] != "exact_case_sensitive_source_feature_id":
        raise ValidationError("GEO count sensitivity feature identity policy is unsupported")
    if comparison["sensitivity_dimension"] != "normalization_and_expression_scale":
        raise ValidationError("GEO count sensitivity dimension is unsupported")
    _text(comparison["accession"], "accession")
    for key in ("count_matrix_source_sha256", "metadata_source_sha256"):
        if _ADDRESS_RE.fullmatch(str(comparison[key])) is None:
            raise ValidationError(f"GEO count sensitivity {key} is invalid")
    for key in (
        "left_normalization",
        "left_normalization_method",
        "left_expression_scale",
        "right_normalization",
        "right_normalization_method",
        "right_expression_scale",
        "pair_key_column",
        "design",
        "group_orientation",
        "effect_direction_basis",
        "rank_biserial_effect_direction_basis",
    ):
        _text(comparison[key], key)
    if comparison["fdr_method"] not in {"bh", "by"}:
        raise ValidationError("GEO count sensitivity FDR method is unsupported")
    threshold = _finite(comparison["fdr_threshold"], "FDR threshold")
    if not 0.0 < threshold <= 1.0:
        raise ValidationError("GEO count sensitivity FDR threshold is outside (0, 1]")
    if (
        type(comparison["case_filters"]) is not list
        or type(comparison["reference_filters"]) is not list
    ):
        raise ValidationError("GEO count sensitivity filters must be lists")

    runs = report["runs"]
    if type(runs) is not list or len(runs) != 2:
        raise ValidationError("GEO count sensitivity requires exactly two run summaries")
    roles: list[str] = []
    for run in runs:
        if type(run) is not dict:
            raise ValidationError("GEO count sensitivity run rows must be objects")
        required_run = {
            "role",
            "accession",
            "count_matrix_source_sha256",
            "metadata_source_sha256",
            "report_content_address",
            "case_filters",
            "reference_filters",
            "pair_key_column",
            "matched_pair_count",
            "case_sample_count_selected",
            "reference_sample_count_selected",
            "normalization",
            "normalization_method",
            "expression_scale",
            "fdr_method",
            "fdr_threshold",
            "tested_feature_count",
            "reported_feature_count",
            "fdr_significant_feature_count",
            "sign_test_fdr_significant_feature_count",
        }
        optional_run = {
            "ranked_feature_count",
            "additional_tracked_feature_count",
            "tracked_feature_ids",
        }
        run_keys = frozenset(run)
        if not required_run.issubset(run_keys) or not run_keys.issubset(
            required_run | optional_run
        ):
            raise ValidationError("GEO count sensitivity run has an invalid shape")
        role = _text(run["role"], "run role")
        roles.append(role)
        if role not in {"left", "right"}:
            raise ValidationError("GEO count sensitivity run role is unsupported")
        if run["accession"] != comparison["accession"]:
            raise ValidationError("GEO count sensitivity run accession does not match comparison")
        for key in ("count_matrix_source_sha256", "metadata_source_sha256"):
            if _ADDRESS_RE.fullmatch(str(run[key])) is None:
                raise ValidationError(f"GEO count sensitivity run {key} is invalid")
        if _REPORT_ADDRESS_RE.fullmatch(str(run["report_content_address"])) is None:
            raise ValidationError("GEO count sensitivity report address is invalid")
        for key in (
            "matched_pair_count",
            "case_sample_count_selected",
            "reference_sample_count_selected",
            "tested_feature_count",
            "reported_feature_count",
            "fdr_significant_feature_count",
            "sign_test_fdr_significant_feature_count",
        ):
            _count(run[key], f"run {key}")
        ranked_feature_count = _count(
            run.get("ranked_feature_count", run["reported_feature_count"]),
            "run ranked_feature_count",
        )
        additional_tracked_feature_count = _count(
            run.get("additional_tracked_feature_count", 0),
            "run additional_tracked_feature_count",
        )
        tracked_feature_ids = run.get("tracked_feature_ids", [])
        if type(tracked_feature_ids) is not list or any(
            type(feature_id) is not str or not feature_id.strip()
            for feature_id in tracked_feature_ids
        ) or len(set(tracked_feature_ids)) != len(tracked_feature_ids):
            raise ValidationError("GEO count sensitivity run tracked feature IDs are invalid")
        if (
            ranked_feature_count + additional_tracked_feature_count
            != run["reported_feature_count"]
            or additional_tracked_feature_count > len(tracked_feature_ids)
        ):
            raise ValidationError("GEO count sensitivity run coverage is inconsistent")
        _finite(run["fdr_threshold"], "run FDR threshold")
    if roles != ["left", "right"]:
        raise ValidationError("GEO count sensitivity run roles must be left then right")

    features = report["features"]
    if type(features) is not list or not 1 <= len(features) <= 500:
        raise ValidationError("GEO count sensitivity features must contain between 1 and 500 rows")
    feature_ids: set[str] = set()
    direction_counts = {key: 0 for key in _DIRECTION_STATES}
    fdr_counts = {key: 0 for key in _FDR_STATES}
    sign_counts = {key: 0 for key in _SIGN_STATES}
    expected_feature_keys = {"feature_id", "runs", "summary"}
    for feature in features:
        if type(feature) is not dict or frozenset(feature) != frozenset(expected_feature_keys):
            raise ValidationError("GEO count sensitivity feature row has an invalid shape")
        feature_id = _text(feature["feature_id"], "feature identifier")
        if feature_id in feature_ids:
            raise ValidationError("GEO count sensitivity repeats a feature identifier")
        feature_ids.add(feature_id)
        observations = feature["runs"]
        if type(observations) is not list or len(observations) != 2:
            raise ValidationError("GEO count sensitivity feature run rows do not match runs")
        for observation, expected_role in zip(observations, ("left", "right"), strict=True):
            if type(observation) is not dict or frozenset(observation) != frozenset(
                {"role", "result_state", "aggregate_result"}
            ):
                raise ValidationError(
                    "GEO count sensitivity feature observation has an invalid shape"
                )
            if observation["role"] != expected_role:
                raise ValidationError("GEO count sensitivity feature roles are not ordered")
            if observation["result_state"] not in {"reported", "not_reported_in_bounded_results"}:
                raise ValidationError("GEO count sensitivity feature result state is unsupported")
            aggregate = observation["aggregate_result"]
            if aggregate is not None and type(aggregate) is not dict:
                raise ValidationError(
                    "GEO count sensitivity aggregate result must be an object or null"
                )
        summary = feature["summary"]
        if type(summary) is not dict or frozenset(summary) != frozenset(
            {
                "direction_sensitivity",
                "fdr_sensitivity",
                "sign_test_fdr_sensitivity",
                "median_effect_delta_right_minus_left",
                "mean_effect_delta_right_minus_left",
            }
        ):
            raise ValidationError("GEO count sensitivity feature summary has an invalid shape")
        direction = summary["direction_sensitivity"]
        fdr = summary["fdr_sensitivity"]
        sign = summary["sign_test_fdr_sensitivity"]
        if direction not in _DIRECTION_STATES or fdr not in _FDR_STATES or sign not in _SIGN_STATES:
            raise ValidationError("GEO count sensitivity feature state is unsupported")
        direction_counts[direction] += 1
        fdr_counts[fdr] += 1
        sign_counts[sign] += 1
        for key in ("median_effect_delta_right_minus_left", "mean_effect_delta_right_minus_left"):
            if summary[key] is not None:
                _finite(summary[key], f"feature {key}")

    summary = report["summary"]
    if type(summary) is not dict or frozenset(summary) != _REPORT_SUMMARY_FIELDS:
        raise ValidationError("GEO count sensitivity summary has an invalid shape")
    expected = {
        "run_count": 2,
        "feature_count": len(features),
        "stable_direction_feature_count": direction_counts["stable_direction"],
        "changed_direction_feature_count": direction_counts["changed_direction"],
        "insufficient_direction_feature_count": direction_counts["insufficient_direction_evidence"],
        "not_reported_direction_feature_count": direction_counts["not_reported_in_bounded_results"],
        "stable_fdr_significance_feature_count": fdr_counts["stable_fdr_significance"],
        "changed_fdr_significance_feature_count": fdr_counts["changed_fdr_significance"],
        "insufficient_fdr_feature_count": fdr_counts["insufficient_fdr_evidence"],
        "not_reported_fdr_feature_count": fdr_counts["not_reported_in_bounded_results"],
        "stable_sign_test_fdr_significance_feature_count": sign_counts[
            "stable_sign_test_fdr_significance"
        ],
        "changed_sign_test_fdr_significance_feature_count": sign_counts[
            "changed_sign_test_fdr_significance"
        ],
        "insufficient_sign_test_fdr_feature_count": sign_counts[
            "insufficient_sign_test_fdr_evidence"
        ],
        "not_reported_sign_test_fdr_feature_count": sign_counts["not_reported_in_bounded_results"],
    }
    for key, value in expected.items():
        if _count(summary.get(key), f"summary {key}") != value:
            raise ValidationError(f"GEO count sensitivity summary {key} does not match rows")
    if type(report["analysis"]) is not dict:
        raise ValidationError("GEO count sensitivity analysis must be an object")
    if type(report["limitations"]) is not list or any(
        type(item) is not str or not item.strip() for item in report["limitations"]
    ):
        raise ValidationError("GEO count sensitivity limitations must be non-empty text")
    return report


class GeoCountSensitivityStore:
    """Persist same-source sensitivity reports and expose bounded projections."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = ObjectStore(self.root)
        self.records = self.root / "geo-count-sensitivity"
        self.locks = self.root / ".locks" / "geo-count-sensitivity"
        try:
            _validate_storage_parent(self.records, "GEO count sensitivity store")
            if self.records.is_symlink():
                raise StoreError("GEO count sensitivity store must be regular")
            self.records.mkdir(parents=True, exist_ok=True)
            if self.records.is_symlink() or not self.records.is_dir():
                raise StoreError("GEO count sensitivity store must be regular")
            _validate_storage_parent(self.locks, "GEO count sensitivity lock directory")
            if self.locks.is_symlink():
                raise StoreError("GEO count sensitivity lock directory must be regular")
            self.locks.mkdir(parents=True, exist_ok=True)
            if self.locks.is_symlink() or not self.locks.is_dir():
                raise StoreError("GEO count sensitivity lock directory must be regular")
        except StoreError:
            raise
        except OSError as error:
            raise StoreError("GEO count sensitivity store could not be initialized") from error
        self._lock = _run_lock(self.records)

    @staticmethod
    def _comparison_id(body: Mapping[str, Any]) -> str:
        return f"geo-count-sensitivity-{content_hash(body).split(':', 1)[1]}"

    def _record_path(self, comparison_id: str) -> Path:
        if type(comparison_id) is not str or _COMPARISON_ID_RE.fullmatch(comparison_id) is None:
            raise ValidationError("GEO count sensitivity comparison identifier is invalid")
        return self.records / f"{comparison_id}.json"

    def _decode_record(self, path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise StoreError("GEO count sensitivity catalog contains an unsafe record")
        try:
            raw = _strict_json_loads(
                read_bytes(
                    path,
                    field="GEO count sensitivity catalog record",
                    max_bytes=MAX_COUNT_SENSITIVITY_RECORD_BYTES,
                )
            )
        except (OSError, UnicodeError, ValueError, ValidationError) as error:
            raise StoreError(
                "GEO count sensitivity catalog record could not be verified"
            ) from error
        if type(raw) is not dict or frozenset(raw) != frozenset(
            {"schema", "comparison_id", "report_address", "summary"}
        ):
            raise StoreError("GEO count sensitivity catalog record has an invalid shape")
        if raw["schema"] != GEO_COUNT_SENSITIVITY_RECORD_SCHEMA:
            raise StoreError("GEO count sensitivity catalog schema is unsupported")
        comparison_id = raw["comparison_id"]
        if (
            type(comparison_id) is not str
            or path.stem != comparison_id
            or _COMPARISON_ID_RE.fullmatch(comparison_id) is None
        ):
            raise StoreError("GEO count sensitivity identifier is invalid")
        if _ADDRESS_RE.fullmatch(str(raw["report_address"])) is None:
            raise StoreError("GEO count sensitivity report address is invalid")
        summary_keys = frozenset(raw["summary"]) if type(raw["summary"]) is dict else frozenset()
        if summary_keys not in {_BASE_SUMMARY_FIELDS, _SUMMARY_FIELDS}:
            raise StoreError("GEO count sensitivity catalog summary has an invalid shape")
        body = {key: value for key, value in raw.items() if key != "comparison_id"}
        if self._comparison_id(body) != comparison_id:
            raise StoreError("GEO count sensitivity catalog record address does not verify")
        return raw

    def save(self, report: object) -> dict[str, Any]:
        validated = validate_geo_count_sensitivity_report(report)
        if len(canonical_json(validated).encode("utf-8")) > MAX_COUNT_SENSITIVITY_REPORT_BYTES:
            raise StoreError("GEO count sensitivity report exceeds the storage byte limit")
        report_address = self.objects.put(validated)
        body = {
            "schema": GEO_COUNT_SENSITIVITY_RECORD_SCHEMA,
            "report_address": report_address,
            "summary": {
                "content_address": validated["content_address"],
                **summarize_geo_count_sensitivity_report(validated),
            },
        }
        comparison_id = self._comparison_id(body)
        record = body | {"comparison_id": comparison_id}
        path = self._record_path(comparison_id)
        try:
            with self._lock, _filesystem_lock(self.locks / f"{comparison_id}.lock"):
                if path.is_symlink():
                    raise StoreError("GEO count sensitivity catalog record path is unsafe")
                if path.exists():
                    if canonical_json(self._decode_record(path)) != canonical_json(record):
                        raise StoreError(
                            "GEO count sensitivity record differs at immutable identifier"
                        )
                else:
                    atomic_write_text(
                        path, canonical_json(record), field="GEO count sensitivity catalog record"
                    )
        except (OSError, ValidationError) as error:
            raise StoreError("GEO count sensitivity record could not be saved") from error
        return record

    def save_from_analysis_ids(
        self, analysis_ids: Sequence[str], *, feature_ids: Sequence[str]
    ) -> dict[str, Any]:
        from .geo_analysis_store import GeoAnalysisStore

        if not isinstance(analysis_ids, Sequence) or isinstance(
            analysis_ids, (str, bytes, bytearray)
        ):
            raise ValidationError("GEO count sensitivity analysis IDs must be a sequence")
        source = GeoAnalysisStore(self.root)
        reports = tuple(source.get_report(analysis_id)["report"] for analysis_id in analysis_ids)
        return self.save(build_geo_count_sensitivity_report(reports, feature_ids=feature_ids))

    def list_reports(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= MAX_COUNT_SENSITIVITY_OFFSET:
            raise ValidationError("GEO count sensitivity offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_COUNT_SENSITIVITY_PAGE_SIZE:
            raise ValidationError("GEO count sensitivity limit is outside the supported range")
        paths = sorted(
            self.records.glob("geo-count-sensitivity-*.json"), key=lambda item: item.name
        )
        if len(paths) > MAX_COUNT_SENSITIVITY_RECORDS:
            raise StoreError("GEO count sensitivity catalog exceeds its record limit")
        records = [self._decode_record(path) for path in paths]
        rows = [{"comparison_id": item["comparison_id"], **item["summary"]} for item in records]
        page = rows[offset : offset + limit]
        return {
            "schema": GEO_COUNT_SENSITIVITY_CATALOG_SCHEMA,
            "offset": offset,
            "limit": limit,
            "total_count": len(rows),
            "has_more": offset + len(page) < len(rows),
            "rows": page,
        }

    def get_report(self, comparison_id: str) -> dict[str, Any]:
        path = self._record_path(comparison_id)
        if not path.exists():
            raise KeyError(comparison_id)
        record = self._decode_record(path)
        report = self.objects.get(record["report_address"])
        validated = validate_geo_count_sensitivity_report(report)
        expected_summary = {
            "content_address": validated["content_address"],
            **summarize_geo_count_sensitivity_report(validated),
        }
        if expected_summary != record["summary"] and {
            key: expected_summary[key] for key in _BASE_SUMMARY_FIELDS
        } != record["summary"]:
            raise StoreError("GEO count sensitivity catalog summary does not match its report")
        return {
            "schema": GEO_COUNT_SENSITIVITY_RECORD_SCHEMA,
            "comparison_id": comparison_id,
            "report_address": record["report_address"],
            "summary": record["summary"],
            "report": validated,
        }

    @staticmethod
    def _filter_features(
        features: list[Mapping[str, Any]],
        *,
        feature_contains: str | None,
        direction_sensitivity: str | None,
        fdr_sensitivity: str | None,
        sign_test_fdr_sensitivity: str | None,
    ) -> tuple[list[Mapping[str, Any]], dict[str, Any]]:
        feature_contains = _query_text(feature_contains, "feature query")
        if direction_sensitivity is not None and direction_sensitivity not in _DIRECTION_STATES:
            raise ValidationError("GEO count sensitivity direction state is unsupported")
        if fdr_sensitivity is not None and fdr_sensitivity not in _FDR_STATES:
            raise ValidationError("GEO count sensitivity FDR state is unsupported")
        if sign_test_fdr_sensitivity is not None and sign_test_fdr_sensitivity not in _SIGN_STATES:
            raise ValidationError("GEO count sensitivity sign-test FDR state is unsupported")
        rows = [
            feature
            for feature in features
            if (feature_contains is None or feature_contains in feature["feature_id"].casefold())
            and (
                direction_sensitivity is None
                or feature["summary"]["direction_sensitivity"] == direction_sensitivity
            )
            and (
                fdr_sensitivity is None or feature["summary"]["fdr_sensitivity"] == fdr_sensitivity
            )
            and (
                sign_test_fdr_sensitivity is None
                or feature["summary"]["sign_test_fdr_sensitivity"] == sign_test_fdr_sensitivity
            )
        ]
        return rows, {
            "feature_contains": feature_contains,
            "direction_sensitivity": direction_sensitivity,
            "fdr_sensitivity": fdr_sensitivity,
            "sign_test_fdr_sensitivity": sign_test_fdr_sensitivity,
        }

    def page_features(
        self,
        comparison_id: str,
        *,
        offset: int = 0,
        limit: int = 25,
        feature_contains: str | None = None,
        direction_sensitivity: str | None = None,
        fdr_sensitivity: str | None = None,
        sign_test_fdr_sensitivity: str | None = None,
    ) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= MAX_COUNT_SENSITIVITY_OFFSET:
            raise ValidationError(
                "GEO count sensitivity feature offset is outside the supported range"
            )
        if type(limit) is not int or not 1 <= limit <= MAX_COUNT_SENSITIVITY_PAGE_SIZE:
            raise ValidationError(
                "GEO count sensitivity feature limit is outside the supported range"
            )
        saved = self.get_report(comparison_id)
        report = saved["report"]
        features, filters = self._filter_features(
            report["features"],
            feature_contains=feature_contains,
            direction_sensitivity=direction_sensitivity,
            fdr_sensitivity=fdr_sensitivity,
            sign_test_fdr_sensitivity=sign_test_fdr_sensitivity,
        )
        page = features[offset : offset + limit]
        return {
            "schema": GEO_COUNT_SENSITIVITY_PAGE_SCHEMA,
            "comparison_id": comparison_id,
            "report_address": saved["report_address"],
            "summary": saved["summary"],
            "comparison": report["comparison"],
            "runs": report["runs"],
            "features": page,
            "offset": offset,
            "limit": limit,
            "total_features": len(features),
            "unfiltered_feature_count": len(report["features"]),
            "filters": filters,
            "analysis": report["analysis"],
            "limitations": report["limitations"],
            "has_more": offset + len(page) < len(features),
        }

    def features_csv(
        self,
        comparison_id: str,
        *,
        feature_contains: str | None = None,
        direction_sensitivity: str | None = None,
        fdr_sensitivity: str | None = None,
        sign_test_fdr_sensitivity: str | None = None,
    ) -> str:
        saved = self.get_report(comparison_id)
        features, _filters = self._filter_features(
            saved["report"]["features"],
            feature_contains=feature_contains,
            direction_sensitivity=direction_sensitivity,
            fdr_sensitivity=fdr_sensitivity,
            sign_test_fdr_sensitivity=sign_test_fdr_sensitivity,
        )
        fields = (
            "feature_id",
            "direction_sensitivity",
            "fdr_sensitivity",
            "sign_test_fdr_sensitivity",
            "median_effect_delta_right_minus_left",
            "mean_effect_delta_right_minus_left",
            "left_result_state",
            "right_result_state",
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(fields)
        for feature in features:
            summary = feature["summary"]
            runs = feature["runs"]
            writer.writerow(
                (
                    feature["feature_id"],
                    summary["direction_sensitivity"],
                    summary["fdr_sensitivity"],
                    summary["sign_test_fdr_sensitivity"],
                    summary["median_effect_delta_right_minus_left"],
                    summary["mean_effect_delta_right_minus_left"],
                    runs[0]["result_state"],
                    runs[1]["result_state"],
                )
            )
        rendered = output.getvalue()
        if len(rendered.encode("utf-8")) > MAX_COUNT_SENSITIVITY_EXPORT_BYTES:
            raise StoreError("GEO count sensitivity CSV exceeds the export byte limit")
        return rendered

    def runs_csv(self, comparison_id: str) -> str:
        """Export verified run-level provenance without private sample metadata."""

        saved = self.get_report(comparison_id)
        fields = (
            "role",
            "accession",
            "normalization",
            "normalization_method",
            "expression_scale",
            "count_matrix_source_sha256",
            "metadata_source_sha256",
            "pair_key_column",
            "matched_pair_count",
            "case_sample_count_selected",
            "reference_sample_count_selected",
            "fdr_method",
            "fdr_threshold",
            "tested_feature_count",
            "reported_feature_count",
            "ranked_feature_count",
            "additional_tracked_feature_count",
            "tracked_feature_ids",
            "fdr_significant_feature_count",
            "sign_test_fdr_significant_feature_count",
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(fields)
        for run in saved["report"]["runs"]:
            writer.writerow(
                (
                    run["role"],
                    run["accession"],
                    run["normalization"],
                    run["normalization_method"],
                    run["expression_scale"],
                    run["count_matrix_source_sha256"],
                    run["metadata_source_sha256"],
                    run["pair_key_column"],
                    run["matched_pair_count"],
                    run["case_sample_count_selected"],
                    run["reference_sample_count_selected"],
                    run["fdr_method"],
                    run["fdr_threshold"],
                    run["tested_feature_count"],
                    run["reported_feature_count"],
                    run.get("ranked_feature_count", run["reported_feature_count"]),
                    run.get("additional_tracked_feature_count", 0),
                    canonical_json(run.get("tracked_feature_ids", [])),
                    run["fdr_significant_feature_count"],
                    run["sign_test_fdr_significant_feature_count"],
                )
            )
        rendered = output.getvalue()
        if len(rendered.encode("utf-8")) > MAX_COUNT_SENSITIVITY_EXPORT_BYTES:
            raise StoreError("GEO count sensitivity run CSV exceeds the export byte limit")
        return rendered


__all__ = [
    "GEO_COUNT_SENSITIVITY_CATALOG_SCHEMA",
    "GEO_COUNT_SENSITIVITY_PAGE_SCHEMA",
    "GEO_COUNT_SENSITIVITY_RECORD_SCHEMA",
    "GeoCountSensitivityStore",
    "validate_geo_count_sensitivity_report",
]

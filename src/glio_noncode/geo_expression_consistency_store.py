"""Immutable persistence for cross-study GEO expression consistency reports.

The comparison is deliberately a direction-review artifact.  It preserves
which saved Series and exact feature IDs were compared, while keeping sample
accessions and source report internals behind the expression-analysis store.
"""

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
from .geo_consistency import build_geo_contrast_consistency_report
from .serialization import _strict_json_loads, canonical_json, content_hash
from .storage import ObjectStore, _filesystem_lock, _run_lock, _validate_storage_parent

GEO_EXPRESSION_CONSISTENCY_RECORD_SCHEMA = (
    "glio-noncode.geo-expression-consistency-record.v1"
)
GEO_EXPRESSION_CONSISTENCY_CATALOG_SCHEMA = (
    "glio-noncode.geo-expression-consistency-catalog.v1"
)
GEO_EXPRESSION_CONSISTENCY_PAGE_SCHEMA = (
    "glio-noncode.geo-expression-consistency-page.v1"
)
MAX_CONSISTENCY_REPORT_BYTES = 32 * 1024 * 1024
MAX_CONSISTENCY_RECORD_BYTES = 256 * 1024
MAX_CONSISTENCY_RECORDS = 10_000
MAX_CONSISTENCY_PAGE_SIZE = 100
MAX_CONSISTENCY_OFFSET = 100_000
MAX_CONSISTENCY_QUERY_LENGTH = 256
MAX_CONSISTENCY_EXPORT_BYTES = 16 * 1024 * 1024

_COMPARISON_ID_RE = re.compile(r"geo-consistency-[0-9a-f]{64}\Z")
_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CONTENT_ADDRESS_RE = re.compile(r"geo-contrast-consistency:[0-9a-f]{64}\Z")
_CONTRAST_ADDRESS_RE = re.compile(r"geo-expression-contrast:[0-9a-f]{64}\Z")
_DIRECTION_STATES = frozenset(
    {
        "concordant_among_reported",
        "discordant_among_reported",
        "insufficient_tested_reports",
    }
)
_FDR_DIRECTION_STATES = frozenset(
    {
        "concordant_among_fdr_significant",
        "discordant_among_fdr_significant",
        "insufficient_fdr_significant_reports",
    }
)
_BASE_SUMMARY_FIELDS = frozenset(
    {
        "content_address",
        "study_count",
        "feature_count",
        "accessions",
        "platform_id",
        "scale",
        "fdr_method",
        "fdr_threshold",
        "concordant_feature_count",
        "discordant_feature_count",
        "insufficient_feature_count",
        "fdr_significant_concordant_feature_count",
        "fdr_significant_discordant_feature_count",
        "fdr_significant_insufficient_feature_count",
        "shared_sample_id_count_across_series",
        "sample_ids_assigned_to_different_groups",
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


def _count(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValidationError(f"GEO consistency {label} must be an integer of at least {minimum}")
    return value


def _finite(value: object, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValidationError(f"GEO consistency {label} must be finite numeric data")
    return float(value)


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValidationError(f"GEO consistency {label} must be non-empty text")
    return value


def _query_text(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > MAX_CONSISTENCY_QUERY_LENGTH
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValidationError(f"GEO consistency {label} is outside the supported range")
    return value.casefold()


def _check_public_shape(value: object) -> None:
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
            }:
                raise ValidationError("GEO consistency report contains sample-level identifiers")
            _check_public_shape(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_public_shape(item)


def validate_geo_expression_consistency_report(report: object) -> dict[str, Any]:
    """Validate the public, content-addressed consistency report contract."""

    if type(report) is not dict:
        raise ValidationError("GEO consistency report must be an object")
    required = {
        "schema", "status", "comparison", "studies", "features", "summary",
        "analysis", "limitations", "content_address",
    }
    if frozenset(report) != frozenset(required):
        raise ValidationError("GEO consistency report has an invalid top-level shape")
    if report["schema"] != "glio-noncode.geo-contrast-consistency.v1":
        raise ValidationError("unsupported GEO consistency report schema")
    if report["status"] != "completed":
        raise ValidationError("only completed GEO consistency reports can be saved")
    address = report["content_address"]
    if type(address) is not str or _CONTENT_ADDRESS_RE.fullmatch(address) is None:
        raise ValidationError("GEO consistency content address is invalid")
    body = {key: value for key, value in report.items() if key != "content_address"}
    if address != content_hash(body, prefix="geo-contrast-consistency"):
        raise ValidationError("GEO consistency content address does not match contents")
    _check_public_shape(report)

    comparison = report["comparison"]
    if type(comparison) is not dict:
        raise ValidationError("GEO consistency comparison must be an object")
    for key in (
        "feature_identity", "scale", "fdr_method", "group_orientation",
        "case_filters", "reference_filters", "model_signature",
    ):
        if key not in comparison:
            raise ValidationError(f"GEO consistency comparison is missing {key}")
    if comparison["feature_identity"] != "exact_case_sensitive_feature_id":
        raise ValidationError("GEO consistency feature identity policy is unsupported")
    if comparison["fdr_method"] not in {"bh", "by"}:
        raise ValidationError("GEO consistency FDR method is unsupported")
    threshold = _finite(comparison.get("fdr_threshold"), "FDR threshold")
    if not 0.0 < threshold <= 1.0:
        raise ValidationError("GEO consistency FDR threshold is outside (0, 1]")
    if type(comparison["case_filters"]) is not list or type(comparison["reference_filters"]) is not list:
        raise ValidationError("GEO consistency filter projections must be lists")

    studies = report["studies"]
    if type(studies) is not list or not 2 <= len(studies) <= 8:
        raise ValidationError("GEO consistency requires between 2 and 8 studies")
    accessions: list[str] = []
    platform_ids: list[str] = []
    for study in studies:
        if type(study) is not dict:
            raise ValidationError("GEO consistency study rows must be objects")
        for key in (
            "accession", "platform_id", "matrix_source_sha256", "contrast_report_address",
            "case_filters", "reference_filters", "tracked_feature_ids", "case_sample_count",
            "reference_sample_count", "matrix_feature_count", "tested_feature_count",
            "reported_feature_count", "additional_feature_result_count", "result_limit",
        ):
            if key not in study:
                raise ValidationError(f"GEO consistency study is missing {key}")
        accessions.append(_text(study["accession"], "study accession"))
        platform_ids.append(_text(study["platform_id"], "study platform"))
        if _ADDRESS_RE.fullmatch(str(study["matrix_source_sha256"])) is None:
            raise ValidationError("GEO consistency matrix source address is invalid")
        if _CONTRAST_ADDRESS_RE.fullmatch(str(study["contrast_report_address"])) is None:
            raise ValidationError("GEO consistency contrast report address is invalid")
        for key in (
            "case_sample_count", "reference_sample_count", "matrix_feature_count",
            "tested_feature_count", "reported_feature_count", "additional_feature_result_count",
            "result_limit",
        ):
            _count(study[key], f"study {key}")
        if study["case_sample_count"] < 2 or study["reference_sample_count"] < 2:
            raise ValidationError("GEO consistency study groups must each contain at least two samples")
        if type(study["tracked_feature_ids"]) is not list:
            raise ValidationError("GEO consistency tracked feature IDs must be a list")
    if len(set(accessions)) != len(accessions):
        raise ValidationError("GEO consistency studies must use distinct accessions")
    if len(set(platform_ids)) != 1:
        raise ValidationError("GEO consistency studies must use one platform")

    features = report["features"]
    if type(features) is not list or not 1 <= len(features) <= 500:
        raise ValidationError("GEO consistency features must contain between 1 and 500 rows")
    feature_ids: set[str] = set()
    direction_counts = {key: 0 for key in _DIRECTION_STATES}
    fdr_direction_counts = {key: 0 for key in _FDR_DIRECTION_STATES}
    for feature in features:
        if type(feature) is not dict or set(feature) != {"feature_id", "studies", "summary"}:
            raise ValidationError("GEO consistency feature row has an invalid shape")
        feature_id = _text(feature["feature_id"], "feature identifier")
        if feature_id in feature_ids:
            raise ValidationError("GEO consistency repeats a feature identifier")
        feature_ids.add(feature_id)
        feature_summary = feature["summary"]
        if type(feature_summary) is not dict:
            raise ValidationError("GEO consistency feature summary must be an object")
        direction = feature_summary.get("direction_consistency")
        fdr_direction = feature_summary.get("fdr_significant_direction_consistency")
        if direction not in _DIRECTION_STATES or fdr_direction not in _FDR_DIRECTION_STATES:
            raise ValidationError("GEO consistency feature direction state is unsupported")
        direction_counts[direction] += 1
        fdr_direction_counts[fdr_direction] += 1
        observations = feature["studies"]
        if type(observations) is not list or len(observations) != len(studies):
            raise ValidationError("GEO consistency feature study rows do not match study count")
        for observation in observations:
            if type(observation) is not dict:
                raise ValidationError("GEO consistency study observations must be objects")

    summary = report["summary"]
    if type(summary) is not dict:
        raise ValidationError("GEO consistency summary must be an object")
    summary_counts = {
        "study_count": len(studies),
        "feature_count": len(features),
        "concordant_feature_count": direction_counts["concordant_among_reported"],
        "discordant_feature_count": direction_counts["discordant_among_reported"],
        "insufficient_feature_count": direction_counts["insufficient_tested_reports"],
        "fdr_significant_concordant_feature_count": fdr_direction_counts[
            "concordant_among_fdr_significant"
        ],
        "fdr_significant_discordant_feature_count": fdr_direction_counts[
            "discordant_among_fdr_significant"
        ],
        "fdr_significant_insufficient_feature_count": fdr_direction_counts[
            "insufficient_fdr_significant_reports"
        ],
    }
    for key, expected in summary_counts.items():
        if _count(summary.get(key), f"summary {key}") != expected:
            raise ValidationError(f"GEO consistency summary {key} does not match feature rows")
    for key in ("shared_sample_id_count_across_series", "sample_ids_assigned_to_different_groups"):
        _count(summary.get(key), f"summary {key}")
    if type(report["limitations"]) is not list or any(
        type(item) is not str or not item.strip() for item in report["limitations"]
    ):
        raise ValidationError("GEO consistency limitations must be non-empty text")
    return report


def summarize_geo_expression_consistency_report(report: Mapping[str, Any]) -> dict[str, Any]:
    comparison = report["comparison"]
    summary = report["summary"]
    studies = report["studies"]
    return {
        "content_address": report["content_address"],
        "study_count": summary["study_count"],
        "feature_count": summary["feature_count"],
        "accessions": [study["accession"] for study in studies],
        "platform_id": studies[0]["platform_id"],
        "scale": comparison["scale"],
        "fdr_method": comparison["fdr_method"],
        "fdr_threshold": comparison["fdr_threshold"],
        "concordant_feature_count": summary["concordant_feature_count"],
        "discordant_feature_count": summary["discordant_feature_count"],
        "insufficient_feature_count": summary["insufficient_feature_count"],
        "fdr_significant_concordant_feature_count": summary[
            "fdr_significant_concordant_feature_count"
        ],
        "fdr_significant_discordant_feature_count": summary[
            "fdr_significant_discordant_feature_count"
        ],
        "fdr_significant_insufficient_feature_count": summary[
            "fdr_significant_insufficient_feature_count"
        ],
        "shared_sample_id_count_across_series": summary[
            "shared_sample_id_count_across_series"
        ],
        "sample_ids_assigned_to_different_groups": summary[
            "sample_ids_assigned_to_different_groups"
        ],
        "reported_feature_count_total": sum(
            study["reported_feature_count"] for study in studies
        ),
        "ranked_feature_count_total": sum(
            study["reported_feature_count"] - study["additional_feature_result_count"]
            for study in studies
        ),
        "additional_tracked_feature_count_total": sum(
            study["additional_feature_result_count"] for study in studies
        ),
        "tracked_feature_id_count_total": sum(
            len(study["tracked_feature_ids"]) for study in studies
        ),
    }


class GeoExpressionConsistencyStore:
    """Immutable consistency reports built from saved expression analyses."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = ObjectStore(self.root)
        self.records = self.root / "geo-expression-consistency"
        self.locks = self.root / ".locks" / "geo-expression-consistency"
        try:
            _validate_storage_parent(self.records, "GEO expression consistency store")
            if self.records.is_symlink():
                raise StoreError("GEO expression consistency store must be a regular directory")
            self.records.mkdir(parents=True, exist_ok=True)
            if self.records.is_symlink() or not self.records.is_dir():
                raise StoreError("GEO expression consistency store must be a regular directory")
            _validate_storage_parent(self.locks, "GEO expression consistency lock directory")
            if self.locks.is_symlink():
                raise StoreError("GEO expression consistency lock directory must be regular")
            self.locks.mkdir(parents=True, exist_ok=True)
            if self.locks.is_symlink() or not self.locks.is_dir():
                raise StoreError("GEO expression consistency lock directory must be regular")
        except StoreError:
            raise
        except OSError as error:
            raise StoreError("GEO expression consistency store could not be initialized") from error
        self._lock = _run_lock(self.records)

    @staticmethod
    def _comparison_id(body: Mapping[str, Any]) -> str:
        return f"geo-consistency-{content_hash(body).split(':', 1)[1]}"

    def _record_path(self, comparison_id: str) -> Path:
        if type(comparison_id) is not str or _COMPARISON_ID_RE.fullmatch(comparison_id) is None:
            raise ValidationError("GEO consistency comparison identifier is invalid")
        return self.records / f"{comparison_id}.json"

    def _decode_record(self, path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise StoreError("GEO consistency catalog contains an unsafe record")
        try:
            raw = _strict_json_loads(
                read_bytes(
                    path,
                    field="GEO consistency catalog record",
                    max_bytes=MAX_CONSISTENCY_RECORD_BYTES,
                )
            )
        except (OSError, UnicodeError, ValueError, ValidationError) as error:
            raise StoreError("GEO consistency catalog record could not be verified") from error
        if type(raw) is not dict or frozenset(raw) != frozenset(
            {"schema", "comparison_id", "report_address", "summary"}
        ):
            raise StoreError("GEO consistency catalog record has an invalid shape")
        if raw["schema"] != GEO_EXPRESSION_CONSISTENCY_RECORD_SCHEMA:
            raise StoreError("GEO consistency catalog schema is unsupported")
        comparison_id = raw["comparison_id"]
        if type(comparison_id) is not str or path.stem != comparison_id:
            raise StoreError("GEO consistency identifier does not match filename")
        if _COMPARISON_ID_RE.fullmatch(comparison_id) is None:
            raise StoreError("GEO consistency identifier is invalid")
        if _ADDRESS_RE.fullmatch(str(raw["report_address"])) is None:
            raise StoreError("GEO consistency report address is invalid")
        summary_keys = frozenset(raw["summary"]) if type(raw["summary"]) is dict else frozenset()
        if summary_keys not in {_BASE_SUMMARY_FIELDS, _SUMMARY_FIELDS}:
            raise StoreError("GEO consistency catalog summary has an invalid shape")
        body = {key: value for key, value in raw.items() if key != "comparison_id"}
        if self._comparison_id(body) != comparison_id:
            raise StoreError("GEO consistency catalog record address does not verify")
        return raw

    def save(self, report: object) -> dict[str, Any]:
        validated = validate_geo_expression_consistency_report(report)
        if len(canonical_json(validated).encode("utf-8")) > MAX_CONSISTENCY_REPORT_BYTES:
            raise StoreError("GEO consistency report exceeds the storage byte limit")
        report_address = self.objects.put(validated)
        body = {
            "schema": GEO_EXPRESSION_CONSISTENCY_RECORD_SCHEMA,
            "report_address": report_address,
            "summary": summarize_geo_expression_consistency_report(validated),
        }
        comparison_id = self._comparison_id(body)
        record = body | {"comparison_id": comparison_id}
        path = self._record_path(comparison_id)
        try:
            with self._lock, _filesystem_lock(self.locks / f"{comparison_id}.lock"):
                if path.is_symlink():
                    raise StoreError("GEO consistency catalog record path is unsafe")
                if path.exists():
                    if canonical_json(self._decode_record(path)) != canonical_json(record):
                        raise StoreError("GEO consistency record differs at immutable identifier")
                else:
                    atomic_write_text(
                        path,
                        canonical_json(record),
                        field="GEO consistency catalog record",
                    )
        except (OSError, ValidationError) as error:
            raise StoreError("GEO consistency record could not be saved") from error
        return record

    def save_from_expression_analyses(
        self,
        analysis_ids: Sequence[str],
        *,
        feature_ids: Sequence[str],
    ) -> dict[str, Any]:
        from .geo_expression_analysis_store import GeoExpressionAnalysisStore

        if not isinstance(analysis_ids, Sequence) or isinstance(analysis_ids, (str, bytes, bytearray)):
            raise ValidationError("GEO consistency analysis IDs must be a sequence")
        expression_store = GeoExpressionAnalysisStore(self.root)
        reports = tuple(
            expression_store.get_report(analysis_id)["report"] for analysis_id in analysis_ids
        )
        return self.save(
            build_geo_contrast_consistency_report(reports, feature_ids=feature_ids)
        )

    def list_reports(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= MAX_CONSISTENCY_OFFSET:
            raise ValidationError("GEO consistency offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_CONSISTENCY_PAGE_SIZE:
            raise ValidationError("GEO consistency limit is outside the supported range")
        paths = sorted(self.records.glob("geo-consistency-*.json"), key=lambda item: item.name)
        if len(paths) > MAX_CONSISTENCY_RECORDS:
            raise StoreError("GEO consistency catalog exceeds its record limit")
        records = [self._decode_record(path) for path in paths]
        rows = [{"comparison_id": item["comparison_id"], **item["summary"]} for item in records]
        page = rows[offset : offset + limit]
        return {
            "schema": GEO_EXPRESSION_CONSISTENCY_CATALOG_SCHEMA,
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
        validated = validate_geo_expression_consistency_report(report)
        expected_summary = summarize_geo_expression_consistency_report(validated)
        if expected_summary != record["summary"] and {
            key: expected_summary[key] for key in _BASE_SUMMARY_FIELDS
        } != record["summary"]:
            raise StoreError("GEO consistency catalog summary does not match its report")
        return {
            "schema": GEO_EXPRESSION_CONSISTENCY_RECORD_SCHEMA,
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
        direction_consistency: str | None,
        fdr_direction_consistency: str | None,
    ) -> tuple[list[Mapping[str, Any]], dict[str, Any]]:
        feature_contains = _query_text(feature_contains, "feature query")
        if direction_consistency is not None and direction_consistency not in _DIRECTION_STATES:
            raise ValidationError("GEO consistency direction state is unsupported")
        if fdr_direction_consistency is not None and fdr_direction_consistency not in _FDR_DIRECTION_STATES:
            raise ValidationError("GEO consistency FDR direction state is unsupported")
        filtered = [
            feature
            for feature in features
            if (
                feature_contains is None
                or feature_contains in feature["feature_id"].casefold()
            )
            and (
                direction_consistency is None
                or feature["summary"]["direction_consistency"] == direction_consistency
            )
            and (
                fdr_direction_consistency is None
                or feature["summary"]["fdr_significant_direction_consistency"]
                == fdr_direction_consistency
            )
        ]
        return filtered, {
            "feature_contains": feature_contains,
            "direction_consistency": direction_consistency,
            "fdr_direction_consistency": fdr_direction_consistency,
        }

    def page_features(
        self,
        comparison_id: str,
        *,
        offset: int = 0,
        limit: int = 25,
        feature_contains: str | None = None,
        direction_consistency: str | None = None,
        fdr_direction_consistency: str | None = None,
    ) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= MAX_CONSISTENCY_OFFSET:
            raise ValidationError("GEO consistency feature offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_CONSISTENCY_PAGE_SIZE:
            raise ValidationError("GEO consistency feature limit is outside the supported range")
        saved = self.get_report(comparison_id)
        report = saved["report"]
        features, filters = self._filter_features(
            report["features"],
            feature_contains=feature_contains,
            direction_consistency=direction_consistency,
            fdr_direction_consistency=fdr_direction_consistency,
        )
        page = features[offset : offset + limit]
        return {
            "schema": GEO_EXPRESSION_CONSISTENCY_PAGE_SCHEMA,
            "comparison_id": comparison_id,
            "report_address": saved["report_address"],
            "summary": saved["summary"],
            "comparison": report["comparison"],
            "studies": report["studies"],
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
        direction_consistency: str | None = None,
        fdr_direction_consistency: str | None = None,
    ) -> str:
        saved = self.get_report(comparison_id)
        features, _filters = self._filter_features(
            saved["report"]["features"],
            feature_contains=feature_contains,
            direction_consistency=direction_consistency,
            fdr_direction_consistency=fdr_direction_consistency,
        )
        fields = (
            "feature_id", "direction_consistency", "tested_count", "untestable_count",
            "not_reported_count", "distinct_directions", "fdr_significant_count",
            "fdr_significant_direction_consistency", "fdr_significant_direction_observation_count",
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(fields)
        for feature in features:
            summary = feature["summary"]
            writer.writerow(
                (
                    feature["feature_id"],
                    summary["direction_consistency"],
                    summary["tested_count"],
                    summary["untestable_count"],
                    summary["not_reported_count"],
                    "|".join(summary["distinct_directions"]),
                    summary["fdr_significant_count"],
                    summary["fdr_significant_direction_consistency"],
                    summary["fdr_significant_direction_observation_count"],
                )
            )
        rendered = output.getvalue()
        if len(rendered.encode("utf-8")) > MAX_CONSISTENCY_EXPORT_BYTES:
            raise StoreError("GEO consistency CSV exceeds the export byte limit")
        return rendered

    def studies_csv(self, comparison_id: str) -> str:
        """Export verified expression-study coverage without sample identifiers."""

        saved = self.get_report(comparison_id)
        fields = (
            "study_index",
            "accession",
            "platform_id",
            "matrix_source_sha256",
            "contrast_report_address",
            "case_sample_count",
            "reference_sample_count",
            "matrix_feature_count",
            "tested_feature_count",
            "reported_feature_count",
            "ranked_feature_count",
            "additional_tracked_feature_count",
            "tracked_feature_ids",
            "result_limit",
        )
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(fields)
        for index, study in enumerate(saved["report"]["studies"], start=1):
            reported_count = study["reported_feature_count"]
            additional_count = study["additional_feature_result_count"]
            writer.writerow(
                (
                    index,
                    study["accession"],
                    study["platform_id"],
                    study["matrix_source_sha256"],
                    study["contrast_report_address"],
                    study["case_sample_count"],
                    study["reference_sample_count"],
                    study["matrix_feature_count"],
                    study["tested_feature_count"],
                    reported_count,
                    reported_count - additional_count,
                    additional_count,
                    canonical_json(study["tracked_feature_ids"]),
                    study["result_limit"],
                )
            )
        rendered = output.getvalue()
        if len(rendered.encode("utf-8")) > MAX_CONSISTENCY_EXPORT_BYTES:
            raise StoreError("GEO consistency study CSV exceeds the export byte limit")
        return rendered

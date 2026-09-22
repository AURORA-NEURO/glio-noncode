"""Immutable persistence for paired-count GEO consistency reports."""

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
from .geo_count_consistency import build_geo_count_consistency_report
from .serialization import _strict_json_loads, canonical_json, content_hash
from .storage import ObjectStore, _filesystem_lock, _run_lock, _validate_storage_parent

GEO_COUNT_CONSISTENCY_RECORD_SCHEMA = "glio-noncode.geo-count-consistency-record.v1"
GEO_COUNT_CONSISTENCY_CATALOG_SCHEMA = "glio-noncode.geo-count-consistency-catalog.v1"
GEO_COUNT_CONSISTENCY_PAGE_SCHEMA = "glio-noncode.geo-count-consistency-page.v1"
MAX_COUNT_CONSISTENCY_REPORT_BYTES = 32 * 1024 * 1024
MAX_COUNT_CONSISTENCY_RECORD_BYTES = 256 * 1024
MAX_COUNT_CONSISTENCY_RECORDS = 10_000
MAX_COUNT_CONSISTENCY_PAGE_SIZE = 100
MAX_COUNT_CONSISTENCY_OFFSET = 100_000
MAX_COUNT_CONSISTENCY_QUERY_LENGTH = 256
MAX_COUNT_CONSISTENCY_EXPORT_BYTES = 16 * 1024 * 1024

_COMPARISON_ID_RE = re.compile(r"geo-count-consistency-[0-9a-f]{64}\Z")
_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CONTENT_ADDRESS_RE = re.compile(r"geo-count-consistency:[0-9a-f]{64}\Z")
_REPORT_ADDRESS_RE = re.compile(r"geo-paired-count-contrast:[0-9a-f]{64}\Z")
_DIRECTION_STATES = frozenset(
    {"concordant_among_tested", "discordant_among_tested", "insufficient_tested_reports"}
)
_FDR_DIRECTION_STATES = frozenset(
    {
        "concordant_among_fdr_significant",
        "discordant_among_fdr_significant",
        "insufficient_fdr_significant_reports",
    }
)
_SIGN_DIRECTION_STATES = frozenset(
    {
        "concordant_among_sign_test_fdr_significant",
        "discordant_among_sign_test_fdr_significant",
        "insufficient_sign_test_fdr_significant_reports",
    }
)
_SUMMARY_FIELDS = frozenset(
    {
        "content_address", "study_count", "feature_count", "accessions", "pair_key_column",
        "normalization_method", "expression_scale", "fdr_method", "fdr_threshold",
        "concordant_feature_count", "discordant_feature_count", "insufficient_feature_count",
        "fdr_significant_concordant_feature_count",
        "fdr_significant_discordant_feature_count",
        "fdr_significant_insufficient_feature_count",
        "sign_test_fdr_significant_concordant_feature_count",
        "sign_test_fdr_significant_discordant_feature_count",
        "sign_test_fdr_significant_insufficient_feature_count",
    }
)


def _count(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValidationError(f"GEO count consistency {label} must be an integer of at least {minimum}")
    return value


def _finite(value: object, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValidationError(f"GEO count consistency {label} must be finite numeric data")
    return float(value)


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValidationError(f"GEO count consistency {label} must be non-empty text")
    return value


def _query_text(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > MAX_COUNT_CONSISTENCY_QUERY_LENGTH
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise ValidationError(f"GEO count consistency {label} is outside the supported range")
    return value.casefold()


def _check_no_identifiers(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is str and key.casefold() in {
                "gsm_id", "gsm_ids", "sample_id", "sample_ids", "subject_id",
                "subject_ids", "patient_id", "patient_ids", "pair_id", "pair_ids",
            }:
                raise ValidationError("GEO count consistency contains sample-level identifiers")
            _check_no_identifiers(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _check_no_identifiers(item)


def validate_geo_count_consistency_report(report: object) -> dict[str, Any]:
    if type(report) is not dict:
        raise ValidationError("GEO count consistency report must be an object")
    required = {
        "schema", "status", "comparison", "studies", "features", "summary", "analysis",
        "limitations", "content_address",
    }
    if frozenset(report) != frozenset(required):
        raise ValidationError("GEO count consistency report has an invalid top-level shape")
    if report["schema"] != "glio-noncode.geo-count-consistency.v1" or report["status"] != "completed":
        raise ValidationError("only completed GEO count consistency reports can be saved")
    address = report["content_address"]
    if type(address) is not str or _CONTENT_ADDRESS_RE.fullmatch(address) is None:
        raise ValidationError("GEO count consistency content address is invalid")
    body = {key: value for key, value in report.items() if key != "content_address"}
    if address != content_hash(body, prefix="geo-count-consistency"):
        raise ValidationError("GEO count consistency content address does not match contents")
    _check_no_identifiers(report)

    comparison = report["comparison"]
    if type(comparison) is not dict:
        raise ValidationError("GEO count consistency comparison must be an object")
    for key in (
        "feature_identity", "normalization", "normalization_method", "expression_scale",
        "fdr_method", "fdr_threshold", "case_filters", "reference_filters",
        "pair_key_column", "design", "group_orientation", "effect_direction_basis",
        "rank_biserial_effect_direction_basis",
    ):
        if key not in comparison:
            raise ValidationError(f"GEO count consistency comparison is missing {key}")
    if comparison["feature_identity"] != "exact_case_sensitive_source_feature_id":
        raise ValidationError("GEO count consistency feature identity policy is unsupported")
    if comparison["fdr_method"] not in {"bh", "by"}:
        raise ValidationError("GEO count consistency FDR method is unsupported")
    threshold = _finite(comparison["fdr_threshold"], "FDR threshold")
    if not 0.0 < threshold <= 1.0:
        raise ValidationError("GEO count consistency FDR threshold is outside (0, 1]")
    if type(comparison["case_filters"]) is not list or type(comparison["reference_filters"]) is not list:
        raise ValidationError("GEO count consistency filters must be lists")

    studies = report["studies"]
    if type(studies) is not list or not 2 <= len(studies) <= 8:
        raise ValidationError("GEO count consistency requires between 2 and 8 studies")
    accessions: list[str] = []
    for study in studies:
        if type(study) is not dict:
            raise ValidationError("GEO count consistency study rows must be objects")
        for key in (
            "accession", "count_matrix_source_sha256", "metadata_source_sha256",
            "report_content_address", "case_filters", "reference_filters", "pair_key_column",
            "matched_pair_count", "case_sample_count_selected", "reference_sample_count_selected",
            "normalization", "normalization_method", "expression_scale", "fdr_method",
            "fdr_threshold", "tested_feature_count", "reported_feature_count",
            "fdr_significant_feature_count", "sign_test_fdr_significant_feature_count",
        ):
            if key not in study:
                raise ValidationError(f"GEO count consistency study is missing {key}")
        accessions.append(_text(study["accession"], "study accession"))
        for key in ("count_matrix_source_sha256", "metadata_source_sha256"):
            if _ADDRESS_RE.fullmatch(str(study[key])) is None:
                raise ValidationError(f"GEO count consistency {key} is invalid")
        if _REPORT_ADDRESS_RE.fullmatch(str(study["report_content_address"])) is None:
            raise ValidationError("GEO count consistency report address is invalid")
        for key in (
            "matched_pair_count", "case_sample_count_selected", "reference_sample_count_selected",
            "tested_feature_count", "reported_feature_count", "fdr_significant_feature_count",
            "sign_test_fdr_significant_feature_count",
        ):
            _count(study[key], f"study {key}")
    if len(set(accessions)) != len(accessions):
        raise ValidationError("GEO count consistency studies must use distinct accessions")

    features = report["features"]
    if type(features) is not list or not 1 <= len(features) <= 500:
        raise ValidationError("GEO count consistency features must contain between 1 and 500 rows")
    feature_ids: set[str] = set()
    direction_counts = {key: 0 for key in _DIRECTION_STATES}
    fdr_counts = {key: 0 for key in _FDR_DIRECTION_STATES}
    sign_counts = {key: 0 for key in _SIGN_DIRECTION_STATES}
    for feature in features:
        if type(feature) is not dict or set(feature) != {"feature_id", "studies", "summary"}:
            raise ValidationError("GEO count consistency feature row has an invalid shape")
        feature_id = _text(feature["feature_id"], "feature identifier")
        if feature_id in feature_ids:
            raise ValidationError("GEO count consistency repeats a feature identifier")
        feature_ids.add(feature_id)
        summary = feature["summary"]
        if type(summary) is not dict:
            raise ValidationError("GEO count consistency feature summary must be an object")
        for key, choices in (
            ("direction_consistency", _DIRECTION_STATES),
            ("fdr_significant_direction_consistency", _FDR_DIRECTION_STATES),
            ("sign_test_fdr_significant_direction_consistency", _SIGN_DIRECTION_STATES),
        ):
            if summary.get(key) not in choices:
                raise ValidationError(f"GEO count consistency {key} is unsupported")
        direction_counts[summary["direction_consistency"]] += 1
        fdr_counts[summary["fdr_significant_direction_consistency"]] += 1
        sign_counts[summary["sign_test_fdr_significant_direction_consistency"]] += 1
        observations = feature["studies"]
        if type(observations) is not list or len(observations) != len(studies):
            raise ValidationError("GEO count consistency feature study rows do not match studies")

    summary = report["summary"]
    if type(summary) is not dict:
        raise ValidationError("GEO count consistency summary must be an object")
    expected = {
        "study_count": len(studies), "feature_count": len(features),
        "concordant_feature_count": direction_counts["concordant_among_tested"],
        "discordant_feature_count": direction_counts["discordant_among_tested"],
        "insufficient_feature_count": direction_counts["insufficient_tested_reports"],
        "fdr_significant_concordant_feature_count": fdr_counts["concordant_among_fdr_significant"],
        "fdr_significant_discordant_feature_count": fdr_counts["discordant_among_fdr_significant"],
        "fdr_significant_insufficient_feature_count": fdr_counts["insufficient_fdr_significant_reports"],
        "sign_test_fdr_significant_concordant_feature_count": sign_counts[
            "concordant_among_sign_test_fdr_significant"
        ],
        "sign_test_fdr_significant_discordant_feature_count": sign_counts[
            "discordant_among_sign_test_fdr_significant"
        ],
        "sign_test_fdr_significant_insufficient_feature_count": sign_counts[
            "insufficient_sign_test_fdr_significant_reports"
        ],
    }
    for key, value in expected.items():
        if _count(summary.get(key), f"summary {key}") != value:
            raise ValidationError(f"GEO count consistency summary {key} does not match rows")
    if type(report["limitations"]) is not list or any(
        type(item) is not str or not item.strip() for item in report["limitations"]
    ):
        raise ValidationError("GEO count consistency limitations must be non-empty text")
    return report


def summarize_geo_count_consistency_report(report: Mapping[str, Any]) -> dict[str, Any]:
    comparison = report["comparison"]
    summary = report["summary"]
    studies = report["studies"]
    return {
        "content_address": report["content_address"],
        "study_count": summary["study_count"],
        "feature_count": summary["feature_count"],
        "accessions": [study["accession"] for study in studies],
        "pair_key_column": comparison["pair_key_column"],
        "normalization_method": comparison["normalization_method"],
        "expression_scale": comparison["expression_scale"],
        "fdr_method": comparison["fdr_method"],
        "fdr_threshold": comparison["fdr_threshold"],
        **{
            key: summary[key]
            for key in (
                "concordant_feature_count", "discordant_feature_count", "insufficient_feature_count",
                "fdr_significant_concordant_feature_count",
                "fdr_significant_discordant_feature_count",
                "fdr_significant_insufficient_feature_count",
                "sign_test_fdr_significant_concordant_feature_count",
                "sign_test_fdr_significant_discordant_feature_count",
                "sign_test_fdr_significant_insufficient_feature_count",
            )
        },
    }


class GeoCountConsistencyStore:
    """Immutable paired-count consistency reports and bounded review pages."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = ObjectStore(self.root)
        self.records = self.root / "geo-count-consistency"
        self.locks = self.root / ".locks" / "geo-count-consistency"
        try:
            _validate_storage_parent(self.records, "GEO count consistency store")
            if self.records.is_symlink():
                raise StoreError("GEO count consistency store must be regular")
            self.records.mkdir(parents=True, exist_ok=True)
            if self.records.is_symlink() or not self.records.is_dir():
                raise StoreError("GEO count consistency store must be regular")
            _validate_storage_parent(self.locks, "GEO count consistency lock directory")
            if self.locks.is_symlink():
                raise StoreError("GEO count consistency lock directory must be regular")
            self.locks.mkdir(parents=True, exist_ok=True)
            if self.locks.is_symlink() or not self.locks.is_dir():
                raise StoreError("GEO count consistency lock directory must be regular")
        except StoreError:
            raise
        except OSError as error:
            raise StoreError("GEO count consistency store could not be initialized") from error
        self._lock = _run_lock(self.records)

    @staticmethod
    def _comparison_id(body: Mapping[str, Any]) -> str:
        return f"geo-count-consistency-{content_hash(body).split(':', 1)[1]}"

    def _record_path(self, comparison_id: str) -> Path:
        if type(comparison_id) is not str or _COMPARISON_ID_RE.fullmatch(comparison_id) is None:
            raise ValidationError("GEO count consistency comparison identifier is invalid")
        return self.records / f"{comparison_id}.json"

    def _decode_record(self, path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise StoreError("GEO count consistency catalog contains an unsafe record")
        try:
            raw = _strict_json_loads(read_bytes(path, field="GEO count consistency catalog record", max_bytes=MAX_COUNT_CONSISTENCY_RECORD_BYTES))
        except (OSError, UnicodeError, ValueError, ValidationError) as error:
            raise StoreError("GEO count consistency catalog record could not be verified") from error
        if type(raw) is not dict or frozenset(raw) != frozenset({"schema", "comparison_id", "report_address", "summary"}):
            raise StoreError("GEO count consistency catalog record has an invalid shape")
        if raw["schema"] != GEO_COUNT_CONSISTENCY_RECORD_SCHEMA:
            raise StoreError("GEO count consistency catalog schema is unsupported")
        comparison_id = raw["comparison_id"]
        if type(comparison_id) is not str or path.stem != comparison_id or _COMPARISON_ID_RE.fullmatch(comparison_id) is None:
            raise StoreError("GEO count consistency identifier is invalid")
        if _ADDRESS_RE.fullmatch(str(raw["report_address"])) is None:
            raise StoreError("GEO count consistency report address is invalid")
        if type(raw["summary"]) is not dict or frozenset(raw["summary"]) != _SUMMARY_FIELDS:
            raise StoreError("GEO count consistency catalog summary has an invalid shape")
        body = {key: value for key, value in raw.items() if key != "comparison_id"}
        if self._comparison_id(body) != comparison_id:
            raise StoreError("GEO count consistency catalog record address does not verify")
        return raw

    def save(self, report: object) -> dict[str, Any]:
        validated = validate_geo_count_consistency_report(report)
        if len(canonical_json(validated).encode("utf-8")) > MAX_COUNT_CONSISTENCY_REPORT_BYTES:
            raise StoreError("GEO count consistency report exceeds the storage byte limit")
        report_address = self.objects.put(validated)
        body = {
            "schema": GEO_COUNT_CONSISTENCY_RECORD_SCHEMA,
            "report_address": report_address,
            "summary": summarize_geo_count_consistency_report(validated),
        }
        comparison_id = self._comparison_id(body)
        record = body | {"comparison_id": comparison_id}
        path = self._record_path(comparison_id)
        try:
            with self._lock, _filesystem_lock(self.locks / f"{comparison_id}.lock"):
                if path.is_symlink():
                    raise StoreError("GEO count consistency catalog record path is unsafe")
                if path.exists():
                    if canonical_json(self._decode_record(path)) != canonical_json(record):
                        raise StoreError("GEO count consistency record differs at immutable identifier")
                else:
                    atomic_write_text(path, canonical_json(record), field="GEO count consistency catalog record")
        except (OSError, ValidationError) as error:
            raise StoreError("GEO count consistency record could not be saved") from error
        return record

    def save_from_analysis_ids(self, analysis_ids: Sequence[str], *, feature_ids: Sequence[str]) -> dict[str, Any]:
        from .geo_analysis_store import GeoAnalysisStore

        if not isinstance(analysis_ids, Sequence) or isinstance(analysis_ids, (str, bytes, bytearray)):
            raise ValidationError("GEO count consistency analysis IDs must be a sequence")
        source = GeoAnalysisStore(self.root)
        reports = tuple(source.get_report(analysis_id)["report"] for analysis_id in analysis_ids)
        return self.save(build_geo_count_consistency_report(reports, feature_ids=feature_ids))

    def list_reports(self, *, offset: int = 0, limit: int = 20) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= MAX_COUNT_CONSISTENCY_OFFSET:
            raise ValidationError("GEO count consistency offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_COUNT_CONSISTENCY_PAGE_SIZE:
            raise ValidationError("GEO count consistency limit is outside the supported range")
        paths = sorted(self.records.glob("geo-count-consistency-*.json"), key=lambda item: item.name)
        if len(paths) > MAX_COUNT_CONSISTENCY_RECORDS:
            raise StoreError("GEO count consistency catalog exceeds its record limit")
        records = [self._decode_record(path) for path in paths]
        rows = [{"comparison_id": item["comparison_id"], **item["summary"]} for item in records]
        page = rows[offset : offset + limit]
        return {"schema": GEO_COUNT_CONSISTENCY_CATALOG_SCHEMA, "offset": offset, "limit": limit, "total_count": len(rows), "has_more": offset + len(page) < len(rows), "rows": page}

    def get_report(self, comparison_id: str) -> dict[str, Any]:
        path = self._record_path(comparison_id)
        if not path.exists():
            raise KeyError(comparison_id)
        record = self._decode_record(path)
        report = self.objects.get(record["report_address"])
        validated = validate_geo_count_consistency_report(report)
        if summarize_geo_count_consistency_report(validated) != record["summary"]:
            raise StoreError("GEO count consistency catalog summary does not match its report")
        return {"schema": GEO_COUNT_CONSISTENCY_RECORD_SCHEMA, "comparison_id": comparison_id, "report_address": record["report_address"], "summary": record["summary"], "report": validated}

    @staticmethod
    def _filter_features(features: list[Mapping[str, Any]], *, feature_contains: str | None, direction_consistency: str | None, fdr_direction_consistency: str | None, sign_test_direction_consistency: str | None) -> tuple[list[Mapping[str, Any]], dict[str, Any]]:
        feature_contains = _query_text(feature_contains, "feature query")
        if direction_consistency is not None and direction_consistency not in _DIRECTION_STATES:
            raise ValidationError("GEO count consistency direction state is unsupported")
        if fdr_direction_consistency is not None and fdr_direction_consistency not in _FDR_DIRECTION_STATES:
            raise ValidationError("GEO count consistency FDR direction state is unsupported")
        if sign_test_direction_consistency is not None and sign_test_direction_consistency not in _SIGN_DIRECTION_STATES:
            raise ValidationError("GEO count consistency sign-test direction state is unsupported")
        rows = [
            feature for feature in features
            if (feature_contains is None or feature_contains in feature["feature_id"].casefold())
            and (direction_consistency is None or feature["summary"]["direction_consistency"] == direction_consistency)
            and (fdr_direction_consistency is None or feature["summary"]["fdr_significant_direction_consistency"] == fdr_direction_consistency)
            and (sign_test_direction_consistency is None or feature["summary"]["sign_test_fdr_significant_direction_consistency"] == sign_test_direction_consistency)
        ]
        return rows, {"feature_contains": feature_contains, "direction_consistency": direction_consistency, "fdr_direction_consistency": fdr_direction_consistency, "sign_test_direction_consistency": sign_test_direction_consistency}

    def page_features(self, comparison_id: str, *, offset: int = 0, limit: int = 25, feature_contains: str | None = None, direction_consistency: str | None = None, fdr_direction_consistency: str | None = None, sign_test_direction_consistency: str | None = None) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= MAX_COUNT_CONSISTENCY_OFFSET:
            raise ValidationError("GEO count consistency feature offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_COUNT_CONSISTENCY_PAGE_SIZE:
            raise ValidationError("GEO count consistency feature limit is outside the supported range")
        saved = self.get_report(comparison_id)
        report = saved["report"]
        features, filters = self._filter_features(report["features"], feature_contains=feature_contains, direction_consistency=direction_consistency, fdr_direction_consistency=fdr_direction_consistency, sign_test_direction_consistency=sign_test_direction_consistency)
        page = features[offset : offset + limit]
        return {"schema": GEO_COUNT_CONSISTENCY_PAGE_SCHEMA, "comparison_id": comparison_id, "report_address": saved["report_address"], "summary": saved["summary"], "comparison": report["comparison"], "studies": report["studies"], "features": page, "offset": offset, "limit": limit, "total_features": len(features), "unfiltered_feature_count": len(report["features"]), "filters": filters, "analysis": report["analysis"], "limitations": report["limitations"], "has_more": offset + len(page) < len(features)}

    def features_csv(self, comparison_id: str, *, feature_contains: str | None = None, direction_consistency: str | None = None, fdr_direction_consistency: str | None = None, sign_test_direction_consistency: str | None = None) -> str:
        saved = self.get_report(comparison_id)
        features, _filters = self._filter_features(saved["report"]["features"], feature_contains=feature_contains, direction_consistency=direction_consistency, fdr_direction_consistency=fdr_direction_consistency, sign_test_direction_consistency=sign_test_direction_consistency)
        fields = ("feature_id", "direction_consistency", "fdr_significant_direction_consistency", "sign_test_fdr_significant_direction_consistency", "tested_count", "untestable_count", "not_reported_count", "distinct_directions", "fdr_significant_count", "sign_test_fdr_significant_count")
        output = io.StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(fields)
        for feature in features:
            summary = feature["summary"]
            writer.writerow((feature["feature_id"], summary["direction_consistency"], summary["fdr_significant_direction_consistency"], summary["sign_test_fdr_significant_direction_consistency"], summary["tested_count"], summary["untestable_count"], summary["not_reported_count"], "|".join(summary["distinct_directions"]), summary["fdr_significant_count"], summary["sign_test_fdr_significant_count"]))
        rendered = output.getvalue()
        if len(rendered.encode("utf-8")) > MAX_COUNT_CONSISTENCY_EXPORT_BYTES:
            raise StoreError("GEO count consistency CSV exceeds the export byte limit")
        return rendered


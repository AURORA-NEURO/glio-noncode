"""Immutable persistence for GEO preparation and design preflight reports.

The preflight catalog keeps QC, sample-metadata, and contrast-design results
alongside final GEO analyses without turning them into statistical findings.
Catalog rows are bounded projections; the full content-addressed report is
available only through its explicit report export.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ._safe_persistence import atomic_write_text, read_bytes
from .errors import StoreError, ValidationError
from .serialization import _strict_json_loads, canonical_json, content_hash
from .storage import ObjectStore, _filesystem_lock, _run_lock, _validate_storage_parent

GEO_PREFLIGHT_RECORD_SCHEMA = "glio-noncode.geo-preflight-record.v1"
GEO_PREFLIGHT_CATALOG_SCHEMA = "glio-noncode.geo-preflight-catalog.v1"
GEO_PREFLIGHT_PAGE_SCHEMA = "glio-noncode.geo-preflight-page.v1"
MAX_GEO_PREFLIGHT_REPORT_BYTES = 64 * 1024 * 1024
MAX_GEO_PREFLIGHT_RECORD_BYTES = 256 * 1024
MAX_GEO_PREFLIGHT_RECORDS = 10_000
MAX_GEO_PREFLIGHT_PAGE_SIZE = 100
MAX_GEO_PREFLIGHT_OFFSET = 100_000

_PREFLIGHT_ID_RE = re.compile(r"geo-preflight-[0-9a-f]{64}\Z")
_ADDRESS_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_ACCESSION_RE = re.compile(r"GSE[0-9]{1,12}\Z")
_SOURCE_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")

_REPORT_SPECS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "glio-noncode.geo-expression-quality.v1": (
        "expression_quality",
        "geo-expression-quality",
        (
            "measurement_count",
            "observed_measurement_count",
            "missing_measurement_count",
            "overall_missing_fraction",
            "complete_feature_count",
            "feature_with_missing_measurement_count",
            "exact_duplicate_profile_group_count",
            "samples_in_exact_duplicate_profile_groups",
        ),
    ),
    "glio-noncode.geo-sample-metadata.v1": (
        "sample_metadata",
        "geo-sample-metadata",
        (
            "samples_with_characteristics_count",
            "samples_without_characteristics_count",
            "characteristic_field_count",
            "characteristic_annotation_entry_count",
            "distinct_characteristic_entry_count",
            "duplicate_characteristic_entry_count",
            "distinct_field_value_category_count",
            "reported_category_count",
            "omitted_category_count",
            "omitted_category_sample_memberships",
        ),
    ),
    "glio-noncode.geo-contrast-design.v1": (
        "contrast_design",
        "geo-contrast-design",
        (
            "selected_case_count",
            "selected_reference_count",
            "overlap_count",
            "unassigned_count",
            "missing_covariate_exclusion_count",
            "complete_case_count",
            "design_estimable",
        ),
    ),
    "glio-noncode.geo-count-metadata.v1": (
        "count_metadata",
        "geo-count-metadata",
        (
            "column_count",
            "distinct_non_key_category_count_lower_bound",
            "fields_with_suppressed_values_count",
        ),
    ),
    "glio-noncode.geo-count-contrast-design.v1": (
        "count_contrast_design",
        "geo-count-contrast-design",
        (
            "case_sample_count",
            "reference_sample_count",
            "overlap_sample_count",
            "matched_pair_count",
            "feature_row_count",
            "uniquely_labeled_feature_count",
            "design_estimable",
        ),
    ),
}
_KIND_TO_SCHEMA = {spec[0]: schema for schema, spec in _REPORT_SPECS.items()}
_LEGACY_METRIC_FIELDS = {
    "glio-noncode.geo-count-contrast-design.v1": (
        "selected_case_count",
        "selected_reference_count",
        "overlap_count",
        "unassigned_count",
        "complete_pair_count",
        "design_estimable",
    )
}
_LEGACY_SOURCE_DIMENSION_SCHEMAS = frozenset(
    {
        "glio-noncode.geo-count-metadata.v1",
        "glio-noncode.geo-count-contrast-design.v1",
    }
)
_SUMMARY_FIELDS = frozenset(
    {
        "accession",
        "retrieval",
        "source_sha256",
        "sample_count",
        "feature_count",
        "design_state",
        "metrics",
    }
)


def _bounded_scalar(value: object) -> int | float | bool | str | None:
    if value is None or type(value) in (int, bool, str):
        if type(value) is str and len(value) > 256:
            return None
        return value
    if type(value) is float and math.isfinite(value):
        return value
    return None


def _nonnegative_count(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _report_counts(
    report_schema: str,
    report: Mapping[str, Any],
    source: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> tuple[int | None, int | None]:
    """Project source dimensions while respecting each preflight schema's shape."""

    sample_count = _nonnegative_count(source.get("sample_count"))
    feature_count = _nonnegative_count(source.get("feature_count"))
    if report_schema == "glio-noncode.geo-count-metadata.v1" and sample_count is None:
        sample_count = _nonnegative_count(summary.get("sample_count"))
    elif report_schema == "glio-noncode.geo-count-contrast-design.v1":
        matrix = report.get("matrix")
        if isinstance(matrix, Mapping):
            sample_count = _nonnegative_count(matrix.get("sample_count"))
            feature_count = _nonnegative_count(matrix.get("feature_row_count"))
    return sample_count, feature_count


def _spec(report_schema: object) -> tuple[str, str, tuple[str, ...]]:
    if type(report_schema) is not str or report_schema not in _REPORT_SPECS:
        raise ValidationError("unsupported GEO preflight report schema")
    return _REPORT_SPECS[report_schema]


def validate_geo_preflight_report(report: object) -> dict[str, Any]:
    """Validate a completed, content-addressed preparation report."""

    if type(report) is not dict:
        raise ValidationError("GEO preflight report must be an object")
    report_schema = report.get("schema")
    _kind, prefix, _metric_fields = _spec(report_schema)
    if report.get("status") != "completed":
        raise ValidationError("only completed GEO preflight reports can be saved")
    address = report.get("content_address")
    if type(address) is not str:
        raise ValidationError("GEO preflight report is missing its content address")
    body = {key: value for key, value in report.items() if key != "content_address"}
    if address != content_hash(body, prefix=prefix):
        raise ValidationError("GEO preflight report content address does not match contents")
    source = report.get("source")
    if not isinstance(source, Mapping):
        raise ValidationError("GEO preflight report source is invalid")
    accession = source.get("accession")
    if type(accession) is not str or _ACCESSION_RE.fullmatch(accession) is None:
        raise ValidationError("GEO preflight source accession is invalid")
    digest = source.get("source_sha256")
    if type(digest) is not str or _SOURCE_DIGEST_RE.fullmatch(digest) is None:
        raise ValidationError("GEO preflight source digest is invalid")
    if not isinstance(report.get("summary"), Mapping):
        raise ValidationError("GEO preflight report summary is invalid")
    return report


def summarize_geo_preflight_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Create a fixed-shape catalog row with aggregate-only metrics."""

    report_schema = report["schema"]
    kind, _prefix, metric_fields = _spec(report_schema)
    source = report["source"]
    summary = report["summary"]
    design = report.get("design")
    design_state = design.get("state") if isinstance(design, Mapping) else None
    metrics = {key: _bounded_scalar(summary.get(key)) for key in metric_fields}
    sample_count, feature_count = _report_counts(report_schema, report, source, summary)
    return {
        "accession": source["accession"],
        "retrieval": source.get("retrieval"),
        "source_sha256": source["source_sha256"],
        "sample_count": sample_count,
        "feature_count": feature_count,
        "design_state": design_state if type(design_state) is str else None,
        "metrics": metrics,
        "kind": kind,
    }


def _validate_summary_projection(
    report_schema: str,
    summary: Mapping[str, Any],
) -> None:
    """Validate the fixed-shape values stored in one catalog row."""

    if frozenset(summary) != _SUMMARY_FIELDS:
        raise StoreError("GEO preflight catalog summary has an invalid shape")
    accession = summary.get("accession")
    if type(accession) is not str or _ACCESSION_RE.fullmatch(accession) is None:
        raise StoreError("GEO preflight catalog accession is invalid")
    retrieval = summary.get("retrieval")
    if retrieval is not None and type(retrieval) is not str:
        raise StoreError("GEO preflight catalog retrieval is invalid")
    digest = summary.get("source_sha256")
    if type(digest) is not str or _SOURCE_DIGEST_RE.fullmatch(digest) is None:
        raise StoreError("GEO preflight catalog source digest is invalid")
    for key in ("sample_count", "feature_count"):
        value = summary.get(key)
        if value is not None and (type(value) is not int or value < 0):
            raise StoreError(f"GEO preflight catalog {key} is invalid")
    design_state = summary.get("design_state")
    if design_state is not None and type(design_state) is not str:
        raise StoreError("GEO preflight catalog design state is invalid")
    metrics = summary.get("metrics")
    if type(metrics) is not dict:
        raise StoreError("GEO preflight catalog metrics are invalid")
    _kind, _prefix, metric_fields = _spec(report_schema)
    accepted_metric_fields = {frozenset(metric_fields)}
    if report_schema in _LEGACY_METRIC_FIELDS:
        accepted_metric_fields.add(frozenset(_LEGACY_METRIC_FIELDS[report_schema]))
    if frozenset(metrics) not in accepted_metric_fields:
        raise StoreError("GEO preflight catalog metrics have an invalid shape")
    for value in metrics.values():
        if _bounded_scalar(value) != value:
            raise StoreError("GEO preflight catalog metric value is invalid")


class GeoPreflightStore:
    """Immutable content-addressed GEO preflight records and catalog pages."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.objects = ObjectStore(self.root)
        self.records = self.root / "geo-preflights"
        self.locks = self.root / ".locks" / "geo-preflights"
        try:
            _validate_storage_parent(self.records, "GEO preflight store")
            if self.records.is_symlink():
                raise StoreError("GEO preflight store must be a regular directory")
            self.records.mkdir(parents=True, exist_ok=True)
            if self.records.is_symlink() or not self.records.is_dir():
                raise StoreError("GEO preflight store must be a regular directory")
            _validate_storage_parent(self.locks, "GEO preflight lock directory")
            if self.locks.is_symlink():
                raise StoreError("GEO preflight lock directory must be regular")
            self.locks.mkdir(parents=True, exist_ok=True)
            if self.locks.is_symlink() or not self.locks.is_dir():
                raise StoreError("GEO preflight lock directory must be regular")
        except StoreError:
            raise
        except OSError as error:
            raise StoreError("GEO preflight store could not be initialized") from error
        self._lock = _run_lock(self.records)

    @staticmethod
    def _preflight_id(body: Mapping[str, Any]) -> str:
        return f"geo-preflight-{content_hash(body).split(':', 1)[1]}"

    def _record_path(self, preflight_id: str) -> Path:
        if type(preflight_id) is not str or _PREFLIGHT_ID_RE.fullmatch(preflight_id) is None:
            raise ValidationError("GEO preflight identifier is invalid")
        return self.records / f"{preflight_id}.json"

    def _decode_record(self, path: Path) -> dict[str, Any]:
        if path.is_symlink():
            raise StoreError("GEO preflight catalog contains an unsafe record")
        try:
            raw = _strict_json_loads(
                read_bytes(
                    path,
                    field="GEO preflight catalog record",
                    max_bytes=MAX_GEO_PREFLIGHT_RECORD_BYTES,
                )
            )
        except (OSError, UnicodeError, ValueError, ValidationError) as error:
            raise StoreError("GEO preflight catalog record could not be verified") from error
        expected = {"schema", "preflight_id", "report_schema", "kind", "report_address", "summary"}
        if type(raw) is not dict or frozenset(raw) != expected:
            raise StoreError("GEO preflight catalog record has an invalid shape")
        if raw["schema"] != GEO_PREFLIGHT_RECORD_SCHEMA:
            raise StoreError("GEO preflight catalog record schema is unsupported")
        if type(raw["preflight_id"]) is not str or path.stem != raw["preflight_id"]:
            raise StoreError("GEO preflight identifier does not match filename")
        if _PREFLIGHT_ID_RE.fullmatch(raw["preflight_id"]) is None:
            raise StoreError("GEO preflight identifier is invalid")
        kind, _prefix, _metrics = _spec(raw["report_schema"])
        if raw["kind"] != kind or _ADDRESS_RE.fullmatch(str(raw["report_address"])) is None:
            raise StoreError("GEO preflight catalog record references are invalid")
        if type(raw["summary"]) is not dict:
            raise StoreError("GEO preflight catalog summary has an invalid shape")
        _validate_summary_projection(raw["report_schema"], raw["summary"])
        body = {key: value for key, value in raw.items() if key != "preflight_id"}
        if self._preflight_id(body) != raw["preflight_id"]:
            raise StoreError("GEO preflight catalog record address does not verify")
        return raw

    def save(self, report: object) -> dict[str, Any]:
        """Persist one completed preparation report."""

        validated = validate_geo_preflight_report(report)
        if len(canonical_json(validated).encode("utf-8")) > MAX_GEO_PREFLIGHT_REPORT_BYTES:
            raise StoreError("GEO preflight report exceeds the storage byte limit")
        report_address = self.objects.put(validated)
        summary = summarize_geo_preflight_report(validated)
        kind = summary.pop("kind")
        body = {
            "schema": GEO_PREFLIGHT_RECORD_SCHEMA,
            "report_schema": validated["schema"],
            "kind": kind,
            "report_address": report_address,
            "summary": summary,
        }
        preflight_id = self._preflight_id(body)
        record = body | {"preflight_id": preflight_id}
        path = self._record_path(preflight_id)
        try:
            with self._lock, _filesystem_lock(self.locks / f"{preflight_id}.lock"):
                if path.is_symlink():
                    raise StoreError("GEO preflight catalog record path is unsafe")
                if path.exists():
                    if canonical_json(self._decode_record(path)) != canonical_json(record):
                        raise StoreError("GEO preflight record differs at immutable identifier")
                else:
                    atomic_write_text(
                        path,
                        canonical_json(record),
                        field="GEO preflight catalog record",
                    )
        except (OSError, ValidationError) as error:
            raise StoreError("GEO preflight record could not be saved") from error
        return record

    def list_reports(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        kind: str | None = None,
        accession: str | None = None,
    ) -> dict[str, Any]:
        if type(offset) is not int or not 0 <= offset <= MAX_GEO_PREFLIGHT_OFFSET:
            raise ValidationError("GEO preflight offset is outside the supported range")
        if type(limit) is not int or not 1 <= limit <= MAX_GEO_PREFLIGHT_PAGE_SIZE:
            raise ValidationError("GEO preflight limit is outside the supported range")
        if kind is not None and kind not in _KIND_TO_SCHEMA:
            raise ValidationError("GEO preflight kind is unsupported")
        if accession is not None:
            if type(accession) is not str or _ACCESSION_RE.fullmatch(accession) is None:
                raise ValidationError("GEO preflight accession is invalid")
        paths = sorted(self.records.glob("geo-preflight-*.json"), key=lambda item: item.name)
        if len(paths) > MAX_GEO_PREFLIGHT_RECORDS:
            raise StoreError("GEO preflight catalog exceeds its record limit")
        records = [self._decode_record(path) for path in paths]
        filtered = [
            item
            for item in records
            if (kind is None or item["kind"] == kind)
            and (accession is None or item["summary"]["accession"] == accession)
        ]
        rows = [
            {
                "preflight_id": item["preflight_id"],
                "report_schema": item["report_schema"],
                "kind": item["kind"],
                "report_address": item["report_address"],
                **item["summary"],
            }
            for item in filtered
        ]
        page = rows[offset : offset + limit]
        return {
            "schema": GEO_PREFLIGHT_CATALOG_SCHEMA,
            "offset": offset,
            "limit": limit,
            "total_count": len(rows),
            "has_more": offset + len(page) < len(rows),
            "rows": page,
        }

    def get_report(self, preflight_id: str) -> dict[str, Any]:
        path = self._record_path(preflight_id)
        if not path.exists():
            raise KeyError(preflight_id)
        record = self._decode_record(path)
        report = self.objects.get(record["report_address"])
        validated = validate_geo_preflight_report(report)
        expected_summary = summarize_geo_preflight_report(validated)
        stored_summary = {**record["summary"], "kind": record["kind"]}
        legacy_fields = _LEGACY_METRIC_FIELDS.get(record["report_schema"])
        if record["report_schema"] in _LEGACY_SOURCE_DIMENSION_SCHEMAS:
            expected_summary = dict(expected_summary)
            for field in ("sample_count", "feature_count"):
                if record["summary"].get(field) is None:
                    expected_summary[field] = None
        if legacy_fields and frozenset(record["summary"]["metrics"]) == frozenset(legacy_fields):
            expected_summary = dict(expected_summary)
            expected_summary["metrics"] = {
                key: _bounded_scalar(validated["summary"].get(key))
                for key in legacy_fields
            }
        if expected_summary != stored_summary:
            raise StoreError("GEO preflight catalog summary does not match its report")
        return {
            "schema": GEO_PREFLIGHT_RECORD_SCHEMA,
            "preflight_id": preflight_id,
            "report_schema": record["report_schema"],
            "kind": record["kind"],
            "report_address": record["report_address"],
            "summary": record["summary"],
            "report": validated,
        }


__all__ = [
    "GEO_PREFLIGHT_CATALOG_SCHEMA",
    "GEO_PREFLIGHT_PAGE_SCHEMA",
    "GEO_PREFLIGHT_RECORD_SCHEMA",
    "GeoPreflightStore",
    "summarize_geo_preflight_report",
    "validate_geo_preflight_report",
]

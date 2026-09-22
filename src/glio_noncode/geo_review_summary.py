"""Aggregate health and integrity summary for the saved GEO workspace."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import StoreError, ValidationError
from .geo_analysis_store import GeoAnalysisStore
from .geo_count_consistency_store import GeoCountConsistencyStore
from .geo_count_sensitivity_store import GeoCountSensitivityStore
from .geo_expression_analysis_store import GeoExpressionAnalysisStore
from .geo_expression_consistency_store import GeoExpressionConsistencyStore
from .geo_preflight_store import GeoPreflightStore
from .serialization import content_hash

GEO_REVIEW_SUMMARY_SCHEMA = "glio-noncode.geo-review-summary.v1"
MAX_GEO_REVIEW_RECORDS = 10_000
CATALOG_PAGE_SIZE = 20
GEO_REVIEW_LEDGER_COLUMNS = (
    "catalog",
    "record_id",
    "accessions",
    "feature_count",
    "tested_feature_count",
    "reported_feature_count",
    "fdr_significant_feature_count",
    "verification",
    "state",
)
GEO_PREFLIGHT_LEDGER_COLUMNS = (
    "preflight_id",
    "kind",
    "report_schema",
    "accession",
    "retrieval",
    "source_sha256",
    "report_address",
    "sample_count",
    "feature_count",
    "design_state",
    "verification",
)


def _catalog_rows(store: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = store.list_reports(offset=offset, limit=CATALOG_PAGE_SIZE)
        page_rows = page["rows"]
        if not isinstance(page_rows, list):
            raise StoreError("GEO catalog returned an invalid row projection")
        rows.extend(page_rows)
        if len(rows) > MAX_GEO_REVIEW_RECORDS:
            raise StoreError("GEO workspace exceeds its review record limit")
        if not page["has_more"]:
            return rows
        offset += len(page_rows)
        if not page_rows:
            raise StoreError("GEO catalog pagination did not advance")


def _number(row: Mapping[str, Any], key: str) -> int:
    value = row.get(key, 0)
    return value if type(value) is int and value >= 0 else 0


def _accessions(rows: list[Mapping[str, Any]]) -> list[str]:
    values: set[str] = set()
    for row in rows:
        accession = row.get("accession")
        if type(accession) is str and accession.strip():
            values.add(accession)
        for value in row.get("accessions", []):
            if type(value) is str and value.strip():
                values.add(value)
    return sorted(values)


def _catalog_projection(
    *,
    name: str,
    store: Any,
    identifier_key: str,
    feature_key: str,
    tested_key: str | None,
    reported_key: str | None,
    fdr_key: str | None,
    verify_reports: bool,
    total_keys: Sequence[str] = (),
) -> tuple[dict[str, Any], int]:
    rows = _catalog_rows(store)
    verified = 0
    failures = 0
    for row in rows:
        identifier = row.get(identifier_key)
        if type(identifier) is not str or not identifier:
            failures += 1
            continue
        if not verify_reports:
            verified += 1
            continue
        try:
            store.get_report(identifier)
        except (KeyError, OSError, StoreError, ValidationError, ValueError):
            failures += 1
        else:
            verified += 1
    projection = {
        "name": name,
        "record_count": len(rows),
        "verified_record_count": verified,
        "feature_count_total": sum(_number(row, feature_key) for row in rows),
        "accession_count": len(_accessions(rows)),
        "accessions": _accessions(rows),
        "catalog_state": "verified" if failures == 0 else "review",
    }
    if tested_key is not None:
        projection["tested_feature_count_total"] = sum(
            _number(row, tested_key) for row in rows
        )
    if reported_key is not None:
        projection["reported_feature_count_total"] = sum(
            _number(row, reported_key) for row in rows
        )
    if fdr_key is not None:
        projection["fdr_significant_feature_count_total"] = sum(
            _number(row, fdr_key) for row in rows
        )
    for key in total_keys:
        projection[key] = sum(_number(row, key) for row in rows)
    return projection, failures


def _preflight_projection(
    root: str | Path,
    *,
    verify_reports: bool,
) -> tuple[dict[str, Any], int]:
    store = GeoPreflightStore(root)
    rows = _catalog_rows(store)
    verified = 0
    failures = 0
    kind_counts: dict[str, int] = {}
    design_state_counts: dict[str, int] = {}
    for row in rows:
        kind = row.get("kind")
        if type(kind) is str and kind:
            kind_counts[kind] = kind_counts.get(kind, 0) + 1
        design_state = row.get("design_state")
        if type(design_state) is str and design_state:
            design_state_counts[design_state] = design_state_counts.get(design_state, 0) + 1
        identifier = row.get("preflight_id")
        if not verify_reports:
            verified += 1
            continue
        if type(identifier) is not str or not identifier:
            failures += 1
            continue
        try:
            store.get_report(identifier)
        except (KeyError, OSError, StoreError, ValidationError, ValueError):
            failures += 1
        else:
            verified += 1
    return {
        "name": "preflights",
        "record_count": len(rows),
        "verified_record_count": verified,
        "feature_count_total": sum(_number(row, "feature_count") for row in rows),
        "sample_count_total": sum(_number(row, "sample_count") for row in rows),
        "accession_count": len(_accessions(rows)),
        "accessions": _accessions(rows),
        "kind_counts": dict(sorted(kind_counts.items())),
        "design_state_counts": dict(sorted(design_state_counts.items())),
        "catalog_state": "verified" if failures == 0 else "review",
    }, failures


def _catalog_ledger(
    *,
    name: str,
    store: Any,
    identifier_key: str,
    feature_key: str,
    tested_key: str | None,
    fdr_key: str | None,
    verify_reports: bool,
) -> tuple[list[dict[str, Any]], int]:
    """Return one bounded, public ledger row for every catalog record."""

    rows = _catalog_rows(store)
    ledger: list[dict[str, Any]] = []
    failures = 0
    for row in rows:
        identifier = row.get(identifier_key)
        accession_values = _accessions([row])
        verification = "not_requested"
        state = "review"
        if type(identifier) is not str or not identifier:
            failures += 1
            verification = "invalid"
        elif verify_reports:
            try:
                store.get_report(identifier)
            except (KeyError, OSError, StoreError, ValidationError, ValueError):
                failures += 1
                verification = "failed"
            else:
                verification = "verified"
                state = "verified"
        else:
            state = "cataloged"
        ledger.append(
            {
                "catalog": name,
                "record_id": identifier if type(identifier) is str else "",
                "accessions": ",".join(accession_values),
                "feature_count": _number(row, feature_key),
                "tested_feature_count": (
                    _number(row, tested_key) if tested_key is not None else 0
                ),
                "reported_feature_count": _number(row, "reported_feature_count"),
                "fdr_significant_feature_count": (
                    _number(row, fdr_key) if fdr_key is not None else 0
                ),
                "verification": verification,
                "state": state,
            }
        )
    return ledger, failures


def build_geo_review_ledger(
    root: str | Path,
    *,
    verify_reports: bool = True,
) -> list[dict[str, Any]]:
    """Build the row-level aggregate ledger used by CSV export."""

    if type(verify_reports) is not bool:
        raise ValidationError("GEO review report verification flag must be boolean")
    specifications = (
        {
            "name": "paired_count_analyses",
            "store": GeoAnalysisStore(root),
            "identifier_key": "analysis_id",
            "feature_key": "feature_row_count",
            "tested_key": "tested_feature_count",
            "fdr_key": "fdr_significant_feature_count",
        },
        {
            "name": "expression_analyses",
            "store": GeoExpressionAnalysisStore(root),
            "identifier_key": "analysis_id",
            "feature_key": "feature_count",
            "tested_key": "tested_feature_count",
            "fdr_key": "fdr_significant_feature_count",
        },
        {
            "name": "paired_count_comparisons",
            "store": GeoCountConsistencyStore(root),
            "identifier_key": "comparison_id",
            "feature_key": "feature_count",
            "tested_key": None,
            "fdr_key": None,
        },
        {
            "name": "paired_count_sensitivity_comparisons",
            "store": GeoCountSensitivityStore(root),
            "identifier_key": "comparison_id",
            "feature_key": "feature_count",
            "tested_key": None,
            "fdr_key": None,
        },
        {
            "name": "expression_comparisons",
            "store": GeoExpressionConsistencyStore(root),
            "identifier_key": "comparison_id",
            "feature_key": "feature_count",
            "tested_key": None,
            "fdr_key": None,
        },
        {
            "name": "preflights",
            "store": GeoPreflightStore(root),
            "identifier_key": "preflight_id",
            "feature_key": "feature_count",
            "tested_key": None,
            "fdr_key": None,
        },
    )
    ledger: list[dict[str, Any]] = []
    for specification in specifications:
        rows, _ = _catalog_ledger(
            name=specification["name"],
            store=specification["store"],
            identifier_key=specification["identifier_key"],
            feature_key=specification["feature_key"],
            tested_key=specification["tested_key"],
            fdr_key=specification["fdr_key"],
            verify_reports=verify_reports,
        )
        ledger.extend(rows)
    return ledger


def geo_review_ledger_csv(
    root: str | Path,
    *,
    verify_reports: bool = True,
) -> str:
    """Serialize the aggregate GEO ledger without private or raw data fields."""

    return render_geo_review_ledger_csv(
        build_geo_review_ledger(root, verify_reports=verify_reports)
    )


def render_geo_review_ledger_csv(ledger: list[Mapping[str, Any]]) -> str:
    """Render already-verified ledger rows without reopening stored reports."""

    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(GEO_REVIEW_LEDGER_COLUMNS),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(ledger)
    return output.getvalue()


def build_geo_preflight_ledger(
    root: str | Path,
    *,
    verify_reports: bool = True,
) -> list[dict[str, Any]]:
    """Build a kind-aware aggregate ledger for saved preparation reports."""

    if type(verify_reports) is not bool:
        raise ValidationError("GEO preflight ledger verification flag must be boolean")
    store = GeoPreflightStore(root)
    rows = _catalog_rows(store)
    ledger: list[dict[str, Any]] = []
    for row in rows:
        identifier = row.get("preflight_id")
        verification = "not_requested"
        if type(identifier) is not str or not identifier:
            verification = "invalid"
        elif verify_reports:
            try:
                store.get_report(identifier)
            except (KeyError, OSError, StoreError, ValidationError, ValueError):
                verification = "failed"
            else:
                verification = "verified"
        ledger.append(
            {
                "preflight_id": identifier if type(identifier) is str else "",
                "kind": row.get("kind") or "",
                "report_schema": row.get("report_schema") or "",
                "accession": row.get("accession") or "",
                "retrieval": row.get("retrieval") or "",
                "source_sha256": row.get("source_sha256") or "",
                "report_address": row.get("report_address") or "",
                "sample_count": row.get("sample_count"),
                "feature_count": row.get("feature_count"),
                "design_state": row.get("design_state") or "",
                "verification": verification,
            }
        )
    return ledger


def render_geo_preflight_ledger_csv(ledger: list[Mapping[str, Any]]) -> str:
    """Render the kind-aware aggregate preflight ledger as CSV."""

    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(GEO_PREFLIGHT_LEDGER_COLUMNS),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(ledger)
    return output.getvalue()


def geo_preflight_ledger_csv(
    root: str | Path,
    *,
    verify_reports: bool = True,
) -> str:
    """Build and serialize the aggregate preflight ledger."""

    return render_geo_preflight_ledger_csv(
        build_geo_preflight_ledger(root, verify_reports=verify_reports)
    )


def build_geo_review_summary(
    root: str | Path,
    *,
    verify_reports: bool = True,
) -> dict[str, Any]:
    """Build a deterministic, aggregate-only GEO workspace health summary."""

    if type(verify_reports) is not bool:
        raise ValidationError("GEO review report verification flag must be boolean")
    analysis, analysis_failures = _catalog_projection(
        name="paired_count_analyses",
        store=GeoAnalysisStore(root),
        identifier_key="analysis_id",
        feature_key="feature_row_count",
        tested_key="tested_feature_count",
        reported_key="reported_feature_count",
        fdr_key="fdr_significant_feature_count",
        verify_reports=verify_reports,
    )
    expression, expression_failures = _catalog_projection(
        name="expression_analyses",
        store=GeoExpressionAnalysisStore(root),
        identifier_key="analysis_id",
        feature_key="feature_count",
        tested_key="tested_feature_count",
        reported_key="reported_feature_count",
        fdr_key="fdr_significant_feature_count",
        verify_reports=verify_reports,
    )
    count_comparisons, count_comparison_failures = _catalog_projection(
        name="paired_count_comparisons",
        store=GeoCountConsistencyStore(root),
        identifier_key="comparison_id",
        feature_key="feature_count",
        tested_key=None,
        reported_key=None,
        fdr_key=None,
        total_keys=(
            "reported_feature_count_total",
            "ranked_feature_count_total",
            "additional_tracked_feature_count_total",
            "tracked_feature_id_count_total",
        ),
        verify_reports=verify_reports,
    )
    count_sensitivities, count_sensitivity_failures = _catalog_projection(
        name="paired_count_sensitivity_comparisons",
        store=GeoCountSensitivityStore(root),
        identifier_key="comparison_id",
        feature_key="feature_count",
        tested_key=None,
        reported_key=None,
        fdr_key=None,
        total_keys=(
            "reported_feature_count_total",
            "ranked_feature_count_total",
            "additional_tracked_feature_count_total",
            "tracked_feature_id_count_total",
        ),
        verify_reports=verify_reports,
    )
    expression_comparisons, expression_comparison_failures = _catalog_projection(
        name="expression_comparisons",
        store=GeoExpressionConsistencyStore(root),
        identifier_key="comparison_id",
        feature_key="feature_count",
        tested_key=None,
        reported_key=None,
        fdr_key=None,
        verify_reports=verify_reports,
    )
    preflights, preflight_failures = _preflight_projection(
        root,
        verify_reports=verify_reports,
    )
    failures = (
        analysis_failures
        + expression_failures
        + count_comparison_failures
        + count_sensitivity_failures
        + expression_comparison_failures
        + preflight_failures
    )
    body = {
        "schema": GEO_REVIEW_SUMMARY_SCHEMA,
        "status": "ready" if failures == 0 else "review",
        "verification_requested": verify_reports,
        "catalogs": {
            "paired_count_analyses": analysis,
            "expression_analyses": expression,
            "paired_count_comparisons": count_comparisons,
            "paired_count_sensitivity_comparisons": count_sensitivities,
            "expression_comparisons": expression_comparisons,
            "preflights": preflights,
        },
        "integrity": {
            "catalog_records": "validated",
            "report_objects": "verified" if verify_reports and failures == 0 else (
                "review" if verify_reports else "not_requested"
            ),
            "verification_failure_count": failures,
        },
        "limitations": [
            (
                "This is an archive-health projection, not a statistical reanalysis "
                "or scientific conclusion."
            ),
            (
                "Counts are sums of catalog summaries and are not deduplicated across "
                "studies or comparisons."
            ),
            (
                "Sample, subject, pair, and raw matrix identifiers are never included "
                "in this projection."
            ),
        ],
    }
    return body | {"content_address": content_hash(body, prefix="geo-review-summary")}


__all__ = [
    "GEO_PREFLIGHT_LEDGER_COLUMNS",
    "GEO_REVIEW_LEDGER_COLUMNS",
    "GEO_REVIEW_SUMMARY_SCHEMA",
    "build_geo_preflight_ledger",
    "build_geo_review_ledger",
    "build_geo_review_summary",
    "geo_preflight_ledger_csv",
    "geo_review_ledger_csv",
    "render_geo_preflight_ledger_csv",
    "render_geo_review_ledger_csv",
]

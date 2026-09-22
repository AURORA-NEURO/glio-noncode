"""Aggregate health and integrity summary for the saved GEO workspace."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import StoreError, ValidationError
from .geo_analysis_store import GeoAnalysisStore
from .geo_count_consistency_store import GeoCountConsistencyStore
from .geo_expression_analysis_store import GeoExpressionAnalysisStore
from .geo_expression_consistency_store import GeoExpressionConsistencyStore
from .serialization import content_hash

GEO_REVIEW_SUMMARY_SCHEMA = "glio-noncode.geo-review-summary.v1"
MAX_GEO_REVIEW_RECORDS = 10_000
CATALOG_PAGE_SIZE = 20


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
    fdr_key: str | None,
    verify_reports: bool,
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
    if fdr_key is not None:
        projection["fdr_significant_feature_count_total"] = sum(
            _number(row, fdr_key) for row in rows
        )
    return projection, failures


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
        fdr_key="fdr_significant_feature_count",
        verify_reports=verify_reports,
    )
    expression, expression_failures = _catalog_projection(
        name="expression_analyses",
        store=GeoExpressionAnalysisStore(root),
        identifier_key="analysis_id",
        feature_key="feature_count",
        tested_key="tested_feature_count",
        fdr_key="fdr_significant_feature_count",
        verify_reports=verify_reports,
    )
    count_comparisons, count_comparison_failures = _catalog_projection(
        name="paired_count_comparisons",
        store=GeoCountConsistencyStore(root),
        identifier_key="comparison_id",
        feature_key="feature_count",
        tested_key=None,
        fdr_key=None,
        verify_reports=verify_reports,
    )
    expression_comparisons, expression_comparison_failures = _catalog_projection(
        name="expression_comparisons",
        store=GeoExpressionConsistencyStore(root),
        identifier_key="comparison_id",
        feature_key="feature_count",
        tested_key=None,
        fdr_key=None,
        verify_reports=verify_reports,
    )
    failures = (
        analysis_failures
        + expression_failures
        + count_comparison_failures
        + expression_comparison_failures
    )
    body = {
        "schema": GEO_REVIEW_SUMMARY_SCHEMA,
        "status": "ready" if failures == 0 else "review",
        "verification_requested": verify_reports,
        "catalogs": {
            "paired_count_analyses": analysis,
            "expression_analyses": expression,
            "paired_count_comparisons": count_comparisons,
            "expression_comparisons": expression_comparisons,
        },
        "integrity": {
            "catalog_records": "validated",
            "report_objects": "verified" if verify_reports and failures == 0 else (
                "review" if verify_reports else "not_requested"
            ),
            "verification_failure_count": failures,
        },
        "limitations": [
            "This is an archive-health projection, not a statistical reanalysis or scientific conclusion.",
            "Counts are sums of catalog summaries and are not deduplicated across studies or comparisons.",
            "Sample, subject, pair, and raw matrix identifiers are never included in this projection.",
        ],
    }
    return body | {"content_address": content_hash(body, prefix="geo-review-summary")}


__all__ = ["GEO_REVIEW_SUMMARY_SCHEMA", "build_geo_review_summary"]

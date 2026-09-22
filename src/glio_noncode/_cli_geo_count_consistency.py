"""Focused CLI for comparing saved paired GEO count contrasts."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ._cli_support import read_mapping, write_json
from .errors import StoreError, ValidationError
from .geo_analysis_store import GeoAnalysisStore
from .geo_count_consistency import (
    MAX_COUNT_CONSISTENCY_FEATURES,
    MAX_COUNT_CONTRAST_REPORTS,
    CountContrastCompatibilityError,
    build_geo_count_consistency_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode geo-count-consistency",
        description=(
            "Compare exact source-feature directions across completed paired GEO count "
            "reports. Effect sizes and p-values remain per-study; no pooling is performed."
        ),
    )
    parser.add_argument(
        "reports",
        nargs="*",
        metavar="REPORT.json",
        help="completed paired-count JSON reports; supply two or more distinct studies",
    )
    parser.add_argument(
        "--analysis-id",
        action="append",
        default=[],
        metavar="GEO-ID",
        help="saved analysis ID from --data-root; repeat for two or more studies",
    )
    parser.add_argument(
        "--data-root",
        default=".glio",
        help="local GEO analysis store used with --analysis-id",
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        action="append",
        metavar="ID",
        help=(
            "exact case-sensitive source feature ID to compare; repeat as needed "
            f"(maximum {MAX_COUNT_CONSISTENCY_FEATURES})"
        ),
    )
    parser.add_argument("--output", default="-", help="JSON report path, or - for stdout")
    return parser


def _error_report(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "glio-noncode.geo-count-consistency.v1",
        "status": "invalid",
        "error": {"code": code, "message": message},
    }


def _load_reports(args: argparse.Namespace) -> tuple[dict[str, Any], ...]:
    if bool(args.reports) == bool(args.analysis_id):
        raise ValidationError(
            "supply either paired-count report paths or repeated --analysis-id values"
        )
    if args.analysis_id:
        if not 2 <= len(args.analysis_id) <= MAX_COUNT_CONTRAST_REPORTS:
            raise ValidationError(
                "GEO count consistency requires between "
                f"2 and {MAX_COUNT_CONTRAST_REPORTS} saved analysis IDs"
            )
        store = GeoAnalysisStore(args.data_root)
        return tuple(store.get_report(analysis_id)["report"] for analysis_id in args.analysis_id)
    if not 2 <= len(args.reports) <= MAX_COUNT_CONTRAST_REPORTS:
        raise ValidationError(
            "GEO count consistency requires between "
            f"2 and {MAX_COUNT_CONTRAST_REPORTS} report paths"
        )
    return tuple(read_mapping(path, "GEO paired-count report") for path in args.reports)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        reports = _load_reports(args)
        report = build_geo_count_consistency_report(reports, feature_ids=args.feature_id)
    except CountContrastCompatibilityError as error:
        report = _error_report(error.code, str(error))
    except (KeyError, OSError, StoreError, ValueError, ValidationError):
        report = _error_report(
            "invalid_or_unreadable_count_contrast_report",
            "A paired-count report or saved analysis could not be read, verified, or compared "
            "with the requested features.",
        )

    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            "error: GEO count consistency report could not be written "
            f"({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2


__all__ = ["build_parser", "main"]

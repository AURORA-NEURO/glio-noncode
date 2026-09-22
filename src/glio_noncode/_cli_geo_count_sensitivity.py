"""Focused CLI for same-source paired-count normalization sensitivity."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ._cli_support import read_mapping, write_json
from .errors import StoreError, ValidationError
from .geo_analysis_store import GeoAnalysisStore
from .geo_count_sensitivity import (
    MAX_COUNT_SENSITIVITY_FEATURES,
    CountSensitivityCompatibilityError,
    build_geo_count_sensitivity_report,
)
from .geo_count_sensitivity_store import GeoCountSensitivityStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode geo-count-sensitivity",
        description=(
            "Compare two compatible paired GEO count reports from one Series across "
            "normalization methods without pooling statistics."
        ),
    )
    parser.add_argument(
        "reports",
        nargs="*",
        metavar="REPORT.json",
        help="two completed paired-count JSON reports from the same Series",
    )
    parser.add_argument(
        "--analysis-id",
        action="append",
        default=[],
        metavar="GEO-ID",
        help="saved analysis ID from --data-root; repeat exactly twice",
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
            f"(maximum {MAX_COUNT_SENSITIVITY_FEATURES})"
        ),
    )
    parser.add_argument("--output", default="-", help="JSON report path, or - for stdout")
    parser.add_argument(
        "--save-to-workspace",
        action="store_true",
        help="persist a completed sensitivity comparison in the GEO workspace",
    )
    return parser


def _error_report(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "glio-noncode.geo-count-sensitivity.v1",
        "status": "invalid",
        "error": {"code": code, "message": message},
    }


def _load_reports(args: argparse.Namespace) -> tuple[dict[str, Any], ...]:
    if bool(args.reports) == bool(args.analysis_id):
        raise ValidationError(
            "supply either paired-count report paths or exactly two --analysis-id values"
        )
    if args.analysis_id:
        if len(args.analysis_id) != 2:
            raise ValidationError("GEO count sensitivity requires exactly two saved analysis IDs")
        store = GeoAnalysisStore(args.data_root)
        return tuple(store.get_report(analysis_id)["report"] for analysis_id in args.analysis_id)
    if len(args.reports) != 2:
        raise ValidationError("GEO count sensitivity requires exactly two report paths")
    return tuple(read_mapping(path, "GEO paired-count report") for path in args.reports)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        reports = _load_reports(args)
        report = build_geo_count_sensitivity_report(reports, feature_ids=args.feature_id)
    except CountSensitivityCompatibilityError as error:
        report = _error_report("incompatible_sensitivity_reports", str(error))
    except (KeyError, OSError, StoreError, ValueError, ValidationError):
        report = _error_report(
            "invalid_or_unreadable_count_contrast_report",
            "Two paired-count reports or saved analyses could not be read, verified, or compared "
            "with the requested features.",
        )

    if report.get("status") == "completed" and args.save_to_workspace:
        try:
            saved = GeoCountSensitivityStore(args.data_root).save(report)
            print(f"Saved GEO count sensitivity {saved['comparison_id']}", file=sys.stderr)
        except (OSError, StoreError, ValidationError, ValueError):
            print("error: GEO count sensitivity report could not be saved", file=sys.stderr)
            return 2

    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: GEO count sensitivity report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2


__all__ = ["build_parser", "main"]

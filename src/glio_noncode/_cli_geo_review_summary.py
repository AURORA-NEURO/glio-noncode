"""Focused CLI for inspecting the saved GEO workspace."""

from __future__ import annotations

import argparse
import sys

from ._cli_support import write_json
from .errors import StoreError, ValidationError
from .geo_review_summary import build_geo_review_summary, geo_review_ledger_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode geo-review-summary",
        description=(
            "Verify saved GEO analysis and comparison catalogs and emit an "
            "aggregate-only archive health summary."
        ),
    )
    parser.add_argument(
        "--data-root",
        default=".glio",
        help="local GLIO-NONCODE data root containing saved GEO records",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="emit the row-level aggregate health ledger instead of JSON",
    )
    parser.add_argument(
        "--output", default="-", help="JSON/CSV summary path, or - for stdout"
    )
    parser.add_argument(
        "--skip-report-verification",
        action="store_true",
        help="verify catalog records without reopening each stored report object",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        verify_reports = not args.skip_report_verification
        if args.csv:
            from ._safe_persistence import atomic_write_text

            payload = geo_review_ledger_csv(
                args.data_root,
                verify_reports=verify_reports,
            )
            if args.output == "-":
                sys.stdout.write(payload)
            else:
                atomic_write_text(args.output, payload, field="GEO review CSV output")
            return 0
        summary = build_geo_review_summary(
            args.data_root,
            verify_reports=verify_reports,
        )
        write_json(summary, args.output)
    except (OSError, StoreError, ValidationError, ValueError) as error:
        print(
            "error: GEO workspace summary could not be verified "
            f"({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if summary["status"] == "ready" else 2


__all__ = ["build_parser", "main"]

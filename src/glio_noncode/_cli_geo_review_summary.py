"""Focused CLI for inspecting the saved GEO workspace."""

from __future__ import annotations

import argparse
import sys

from ._cli_support import write_json
from .errors import StoreError, ValidationError
from .geo_review_summary import (
    build_geo_preflight_ledger,
    build_geo_preflight_ledger_document,
    build_geo_review_ledger,
    build_geo_review_ledger_document,
    build_geo_review_summary,
    capabilities,
    preflight_ledger_schema,
    render_geo_preflight_ledger_csv,
    render_geo_review_ledger_csv,
    review_ledger_schema,
    review_summary_schema,
)


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
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument(
        "--csv",
        action="store_true",
        help="emit the row-level aggregate health ledger instead of JSON",
    )
    output_group.add_argument(
        "--preflights-csv",
        action="store_true",
        help="emit a kind-aware aggregate ledger for saved GEO preflights",
    )
    output_group.add_argument(
        "--ledger-json",
        action="store_true",
        help="emit the content-addressed JSON form of the aggregate GEO ledger",
    )
    output_group.add_argument(
        "--preflights-json",
        action="store_true",
        help="emit the content-addressed JSON form of the saved preflight ledger",
    )
    output_group.add_argument(
        "--schema",
        choices=("summary", "ledger", "preflights"),
        help="emit a JSON Schema for a GEO review document",
    )
    output_group.add_argument(
        "--capabilities",
        action="store_true",
        help="emit the public GEO review capability and endpoint contract",
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
        if args.capabilities:
            write_json(capabilities(), args.output)
            return 0
        if args.schema:
            schema_builders = {
                "summary": review_summary_schema,
                "ledger": review_ledger_schema,
                "preflights": preflight_ledger_schema,
            }
            write_json(schema_builders[args.schema](), args.output)
            return 0
        if args.preflights_json:
            document = build_geo_preflight_ledger_document(
                args.data_root,
                verify_reports=verify_reports,
            )
            write_json(document, args.output)
            return 0 if all(
                row["verification"] not in {"invalid", "failed"}
                for row in document["rows"]
            ) else 2
        if args.ledger_json:
            document = build_geo_review_ledger_document(
                args.data_root,
                verify_reports=verify_reports,
            )
            write_json(document, args.output)
            return 0 if all(
                row["verification"] not in {"invalid", "failed"}
                for row in document["rows"]
            ) else 2
        if args.csv or args.preflights_csv:
            from ._safe_persistence import atomic_write_text

            if args.preflights_csv:
                ledger = build_geo_preflight_ledger(
                    args.data_root,
                    verify_reports=verify_reports,
                )
                payload = render_geo_preflight_ledger_csv(ledger)
            else:
                ledger = build_geo_review_ledger(
                    args.data_root,
                    verify_reports=verify_reports,
                )
                payload = render_geo_review_ledger_csv(ledger)
            if args.output == "-":
                sys.stdout.write(payload)
            else:
                atomic_write_text(args.output, payload, field="GEO review CSV output")
            return 0 if all(
                row["verification"] not in {"invalid", "failed"} for row in ledger
            ) else 2
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

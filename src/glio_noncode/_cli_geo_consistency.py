"""Compare exact feature directions across bounded GEO contrast reports."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ._cli_support import read_mapping, write_json
from .errors import ValidationError
from .geo_consistency import (
    MAX_CONTRAST_REPORTS,
    ContrastCompatibilityError,
    build_geo_contrast_consistency_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode geo-consistency",
        description=(
            "Compare selected exact feature directions across completed GEO contrast reports. "
            "Does not pool effect sizes or p-values."
        ),
    )
    parser.add_argument(
        "reports",
        nargs="+",
        metavar="CONTRAST.json",
        help="completed geo-contrast JSON report; supply two or more distinct studies",
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        action="append",
        metavar="ID",
        help="exact case-sensitive platform feature ID to compare; repeat as needed",
    )
    parser.add_argument("--output", default="-", help="JSON report path, or - for stdout")
    return parser


def _error_report(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "glio-noncode.geo-contrast-consistency.v1",
        "status": "invalid",
        "error": {"code": code, "message": message},
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if not 2 <= len(args.reports) <= MAX_CONTRAST_REPORTS:
            raise ValidationError(
                f"GEO consistency requires between 2 and {MAX_CONTRAST_REPORTS} contrast reports"
            )
        reports = tuple(
            read_mapping(path, "GEO contrast report")
            for path in args.reports
        )
        report = build_geo_contrast_consistency_report(
            reports,
            feature_ids=args.feature_id,
        )
    except ContrastCompatibilityError as error:
        report = _error_report(error.code, str(error))
    except (OSError, ValueError, ValidationError):
        report = _error_report(
            "invalid_or_unreadable_contrast_report",
            "A contrast report could not be read, verified, or compared with the requested "
            "features.",
        )

    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: GEO consistency report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2

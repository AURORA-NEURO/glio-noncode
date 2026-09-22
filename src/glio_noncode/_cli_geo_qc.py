"""Focused command for descriptive GEO Series Matrix quality summaries."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ._cli_support import write_json
from .errors import SourceError, SourceNotFoundError, ValidationError
from .expression_evidence import ExpressionScale
from .geo_quality import build_expression_quality_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode geo-qc",
        description=(
            "Summarize sample coverage and expression distributions in one GEO Series Matrix. "
            "Flag exact repeated profiles without excluding samples."
        ),
    )
    parser.add_argument("accession", help="NCBI GEO Series accession, such as GSE103227")
    parser.add_argument(
        "--scale",
        required=True,
        choices=tuple(item.value for item in ExpressionScale),
        help="declared data scale after reviewing GEO processing metadata",
    )
    parser.add_argument(
        "--matrix-file",
        help="use a previously downloaded .txt or .txt.gz Series Matrix instead of HTTPS",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTPS timeout in seconds")
    parser.add_argument("--output", default="-", help="JSON report path, or - for stdout")
    return parser


def _error_report(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "glio-noncode.geo-expression-quality.v1",
        "status": "invalid",
        "error": {"code": code, "message": message},
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_expression_quality_report(
            args.accession,
            scale=args.scale,
            matrix_file=args.matrix_file,
            timeout_seconds=args.timeout,
        )
    except SourceNotFoundError:
        report = _error_report(
            "matrix_not_found",
            "No canonical GEO Series Matrix file was found; use --matrix-file "
            "for a downloaded matrix.",
        )
    except SourceError:
        report = _error_report(
            "source_unavailable",
            "NCBI GEO could not be reached or returned an unsuccessful response.",
        )
    except ValidationError:
        report = _error_report(
            "invalid_input_or_matrix",
            "The GEO request or Series Matrix failed validation.",
        )
    except OSError:
        report = _error_report(
            "matrix_read_error",
            "The local GEO Series Matrix could not be read as a regular bounded file.",
        )

    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: GEO quality report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2

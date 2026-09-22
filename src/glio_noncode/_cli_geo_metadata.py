"""Focused command for GEO sample annotation inventory and cohort-design review."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ._cli_support import write_json
from .errors import SourceError, SourceNotFoundError, ValidationError
from .geo_metadata import build_geo_sample_metadata_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode geo-metadata",
        description=(
            "Inventory GEO sample characteristics and category counts before choosing "
            "explicit contrast filters."
        ),
    )
    parser.add_argument("accession", help="NCBI GEO Series accession, such as GSE103227")
    parser.add_argument(
        "--matrix-file",
        help="use a previously downloaded .txt or .txt.gz Series Matrix instead of HTTPS",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTPS timeout in seconds")
    parser.add_argument("--output", default="-", help="JSON report path, or - for stdout")
    return parser


def _error_report(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "glio-noncode.geo-sample-metadata.v1",
        "status": "invalid",
        "error": {"code": code, "message": message},
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_geo_sample_metadata_report(
            args.accession,
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
            f"error: GEO sample metadata report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2

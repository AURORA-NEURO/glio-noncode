"""Focused command for metadata-only GEO contrast design preflight."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ._cli_support import write_json
from .errors import SourceError, SourceNotFoundError, ValidationError
from .geo_design import build_geo_contrast_design_report


def _characteristic_filter(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("sample filter must be FIELD=VALUE")
    field, expected = value.split("=", 1)
    if not field.strip() or not expected.strip():
        raise argparse.ArgumentTypeError("sample filter must be FIELD=VALUE")
    return field.strip(), expected.strip()


def _covariate_specification(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("covariate must be FIELD=continuous or FIELD=categorical")
    field, kind = value.split("=", 1)
    field = field.strip()
    kind = kind.strip().casefold()
    if not field or kind not in {"continuous", "categorical"}:
        raise argparse.ArgumentTypeError("covariate must be FIELD=continuous or FIELD=categorical")
    return field, kind


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode geo-design",
        description=(
            "Check explicit GEO group selection, covariate completeness, and model "
            "estimability without calculating expression effects or p-values."
        ),
    )
    parser.add_argument("accession", help="NCBI GEO Series accession, such as GSE103227")
    parser.add_argument(
        "--case-filter",
        required=True,
        action="append",
        type=_characteristic_filter,
        metavar="FIELD=VALUE",
        help="sample characteristic required for the case group; repeat for AND filters",
    )
    parser.add_argument(
        "--reference-filter",
        required=True,
        action="append",
        type=_characteristic_filter,
        metavar="FIELD=VALUE",
        help="sample characteristic required for the reference group; repeat for AND filters",
    )
    parser.add_argument(
        "--covariate",
        action="append",
        type=_covariate_specification,
        default=[],
        metavar="FIELD=continuous|categorical",
        help="audit a declared sample covariate; repeat as needed",
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
        "schema": "glio-noncode.geo-contrast-design.v1",
        "status": "invalid",
        "error": {"code": code, "message": message},
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_geo_contrast_design_report(
            args.accession,
            case_filters=args.case_filter,
            reference_filters=args.reference_filter,
            covariates=args.covariate,
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
            "The GEO request, sample filters, covariates, or Series Matrix failed validation.",
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
            f"error: GEO design report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2

"""Focused command for exploratory two-group GEO expression screening."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ._cli_support import write_json
from .errors import SourceError, SourceNotFoundError, ValidationError
from .expression_evidence import ExpressionScale
from .geo_expression import build_expression_contrast_report


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
        prog="glio-noncode geo-contrast",
        description=(
            "Screen all features in one GEO matrix between explicitly selected "
            "sample groups with multiple-testing correction; optional covariates "
            "use an additive linear model."
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
        "--scale",
        required=True,
        choices=tuple(item.value for item in ExpressionScale),
        help="declared data scale after reviewing GEO processing metadata",
    )
    parser.add_argument(
        "--covariate",
        action="append",
        type=_covariate_specification,
        default=[],
        metavar="FIELD=continuous|categorical",
        help=(
            "adjust for a declared sample characteristic; repeat as needed, "
            "for example age=continuous or batch=categorical"
        ),
    )
    parser.add_argument(
        "--matrix-file",
        help="use a previously downloaded .txt or .txt.gz Series Matrix instead of HTTPS",
    )
    parser.add_argument(
        "--fdr",
        type=float,
        default=0.05,
        help="FDR threshold in (0, 1], default 0.05",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=1_000,
        help="maximum ranked feature rows to include (all features are tested), default 1000",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTPS timeout in seconds")
    parser.add_argument("--output", default="-", help="JSON report path, or - for stdout")
    return parser


def _error_report(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "glio-noncode.geo-expression-contrast.v1",
        "status": "invalid",
        "error": {"code": code, "message": message},
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_expression_contrast_report(
            args.accession,
            case_filters=args.case_filter,
            reference_filters=args.reference_filter,
            scale=args.scale,
            matrix_file=args.matrix_file,
            timeout_seconds=args.timeout,
            fdr_threshold=args.fdr,
            top=args.top,
            covariates=args.covariate,
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
            "The GEO request, sample filters, or Series Matrix failed validation.",
        )
    except OSError:
        report = _error_report(
            "matrix_read_error",
            "The local GEO Series Matrix could not be read as a regular bounded file.",
        )
    except ArithmeticError:
        report = _error_report(
            "statistical_numerical_failure",
            "The adjusted-model calculation could not be represented reliably.",
        )

    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: GEO contrast report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2

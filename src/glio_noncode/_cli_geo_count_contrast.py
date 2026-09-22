"""Focused command for paired contrasts over GEO supplementary count tables."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ._cli_support import write_json
from .errors import SourceError, SourceNotFoundError, StoreError, ValidationError
from .geo_analysis_store import GeoAnalysisStore
from .geo_expression import (
    DEFAULT_GEO_CONFIDENCE_LEVEL,
    GEO_COUNT_NORMALIZATION_METHODS,
    build_geo_count_contrast_report,
)
from .geo_metadata import build_geo_count_contrast_design_report
from .geo_preflight_store import GeoPreflightStore


def _group_filter(value: str, label: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError(f"{label} must be FIELD=VALUE")
    field, expected = value.split("=", 1)
    if not field.strip() or not expected.strip():
        raise argparse.ArgumentTypeError(f"{label} must be FIELD=VALUE")
    return field.strip(), expected.strip()


def _case_filter(value: str) -> tuple[str, str]:
    return _group_filter(value, "case filter")


def _reference_filter(value: str) -> tuple[str, str]:
    return _group_filter(value, "reference filter")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode geo-count-contrast",
        description=(
            "Run a paired exploratory screen with signed-rank and direction-consistency "
            "tests over one GEO supplementary integer-count matrix."
        ),
    )
    parser.add_argument("accession", help="NCBI GEO Series accession, such as GSE141945")
    parser.add_argument(
        "--case-filter",
        required=True,
        action="append",
        type=_case_filter,
        metavar="FIELD=VALUE",
        help="sample characteristic required for the case group; repeat for AND filters",
    )
    parser.add_argument(
        "--reference-filter",
        required=True,
        action="append",
        type=_reference_filter,
        metavar="FIELD=VALUE",
        help="sample characteristic required for the reference group; repeat for AND filters",
    )
    parser.add_argument(
        "--sample-key-column",
        required=True,
        help="exact metadata header matching count-matrix sample IDs; empty string means blank",
    )
    parser.add_argument(
        "--pair-key-column",
        required=True,
        help="exact metadata header holding the unique subject/pair key",
    )
    parser.add_argument("--counts-file-name", help="GEO supplementary count-matrix filename")
    parser.add_argument("--metadata-file-name", help="GEO supplementary sample-metadata filename")
    parser.add_argument("--counts-file", help="local count matrix .csv/.tsv or compressed file")
    parser.add_argument(
        "--metadata-file", help="local sample metadata .csv/.tsv or compressed file"
    )
    parser.add_argument(
        "--feature-annotation-file",
        help=(
            "optional UTF-8 CSV with source_feature_id,curated_feature_id columns; "
            "source IDs remain unchanged"
        ),
    )
    parser.add_argument(
        "--counts-delimiter",
        choices=("comma", "tab"),
        default="comma",
        help="explicit delimiter used by the count matrix",
    )
    parser.add_argument(
        "--metadata-delimiter",
        choices=("comma", "tab"),
        default="comma",
        help="explicit delimiter used by the sample metadata",
    )
    parser.add_argument(
        "--normalization-method",
        choices=GEO_COUNT_NORMALIZATION_METHODS,
        default="log2_cpm",
        help="count normalization: basic library CPM or optional TMM-adjusted CPM",
    )
    parser.add_argument("--fdr", type=float, default=0.05, help="FDR threshold in (0, 1]")
    parser.add_argument(
        "--confidence-level",
        type=float,
        default=DEFAULT_GEO_CONFIDENCE_LEVEL,
        help="pointwise confidence level for median paired-difference intervals (0, 1)",
    )
    parser.add_argument(
        "--fdr-method",
        choices=("bh", "by"),
        default="bh",
        help="multiple-testing adjustment: Benjamini-Hochberg (bh) or Benjamini-Yekutieli (by)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=1_000,
        help="maximum ranked features to include; all eligible rows are tested",
    )
    parser.add_argument(
        "--track-feature-id",
        action="append",
        default=[],
        metavar="FEATURE_ID",
        help=(
            "retain this exact source feature ID even when it falls outside --top; "
            "repeat for explicit cross-run sensitivity features"
        ),
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTPS timeout in seconds")
    parser.add_argument("--output", default="-", help="JSON report path, or - for stdout")
    parser.add_argument(
        "--save-to-workspace",
        action="store_true",
        help="persist the completed aggregate report in the local GEO analysis catalog",
    )
    parser.add_argument(
        "--data-root",
        default=".glio",
        help="local GLIO-NONCODE data root used with --save-to-workspace",
    )
    return parser


def _error_report(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "glio-noncode.geo-paired-count-contrast.v1",
        "status": "invalid",
        "error": {"code": code, "message": message},
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    delimiter = {"comma": ",", "tab": "\t"}
    try:
        report = build_geo_count_contrast_report(
            args.accession,
            case_filters=args.case_filter,
            reference_filters=args.reference_filter,
            sample_key_column=args.sample_key_column,
            pair_key_column=args.pair_key_column,
            counts_file_name=args.counts_file_name,
            metadata_file_name=args.metadata_file_name,
            counts_file=args.counts_file,
            metadata_file=args.metadata_file,
            counts_delimiter=delimiter[args.counts_delimiter],
            metadata_delimiter=delimiter[args.metadata_delimiter],
            timeout_seconds=args.timeout,
            fdr_threshold=args.fdr,
            confidence_level=args.confidence_level,
            fdr_method=args.fdr_method,
            top=args.top,
            feature_annotation_file=args.feature_annotation_file,
            normalization_method=args.normalization_method,
            track_feature_ids=args.track_feature_id,
        )
    except SourceNotFoundError:
        report = _error_report(
            "supplementary_file_not_found",
            "A requested canonical GEO supplementary file was not found.",
        )
    except SourceError:
        report = _error_report(
            "source_unavailable",
            "NCBI GEO could not be reached or returned an unsuccessful response.",
        )
    except ValidationError:
        report = _error_report(
            "invalid_input_or_matrix",
            "GEO files, pair keys, group filters, or analysis settings failed validation.",
        )
    except OSError:
        report = _error_report(
            "matrix_read_error",
            "A local GEO file could not be read as a regular bounded file.",
        )
    except ArithmeticError:
        report = _error_report(
            "statistical_numerical_failure",
            "The paired signed-rank calculation could not be represented reliably.",
        )

    if args.save_to_workspace and report.get("status") == "completed":
        try:
            saved = GeoAnalysisStore(args.data_root).save(report)
        except (OSError, StoreError, ValidationError) as error:
            print(
                "error: GEO analysis report could not be saved "
                f"({type(error).__name__})",
                file=sys.stderr,
            )
            return 2
        print(f"Saved GEO analysis {saved['analysis_id']}", file=sys.stderr)

    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: GEO paired-count report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2


def build_design_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode geo-count-design",
        description=(
            "Validate a GEO supplementary-count sample join and paired design "
            "without calculating effects or p-values."
        ),
    )
    parser.add_argument("accession", help="NCBI GEO Series accession, such as GSE141945")
    parser.add_argument(
        "--case-filter",
        required=True,
        action="append",
        type=_case_filter,
        metavar="FIELD=VALUE",
        help="sample characteristic required for the case group; repeat for AND filters",
    )
    parser.add_argument(
        "--reference-filter",
        required=True,
        action="append",
        type=_reference_filter,
        metavar="FIELD=VALUE",
        help="sample characteristic required for the reference group; repeat for AND filters",
    )
    parser.add_argument(
        "--sample-key-column",
        required=True,
        help="exact metadata header matching count-matrix sample IDs; empty string means blank",
    )
    parser.add_argument(
        "--pair-key-column",
        required=True,
        help="exact metadata header holding the unique subject/pair key",
    )
    parser.add_argument("--counts-file-name", help="GEO supplementary count-matrix filename")
    parser.add_argument("--metadata-file-name", help="GEO supplementary sample-metadata filename")
    parser.add_argument("--counts-file", help="local count matrix .csv/.tsv or compressed file")
    parser.add_argument(
        "--metadata-file", help="local sample metadata .csv/.tsv or compressed file"
    )
    parser.add_argument(
        "--counts-delimiter",
        choices=("comma", "tab"),
        default="comma",
        help="explicit delimiter used by the count matrix",
    )
    parser.add_argument(
        "--metadata-delimiter",
        choices=("comma", "tab"),
        default="comma",
        help="explicit delimiter used by the metadata file",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTPS timeout in seconds")
    parser.add_argument("--output", default="-", help="JSON report path, or - for stdout")
    parser.add_argument(
        "--save-to-workspace",
        action="store_true",
        help="save the completed preflight in the local catalog",
    )
    parser.add_argument(
        "--data-root",
        default=".glio",
        help="local GLIO-NONCODE data root used with --save-to-workspace",
    )
    return parser


def design_main(argv: list[str] | None = None) -> int:
    args = build_design_parser().parse_args(argv)
    delimiter = {"comma": ",", "tab": "\t"}
    try:
        report = build_geo_count_contrast_design_report(
            args.accession,
            case_filters=args.case_filter,
            reference_filters=args.reference_filter,
            sample_key_column=args.sample_key_column,
            pair_key_column=args.pair_key_column,
            counts_file_name=args.counts_file_name,
            metadata_file_name=args.metadata_file_name,
            counts_file=args.counts_file,
            metadata_file=args.metadata_file,
            counts_delimiter=delimiter[args.counts_delimiter],
            metadata_delimiter=delimiter[args.metadata_delimiter],
            timeout_seconds=args.timeout,
        )
    except SourceNotFoundError:
        report = {
            "schema": "glio-noncode.geo-count-contrast-design.v1",
            "status": "invalid",
            "error": {
                "code": "supplementary_file_not_found",
                "message": "A requested canonical GEO supplementary file was not found.",
            },
        }
    except SourceError:
        report = {
            "schema": "glio-noncode.geo-count-contrast-design.v1",
            "status": "invalid",
            "error": {
                "code": "source_unavailable",
                "message": "NCBI GEO could not be reached or returned an unsuccessful response.",
            },
        }
    except ValidationError:
        report = {
            "schema": "glio-noncode.geo-count-contrast-design.v1",
            "status": "invalid",
            "error": {
                "code": "invalid_input_or_matrix",
                "message": (
                    "GEO files, sample joins, pair keys, or group filters failed validation."
                ),
            },
        }
    except OSError:
        report = {
            "schema": "glio-noncode.geo-count-contrast-design.v1",
            "status": "invalid",
            "error": {
                "code": "matrix_read_error",
                "message": "A local GEO file could not be read as a regular bounded file.",
            },
        }

    if args.save_to_workspace and report.get("status") == "completed":
        try:
            saved = GeoPreflightStore(args.data_root).save(report)
        except (OSError, StoreError, ValidationError) as error:
            print(
                f"error: GEO count-design report could not be saved ({type(error).__name__})",
                file=sys.stderr,
            )
            return 2
        print(f"Saved GEO preflight {saved['preflight_id']}", file=sys.stderr)

    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: GEO count-design report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2

"""Inspect GEO supplementary count-matrix metadata before selecting cohorts."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ._cli_support import write_json
from .errors import SourceError, SourceNotFoundError, StoreError, ValidationError
from .geo_metadata import build_geo_count_metadata_report
from .geo_preflight_store import GeoPreflightStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode geo-count-metadata",
        description=(
            "Inventory supplementary GEO count-matrix metadata columns and categories "
            "without emitting sample or pair identifiers."
        ),
    )
    parser.add_argument("accession", help="NCBI GEO Series accession, such as GSE141945")
    parser.add_argument(
        "--sample-key-column",
        required=True,
        help="exact metadata header matching count-matrix sample IDs; empty string means blank",
    )
    parser.add_argument(
        "--pair-key-column",
        help="optional subject/pair key whose completeness and repetition are summarized",
    )
    parser.add_argument("--metadata-file-name", help="GEO supplementary metadata filename")
    parser.add_argument(
        "--metadata-file", help="local supplementary metadata .csv/.tsv or compressed file"
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


def _error_report(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "glio-noncode.geo-count-metadata.v1",
        "status": "invalid",
        "error": {"code": code, "message": message},
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    delimiter = {"comma": ",", "tab": "\t"}
    try:
        report = build_geo_count_metadata_report(
            args.accession,
            sample_key_column=args.sample_key_column,
            pair_key_column=args.pair_key_column,
            metadata_file_name=args.metadata_file_name,
            metadata_file=args.metadata_file,
            metadata_delimiter=delimiter[args.metadata_delimiter],
            timeout_seconds=args.timeout,
        )
    except SourceNotFoundError:
        report = _error_report(
            "metadata_file_not_found",
            "The requested canonical GEO supplementary metadata file was not found.",
        )
    except SourceError:
        report = _error_report(
            "source_unavailable",
            "NCBI GEO could not be reached or returned an unsuccessful response.",
        )
    except ValidationError:
        report = _error_report(
            "invalid_input_or_metadata",
            "The GEO request, metadata table, sample key, or pair key failed validation.",
        )
    except OSError:
        report = _error_report(
            "metadata_read_error",
            "The local GEO metadata file could not be read as a regular bounded file.",
        )

    if args.save_to_workspace and report.get("status") == "completed":
        try:
            saved = GeoPreflightStore(args.data_root).save(report)
        except (OSError, StoreError, ValidationError) as error:
            print(
                f"error: GEO count-metadata report could not be saved ({type(error).__name__})",
                file=sys.stderr,
            )
            return 2
        print(f"Saved GEO preflight {saved['preflight_id']}", file=sys.stderr)

    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: GEO count-metadata report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2


__all__ = ["build_parser", "main"]

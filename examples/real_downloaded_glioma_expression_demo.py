#!/usr/bin/env python3
"""Run the reusable GEO supplementary-count expression workflow on real data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from glio_noncode.errors import GlioError
from glio_noncode.geo_expression import (
    GEO_COUNT_NORMALIZATION_METHODS,
    build_geo_count_outlier_report,
)

ACCESSION = "GSE141945"
COUNTS_FILE_NAME = "GSE141945_RNAseq.counts.csv.gz"
METADATA_FILE_NAME = "GSE141945_RNAseq.metadata.csv.gz"
RESEARCH_WARNING = (
    "RESEARCH USE ONLY. This exploratory expression comparison is not a diagnosis, "
    "treatment recommendation, differential-expression study, or regulatory-element validation."
)


def run_demo(
    *,
    counts_file: Path | None = None,
    metadata_file: Path | None = None,
    feature_annotation_file: Path | None = None,
    normalization_method: str = "log2_cpm",
    timeout_seconds: float = 30.0,
) -> dict[str, object]:
    if (counts_file is None) != (metadata_file is None):
        raise ValueError("provide both local supplementary files or neither")
    return build_geo_count_outlier_report(
        ACCESSION,
        feature_id="EGFR",
        sample_key_column="",
        sample_filters=(("Timepoint", "Tumor"),),
        counts_file_name=None if counts_file is not None else COUNTS_FILE_NAME,
        metadata_file_name=None if metadata_file is not None else METADATA_FILE_NAME,
        counts_file=counts_file,
        metadata_file=metadata_file,
        counts_delimiter=",",
        metadata_delimiter=",",
        timeout_seconds=timeout_seconds,
        feature_annotation_file=feature_annotation_file,
        normalization_method=normalization_method,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts-file", type=Path, help="use a downloaded count matrix locally")
    parser.add_argument("--metadata-file", type=Path, help="use its downloaded metadata locally")
    parser.add_argument(
        "--feature-annotation-file",
        type=Path,
        help="optional source_feature_id,curated_feature_id CSV for reviewed identifiers",
    )
    parser.add_argument(
        "--normalization-method",
        choices=GEO_COUNT_NORMALIZATION_METHODS,
        default="log2_cpm",
        help="use raw-library CPM or optional TMM-adjusted CPM",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="NCBI HTTPS timeout in seconds")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_demo(
            counts_file=args.counts_file,
            metadata_file=args.metadata_file,
            feature_annotation_file=args.feature_annotation_file,
            normalization_method=args.normalization_method,
            timeout_seconds=args.timeout,
        )
    except (GlioError, OSError, ValueError) as error:
        print(
            json.dumps(
                {
                    "demo_completed": False,
                    "error": type(error).__name__,
                    "research_use_only": True,
                    "warning": RESEARCH_WARNING,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    report["research_use_only"] = True
    report["warning"] = RESEARCH_WARNING
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

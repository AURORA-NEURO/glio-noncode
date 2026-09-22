#!/usr/bin/env python3
"""Run a paired tumor-versus-organoid screen on the public GSE141945 counts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from glio_noncode.errors import GlioError
from glio_noncode.geo_expression import (
    GEO_COUNT_NORMALIZATION_METHODS,
    build_geo_count_contrast_report,
)

ACCESSION = "GSE141945"
COUNTS_FILE_NAME = "GSE141945_RNAseq.counts.csv.gz"
METADATA_FILE_NAME = "GSE141945_RNAseq.metadata.csv.gz"
RESEARCH_WARNING = (
    "RESEARCH USE ONLY. This exploratory paired log2-CPM screen is not a count-model "
    "differential-expression analysis, causal variant result, diagnosis, or treatment advice."
)


def run_demo(
    *,
    counts_file: Path | None = None,
    metadata_file: Path | None = None,
    feature_annotation_file: Path | None = None,
    timeout_seconds: float = 30.0,
    fdr_threshold: float = 0.05,
    fdr_method: str = "bh",
    top: int = 25,
    normalization_method: str = "log2_cpm",
) -> dict[str, object]:
    if (counts_file is None) != (metadata_file is None):
        raise ValueError("provide both local supplementary files or neither")
    return build_geo_count_contrast_report(
        ACCESSION,
        case_filters=(("Timepoint", "Tumor"),),
        reference_filters=(("Timepoint", "1wk"),),
        sample_key_column="",
        pair_key_column="Patient",
        counts_file_name=None if counts_file is not None else COUNTS_FILE_NAME,
        metadata_file_name=None if metadata_file is not None else METADATA_FILE_NAME,
        counts_file=counts_file,
        metadata_file=metadata_file,
        counts_delimiter=",",
        metadata_delimiter=",",
        timeout_seconds=timeout_seconds,
        fdr_threshold=fdr_threshold,
        fdr_method=fdr_method,
        top=top,
        feature_annotation_file=feature_annotation_file,
        normalization_method=normalization_method,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counts-file", type=Path, help="use a downloaded count matrix locally")
    parser.add_argument("--metadata-file", type=Path, help="use downloaded sample metadata locally")
    parser.add_argument(
        "--feature-annotation-file",
        type=Path,
        help="optional source_feature_id,curated_feature_id CSV for reviewed identifiers",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="NCBI HTTPS timeout in seconds")
    parser.add_argument("--fdr", type=float, default=0.05, help="adjusted p-value threshold")
    parser.add_argument("--fdr-method", choices=("bh", "by"), default="bh")
    parser.add_argument("--top", type=int, default=25, help="ranked rows to include in the output")
    parser.add_argument(
        "--normalization-method",
        choices=GEO_COUNT_NORMALIZATION_METHODS,
        default="log2_cpm",
        help="use raw-library CPM or optional TMM-adjusted CPM",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = run_demo(
            counts_file=args.counts_file,
            metadata_file=args.metadata_file,
            feature_annotation_file=args.feature_annotation_file,
            timeout_seconds=args.timeout,
            fdr_threshold=args.fdr,
            fdr_method=args.fdr_method,
            top=args.top,
            normalization_method=args.normalization_method,
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

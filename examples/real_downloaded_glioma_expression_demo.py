#!/usr/bin/env python3
"""Download a public glioblastoma count matrix and exercise expression evidence.

This is a research-only feature demonstration. It does not build a clinical
case, connect expression to a non-coding element, or produce a diagnosis.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path
from urllib.request import Request, urlopen

from glio_noncode.errors import GlioError
from glio_noncode.expression_evidence import (
    ExpressionBatch,
    ExpressionObservation,
    ExpressionScale,
    RNAEvidenceState,
    RobustExpressionOutlierAnalyzer,
)

COUNTS_FILENAME = "GSE141945_RNAseq.counts.csv.gz"
METADATA_FILENAME = "GSE141945_RNAseq.metadata.csv.gz"
GEO_SUPPLEMENTARY_URL = "https://ftp.ncbi.nlm.nih.gov/geo/series/GSE141nnn/GSE141945/suppl/"
SOURCE_ID = "NCBI-GEO-GSE141945"
SOURCE_VERSION = "GEO-processed-counts"
FEATURE_ID = "EGFR"
MAX_MATRIX_ROWS = 150_000
MAX_MATRIX_SAMPLES = 2_000
RESEARCH_WARNING = (
    "RESEARCH USE ONLY. This exploratory expression comparison is not a diagnosis, "
    "treatment recommendation, differential-expression study, or validation of a "
    "non-coding regulatory element."
)


class DemoInputError(ValueError):
    """Raised when a downloaded GEO file is incomplete or malformed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(url: str, destination: Path) -> None:
    """Fetch one public GEO file atomically, leaving no partial destination."""

    request = Request(url, headers={"User-Agent": "glio-noncode-research-demo/1.0"})
    temporary_path: Path | None = None
    try:
        with urlopen(request, timeout=60) as response:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{destination.name}.",
                dir=destination.parent,
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                shutil.copyfileobj(response, temporary)
        with gzip.open(temporary_path, "rb") as compressed:
            compressed.read(1)
        temporary_path.replace(destination)
    except (OSError, TimeoutError) as error:
        raise DemoInputError(f"could not retrieve {destination.name}") from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _ensure_downloads(data_dir: Path) -> tuple[Path, Path]:
    data_dir.mkdir(parents=True, exist_ok=True)
    counts_path = data_dir / COUNTS_FILENAME
    metadata_path = data_dir / METADATA_FILENAME
    if not counts_path.exists():
        _download(GEO_SUPPLEMENTARY_URL + COUNTS_FILENAME, counts_path)
    if not metadata_path.exists():
        _download(GEO_SUPPLEMENTARY_URL + METADATA_FILENAME, metadata_path)
    return counts_path, metadata_path


def _read_metadata(path: Path) -> dict[str, dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["", "Patient", "Timepoint"]:
            raise DemoInputError("GEO metadata columns do not match the expected schema")
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            sample_id = (row.get("") or "").strip()
            if not sample_id or sample_id in rows:
                raise DemoInputError("GEO metadata contains an empty or duplicate sample key")
            rows[sample_id] = row
    if not rows:
        raise DemoInputError("GEO metadata is empty")
    return rows


def _read_feature_and_library_sizes(
    path: Path, feature_id: str
) -> tuple[tuple[str, ...], tuple[int, ...], tuple[int, ...], int, int]:
    """Stream the matrix, retaining only the requested feature and size totals."""

    with gzip.open(path, "rt", encoding="utf-8", newline="") as source:
        reader = csv.reader(source)
        try:
            header = next(reader)
        except StopIteration as error:
            raise DemoInputError("GEO count matrix is empty") from error
        if len(header) < 2 or header[0] not in ("", "gene", "gene_id"):
            raise DemoInputError("GEO count matrix must start with a gene identifier column")
        sample_ids = tuple(item.strip() for item in header[1:])
        if (
            len(sample_ids) > MAX_MATRIX_SAMPLES
            or any(not item for item in sample_ids)
            or len(sample_ids) != len(set(sample_ids))
        ):
            raise DemoInputError("GEO count matrix has invalid sample columns")

        library_sizes = [0] * len(sample_ids)
        seen_features: set[str] = set()
        feature_counts: tuple[int, ...] | None = None
        row_count = 0
        duplicate_feature_labels = 0
        for row in reader:
            if len(row) != len(header):
                raise DemoInputError("GEO count matrix contains a ragged row")
            current_feature = row[0].strip()
            if not current_feature:
                raise DemoInputError("GEO count matrix has an empty gene identifier")
            if current_feature in seen_features:
                duplicate_feature_labels += 1
                if current_feature == feature_id:
                    raise DemoInputError(f"requested gene {feature_id!r} is duplicated")
            seen_features.add(current_feature)
            row_count += 1
            if row_count > MAX_MATRIX_ROWS:
                raise DemoInputError("GEO count matrix exceeds the supported gene-row limit")
            try:
                counts = tuple(int(item) for item in row[1:])
            except ValueError as error:
                raise DemoInputError("GEO count matrix has a non-integer count") from error
            if any(item < 0 for item in counts):
                raise DemoInputError("GEO count matrix has a negative count")
            for index, count in enumerate(counts):
                library_sizes[index] += count
            if current_feature == feature_id:
                feature_counts = counts

    if feature_counts is None:
        raise DemoInputError(f"requested gene {feature_id!r} is absent from the matrix")
    if any(total <= 0 for total in library_sizes):
        raise DemoInputError("GEO count matrix contains a sample with zero library size")
    return (
        sample_ids,
        tuple(library_sizes),
        feature_counts,
        row_count,
        duplicate_feature_labels,
    )


def _observation(
    *, sample_id: str, value: float, scale: ExpressionScale, context_key: str
) -> ExpressionObservation:
    return ExpressionObservation(
        feature_id=FEATURE_ID,
        sample_key=f"private:{sample_id}",
        value=value,
        scale=scale,
        context_key=context_key,
        source_id=SOURCE_ID,
        source_version=SOURCE_VERSION,
    )


def run_demo(data_dir: Path) -> dict[str, object]:
    counts_path, metadata_path = _ensure_downloads(data_dir)
    metadata = _read_metadata(metadata_path)
    (
        sample_ids,
        library_sizes,
        feature_counts,
        gene_rows,
        duplicate_feature_labels,
    ) = _read_feature_and_library_sizes(counts_path, FEATURE_ID)
    if set(sample_ids) != set(metadata):
        raise DemoInputError("GEO metadata sample identifiers do not match the count matrix")

    tumor_samples = tuple(
        sample_id
        for sample_id in sample_ids
        if metadata[sample_id].get("Timepoint", "").strip().casefold() == "tumor"
    )
    if len(tumor_samples) < 6:
        raise DemoInputError("too few tumor samples for the configured reference minimum")

    sample_indexes = {sample_id: index for index, sample_id in enumerate(sample_ids)}
    raw_counts = {
        sample_id: feature_counts[sample_indexes[sample_id]] for sample_id in tumor_samples
    }
    log2_cpm = {
        sample_id: math.log2(
            raw_counts[sample_id] / library_sizes[sample_indexes[sample_id]] * 1_000_000 + 1
        )
        for sample_id in tumor_samples
    }
    context_key = "GSE141945|glioblastoma|primary_tumor|bulk_rna_seq"
    analyzer = RobustExpressionOutlierAnalyzer()

    raw_observations = {
        sample_id: _observation(
            sample_id=sample_id,
            value=float(raw_counts[sample_id]),
            scale=ExpressionScale.RAW_COUNT,
            context_key=context_key,
        )
        for sample_id in tumor_samples
    }
    normalized_observations = {
        sample_id: _observation(
            sample_id=sample_id,
            value=log2_cpm[sample_id],
            scale=ExpressionScale.LOG2_CPM,
            context_key=context_key,
        )
        for sample_id in tumor_samples
    }

    raw_states: Counter[str] = Counter()
    raw_reason_codes: Counter[str] = Counter()
    normalized_states: Counter[str] = Counter()
    normalized_directions: Counter[str] = Counter()
    robust_scores: list[float] = []
    reference_sizes: set[int] = set()
    for target_id in tumor_samples:
        other_samples = tuple(item for item in tumor_samples if item != target_id)
        raw_references = ExpressionBatch(tuple(raw_observations[item] for item in other_samples))
        raw_result = analyzer.analyze(
            raw_observations[target_id], raw_references, expected_context_key=context_key
        )
        raw_states[raw_result.state.value] += 1
        raw_reason_codes.update(raw_result.reason_codes)

        normalized_references = ExpressionBatch(
            tuple(normalized_observations[item] for item in other_samples)
        )
        result = analyzer.analyze(
            normalized_observations[target_id],
            normalized_references,
            expected_context_key=context_key,
        )
        normalized_states[result.state.value] += 1
        normalized_directions[result.direction.value] += 1
        reference_sizes.add(result.reference_count)
        if result.robust_z is not None:
            robust_scores.append(result.robust_z)

    if raw_states != Counter({RNAEvidenceState.OUT_OF_DOMAIN.value: len(tumor_samples)}):
        raise DemoInputError("raw-count safety check did not reject every unnormalized comparison")
    if raw_reason_codes != Counter({"unnormalized_expression_scale": len(tumor_samples)}):
        raise DemoInputError("raw-count safety check returned unexpected reason codes")

    return {
        "demo_completed": True,
        "research_use_only": True,
        "warning": RESEARCH_WARNING,
        "source": {
            "accession": "GSE141945",
            "counts_file": COUNTS_FILENAME,
            "counts_sha256": _sha256(counts_path),
            "counts_bytes": counts_path.stat().st_size,
            "metadata_file": METADATA_FILENAME,
            "metadata_sha256": _sha256(metadata_path),
            "metadata_bytes": metadata_path.stat().st_size,
        },
        "input": {
            "gene_rows": gene_rows,
            "duplicate_feature_labels": duplicate_feature_labels,
            "matrix_samples": len(sample_ids),
            "tumor_samples_tested": len(tumor_samples),
            "feature_id": FEATURE_ID,
            "normalization": "log2(counts per million + 1)",
        },
        "raw_count_guard": {
            "outcome": "out_of_domain",
            "reason": "unnormalized_expression_scale",
            "comparisons_rejected": sum(raw_states.values()),
        },
        "leave_one_out_expression_comparison": {
            "method": "median/MAD robust outlier score",
            "reference_count_per_comparison": sorted(reference_sizes),
            "outlier_state_counts": dict(sorted(normalized_states.items())),
            "direction_counts": dict(sorted(normalized_directions.items())),
            "robust_score_range": [round(min(robust_scores), 6), round(max(robust_scores), 6)],
        },
        "interpretation_limit": (
            "A detected outlier is a descriptive single-feature cohort deviation only. "
            "It is not a p-value, independent validation, regulatory-element link, "
            "diagnosis, or treatment signal."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(".glio-gse141945-demo"),
        help="local cache directory for the public GEO downloads",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = run_demo(args.data_dir)
    except (DemoInputError, GlioError, OSError) as error:
        print(
            json.dumps({"demo_completed": False, "error": str(error)}, sort_keys=True),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Bounded aggregate batch analysis for multiple phased sequence inputs."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from typing import Any

from ._cli_sequence import build_analysis_report
from ._cli_support import read_mapping, write_json
from .errors import StoreError, ValidationError
from .serialization import canonical_json, content_hash

MAX_BATCH_ANALYSES = 128
_INPUT_SCHEMA = "glio-noncode.sequence-haplotype-batch-input.v1"
_OUTPUT_SCHEMA = "glio-noncode.sequence-haplotype-batch-analysis.v1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode sequence-batch",
        description=(
            "Run bounded phased sequence analyses over a shared downloaded "
            "reference window and emit aggregate motif-change counts."
        ),
    )
    parser.add_argument("input", help="batch input JSON, or - for stdin")
    parser.add_argument("--output", default="-", help="JSON batch report path, or - for stdout")
    parser.add_argument(
        "--save-to-workspace",
        action="store_true",
        help="persist the completed aggregate report in the local workspace",
    )
    parser.add_argument(
        "--data-root", default=".glio", help="workspace root used with --save-to-workspace"
    )
    return parser


def _shared_signature(report: dict[str, Any]) -> str:
    source = report["source"]
    inputs = report["inputs"]
    return canonical_json(
        {
            "genome_build": inputs["genome_build"],
            "source_id": source["source_id"],
            "source_version": source["source_version"],
            "source_url": source["source_url"],
            "response_hash": source["response_hash"],
            "sequence_interval": source["sequence_interval"],
            "sequence_hash": source["sequence_hash"],
            "motifs": inputs["motifs"],
        }
    )


def _public_record(report: dict[str, Any]) -> dict[str, Any]:
    inputs = report["inputs"]
    analysis = report["analysis"]
    return {
        "analysis_address": analysis["content_address"],
        "analysis_state": report["analysis_state"],
        "variant_count": inputs["variant_count"],
        "motif_count": inputs["motif_count"],
        "created_motif_count": len(analysis["created_hits"]),
        "disrupted_motif_count": len(analysis["disrupted_hits"]),
    }


def build_batch_report(raw: dict[str, Any]) -> dict[str, Any]:
    if type(raw) is not dict or frozenset(raw) != {"schema", "analyses"}:
        raise ValidationError("sequence batch input has an invalid exact top-level shape")
    if raw["schema"] != _INPUT_SCHEMA:
        raise ValidationError("sequence batch input schema is unsupported")
    analyses = raw["analyses"]
    if type(analyses) is not list or not 1 <= len(analyses) <= MAX_BATCH_ANALYSES:
        raise ValidationError(
            f"sequence batch must contain between 1 and {MAX_BATCH_ANALYSES} analyses"
        )
    reports = [build_analysis_report(dict(item)) for item in analyses]
    signatures = {
        _shared_signature(report) for report in reports if report["status"] == "completed"
    }
    if len(signatures) != 1:
        raise ValidationError("sequence batch reports must share one reference and motif context")
    first = reports[0]
    source = first["source"]
    inputs = first["inputs"]
    public_records = [_public_record(report) for report in reports]
    supported_count = sum(report["analysis_state"] == "supported" for report in reports)
    abstained_count = len(reports) - supported_count
    motif_counts: Counter[tuple[str, str, str, str, str]] = Counter()
    motif_names: dict[tuple[str, str, str, str, str], str] = {}
    for report in reports:
        for change in ("created", "disrupted"):
            for hit in report["analysis"][f"{change}_hits"]:
                key = (
                    change,
                    hit["motif_id"],
                    hit["matched_sequence"],
                    hit["strand"],
                    hit["source_id"],
                )
                motif_counts[key] += 1
                motif_names[key] = hit["name"]
    motif_changes = [
        {
            "change": key[0],
            "motif_id": key[1],
            "name": motif_names[key],
            "matched_sequence": key[2],
            "strand": key[3],
            "source_id": key[4],
            "analysis_count": count,
            "analysis_fraction": count / len(reports),
        }
        for key, count in sorted(motif_counts.items())
    ]
    body: dict[str, Any] = {
        "schema": _OUTPUT_SCHEMA,
        "status": "completed",
        "source": {
            "source_id": source["source_id"],
            "source_version": source["source_version"],
            "source_url": source["source_url"],
            "retrieved_at": source["retrieved_at"],
            "response_hash": source["response_hash"],
            "sequence_interval": source["sequence_interval"],
            "sequence_hash": source["sequence_hash"],
        },
        "design": {
            "genome_build": inputs["genome_build"],
            "analysis_count": len(reports),
            "supported_count": supported_count,
            "abstained_count": abstained_count,
            "motif_count": inputs["motif_count"],
            "shared_context_hash": content_hash(_shared_signature(first)),
        },
        "records": public_records,
        "motif_changes": motif_changes,
        "limitations": [
            (
                "Each record uses caller-provided phase and haplotype assignments; "
                "this batch does not infer phase."
            ),
            (
                "Analysis counts describe reports with a motif delta, not independent "
                "biological prevalence."
            ),
            (
                "Sequence-only motif changes do not establish binding, chromatin activity, "
                "target gene, or causality."
            ),
            (
                "Raw bases, genotype strings, and sample identifiers are intentionally "
                "absent from this aggregate report."
            ),
        ],
    }
    return body | {
        "content_address": content_hash(body, prefix="sequence-haplotype-batch-analysis")
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_batch_report(dict(read_mapping(args.input, "sequence batch input")))
    except (OSError, ValueError, ValidationError) as error:
        report = {
            "schema": _OUTPUT_SCHEMA,
            "status": "invalid",
            "error": {
                "code": "invalid_sequence_batch_input",
                "message": "The batch inputs did not share a complete validated context.",
            },
        }
        if args.output == "-":
            print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
    if report.get("status") == "completed" and args.save_to_workspace:
        try:
            from .sequence_batch_store import SequenceBatchStore

            saved = SequenceBatchStore(args.data_root).save(report)
        except (OSError, StoreError, ValidationError) as error:
            report = {
                "schema": _OUTPUT_SCHEMA,
                "status": "invalid",
                "error": {
                    "code": "sequence_batch_persistence_failed",
                    "message": "The completed sequence batch could not be saved to the workspace.",
                },
            }
            if args.output == "-":
                print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        else:
            print(
                f"Saved sequence batch {saved['batch_id']} to {args.data_root}",
                file=sys.stderr,
            )
    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: sequence-batch report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2


__all__ = ["MAX_BATCH_ANALYSES", "build_batch_report", "build_parser", "main"]

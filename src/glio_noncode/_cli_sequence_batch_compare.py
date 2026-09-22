"""Compare aggregate motif-change prevalence between two batch reports."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ._cli_support import read_mapping, write_json
from .errors import StoreError, ValidationError
from .sequence_batch_store import validate_sequence_batch_report
from .serialization import content_hash

_OUTPUT_SCHEMA = "glio-noncode.sequence-haplotype-batch-comparison.v1"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode sequence-batch-compare",
        description="Compare exact motif-change prevalence across two aggregate sequence batches.",
    )
    parser.add_argument("left", help="left batch report JSON")
    parser.add_argument("right", help="right batch report JSON")
    parser.add_argument("--output", default="-", help="JSON comparison path, or - for stdout")
    parser.add_argument(
        "--save-to-workspace",
        action="store_true",
        help="persist the completed comparison in the local workspace",
    )
    parser.add_argument(
        "--data-root", default=".glio", help="workspace root used with --save-to-workspace"
    )
    return parser


def _context(report: dict[str, Any]) -> tuple[Any, ...]:
    source = report["source"]
    design = report["design"]
    return (
        source["response_hash"],
        source["sequence_hash"],
        tuple(source["sequence_interval"]),
        design["genome_build"],
        design["shared_context_hash"],
    )


def _batch_summary(report: dict[str, Any]) -> dict[str, Any]:
    design = report["design"]
    return {
        "content_address": report["content_address"],
        "analysis_count": design["analysis_count"],
        "supported_count": design["supported_count"],
        "abstained_count": design["abstained_count"],
    }


def _change_key(change: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        change["change"],
        change["motif_id"],
        change["matched_sequence"],
        change["strand"],
        change["source_id"],
    )


def build_batch_comparison(left: object, right: object) -> dict[str, Any]:
    left_report = validate_sequence_batch_report(left)
    right_report = validate_sequence_batch_report(right)
    if _context(left_report) != _context(right_report):
        raise ValidationError("sequence batch comparison requires one shared reference context")
    left_changes = {_change_key(item): item for item in left_report["motif_changes"]}
    right_changes = {_change_key(item): item for item in right_report["motif_changes"]}
    changes: list[dict[str, Any]] = []
    for key in sorted(set(left_changes) | set(right_changes)):
        left_item = left_changes.get(key)
        right_item = right_changes.get(key)
        left_fraction = None if left_item is None else left_item["analysis_fraction"]
        right_fraction = None if right_item is None else right_item["analysis_fraction"]
        if left_fraction is None or right_fraction is None:
            direction = "not_reported_in_one_batch"
            delta = None
        else:
            delta = right_fraction - left_fraction
            direction = "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged"
        item = right_item or left_item
        assert item is not None
        changes.append(
            {
                "change": key[0],
                "motif_id": key[1],
                "name": item["name"],
                "matched_sequence": key[2],
                "strand": key[3],
                "source_id": key[4],
                "left_analysis_count": None if left_item is None else left_item["analysis_count"],
                "right_analysis_count": None
                if right_item is None
                else right_item["analysis_count"],
                "left_analysis_fraction": left_fraction,
                "right_analysis_fraction": right_fraction,
                "delta_fraction": delta,
                "direction": direction,
            }
        )
    body: dict[str, Any] = {
        "schema": _OUTPUT_SCHEMA,
        "status": "completed",
        "source": left_report["source"],
        "left": _batch_summary(left_report),
        "right": _batch_summary(right_report),
        "changes": changes,
        "limitations": [
            (
                "Comparison uses exact motif IDs, matched sequences, strand, and source IDs; "
                "aliases are not merged."
            ),
            (
                "A missing motif-change row is classified as not reported in one batch, "
                "not as negative evidence."
            ),
            (
                "Aggregate prevalence differences do not establish binding, activity, "
                "or causal effect."
            ),
        ],
    }
    return body | {"content_address": content_hash(body, prefix="sequence-batch-comparison")}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        left = read_mapping(args.left, "left sequence batch report")
        right = read_mapping(args.right, "right sequence batch report")
        report = build_batch_comparison(left, right)
    except (OSError, ValueError, ValidationError) as error:
        report = {
            "schema": _OUTPUT_SCHEMA,
            "status": "invalid",
            "error": {
                "code": "invalid_sequence_batch_comparison",
                "message": "The two batch reports were not compatible aggregate reports.",
            },
        }
        if args.output == "-":
            print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
    if report.get("status") == "completed" and args.save_to_workspace:
        try:
            from .sequence_batch_comparison_store import SequenceBatchComparisonStore

            saved = SequenceBatchComparisonStore(args.data_root).save(report)
        except (OSError, StoreError, ValidationError) as error:
            report = {
                "schema": _OUTPUT_SCHEMA,
                "status": "invalid",
                "error": {
                    "code": "sequence_batch_comparison_persistence_failed",
                    "message": (
                        "The completed sequence comparison could not be saved to the workspace."
                    ),
                },
            }
            if args.output == "-":
                print(f"error: {type(error).__name__}: {error}", file=sys.stderr)
        else:
            print(
                f"Saved sequence comparison {saved['comparison_id']} to {args.data_root}",
                file=sys.stderr,
            )
    try:
        write_json(report, args.output)
    except (OSError, ValueError, ValidationError) as error:
        print(
            f"error: sequence-batch-compare report could not be written ({type(error).__name__})",
            file=sys.stderr,
        )
        return 2
    return 0 if report.get("status") == "completed" else 2


__all__ = ["build_batch_comparison", "build_parser", "main"]

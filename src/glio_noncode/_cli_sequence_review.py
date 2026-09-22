"""CLI for auditing and projecting the saved phased-sequence archive."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ._cli_support import write_json
from .errors import StoreError, ValidationError
from .sequence_review_store import SequenceReviewStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glio-noncode sequence-review",
        description=(
            "Review saved sequence analyses and batches through bounded, aggregate, "
            "content-addressed projections."
        ),
    )
    parser.add_argument(
        "--data-root", default=".glio", help="workspace root containing saved reports"
    )
    commands = parser.add_subparsers(dest="operation", required=True)

    def add_data_root_option(command: argparse.ArgumentParser) -> None:
        command.add_argument(
            "--data-root",
            default=argparse.SUPPRESS,
            help="workspace root containing saved reports",
        )

    summary = commands.add_parser("summary", help="summarize saved sequence catalogs")
    add_data_root_option(summary)
    summary.add_argument("--output", default="-", help="JSON result path, or - for stdout")

    verify = commands.add_parser("verify", help="reopen and verify every saved sequence object")
    add_data_root_option(verify)
    verify.add_argument("--output", default="-", help="JSON result path, or - for stdout")

    motifs = commands.add_parser(
        "motifs", help="aggregate exact motif changes across saved reports"
    )
    add_data_root_option(motifs)
    motifs.add_argument("--source-id", default=None)
    motifs.add_argument("--genome-build", default=None)
    motifs.add_argument("--change", choices=("created", "disrupted"), default=None)
    motifs.add_argument("--motif-contains", default=None)
    motifs.add_argument("--offset", type=int, default=0)
    motifs.add_argument("--limit", type=int, default=100)
    motifs.add_argument("--csv", action="store_true", help="emit aggregate CSV instead of JSON")
    motifs.add_argument("--output", default="-", help="JSON/CSV result path, or - for stdout")
    return parser


def _write_text(payload: str, output: str) -> None:
    if output == "-":
        sys.stdout.write(payload)
        return
    from ._safe_persistence import atomic_write_text

    atomic_write_text(output, payload, field="sequence review output")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        store = SequenceReviewStore(args.data_root)
        if args.operation == "summary":
            payload: Any = store.summary()
            write_json(payload, args.output)
        elif args.operation == "verify":
            payload = store.verify()
            write_json(payload, args.output)
        else:
            filters = {
                "source_id": args.source_id,
                "genome_build": args.genome_build,
                "change": args.change,
                "motif_contains": args.motif_contains,
            }
            if args.csv:
                _write_text(store.motifs_csv(**filters), args.output)
            else:
                write_json(
                    store.motif_activity(
                        **filters, offset=args.offset, limit=args.limit
                    ),
                    args.output,
                )
    except (OSError, StoreError, ValidationError, ValueError) as error:
        print(f"error: sequence review failed ({type(error).__name__}): {error}", file=sys.stderr)
        return 2
    return 0


__all__ = ["build_parser", "main"]

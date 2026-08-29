"""Demonstrate an ordered history of verified registry packages.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_demo.py \
        --registry ./review-output/registry-before \
        --registry ./review-output/registry-after \
        --destination ./review-output/history --format markdown
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="demonstrate an ordered verified registry history")
    parser.add_argument("--registry", action="append", required=True, type=Path, help="exact five-file registry directory; repeat in timeline order")
    parser.add_argument("--history-id", default=history.DEFAULT_HISTORY_ID)
    parser.add_argument("--destination", type=Path, default=None, help="optional exact four-file history directory")
    parser.add_argument("--allow-existing", action="store_true", help="replace an exact compatible destination")
    parser.add_argument("--format", choices=("summary", "json", "csv", "markdown"), default="summary")
    return parser


def _render(value: history.RegistryHistory, output_format: str) -> str:
    if output_format == "json":
        return history.history_json(value)
    if output_format == "csv":
        return history.history_csv(value)
    if output_format == "markdown":
        return history.render_markdown(value)
    return json.dumps(value.summary(), indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        value = history.build_history_from_directories(args.registry, history_id=args.history_id)
        if args.destination is not None:
            history.write_history(value, args.destination, overwrite=args.allow_existing)
            value = history.load_history(args.destination)
        sys.stdout.write(_render(value, args.format))
        return 0
    except (GlioError, OSError, ValueError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

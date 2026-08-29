"""Demonstrate bounded inspection of a registry-history package.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_query_demo.py \
        --input ./review-output/history --resource snapshots --format markdown
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_query as query
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="query an ordered verified registry history")
    parser.add_argument("--input", required=True, type=Path, help="exact four-file registry-history directory")
    parser.add_argument("--resource", choices=query.RESOURCES, default="summary")
    parser.add_argument("--state", choices=query.STATE_VALUES, default=None)
    parser.add_argument("--accepted", action="store_true", default=None)
    parser.add_argument("--release-ready", action="store_true", default=None)
    parser.add_argument("--ordinal", type=int, default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=query.DEFAULT_LIMIT)
    parser.add_argument("--format", choices=("json", "csv", "markdown"), default="json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        value = history.load_history(args.input)
        result = query.query_history(value, resource=args.resource, state=args.state, accepted=args.accepted, release_ready=args.release_ready, ordinal=args.ordinal, text=args.text, offset=args.offset, limit=args.limit)
        if args.format == "csv":
            sys.stdout.write(query.query_csv(result))
        elif args.format == "markdown":
            sys.stdout.write(query.render_query_markdown(result))
        else:
            sys.stdout.write(query.query_json(result))
        return 0
    except (GlioError, OSError, ValueError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

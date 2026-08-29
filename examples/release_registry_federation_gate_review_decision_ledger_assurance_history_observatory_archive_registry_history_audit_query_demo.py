"""Demonstrate bounded queries over a registry-history audit.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit_query_demo.py \
        --input ./review-output/history --resource passed --format markdown
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history as history
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit_query as query
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="query an observatory archive registry history audit")
    parser.add_argument("--input", required=True, type=Path, help="exact four-file registry-history directory")
    parser.add_argument("--resource", choices=query.RESOURCES, default="summary")
    status = parser.add_mutually_exclusive_group()
    status.add_argument("--passed", action="store_true", default=None)
    status.add_argument("--failed", action="store_true", default=None)
    parser.add_argument("--check-id", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=query.DEFAULT_LIMIT)
    parser.add_argument("--format", choices=("json", "csv", "markdown"), default="json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        value = audit.audit_history(history.load_history(args.input))
        passed = True if args.passed else False if args.failed else None
        result = query.query_audit(value, resource=args.resource, passed=passed, check_id=args.check_id, text=args.text, offset=args.offset, limit=args.limit)
        if args.format == "csv":
            sys.stdout.write(query.query_csv(result))
        elif args.format == "markdown":
            sys.stdout.write(query.render_query_markdown(result))
        else:
            sys.stdout.write(query.query_json(result))
        return 0 if value.accepted else 2
    except (GlioError, OSError, ValueError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

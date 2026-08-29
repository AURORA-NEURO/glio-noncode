"""Query a verified observatory archive registry diff audit.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_audit_query_demo.py \
        --baseline ./review-output/baseline-registry \
        --candidate ./review-output/candidate-registry \
        --resource evidence --check-id content-address --format markdown
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff as diff
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_audit as audit
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_audit_query as query
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="query a verified observatory archive registry diff audit")
    parser.add_argument("--baseline", required=True, type=Path, help="exact five-file baseline registry directory")
    parser.add_argument("--candidate", required=True, type=Path, help="exact five-file candidate registry directory")
    parser.add_argument("--diff-id", default=diff.DEFAULT_DIFF_ID)
    parser.add_argument("--resource", choices=query.RESOURCES, default="summary")
    parser.add_argument("--passed", action="store_true", default=None)
    parser.add_argument("--failed", action="store_true", default=None)
    parser.add_argument("--check-id", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=query.DEFAULT_LIMIT)
    parser.add_argument("--format", choices=("summary", "json", "csv", "markdown"), default="summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        comparison = diff.build_diff_from_directories(args.baseline, args.candidate, diff_id=args.diff_id)
        report = audit.audit_diff(comparison)
        passed = True if args.passed else False if args.failed else None
        value = query.query_audit(report, resource=args.resource, passed=passed, check_id=args.check_id, text=args.text, offset=args.offset, limit=args.limit)
        if args.format == "summary":
            sys.stdout.write(json.dumps(value.to_dict(), indent=2, sort_keys=True) + "\n")
        elif args.format == "csv":
            sys.stdout.write(query.query_csv(value))
        elif args.format == "markdown":
            sys.stdout.write(query.render_query_markdown(value))
        else:
            sys.stdout.write(query.query_json(value))
        return 0 if report.accepted else 2
    except (GlioError, OSError, ValueError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

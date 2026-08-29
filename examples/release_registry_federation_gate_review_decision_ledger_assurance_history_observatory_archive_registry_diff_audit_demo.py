"""Audit two verified observatory registry packages.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_audit_demo.py \
        --baseline ./review-output/baseline-registry \
        --candidate ./review-output/candidate-registry \
        --format markdown
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
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="audit a verified observatory archive registry diff")
    parser.add_argument("--baseline", required=True, type=Path, help="exact five-file baseline registry directory")
    parser.add_argument("--candidate", required=True, type=Path, help="exact five-file candidate registry directory")
    parser.add_argument("--diff-id", default=diff.DEFAULT_DIFF_ID)
    parser.add_argument("--format", choices=("summary", "json", "markdown"), default="summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        comparison = diff.build_diff_from_directories(args.baseline, args.candidate, diff_id=args.diff_id)
        value = audit.audit_diff(comparison)
        if args.format == "json":
            sys.stdout.write(audit.audit_json(value))
        elif args.format == "markdown":
            sys.stdout.write(audit.render_audit_markdown(value))
        else:
            sys.stdout.write(json.dumps(value.summary(), indent=2, sort_keys=True) + "\n")
        return 0 if value.accepted else 2
    except (GlioError, OSError, ValueError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

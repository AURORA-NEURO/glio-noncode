"""Demonstrate bounded inspection of a registry history release gate.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_query_demo.py \
        --input ./review-output/history --resource passed --format markdown
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate as gate
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_query as query
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="demonstrate bounded registry history release-gate inspection")
    parser.add_argument("--input", required=True, type=Path, help="exact four-file registry history directory")
    parser.add_argument("--resource", choices=query.RESOURCES, default="summary")
    parser.add_argument("--passed", choices=("true", "false"), default=None)
    parser.add_argument("--severity", choices=gate.SEVERITIES, default=None)
    parser.add_argument("--check-id", choices=gate.CHECK_IDS, default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=query.DEFAULT_LIMIT)
    parser.add_argument("--format", choices=("json", "csv", "markdown"), default="json")
    return parser


def _render(value: query.RegistryHistoryReleaseGateQueryResult, output_format: str) -> str:
    if output_format == "csv":
        return query.query_csv(value)
    if output_format == "markdown":
        return query.render_query_markdown(value)
    return query.query_json(value)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        passed = None if args.passed is None else args.passed == "true"
        gate_value = gate.evaluate_history_from_directory(args.input)
        value = query.query_gate(gate_value, resource=args.resource, passed=passed, severity=args.severity, check_id=args.check_id, text=args.text, offset=args.offset, limit=args.limit)
        sys.stdout.write(_render(value, args.format))
        return 0 if gate_value.accepted else 2
    except (GlioError, OSError, ValueError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

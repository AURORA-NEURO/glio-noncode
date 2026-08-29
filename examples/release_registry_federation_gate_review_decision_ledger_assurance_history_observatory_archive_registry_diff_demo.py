"""Demonstrate a deterministic diff between two verified registry packages.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff_demo.py \
        --baseline ./review-output/baseline-registry \
        --candidate ./review-output/candidate-registry \
        --resource items --format markdown
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_diff as diff
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="demonstrate a verified observatory archive registry diff")
    parser.add_argument("--baseline", required=True, type=Path, help="exact five-file baseline registry directory")
    parser.add_argument("--candidate", required=True, type=Path, help="exact five-file candidate registry directory")
    parser.add_argument("--diff-id", default=diff.DEFAULT_DIFF_ID)
    parser.add_argument("--resource", choices=diff.RegistryDiffQuery.RESOURCES, default="summary")
    parser.add_argument("--action", choices=tuple(item.value for item in diff.RegistryDiffAction), default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--format", choices=("summary", "json", "csv", "markdown"), default="summary")
    return parser


def _render(value: diff.RegistryDiff, resource: str, action: str | None, text: str | None, offset: int, limit: int, output_format: str) -> str:
    if resource == "summary" and action is None and text is None and offset == 0 and limit == 50:
        if output_format == "json":
            return diff.diff_json(value)
        if output_format == "csv":
            return diff.diff_csv(value)
        if output_format == "markdown":
            return diff.render_markdown(value)
        return json.dumps(value.summary(), indent=2, sort_keys=True) + "\n"
    result = diff.query_diff(value, resource=resource, action=action, text=text, offset=offset, limit=limit)
    if output_format == "csv":
        return diff.diff_query_csv(result)
    if output_format == "markdown":
        return diff.render_query_markdown(result)
    return diff.diff_query_json(result)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        value = diff.build_diff_from_directories(args.baseline, args.candidate, diff_id=args.diff_id)
        sys.stdout.write(_render(value, args.resource, args.action, args.text, args.offset, args.limit, args.format))
        return 0
    except (GlioError, OSError, ValueError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

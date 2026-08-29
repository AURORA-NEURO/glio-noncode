"""Demonstrate offline observatory archive verification and querying.

The archive is a deterministic single-file transport produced from an exact
five-file observatory package. The demo verifies the ZIP envelope, rehydrates
the embedded observatory package, and emits only public archive/query data.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_demo.py \
        --input ./review-output/observatory.zip \
        --resource checks \
        --severity required \
        --passed \
        --format markdown
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive as archive
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="demonstrate an offline observatory archive")
    parser.add_argument("--input", type=Path, required=True, help="single-file observatory archive")
    parser.add_argument("--resource", choices=archive.ArchiveQuery.RESOURCES, default="summary")
    parser.add_argument("--severity", choices=("required", "optional"), default=None)
    parser.add_argument("--passed", action="store_true", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--format", choices=("json", "csv", "markdown", "summary"), default="summary")
    parser.add_argument("--report", type=Path, default=None, help="optional path for the path-free report")
    return parser


def _write(report: str, destination: Path | None) -> None:
    if destination is None:
        sys.stdout.write(report)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report, encoding="utf-8")


def _summary(result: archive.ArchiveQueryResult) -> str:
    payload = {
        "archive_address": result.archive_address,
        "resource": result.query.resource,
        "severity": result.query.severity,
        "passed": result.query.passed,
        "text": result.query.text,
        "offset": result.query.offset,
        "limit": result.query.limit,
        "total_count": result.total_count,
        "returned_count": result.returned_count,
        "content_address": result.content_address,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _render(result: archive.ArchiveQueryResult, output_format: str) -> str:
    if output_format == "summary":
        return _summary(result)
    if output_format == "csv":
        return archive.query_csv(result)
    if output_format == "markdown":
        return archive.render_query_markdown(result)
    return archive.query_json(result) + "\n"


def run_demo(*, input_archive: Path, resource: str = "summary", severity: str | None = None, passed: bool | None = None, text: str | None = None, offset: int = 0, limit: int = 50) -> archive.ArchiveQueryResult:
    """Verify an archive and return one public query result."""

    value = archive.load_archive(input_archive)
    return archive.query_archive(value, resource=resource, severity=severity, passed=passed, text=text, offset=offset, limit=limit)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_demo(input_archive=args.input, resource=args.resource, severity=args.severity, passed=args.passed, text=args.text, offset=args.offset, limit=args.limit)
        _write(_render(result, args.format), args.report)
        return 0
    except (GlioError, OSError, ValueError) as error:
        _write(json.dumps({"error": str(error)}, sort_keys=True) + "\n", None)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Demonstrate bounded verification-check queries on a persisted observatory.

The input is an exact current-format assurance-history observatory package. The
loader verifies its canonical artifacts and independently recomputed checks
before this example selects a result window. The output contains only public
verification addresses, check projections, and query metadata; the input path
is never included in a report.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_verification_query_demo.py \
        --input ./demo-output/observatory \
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

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory as observatory
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="demonstrate bounded observatory verification queries")
    parser.add_argument("--input", type=Path, required=True, help="exact five-file observatory package")
    parser.add_argument("--resource", choices=observatory.VerificationQuery.RESOURCES, default="summary")
    parser.add_argument("--severity", choices=tuple(observatory.ObservatoryCheckSeverity), default=None)
    parser.add_argument("--passed", action="store_true", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--format", choices=("json", "csv", "markdown", "summary"), default="summary")
    parser.add_argument("--report", type=Path, default=None, help="optional report destination")
    return parser


def _write(report: str, destination: Path | None) -> None:
    if destination is None:
        sys.stdout.write(report)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report, encoding="utf-8")


def _summary(result: observatory.VerificationQueryResult) -> str:
    payload = {
        "verification_address": result.verification_address,
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


def _render(result: observatory.VerificationQueryResult, output_format: str) -> str:
    if output_format == "summary":
        return _summary(result)
    if output_format == "csv":
        return observatory.verification_query_csv(result)
    if output_format == "markdown":
        return observatory.render_verification_query_markdown(result)
    return observatory.verification_query_json(result) + "\n"


def run_demo(*, input_directory: Path, resource: str = "summary", severity: str | None = None, passed: bool | None = None, text: str | None = None, offset: int = 0, limit: int = 50) -> observatory.VerificationQueryResult:
    """Verify an observatory package and return one public query result."""

    verification = observatory.load_verification(input_directory)
    return observatory.query_verification(verification, resource=resource, severity=severity, passed=passed, text=text, offset=offset, limit=limit)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_demo(input_directory=args.input, resource=args.resource, severity=args.severity, passed=args.passed, text=args.text, offset=args.offset, limit=args.limit)
        _write(_render(result, args.format), args.report)
        return 0
    except (GlioError, OSError, ValueError) as error:
        _write(json.dumps({"error": str(error)}, sort_keys=True) + "\n", None)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

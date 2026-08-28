"""Demonstrate current-format decision-ledger assurance on downloaded data.

Usage:

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_demo.py \
        --ledger DIRECTORY --destination DIRECTORY

The script consumes an already persisted current-format review decision ledger.
It never clones a repository, searches for a framework, or converts an older
artifact shape. The output is a compact public summary; persisted packages are
written by the module's exact-file atomic writers.
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
from pathlib import Path
from typing import Any

from glio_noncode import assurance_history_series_release_registry_federation_gate_review as review
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance as assurance
from glio_noncode.errors import ValidationError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="assure a current release-registry federation review decision ledger")
    parser.add_argument("--ledger", required=True, metavar="DIRECTORY", help="current-format four-file decision ledger")
    parser.add_argument("--destination", required=True, metavar="DIRECTORY", help="new exact three-file assurance package")
    parser.add_argument("--baseline", default=None, metavar="DIRECTORY", help="optional exact assurance package for a diff")
    parser.add_argument("--diff-destination", default=None, metavar="DIRECTORY", help="optional exact two-file diff package")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    return parser


def _summary(value: assurance.DecisionLedgerAssuranceGate) -> dict[str, Any]:
    failed_findings = [item.kind for item in value.assurance.findings if not item.passed]
    failed_checks = [item.kind for item in value.gate.checks if not item.passed]
    return {
        "ledger_address": value.gate.ledger_address,
        "assurance_address": value.assurance.content_address,
        "gate_address": value.gate.content_address,
        "bundle_address": value.content_address,
        "assurance_state": value.assurance.state,
        "gate_state": value.gate.state,
        "accepted": value.gate.accepted,
        "release_ready": value.gate.release_ready,
        "finding_count": value.assurance.finding_count,
        "passed_finding_count": value.assurance.passed_count,
        "warning_finding_count": value.assurance.warning_count,
        "blocker_finding_count": value.assurance.blocker_count,
        "check_count": value.gate.check_count,
        "passed_check_count": value.gate.passed_count,
        "warning_check_count": value.gate.warning_count,
        "blocker_check_count": value.gate.blocker_count,
        "source_accepted": value.gate.source_accepted,
        "source_release_ready": value.gate.source_release_ready,
        "failed_findings": failed_findings,
        "failed_checks": failed_checks,
        "package_files": list(assurance.FILES),
    }


def _markdown(value: assurance.DecisionLedgerAssuranceGate, diff: assurance.AssuranceDiff | None) -> str:
    summary = _summary(value)
    lines = ["# Release-Registry Decision-Ledger Assurance Demo", "", "## Result", ""]
    lines.extend(f"- {key}: `{summary[key]}`" for key in sorted(summary))
    lines.extend(["", "## Findings", ""])
    lines.extend(f"- `{item.kind}` / `{item.plane}`: `{item.severity}`, passed=`{item.passed}`" for item in value.assurance.findings)
    lines.extend(["", "## Gate checks", ""])
    lines.extend(f"- `{item.kind}` / `{item.plane}`: passed=`{item.passed}`, required=`{item.required}`" for item in value.gate.checks)
    if diff is not None:
        lines.extend(["", "## Diff", "", f"- state: `{diff.state}`", f"- changed: `{diff.changed_count}`", f"- improved: `{diff.improved_count}`", f"- regressed: `{diff.regressed_count}`"])
    return "\n".join(lines) + "\n"


def run(arguments: argparse.Namespace) -> int:
    ledger = review.load_decision_ledger(Path(arguments.ledger))
    value = assurance.build_assurance_gate(ledger)
    assurance.write_assurance_gate(value, Path(arguments.destination))
    diff = None
    if arguments.baseline:
        if not arguments.diff_destination:
            raise ValidationError("--diff-destination is required with --baseline")
        baseline = assurance.load_assurance_gate(Path(arguments.baseline))
        diff = assurance.build_diff(baseline, value)
        assurance.write_diff(diff, Path(arguments.diff_destination))
    if arguments.format == "markdown":
        print(_markdown(value, diff), end="")
    else:
        payload = _summary(value)
        if diff is not None:
            payload["diff"] = diff.summary()
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return 0 if value.gate.release_ready else 2


def main() -> int:
    try:
        return run(_parser().parse_args())
    except (OSError, ValidationError, ValueError) as error:
        print(json.dumps({"error": str(error)}, sort_keys=True, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Demonstrate independent auditing of a registry-history package.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_audit_demo.py \
        --input ./review-output/history --format markdown
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
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="audit an ordered verified registry history")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="exact four-file registry-history directory")
    source.add_argument("--mapping", type=Path, help="public history JSON mapping")
    parser.add_argument("--format", choices=("json", "markdown", "summary"), default="summary")
    return parser


def _render(value: audit.RegistryHistoryAudit, output_format: str) -> str:
    if output_format == "json":
        return audit.audit_json(value)
    if output_format == "markdown":
        return audit.render_audit_markdown(value)
    return json.dumps(value.summary(), indent=2, sort_keys=True) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.input is not None:
            value = audit.audit_history(history.load_history(args.input))
        else:
            mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
            value = audit.audit_from_mapping(mapping)
        sys.stdout.write(_render(value, args.format))
        return 0 if value.accepted else 2
    except (GlioError, OSError, ValueError, json.JSONDecodeError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

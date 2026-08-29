"""Demonstrate durable packaging and replay of a history release gate.

Example::

    python examples/release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package_demo.py \
        --input ./review-output/history --destination ./review-output/release-gate --format manifest
"""

from __future__ import annotations

# ruff: noqa: E501, I001

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate as gate
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_gate_package as package
from glio_noncode.errors import GlioError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="demonstrate a durable registry history release gate package")
    parser.add_argument("--input", required=True, type=Path, help="exact four-file registry history directory")
    parser.add_argument("--destination", required=True, type=Path, help="exact three-file package destination")
    parser.add_argument("--allow-existing", action="store_true")
    parser.add_argument("--format", choices=("json", "manifest", "summary"), default="summary")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        value = gate.evaluate_history_from_directory(args.input)
        package.write_package(value, args.destination, overwrite=args.allow_existing)
        replayed = package.load_package(args.destination)
        if args.format == "json":
            sys.stdout.write(gate.gate_json(replayed))
        elif args.format == "manifest":
            sys.stdout.write(package.package_manifest_json(replayed))
        else:
            sys.stdout.write(json.dumps(replayed.summary(), indent=2, sort_keys=True) + "\n")
        return 0 if replayed.accepted else 2
    except (GlioError, OSError, ValueError) as error:
        sys.stdout.write(json.dumps({"error": str(error)}, sort_keys=True) + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

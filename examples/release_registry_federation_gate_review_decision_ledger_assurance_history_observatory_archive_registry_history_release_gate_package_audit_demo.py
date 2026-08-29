"""Audit a persisted release-gate package without trusting its producer."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_gate_package_audit_json,
    audit_assurance_history_observatory_archive_registry_history_release_gate_package_directory,
    render_assurance_history_observatory_archive_registry_history_release_gate_package_audit_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="three-file release-gate package directory")
    parser.add_argument("--format", choices=("json", "markdown", "summary"), default="summary")
    args = parser.parse_args()
    value = (
        audit_assurance_history_observatory_archive_registry_history_release_gate_package_directory(args.input)
    )
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_gate_package_audit_json(value))
    elif args.format == "markdown":
        print(
            render_assurance_history_observatory_archive_registry_history_release_gate_package_audit_markdown(value),
            end="",
        )
    else:
        print(json.dumps(value.summary(), indent=2, sort_keys=True))
    return 0 if value.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())

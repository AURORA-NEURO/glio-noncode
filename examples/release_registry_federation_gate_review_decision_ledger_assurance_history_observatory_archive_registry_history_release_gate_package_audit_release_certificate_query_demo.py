"""Inspect the release-certificate decision for a downloaded package."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_query_json,
    query_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_directory,
    render_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_query_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="three-file release-gate package directory")
    parser.add_argument("--resource", choices=("summary", "checks", "passed", "failed", "holds", "blocking", "evidence"), default="summary")
    parser.add_argument("--severity", choices=("hold", "blocking"), default=None)
    parser.add_argument("--check-id", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--format", choices=("json", "markdown", "summary"), default="summary")
    args = parser.parse_args()
    value = query_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_directory(
        args.input,
        resource=args.resource,
        severity=args.severity,
        check_id=args.check_id,
        text=args.text,
        offset=args.offset,
        limit=args.limit,
    )
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_query_json(value))
    elif args.format == "markdown":
        print(
            render_assurance_history_observatory_archive_registry_history_release_gate_package_audit_release_certificate_query_markdown(value),
            end="",
        )
    else:
        print(json.dumps(value.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

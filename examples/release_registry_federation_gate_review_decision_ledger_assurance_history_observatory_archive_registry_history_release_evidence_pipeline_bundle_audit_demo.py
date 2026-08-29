"""Audit a durable five-file release-evidence bundle from downloaded data."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_json,
    audit_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_directory,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="durable five-file release-evidence bundle directory")
    parser.add_argument("--format", choices=("json", "markdown", "summary"), default="markdown")
    args = parser.parse_args()
    value = audit_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_directory(args.input)
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_json(value))
    elif args.format == "summary":
        print(json.dumps(value.summary(), indent=2, sort_keys=True))
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_markdown(value), end="")
    return 0 if value.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())

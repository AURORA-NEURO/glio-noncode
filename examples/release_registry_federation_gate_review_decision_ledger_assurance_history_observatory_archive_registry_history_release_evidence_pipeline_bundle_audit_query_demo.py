"""Query bundle-audit checks from a durable release-evidence bundle."""

from __future__ import annotations

# ruff: noqa: E501
import argparse

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_query_csv,
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_query_json,
    query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_directory,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_query_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="durable five-file release-evidence bundle directory")
    parser.add_argument("--resource", choices=("summary", "checks", "passed", "failed", "evidence"), default="checks")
    parser.add_argument("--check-id", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--format", choices=("json", "csv", "markdown"), default="markdown")
    args = parser.parse_args()
    value = query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_directory(
        args.input,
        resource=args.resource,
        check_id=args.check_id,
        text=args.text,
    )
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_query_json(value))
    elif args.format == "csv":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_query_csv(value), end="")
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_audit_query_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

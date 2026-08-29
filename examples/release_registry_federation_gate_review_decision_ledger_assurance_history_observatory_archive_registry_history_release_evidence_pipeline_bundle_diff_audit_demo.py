"""Audit a release-evidence bundle diff produced from downloaded data."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_json,
    audit_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="verified baseline five-file bundle directory")
    parser.add_argument("--candidate", required=True, help="verified candidate five-file bundle directory")
    parser.add_argument("--diff-id", default=None)
    parser.add_argument("--format", choices=("json", "markdown", "summary"), default="markdown")
    args = parser.parse_args()
    kwargs = {} if args.diff_id is None else {"diff_id": args.diff_id}
    diff = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff(args.baseline, args.candidate, **kwargs)
    value = audit_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff(diff)
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_json(value))
    elif args.format == "summary":
        print(json.dumps(value.summary(), indent=2, sort_keys=True))
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

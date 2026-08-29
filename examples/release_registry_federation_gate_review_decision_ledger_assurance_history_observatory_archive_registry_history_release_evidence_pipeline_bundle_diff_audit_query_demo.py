"""Query checks from a release-evidence bundle diff audit."""

from __future__ import annotations

# ruff: noqa: E501
import argparse

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_query_csv,
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_query_json,
    query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_diff,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_query_markdown,
)
from glio_noncode import (
    assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff as diff,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="verified baseline five-file bundle directory")
    parser.add_argument("--candidate", required=True, help="verified candidate five-file bundle directory")
    parser.add_argument("--resource", choices=("summary", "checks", "passed", "failed", "evidence"), default="summary")
    parser.add_argument("--passed", action="store_true", default=None)
    parser.add_argument("--failed", action="store_false", dest="passed", default=None)
    parser.add_argument("--check-id", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--format", choices=("json", "csv", "markdown"), default="markdown")
    args = parser.parse_args()
    value = query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_diff(
        diff.build_diff(args.baseline, args.candidate),
        resource=args.resource,
        passed=args.passed,
        check_id=args.check_id,
        text=args.text,
        offset=args.offset,
        limit=args.limit,
    )
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_query_json(value))
    elif args.format == "csv":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_query_csv(value), end="")
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_audit_query_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

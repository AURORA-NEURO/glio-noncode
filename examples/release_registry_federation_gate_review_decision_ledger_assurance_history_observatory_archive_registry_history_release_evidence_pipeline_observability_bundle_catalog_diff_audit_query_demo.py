"""Inspect the independent audit checks for a catalog comparison."""

from __future__ import annotations

# ruff: noqa: E501
import argparse

from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog import (
    build_catalog_from_directories,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff import (
    diff_catalogs,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff_audit_query import (
    RESOURCES,
    query_csv,
    query_diff,
    query_json,
    render_query_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left-label", action="append", required=True)
    parser.add_argument("--left-directory", action="append", required=True)
    parser.add_argument("--right-label", action="append", required=True)
    parser.add_argument("--right-directory", action="append", required=True)
    parser.add_argument("--left-catalog-id", default="glio-noncode-observability-bundle-catalog-left")
    parser.add_argument("--right-catalog-id", default="glio-noncode-observability-bundle-catalog-right")
    parser.add_argument("--diff-id", default="glio-noncode-observability-bundle-catalog-diff")
    parser.add_argument("--resource", choices=RESOURCES, default="passed")
    parser.add_argument("--passed", action="store_true", dest="passed", default=None)
    parser.add_argument("--failed", action="store_false", dest="passed")
    parser.add_argument("--check-id", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--format", choices=("json", "csv", "markdown"), default="markdown")
    args = parser.parse_args()
    if len(args.left_label) != len(args.left_directory):
        parser.error("--left-label and --left-directory must be supplied in equal counts")
    if len(args.right_label) != len(args.right_directory):
        parser.error("--right-label and --right-directory must be supplied in equal counts")
    left = build_catalog_from_directories(tuple(zip(args.left_label, args.left_directory, strict=True)), catalog_id=args.left_catalog_id)
    right = build_catalog_from_directories(tuple(zip(args.right_label, args.right_directory, strict=True)), catalog_id=args.right_catalog_id)
    diff = diff_catalogs(left, right, diff_id=args.diff_id)
    value = query_diff(diff, resource=args.resource, passed=args.passed, check_id=args.check_id, text=args.text, offset=args.offset, limit=args.limit)
    if args.format == "json":
        print(query_json(value))
    elif args.format == "csv":
        print(query_csv(value), end="")
    else:
        print(render_query_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

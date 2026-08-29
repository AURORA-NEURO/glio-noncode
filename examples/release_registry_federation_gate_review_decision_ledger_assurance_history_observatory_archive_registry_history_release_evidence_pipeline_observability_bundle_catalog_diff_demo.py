"""Compare two verified observability-bundle catalogs by stable labels."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog import (
    build_catalog_from_directories,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff import (
    diff_catalogs,
    diff_csv,
    diff_json,
    render_diff_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left-label", action="append", required=True, help="path-free label in the baseline catalog")
    parser.add_argument("--left-directory", action="append", required=True, help="verified handoff directory in the baseline catalog")
    parser.add_argument("--right-label", action="append", required=True, help="path-free label in the candidate catalog")
    parser.add_argument("--right-directory", action="append", required=True, help="verified handoff directory in the candidate catalog")
    parser.add_argument("--left-catalog-id", default="glio-noncode-observability-bundle-catalog-left")
    parser.add_argument("--right-catalog-id", default="glio-noncode-observability-bundle-catalog-right")
    parser.add_argument("--diff-id", default="glio-noncode-observability-bundle-catalog-diff")
    parser.add_argument("--format", choices=("json", "csv", "markdown", "summary"), default="summary")
    args = parser.parse_args()
    if len(args.left_label) != len(args.left_directory):
        parser.error("--left-label and --left-directory must be supplied in equal counts")
    if len(args.right_label) != len(args.right_directory):
        parser.error("--right-label and --right-directory must be supplied in equal counts")
    left = build_catalog_from_directories(tuple(zip(args.left_label, args.left_directory, strict=True)), catalog_id=args.left_catalog_id)
    right = build_catalog_from_directories(tuple(zip(args.right_label, args.right_directory, strict=True)), catalog_id=args.right_catalog_id)
    value = diff_catalogs(left, right, diff_id=args.diff_id)
    if args.format == "json":
        print(diff_json(value))
    elif args.format == "csv":
        print(diff_csv(value), end="")
    elif args.format == "markdown":
        print(render_diff_markdown(value), end="")
    else:
        print(json.dumps(value.summary(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

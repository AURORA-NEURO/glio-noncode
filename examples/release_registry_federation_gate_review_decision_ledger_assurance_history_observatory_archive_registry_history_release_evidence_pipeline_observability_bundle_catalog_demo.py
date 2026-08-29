"""Build a deterministic catalog from verified observability handoff directories."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_csv,
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_json,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_from_directories,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", action="append", required=True, help="path-free label for one handoff directory; repeat for multiple entries")
    parser.add_argument("--directory", action="append", required=True, help="verified nine-file observability handoff directory; repeat in label order")
    parser.add_argument("--catalog-id", default="glio-noncode-observability-bundle-catalog")
    parser.add_argument("--format", choices=("json", "csv", "markdown", "summary"), default="markdown")
    args = parser.parse_args()
    if len(args.label) != len(args.directory):
        parser.error("--label and --directory must be supplied in equal counts")
    value = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_from_directories(tuple(zip(args.label, args.directory, strict=True)), catalog_id=args.catalog_id)
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_json(value))
    elif args.format == "csv":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_csv(value), end="")
    elif args.format == "summary":
        print(json.dumps(value.summary(), indent=2, sort_keys=True))
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

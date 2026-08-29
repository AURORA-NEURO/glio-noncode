"""Query a verified observability handoff catalog with bounded filters."""

from __future__ import annotations

# ruff: noqa: E501
import argparse

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_query_csv,
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_query_json,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_from_directories,
    query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_query_markdown,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog import (
    STATES,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_query import (
    RESOURCES,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", action="append", required=True, help="path-free label for one handoff directory; repeat for multiple entries")
    parser.add_argument("--directory", action="append", required=True, help="verified nine-file observability handoff directory; repeat in label order")
    parser.add_argument("--catalog-id", default="glio-noncode-observability-bundle-catalog")
    parser.add_argument("--resource", choices=RESOURCES, default="ready")
    parser.add_argument("--accepted", action="store_true", default=None)
    parser.add_argument("--rejected", action="store_false", dest="accepted", default=None)
    parser.add_argument("--state", choices=STATES, default=None)
    parser.add_argument("--pipeline-state", choices=("ready", "held", "blocked"), default=None)
    parser.add_argument("--observability-state", choices=("ready", "held", "blocked"), default=None)
    parser.add_argument("--audit-state", choices=("complete", "incomplete"), default=None)
    parser.add_argument("--entry-label", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--format", choices=("json", "csv", "markdown"), default="markdown")
    args = parser.parse_args()
    if len(args.label) != len(args.directory):
        parser.error("--label and --directory must be supplied in equal counts")
    catalog = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_from_directories(tuple(zip(args.label, args.directory, strict=True)), catalog_id=args.catalog_id)
    value = query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog(catalog, resource=args.resource, accepted=args.accepted, state=args.state, pipeline_state=args.pipeline_state, observability_state=args.observability_state, audit_state=args.audit_state, label=args.entry_label, text=args.text, offset=args.offset, limit=args.limit)
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_query_json(value))
    elif args.format == "csv":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_query_csv(value), end="")
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_query_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

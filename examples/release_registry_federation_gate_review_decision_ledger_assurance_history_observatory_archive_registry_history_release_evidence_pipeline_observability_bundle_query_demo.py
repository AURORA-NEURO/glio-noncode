"""Query a verified persisted release-evidence observability handoff."""

from __future__ import annotations

# ruff: noqa: E501
import argparse

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_query_json,
    query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_directory,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_query_markdown,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_query import (
    RESOURCES,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="verified persisted observability handoff directory")
    parser.add_argument("--resource", choices=RESOURCES, default="passed")
    parser.add_argument("--passed", action="store_true", default=None)
    parser.add_argument("--failed", action="store_false", dest="passed", default=None)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--event-type", dest="event_type", default=None)
    parser.add_argument("--metric-name", dest="metric_name", default=None)
    parser.add_argument("--plane", default=None)
    parser.add_argument("--check-id", dest="check_id", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    value = query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_directory(
        args.input,
        resource=args.resource,
        passed=args.passed,
        stage=args.stage,
        state=args.state,
        event_type=args.event_type,
        metric_name=args.metric_name,
        plane=args.plane,
        check_id=args.check_id,
        text=args.text,
        offset=args.offset,
        limit=args.limit,
    )
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_query_json(value))
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_query_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

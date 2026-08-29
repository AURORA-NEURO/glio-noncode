"""Compare two verified persisted observability handoffs from downloaded data."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_csv,
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_json,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="verified baseline nine-file observability handoff directory")
    parser.add_argument("--candidate", required=True, help="verified candidate nine-file observability handoff directory")
    parser.add_argument("--diff-id", default=None)
    parser.add_argument("--format", choices=("json", "csv", "markdown", "summary"), default="markdown")
    args = parser.parse_args()
    kwargs = {} if args.diff_id is None else {"diff_id": args.diff_id}
    value = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff(
        args.baseline,
        args.candidate,
        **kwargs,
    )
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_json(value))
    elif args.format == "csv":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_csv(value), end="")
    elif args.format == "summary":
        print(json.dumps(value.summary(), indent=2, sort_keys=True))
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_diff_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

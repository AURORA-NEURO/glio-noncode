"""Query semantic and artifact transitions from verified release-evidence bundles."""

from __future__ import annotations

# ruff: noqa: E501
import argparse

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_query_csv,
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_query_json,
    query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_directories,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_query_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="verified baseline five-file bundle directory")
    parser.add_argument("--candidate", required=True, help="verified candidate five-file bundle directory")
    parser.add_argument("--resource", choices=("summary", "fields", "files", "changed", "unchanged", "evidence"), default="summary")
    parser.add_argument("--action", choices=("added", "removed", "changed", "unchanged"), default=None)
    parser.add_argument("--name", default=None, help="bundle artifact name, such as pipeline.json")
    parser.add_argument("--changed-field", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--format", choices=("json", "csv", "markdown"), default="markdown")
    args = parser.parse_args()
    value = query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_directories(
        args.baseline,
        args.candidate,
        resource=args.resource,
        action=args.action,
        name=args.name,
        changed_field=args.changed_field,
        text=args.text,
        offset=args.offset,
        limit=args.limit,
    )
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_query_json(value))
    elif args.format == "csv":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_query_csv(value), end="")
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_diff_query_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

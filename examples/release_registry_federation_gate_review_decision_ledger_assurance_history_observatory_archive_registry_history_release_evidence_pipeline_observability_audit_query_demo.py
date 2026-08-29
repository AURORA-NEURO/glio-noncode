"""Query independent observability-audit checks from downloaded history."""

from __future__ import annotations

# ruff: noqa: E501
import argparse

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_query_json,
    query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_directory,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_query_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="downloaded history directory")
    parser.add_argument("--resource", choices=("summary", "checks", "passed", "failed", "evidence"), default="failed")
    parser.add_argument("--passed", action="store_true", default=None)
    parser.add_argument("--failed", action="store_false", dest="passed", default=None)
    parser.add_argument("--check-id", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    value = query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_directory(
        args.input,
        resource=args.resource,
        passed=args.passed,
        check_id=args.check_id,
        text=args.text,
        offset=args.offset,
        limit=args.limit,
    )
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_query_json(value))
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_audit_query_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

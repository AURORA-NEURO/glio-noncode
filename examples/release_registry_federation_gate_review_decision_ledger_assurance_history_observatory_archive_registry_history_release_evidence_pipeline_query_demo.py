"""Inspect stages and evidence from a downloaded-history release receipt."""

from __future__ import annotations

# ruff: noqa: E501
import argparse

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query_json,
    query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_directory,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="downloaded history directory")
    parser.add_argument("--resource", choices=("summary", "stages", "decisions", "evidence"), default="stages")
    parser.add_argument("--accepted", action="store_true", default=None)
    parser.add_argument("--rejected", action="store_true", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--stage", default=None)
    parser.add_argument("--text", default=None)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    accepted = True if args.accepted else False if args.rejected else None
    value = query_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_directory(
        args.input,
        resource=args.resource,
        accepted=accepted,
        state=args.state,
        stage=args.stage,
        text=args.text,
        offset=args.offset,
        limit=args.limit,
    )
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query_json(value))
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_query_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

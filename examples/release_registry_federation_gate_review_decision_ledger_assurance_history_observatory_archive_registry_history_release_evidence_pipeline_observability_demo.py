"""Inspect timestamp-free events and metrics from downloaded history."""

from __future__ import annotations

# ruff: noqa: E501
import argparse

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_csv,
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_json,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="downloaded history directory")
    parser.add_argument("--format", choices=("json", "csv", "markdown", "summary"), default="markdown")
    args = parser.parse_args()
    pipeline = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline(args.input)
    value = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability(pipeline)
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_json(value))
    elif args.format == "csv":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_csv(value), end="")
    elif args.format == "summary":
        print(value.summary())
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_markdown(value), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

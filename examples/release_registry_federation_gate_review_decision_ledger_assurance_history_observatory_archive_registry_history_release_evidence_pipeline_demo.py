"""Run the complete release-evidence pipeline on downloaded history data."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_json,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="downloaded history directory")
    parser.add_argument("--destination", default=None, help="optional durable three-file package directory")
    parser.add_argument("--allow-existing", action="store_true")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args()
    value = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline(
        args.input,
        args.destination,
        overwrite=args.allow_existing,
    )
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_json(value))
    else:
        print(json.dumps(value.summary(), indent=2, sort_keys=True))
    return 0 if value.accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())

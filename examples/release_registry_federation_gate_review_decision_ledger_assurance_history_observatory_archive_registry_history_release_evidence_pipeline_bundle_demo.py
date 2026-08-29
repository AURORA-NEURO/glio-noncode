"""Create and verify a portable evidence bundle from downloaded history."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_json,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline,
    load_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle,
    write_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="downloaded history directory")
    parser.add_argument("--destination", required=True, help="portable five-file evidence bundle directory")
    parser.add_argument("--allow-existing", action="store_true")
    parser.add_argument("--format", choices=("json", "summary"), default="summary")
    args = parser.parse_args()
    pipeline = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline(args.input)
    write_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle(
        pipeline,
        args.destination,
        overwrite=args.allow_existing,
    )
    value = load_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle(args.destination)
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_bundle_json(value))
    else:
        print(json.dumps(value.summary(), indent=2, sort_keys=True))
    return 0 if value.pipeline_accepted else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Materialize and verify a release-evidence observability handoff bundle."""

from __future__ import annotations

# ruff: noqa: E501
import argparse

from glio_noncode import (
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_json,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle,
    load_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle,
    write_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline import (
    build_pipeline,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="downloaded history directory")
    parser.add_argument("--destination", required=True, help="exact-member handoff directory")
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()
    pipeline = build_pipeline(args.input)
    value = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle(pipeline)
    write_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle(pipeline, args.destination, overwrite=args.allow_existing)
    verified = load_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle(args.destination)
    print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_json(verified))
    return 0 if verified.audit_accepted and verified.content_address == value.content_address else 2


if __name__ == "__main__":
    raise SystemExit(main())

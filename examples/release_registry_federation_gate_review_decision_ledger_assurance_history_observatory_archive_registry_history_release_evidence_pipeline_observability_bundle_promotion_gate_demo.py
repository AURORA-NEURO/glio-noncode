"""Evaluate whether a verified observability handoff may be promoted."""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode import (
    ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE_OBSERVABILITY_BUNDLE_PROMOTION_GATE_DEFAULT_ALLOWED_DIFF_STATES,
    ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE_OBSERVABILITY_BUNDLE_PROMOTION_GATE_DEFAULT_MAX_CHANGED_FIELDS,
    ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE_OBSERVABILITY_BUNDLE_PROMOTION_GATE_DEFAULT_MAX_CHANGED_ITEMS,
    AssuranceHistoryObservatoryArchiveRegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy,
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_csv,
    assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_json,
    build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_from_directories,
    render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="verified baseline nine-file observability handoff directory")
    parser.add_argument("--candidate", required=True, help="verified candidate nine-file observability handoff directory")
    parser.add_argument("--policy-id", default="glio-noncode-observability-bundle-promotion-policy")
    parser.add_argument("--allowed-diff-state", action="append", choices=("unchanged", "improved", "regressed", "mixed"), default=None)
    parser.add_argument("--max-changed-items", type=int, default=ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE_OBSERVABILITY_BUNDLE_PROMOTION_GATE_DEFAULT_MAX_CHANGED_ITEMS)
    parser.add_argument("--max-changed-fields", type=int, default=ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE_OBSERVABILITY_BUNDLE_PROMOTION_GATE_DEFAULT_MAX_CHANGED_FIELDS)
    parser.add_argument("--format", choices=("json", "csv", "markdown", "summary"), default="markdown")
    args = parser.parse_args()
    policy = AssuranceHistoryObservatoryArchiveRegistryHistoryReleaseEvidencePipelineObservabilityBundlePromotionPolicy(
        policy_id=args.policy_id,
        allowed_diff_states=tuple(args.allowed_diff_state) if args.allowed_diff_state is not None else ASSURANCE_HISTORY_OBSERVATORY_ARCHIVE_REGISTRY_HISTORY_RELEASE_EVIDENCE_PIPELINE_OBSERVABILITY_BUNDLE_PROMOTION_GATE_DEFAULT_ALLOWED_DIFF_STATES,
        max_changed_items=args.max_changed_items,
        max_changed_fields=args.max_changed_fields,
    )
    value = build_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_from_directories(args.baseline, args.candidate, policy=policy)
    if args.format == "json":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_json(value))
    elif args.format == "csv":
        print(assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_csv(value), end="")
    elif args.format == "summary":
        print(json.dumps(value.summary(), indent=2, sort_keys=True))
    else:
        print(render_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_promotion_gate_markdown(value), end="")
    return 0 if value.release_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())

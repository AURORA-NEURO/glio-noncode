"""Run the catalog report, assurance, query, and promotion flow on handoffs.

The example deliberately accepts ordinary downloaded handoff directories.  A
baseline and candidate may point at the same downloaded handoff when testing
the control plane; labels remain distinct catalog identities and no path is
placed into any emitted public document.
"""

from __future__ import annotations

# ruff: noqa: E501
import argparse
import json

from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog import (
    build_catalog_from_directories,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_diff import (
    build_diff,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate import (
    build_promotion_gate,
    gate_csv,
    gate_json,
    render_gate_markdown,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit import (
    audit_gate as audit_promotion_gate,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit import (
    audit_json as promotion_audit_json,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit import (
    render_audit_markdown as render_promotion_audit_markdown,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_audit_query import (
    query_audit as query_promotion_audit,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_query import (
    query_gate,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet import (
    build_release_packet,
    packet_csv,
    packet_json,
    render_packet_markdown,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_query import (
    query_packet,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report import (
    build_report,
    render_report_markdown,
    report_csv,
    report_json,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report_audit import (
    audit_json,
    audit_report,
    render_audit_markdown,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report_audit_query import (
    query_audit,
)
from glio_noncode.assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_report_query import (
    query_report,
)


def _pairs(labels: list[str], directories: list[str], parser: argparse.ArgumentParser, name: str) -> tuple[tuple[str, str], ...]:
    if not labels or len(labels) != len(directories):
        parser.error(f"{name} labels and directories must be supplied in equal non-zero counts")
    return tuple(zip(labels, directories, strict=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-label", action="append", required=True)
    parser.add_argument("--baseline-directory", action="append", required=True)
    parser.add_argument("--candidate-label", action="append", required=True)
    parser.add_argument("--candidate-directory", action="append", required=True)
    parser.add_argument("--baseline-catalog-id", default="glio-noncode-demo-baseline")
    parser.add_argument("--candidate-catalog-id", default="glio-noncode-demo-candidate")
    parser.add_argument("--diff-id", default="glio-noncode-demo-catalog-diff")
    parser.add_argument("--report-id", default="glio-noncode-demo-catalog-report")
    parser.add_argument("--gate-id", default="glio-noncode-demo-catalog-promotion-gate")
    parser.add_argument("--packet-id", default="glio-noncode-demo-catalog-promotion-release-packet")
    parser.add_argument("--resource", choices=("summary", "rows", "accepted", "rejected", "ready", "held", "blocked", "states", "evidence"), default="ready")
    parser.add_argument("--audit-resource", choices=("summary", "checks", "passed", "failed", "evidence"), default="failed")
    parser.add_argument("--gate-resource", choices=("summary", "checks", "passed", "failed", "blocking", "holds", "evidence"), default="failed")
    parser.add_argument("--promotion-audit-resource", choices=("summary", "checks", "passed", "failed", "evidence"), default="failed")
    parser.add_argument("--packet-resource", choices=("summary", "actions", "gate-actions", "audit-actions", "blocking", "holds", "evidence"), default="actions")
    parser.add_argument("--format", choices=("summary", "json", "csv", "markdown"), default="summary")
    args = parser.parse_args()

    baseline = build_catalog_from_directories(_pairs(args.baseline_label, args.baseline_directory, parser, "baseline"), catalog_id=args.baseline_catalog_id)
    candidate = build_catalog_from_directories(_pairs(args.candidate_label, args.candidate_directory, parser, "candidate"), catalog_id=args.candidate_catalog_id)
    diff = build_diff(baseline, candidate, diff_id=args.diff_id)
    report = build_report(candidate, report_id=args.report_id)
    report_assurance = audit_report(report)
    promotion = build_promotion_gate(diff, report, gate_id=args.gate_id)
    promotion_assurance = audit_promotion_gate(promotion)
    release_packet = build_release_packet(promotion, promotion_assurance, packet_id=args.packet_id)
    report_page = query_report(report, resource=args.resource, limit=report.entry_count or 1)
    assurance_page = query_audit(report_assurance, resource=args.audit_resource, limit=12)
    gate_page = query_gate(promotion, resource=args.gate_resource, limit=15)
    promotion_audit_page = query_promotion_audit(promotion_assurance, resource=args.promotion_audit_resource, limit=12)
    release_packet_page = query_packet(release_packet, resource=args.packet_resource, limit=27)

    if args.format == "json":
        print(json.dumps({"catalogs": {"baseline": baseline.summary(), "candidate": candidate.summary()}, "diff": diff.summary(), "report": json.loads(report_json(report)), "report_audit": json.loads(audit_json(report_assurance)), "promotion_gate": json.loads(gate_json(promotion)), "promotion_gate_audit": json.loads(promotion_audit_json(promotion_assurance)), "release_packet": json.loads(packet_json(release_packet)), "report_query": report_page.to_dict(), "report_audit_query": assurance_page.to_dict(), "gate_query": gate_page.to_dict(), "promotion_gate_audit_query": promotion_audit_page.to_dict(), "release_packet_query": release_packet_page.to_dict()}, indent=2, sort_keys=True))
    elif args.format == "csv":
        print(report_csv(report), end="")
        print(gate_csv(promotion), end="")
        print(packet_csv(release_packet), end="")
    elif args.format == "markdown":
        print(render_report_markdown(report), end="")
        print(render_audit_markdown(report_assurance), end="")
        print(render_gate_markdown(promotion), end="")
        print(render_promotion_audit_markdown(promotion_assurance), end="")
        print(render_packet_markdown(release_packet), end="")
    else:
        print(json.dumps({"baseline_entries": baseline.entry_count, "candidate_entries": candidate.entry_count, "diff_state": diff.state, "added": diff.added_count, "removed": diff.removed_count, "changed": diff.changed_count, "accepted": report.accepted_count, "ready": report.ready_count, "rejected": report.rejected_count, "acceptance_basis_points": report.acceptance_basis_points, "readiness_basis_points": report.readiness_basis_points, "report_audit": {"state": report_assurance.state, "passed": report_assurance.passed_count, "failed": report_assurance.failed_count}, "promotion_gate": {"state": promotion.state, "accepted": promotion.accepted, "release_ready": promotion.release_ready, "passed": promotion.passed_count, "failed": promotion.failed_count}, "promotion_gate_audit": {"state": promotion_assurance.state, "passed": promotion_assurance.passed_count, "failed": promotion_assurance.failed_count}, "release_packet": {"state": release_packet.state, "decision": release_packet.decision, "release_ready": release_packet.release_ready, "checks": [release_packet.passed_count, release_packet.check_count], "actions": release_packet.action_count}, "queries": {"report": [report_page.total_count, report_page.returned_count], "report_audit": [assurance_page.total_count, assurance_page.returned_count], "gate": [gate_page.total_count, gate_page.returned_count], "promotion_gate_audit": [promotion_audit_page.total_count, promotion_audit_page.returned_count], "release_packet": [release_packet_page.total_count, release_packet_page.returned_count]}}, indent=2, sort_keys=True))
    return 0 if promotion.release_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())

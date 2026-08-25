"""Compact counters and reviewer partitions for the D13-D16 release."""

from __future__ import annotations

from .frontier_release_closure_bundle import (
    FrontierReleaseSnapshot,
    frontier_release_snapshot_counts,
)
from .frontier_release_closure_contracts import (
    FrontierReleaseClosureCheck,
    FrontierReleaseSummary,
    FrontierReleaseSummaryAudit,
    frontier_release_closure_check,
)
from .frontier_release_closure_support import all_rows, csv_text, markdown_table
from .serialization import content_hash


def build_frontier_release_summary(
    snapshot: FrontierReleaseSnapshot,
) -> FrontierReleaseSummary:
    counts = frontier_release_snapshot_counts(snapshot)
    rows = all_rows(snapshot)
    counters = tuple(
        sorted(
            {
                **counts,
                "source_stage_count": sum(
                    int(row.get("source_stage_count", 0)) for row in rows["domains"]
                ),
                "certification_passed_count": sum(
                    int(row.get("certification_passed_count", 0)) for row in rows["domains"]
                ),
                "deterministic_domain_count": sum(
                    bool(row.get("deterministic_replay")) for row in rows["domains"]
                ),
                "connected_domain_graph_count": sum(
                    int(row.get("graph_component_count", 0)) == 1
                    for row in rows["domains"]
                    if int(row.get("graph_node_count", 0)) > 0
                ),
            }.items()
        )
    )
    accepted = snapshot.accepted and all(bool(row.get("passed")) for row in rows["gates"])
    body = {
        "bundle_id": snapshot.bundle_id,
        "counters": counters,
        "domains": rows["domains"],
        "gates": rows["gates"],
        "dependencies": rows["dependencies"],
        "accepted": accepted,
    }
    return FrontierReleaseSummary(
        **body,
        content_address=content_hash(body, prefix="frontier-release-summary"),
    )


def audit_frontier_release_summary(
    summary: FrontierReleaseSummary,
) -> FrontierReleaseSummaryAudit:
    counters = summary.counter_map
    checks: tuple[FrontierReleaseClosureCheck, ...] = (
        frontier_release_closure_check(
            "summary-address",
            "summary",
            summary.content_address.startswith("frontier-release-summary:"),
            summary.content_address,
            "frontier-release-summary:*",
            "summary is addressed",
        ),
        frontier_release_closure_check(
            "summary-domains",
            "summary",
            counters.get("domain_count") == 4,
            counters.get("domain_count"),
            4,
            "summary conserves four domains",
        ),
        frontier_release_closure_check(
            "summary-artifacts",
            "summary",
            counters.get("artifact_count") == 155,
            counters.get("artifact_count"),
            155,
            "summary conserves domain artifacts",
        ),
        frontier_release_closure_check(
            "summary-dependencies",
            "summary",
            counters.get("dependency_count") == 6,
            counters.get("dependency_count"),
            6,
            "summary conserves dependency edges",
        ),
        frontier_release_closure_check(
            "summary-gates",
            "summary",
            counters.get("gate_count") == 24,
            counters.get("gate_count"),
            24,
            "summary conserves release gates",
        ),
        frontier_release_closure_check(
            "summary-accepted-domains",
            "summary",
            counters.get("accepted_domain_count") == 4,
            counters.get("accepted_domain_count"),
            4,
            "all domains are accepted",
        ),
        frontier_release_closure_check(
            "summary-passed-gates",
            "summary",
            counters.get("passed_gate_count") == 24,
            counters.get("passed_gate_count"),
            24,
            "all gates pass",
        ),
        frontier_release_closure_check(
            "summary-sources",
            "summary",
            counters.get("source_count") == 20,
            counters.get("source_count"),
            20,
            "source receipts are conserved",
        ),
        frontier_release_closure_check(
            "summary-records",
            "summary",
            counters.get("record_count") == 64,
            counters.get("record_count"),
            64,
            "records are conserved",
        ),
        frontier_release_closure_check(
            "summary-evaluation",
            "summary",
            counters.get("evaluation_check_count") == 360,
            counters.get("evaluation_check_count"),
            360,
            "evaluation checks are conserved",
        ),
        frontier_release_closure_check(
            "summary-stages",
            "summary",
            counters.get("closure_stage_count") == 52,
            counters.get("closure_stage_count"),
            52,
            "closure stages are conserved",
        ),
        frontier_release_closure_check(
            "summary-certification",
            "summary",
            counters.get("certification_check_count") == 216,
            counters.get("certification_check_count"),
            216,
            "certification checks are conserved",
        ),
        frontier_release_closure_check(
            "summary-certification-passed",
            "summary",
            counters.get("certification_passed_count") == 216,
            counters.get("certification_passed_count"),
            216,
            "certification checks pass",
        ),
        frontier_release_closure_check(
            "summary-reconciliation",
            "summary",
            counters.get("reconciliation_check_count", 0) > 0,
            counters.get("reconciliation_check_count"),
            ">0",
            "reconciliation checks are present",
        ),
        frontier_release_closure_check(
            "summary-graphs",
            "summary",
            counters.get("graph_node_count", 0) > 0,
            counters.get("graph_node_count"),
            ">0",
            "graph nodes are present",
        ),
        frontier_release_closure_check(
            "summary-determinism",
            "summary",
            counters.get("deterministic_domain_count") == 4,
            counters.get("deterministic_domain_count"),
            4,
            "domain replays are deterministic",
        ),
        frontier_release_closure_check(
            "summary-domain-rows",
            "summary",
            len(summary.domains) == 4,
            len(summary.domains),
            4,
            "domain rows are complete",
        ),
        frontier_release_closure_check(
            "summary-gate-rows",
            "summary",
            len(summary.gates) == 24,
            len(summary.gates),
            24,
            "gate rows are complete",
        ),
        frontier_release_closure_check(
            "summary-dependency-rows",
            "summary",
            len(summary.dependencies) == 6,
            len(summary.dependencies),
            6,
            "dependency rows are complete",
        ),
        frontier_release_closure_check(
            "summary-root",
            "summary",
            summary.accepted,
            summary.accepted,
            True,
            "summary root is accepted",
        ),
    )
    body = {
        "bundle_id": summary.bundle_id,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    return FrontierReleaseSummaryAudit(
        **body,
        content_address=content_hash(body, prefix="frontier-release-summary-audit"),
    )


def frontier_release_summary_csv(summary: FrontierReleaseSummary) -> str:
    return csv_text(summary.domains)


def frontier_release_summary_markdown(summary: FrontierReleaseSummary) -> str:
    lines = [
        "# Frontier release summary",
        "",
        f"Bundle: `{summary.bundle_id}`",
        f"Accepted: `{str(summary.accepted).lower()}`",
        "",
        "| Counter | Value |",
        "| --- | ---: |",
    ]
    lines.extend(f"| `{key}` | `{value}` |" for key, value in summary.counters)
    lines.append("")
    lines.append(markdown_table(summary.domains, "Domain release summary"))
    return "\n".join(lines) + "\n"


__all__ = [
    "audit_frontier_release_summary",
    "build_frontier_release_summary",
    "frontier_release_summary_csv",
    "frontier_release_summary_markdown",
]

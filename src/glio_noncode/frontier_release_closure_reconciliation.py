"""Cross-domain conservation, ordering, and release reconciliation."""

from __future__ import annotations

from typing import Any

from .frontier_release_closure_bundle import FrontierReleaseSnapshot
from .frontier_release_closure_contracts import (
    FRONTIER_RELEASE_CLOSURE_ARTIFACT_COUNT,
    FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT,
    FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
    FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS,
    FRONTIER_RELEASE_CLOSURE_GATE_COUNT,
    FrontierReleaseClosureCheck,
    FrontierReleaseDelta,
    FrontierReleaseReconciliationReport,
    frontier_release_closure_check,
)
from .frontier_release_closure_support import all_rows, forbidden_keys
from .serialization import content_hash


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    expected: Any,
    detail: str,
    plane: str = "reconciliation",
) -> FrontierReleaseClosureCheck:
    return frontier_release_closure_check(check_id, plane, passed, observed, expected, detail)


def reconcile_frontier_release(
    snapshot: FrontierReleaseSnapshot,
) -> FrontierReleaseReconciliationReport:
    rows = all_rows(snapshot)
    domains = rows["domains"]
    artifacts = rows["artifacts"]
    dependencies = rows["dependencies"]
    gates = rows["gates"]
    domain_ids = tuple(str(row.get("domain_id", "")) for row in domains)
    artifact_refs = tuple(str(row.get("artifact_ref", "")) for row in artifacts)
    bundle_ids = tuple(str(row.get("bundle_id", "")) for row in domains)
    dependency_ids = tuple(str(row.get("dependency_id", "")) for row in dependencies)
    by_domain = {
        domain_id: tuple(row for row in artifacts if row.get("domain_id") == domain_id)
        for domain_id in FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS
    }
    checks: list[FrontierReleaseClosureCheck] = [
        _check(
            "root-accepted",
            snapshot.accepted,
            snapshot.accepted,
            True,
            "snapshot root is accepted",
            "manifest",
        ),
        _check(
            "domain-count",
            len(domains) == FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
            len(domains),
            FRONTIER_RELEASE_CLOSURE_DOMAIN_COUNT,
            "four domains are present",
            "domain",
        ),
        _check(
            "domain-order",
            domain_ids == FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS,
            domain_ids,
            FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS,
            "domain order is conserved",
            "domain",
        ),
        _check(
            "domain-identity",
            len(domain_ids) == len(set(domain_ids)) and all(domain_ids),
            len(set(domain_ids)),
            len(domains),
            "domain identities are unique",
            "domain",
        ),
        _check(
            "domain-accepted",
            all(bool(row.get("accepted")) for row in domains),
            sum(bool(row.get("accepted")) for row in domains),
            len(domains),
            "all source domain closures are accepted",
            "domain",
        ),
        _check(
            "bundle-identity",
            len(bundle_ids) == len(set(bundle_ids)) and all(bundle_ids),
            len(set(bundle_ids)),
            len(domains),
            "source bundle identities are unique",
            "domain",
        ),
        _check(
            "domain-addresses",
            all(str(row.get("content_address", "")) for row in domains),
            sum(bool(row.get("content_address")) for row in domains),
            len(domains),
            "domain rows are addressed",
            "domain",
        ),
        _check(
            "artifact-count",
            len(artifacts) == FRONTIER_RELEASE_CLOSURE_ARTIFACT_COUNT,
            len(artifacts),
            FRONTIER_RELEASE_CLOSURE_ARTIFACT_COUNT,
            "all domain manifests are conserved",
            "artifact",
        ),
        _check(
            "artifact-ref-identity",
            len(artifact_refs) == len(set(artifact_refs)) and all(artifact_refs),
            len(set(artifact_refs)),
            len(artifacts),
            "artifact references are unique",
            "artifact",
        ),
        _check(
            "artifact-addresses",
            all(str(row.get("content_address", "")) for row in artifacts),
            sum(bool(row.get("content_address")) for row in artifacts),
            len(artifacts),
            "closure artifact rows are addressed",
            "artifact",
        ),
        _check(
            "artifact-source-addresses",
            all(str(row.get("source_content_address", "")) for row in artifacts),
            sum(bool(row.get("source_content_address")) for row in artifacts),
            len(artifacts),
            "source artifact addresses are retained",
            "artifact",
        ),
    ]
    expected_artifacts = {"D13": 27, "D14": 21, "D15": 56, "D16": 51}
    for domain_id, expected in expected_artifacts.items():
        checks.append(
            _check(
                f"artifact-count-{domain_id.lower()}",
                len(by_domain[domain_id]) == expected,
                len(by_domain[domain_id]),
                expected,
                f"{domain_id} artifact manifest is conserved",
                "artifact",
            )
        )
    source_total = sum(int(row.get("source_count", 0)) for row in domains)
    record_total = sum(int(row.get("record_count", 0)) for row in domains)
    evaluation_total = sum(int(row.get("evaluation_check_count", 0)) for row in domains)
    stage_total = sum(int(row.get("closure_stage_count", 0)) for row in domains)
    certification_total = sum(int(row.get("certification_check_count", 0)) for row in domains)
    checks.extend(
        (
            _check(
                "source-count",
                source_total == 20,
                source_total,
                20,
                "source receipts are conserved across domains",
                "domain",
            ),
            _check(
                "record-count",
                record_total == 64,
                record_total,
                64,
                "records are conserved across domains",
                "domain",
            ),
            _check(
                "evaluation-count",
                evaluation_total == 360,
                evaluation_total,
                360,
                "evaluation checks are conserved across domains",
                "domain",
            ),
            _check(
                "closure-stage-count",
                stage_total == 52,
                stage_total,
                52,
                "closure runtime stages are conserved",
                "runtime",
            ),
            _check(
                "certification-count",
                certification_total == 216,
                certification_total,
                216,
                "certification checks are conserved",
                "certification",
            ),
            _check(
                "certification-pass-count",
                sum(int(row.get("certification_passed_count", 0)) for row in domains) == 216,
                sum(int(row.get("certification_passed_count", 0)) for row in domains),
                216,
                "all domain certification checks pass",
                "certification",
            ),
            _check(
                "reconciliation-depth",
                all(int(row.get("reconciliation_check_count", 0)) > 0 for row in domains),
                [row.get("reconciliation_check_count") for row in domains],
                ">0 per domain",
                "domain reconciliations are substantive",
                "reconciliation",
            ),
            _check(
                "replay-determinism",
                all(bool(row.get("deterministic_replay")) for row in domains),
                sum(bool(row.get("deterministic_replay")) for row in domains),
                len(domains),
                "all domain replays are deterministic",
                "runtime",
            ),
            _check(
                "dependency-count",
                len(dependencies) == FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT,
                len(dependencies),
                FRONTIER_RELEASE_CLOSURE_DEPENDENCY_COUNT,
                "release dependency matrix is complete",
                "dependency",
            ),
            _check(
                "dependency-identity",
                len(dependency_ids) == len(set(dependency_ids)) and all(dependency_ids),
                len(set(dependency_ids)),
                len(dependencies),
                "dependency identities are unique",
                "dependency",
            ),
            _check(
                "dependency-forward",
                all(
                    str(row.get("source_domain_id")) < str(row.get("target_domain_id"))
                    for row in dependencies
                ),
                [
                    (row.get("source_domain_id"), row.get("target_domain_id"))
                    for row in dependencies
                ],
                "forward-only",
                "dependency graph is acyclic",
                "dependency",
            ),
            _check(
                "gate-count",
                len(gates) == FRONTIER_RELEASE_CLOSURE_GATE_COUNT,
                len(gates),
                FRONTIER_RELEASE_CLOSURE_GATE_COUNT,
                "six gates exist for every domain",
                "gate",
            ),
            _check(
                "gate-partition",
                all(
                    sum(row.get("domain_id") == domain_id for row in gates) == 6
                    for domain_id in FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS
                ),
                [
                    sum(row.get("domain_id") == domain_id for row in gates)
                    for domain_id in FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS
                ],
                [6] * 4,
                "gate partitions are balanced",
                "gate",
            ),
            _check(
                "gate-pass-count",
                all(bool(row.get("passed")) for row in gates),
                sum(bool(row.get("passed")) for row in gates),
                len(gates),
                "all release gates pass",
                "gate",
            ),
            _check(
                "gate-addresses",
                all(str(row.get("content_address", "")) for row in gates),
                sum(bool(row.get("content_address")) for row in gates),
                len(gates),
                "gate rows are addressed",
                "gate",
            ),
            _check(
                "forbidden-keys",
                not forbidden_keys(snapshot.to_dict()),
                forbidden_keys(snapshot.to_dict()),
                (),
                "cross-domain public projection is clean",
                "public",
            ),
            _check(
                "runtime-row-count",
                len(rows["runtime"]) == len(domains),
                len(rows["runtime"]),
                len(domains),
                "runtime rows cover every domain",
                "runtime",
            ),
            _check(
                "runtime-addresses",
                all(str(row.get("content_address", "")) for row in rows["runtime"]),
                sum(bool(row.get("content_address")) for row in rows["runtime"]),
                len(rows["runtime"]),
                "runtime rows are addressed",
                "runtime",
            ),
            _check(
                "graph-shape",
                all(int(row.get("graph_component_count", 0)) in {0, 1} for row in domains),
                [row.get("graph_component_count") for row in domains],
                "0 or 1",
                "domain graph shapes are bounded",
                "domain",
            ),
            _check(
                "release-address",
                snapshot.content_address.startswith("frontier-release-snapshot:"),
                snapshot.content_address,
                "frontier-release-snapshot:*",
                "snapshot is content-addressed",
                "manifest",
            ),
        )
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": snapshot.bundle_id, "checks": tuple(checks), "accepted": accepted}
    return FrontierReleaseReconciliationReport(
        **body,
        content_address=content_hash(body, prefix="frontier-release-reconciliation"),
    )


def diff_frontier_release_snapshots(
    left: FrontierReleaseSnapshot,
    right: FrontierReleaseSnapshot,
) -> FrontierReleaseDelta:
    left_domains = {item.domain_id: item.content_address for item in left.domains}
    right_domains = {item.domain_id: item.content_address for item in right.domains}
    left_artifacts = {item.artifact_ref: item.content_address for item in left.artifacts}
    right_artifacts = {item.artifact_ref: item.content_address for item in right.artifacts}
    left_gates = {item.gate_id: item.content_address for item in left.gates}
    right_gates = {item.gate_id: item.content_address for item in right.gates}
    body = {
        "left_bundle_id": left.bundle_id,
        "right_bundle_id": right.bundle_id,
        "left_address": left.content_address,
        "right_address": right.content_address,
        "changed_domains": tuple(
            sorted(
                key
                for key in set(left_domains) | set(right_domains)
                if left_domains.get(key) != right_domains.get(key)
            )
        ),
        "changed_artifacts": tuple(
            sorted(
                key
                for key in set(left_artifacts) | set(right_artifacts)
                if left_artifacts.get(key) != right_artifacts.get(key)
            )
        ),
        "changed_gates": tuple(
            sorted(
                key
                for key in set(left_gates) | set(right_gates)
                if left_gates.get(key) != right_gates.get(key)
            )
        ),
    }
    body["accepted"] = (
        not body["changed_domains"] and not body["changed_artifacts"] and not body["changed_gates"]
    )
    return FrontierReleaseDelta(
        **body,
        content_address=content_hash(body, prefix="frontier-release-delta"),
    )


def frontier_release_reconciliation_markdown(
    report: FrontierReleaseReconciliationReport,
) -> str:
    lines = [
        "# Frontier release reconciliation",
        "",
        f"Bundle: `{report.bundle_id}`",
        f"Accepted: `{str(report.accepted).lower()}`",
        f"Checks: `{report.passed_count}/{len(report.checks)}`",
        "",
        "| Check | Plane | State | Detail |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.check_id}` | `{item.plane}` | `{'pass' if item.passed else 'hold'}` | {item.detail} |"
        for item in report.checks
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "diff_frontier_release_snapshots",
    "frontier_release_reconciliation_markdown",
    "reconcile_frontier_release",
]

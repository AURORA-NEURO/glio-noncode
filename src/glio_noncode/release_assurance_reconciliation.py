"""Independent reconciliation of whole-product release-assurance snapshots."""

from __future__ import annotations

from typing import Any

from .public_surface_audit import PublicSurfaceAudit
from .release_assurance_contracts import (
    RELEASE_ASSURANCE_CHECK_COUNT,
    RELEASE_ASSURANCE_CHECKS_PER_DOMAIN,
    RELEASE_ASSURANCE_DOMAIN_COUNT,
    RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT,
    RELEASE_ASSURANCE_EVIDENCE_LINKS_PER_DOMAIN,
    ReleaseAssurancePlane,
    ReleaseAssuranceReconciliation,
    ReleaseAssuranceReconciliationRow,
    ReleaseAssuranceSnapshot,
)
from .release_assurance_support import forbidden_keys
from .serialization import content_hash
from .service_surface import ServiceSurfaceSnapshot


def _row(
    row_id: str,
    plane: ReleaseAssurancePlane,
    metric: str,
    expected: Any,
    observed: Any,
    detail: str,
    evidence_addresses: tuple[str, ...] = (),
) -> ReleaseAssuranceReconciliationRow:
    passed = expected == observed
    body = {
        "row_id": row_id,
        "plane": plane,
        "metric": metric,
        "expected": expected,
        "observed": observed,
        "passed": passed,
        "detail": detail,
        "evidence_addresses": evidence_addresses,
    }
    return ReleaseAssuranceReconciliationRow(
        **body,
        content_address=content_hash(body, prefix="release-assurance-reconciliation-row"),
    )


def _domain_rows(snapshot: ReleaseAssuranceSnapshot) -> list[ReleaseAssuranceReconciliationRow]:
    rows: list[ReleaseAssuranceReconciliationRow] = []
    for domain in snapshot.domains:
        evidence = tuple(item for item in snapshot.evidence if item.domain_id == domain.domain_id)
        checks = tuple(item for item in snapshot.checks if item.domain_id == domain.domain_id)
        rows.extend((
            _row(
                f"domain:{domain.domain_id}:evidence-count",
                ReleaseAssurancePlane.CROSS_PLANE,
                "evidence_count",
                RELEASE_ASSURANCE_EVIDENCE_LINKS_PER_DOMAIN,
                len(evidence),
                "each domain retains five addressed evidence links",
                tuple(item.content_address for item in evidence),
            ),
            _row(
                f"domain:{domain.domain_id}:check-count",
                ReleaseAssurancePlane.CROSS_PLANE,
                "domain_check_count",
                RELEASE_ASSURANCE_CHECKS_PER_DOMAIN,
                len(checks),
                "each domain retains five domain checks",
                tuple(item.content_address for item in checks),
            ),
            _row(
                f"domain:{domain.domain_id}:accepted-partition",
                ReleaseAssurancePlane.CROSS_PLANE,
                "accepted_partition",
                domain.accepted,
                domain.accepted_count <= domain.denominator,
                "accepted counts cannot exceed domain denominators",
                (domain.content_address,),
            ),
            _row(
                f"domain:{domain.domain_id}:readiness",
                ReleaseAssurancePlane.CROSS_PLANE,
                "readiness_percent",
                round(100.0 * domain.accepted_count / max(1, domain.denominator), 2),
                domain.readiness_percent,
                "readiness is recomputed from conserved counts",
                (domain.content_address,),
            ),
        ))
    return rows


def reconciliation_rows(
    snapshot: ReleaseAssuranceSnapshot,
    *,
    source_snapshot: ServiceSurfaceSnapshot | None = None,
    public_audit: PublicSurfaceAudit | None = None,
) -> tuple[ReleaseAssuranceReconciliationRow, ...]:
    """Return all independent conservation rows without wrapping them."""

    rows = _domain_rows(snapshot)
    domain_ids = tuple(item.domain_id for item in snapshot.domains)
    evidence_ids = tuple(item.link_id for item in snapshot.evidence)
    check_ids = tuple(item.check_id for item in snapshot.checks)
    rows.extend((
        _row("global:domain-count", ReleaseAssurancePlane.CROSS_PLANE, "domain_count",
             RELEASE_ASSURANCE_DOMAIN_COUNT, len(snapshot.domains), "four assurance planes are present"),
        _row("global:evidence-count", ReleaseAssurancePlane.CROSS_PLANE, "evidence_count",
             RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT, len(snapshot.evidence), "evidence denominator is conserved"),
        _row("global:check-count", ReleaseAssurancePlane.CROSS_PLANE, "check_count",
             RELEASE_ASSURANCE_CHECK_COUNT, len(snapshot.checks), "check denominator is conserved"),
        _row("global:domain-order", ReleaseAssurancePlane.CROSS_PLANE, "domain_order",
             ("capability-catalog", "architecture-program", "service-release", "public-surface"),
             domain_ids, "domain order is stable"),
        _row("global:domain-identities", ReleaseAssurancePlane.CROSS_PLANE, "domain_identities",
             len(domain_ids), len(set(domain_ids)), "domain identifiers are unique"),
        _row("global:evidence-identities", ReleaseAssurancePlane.CROSS_PLANE, "evidence_identities",
             len(evidence_ids), len(set(evidence_ids)), "evidence identifiers are unique"),
        _row("global:check-identities", ReleaseAssurancePlane.CROSS_PLANE, "check_identities",
             len(check_ids), len(set(check_ids)), "check identifiers are unique"),
        _row("global:evidence-domain-coverage", ReleaseAssurancePlane.CROSS_PLANE, "evidence_domain_coverage",
             set(domain_ids), {item.domain_id for item in snapshot.evidence}, "evidence references known domains"),
        _row("global:check-domain-coverage", ReleaseAssurancePlane.CROSS_PLANE, "check_domain_coverage",
             set(domain_ids) | {"cross-plane"}, {item.domain_id for item in snapshot.checks}, "checks reference known planes"),
        _row("global:accepted-checks", ReleaseAssurancePlane.CROSS_PLANE, "accepted_checks",
             len(snapshot.checks), snapshot.passed_check_count, "all checks pass for an accepted snapshot"),
        _row("global:source-address", ReleaseAssurancePlane.PUBLIC_BOUNDARY, "source_address_present",
             True, bool(snapshot.service_snapshot_address and snapshot.public_audit_address),
             "source addresses remain present", (snapshot.service_snapshot_address, snapshot.public_audit_address)),
        _row("global:content-addresses", ReleaseAssurancePlane.PUBLIC_BOUNDARY, "content_address_uniqueness",
             len(snapshot.domains) + len(snapshot.evidence) + len(snapshot.checks),
             len({item.content_address for item in (*snapshot.domains, *snapshot.evidence, *snapshot.checks)}),
             "all aggregate rows have unique content addresses"),
        _row("global:public-keys", ReleaseAssurancePlane.PUBLIC_BOUNDARY, "forbidden_keys",
             (), forbidden_keys(snapshot.to_dict()), "public projection contains no prohibited metadata"),
    ))
    if source_snapshot is not None:
        rows.append(_row(
            "source:service-address", ReleaseAssurancePlane.SERVICE, "service_snapshot_address",
            source_snapshot.content_address, snapshot.service_snapshot_address,
            "aggregate retains the exact service snapshot address", (source_snapshot.content_address,),
        ))
    if public_audit is not None:
        rows.append(_row(
            "source:public-audit-address", ReleaseAssurancePlane.PUBLIC_BOUNDARY, "public_audit_address",
            public_audit.content_address, snapshot.public_audit_address,
            "aggregate retains the exact public audit address", (public_audit.content_address,),
        ))
    return tuple(rows)


def reconcile_release_assurance(
    snapshot: ReleaseAssuranceSnapshot,
    *,
    source_snapshot: ServiceSurfaceSnapshot | None = None,
    public_audit: PublicSurfaceAudit | None = None,
) -> ReleaseAssuranceReconciliation:
    """Build an independently addressed reconciliation report."""

    rows = reconciliation_rows(snapshot, source_snapshot=source_snapshot, public_audit=public_audit)
    accepted = snapshot.accepted and all(item.passed for item in rows)
    body = {"bundle_id": snapshot.bundle_id, "rows": rows, "accepted": accepted}
    return ReleaseAssuranceReconciliation(
        snapshot.bundle_id,
        rows,
        accepted,
        content_hash(body, prefix="release-assurance-reconciliation"),
    )


def audit_release_assurance_reconciliation(
    report: ReleaseAssuranceReconciliation,
    snapshot: ReleaseAssuranceSnapshot,
) -> tuple[ReleaseAssuranceReconciliationRow, ...]:
    """Recheck report identity, acceptance, and row address closure."""

    expected = tuple(item.content_address for item in report.rows)
    identity = content_hash(
        {"bundle_id": snapshot.bundle_id, "rows": report.rows, "accepted": report.accepted},
        prefix="release-assurance-reconciliation",
    )
    checks = [
        _row("audit:bundle", ReleaseAssurancePlane.CROSS_PLANE, "bundle_id",
             snapshot.bundle_id, report.bundle_id, "reconciliation bundle matches snapshot"),
        _row("audit:rows", ReleaseAssurancePlane.CROSS_PLANE, "row_count",
             len(report.rows), report.row_count, "row count is self-consistent"),
        _row("audit:row-identities", ReleaseAssurancePlane.CROSS_PLANE, "row_identities",
             len(report.rows), len({item.row_id for item in report.rows}), "row identifiers are unique"),
        _row("audit:row-addresses", ReleaseAssurancePlane.CROSS_PLANE, "row_addresses",
             len(expected), len({item.content_address for item in report.rows}), "row addresses are unique"),
        _row("audit:failed-rows", ReleaseAssurancePlane.CROSS_PLANE, "failed_rows",
             (), report.failed_row_ids, "accepted reports have no failed rows"),
        _row("audit:report-address", ReleaseAssurancePlane.PUBLIC_BOUNDARY, "content_address",
             report.content_address, identity, "report address is reproducible"),
    ]
    return tuple(checks)


__all__ = [
    "audit_release_assurance_reconciliation",
    "reconcile_release_assurance",
    "reconciliation_rows",
]

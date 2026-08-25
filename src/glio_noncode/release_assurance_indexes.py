"""Address-only lookup indexes for release-assurance evidence."""

from __future__ import annotations

from collections.abc import Iterable

from .release_assurance_contracts import (
    ReleaseAssuranceIndexAudit,
    ReleaseAssuranceIndexEntry,
    ReleaseAssuranceIndexes,
    ReleaseAssurancePlane,
    ReleaseAssuranceSnapshot,
    check,
)
from .serialization import content_hash


def _entry(index_name: str, key: str, resource: str, reference: str, source_address: str) -> ReleaseAssuranceIndexEntry:
    body = {"index_name": index_name, "key": key, "resource": resource,
            "reference": reference, "source_address": source_address}
    return ReleaseAssuranceIndexEntry(
        **body,
        content_address=content_hash(body, prefix="release-assurance-index-entry"),
    )


def build_release_assurance_indexes(snapshot: ReleaseAssuranceSnapshot) -> ReleaseAssuranceIndexes:
    """Build five deterministic address-only indexes."""

    domains = tuple(_entry("by_domain_id", item.domain_id, "domains", item.domain_id, item.content_address)
                    for item in snapshot.domains)
    checks = tuple(_entry("by_check_id", item.check_id, "checks", item.check_id, item.content_address)
                   for item in snapshot.checks)
    evidence = tuple(_entry("by_evidence_id", item.link_id, "evidence", item.link_id, item.content_address)
                     for item in snapshot.evidence)
    address_values = [
        ("domains", item.domain_id, item.content_address) for item in snapshot.domains
    ] + [
        ("checks", item.check_id, item.content_address) for item in snapshot.checks
    ] + [
        ("evidence", item.link_id, item.content_address) for item in snapshot.evidence
    ]
    addresses = tuple(_entry("by_content_address", address, resource, reference, address)
                      for resource, reference, address in sorted(address_values, key=lambda value: value[2]))
    states = tuple(_entry("by_state", "accepted", "domains", item.domain_id, item.content_address)
                   for item in snapshot.domains if item.accepted) + tuple(
        _entry("by_state", "passed", "checks", item.check_id, item.content_address)
        for item in snapshot.checks if item.passed
    )
    body = {"bundle_id": snapshot.bundle_id, "by_domain_id": domains,
            "by_check_id": checks, "by_evidence_id": evidence,
            "by_content_address": addresses, "by_state": states,
            "accepted": snapshot.accepted}
    return ReleaseAssuranceIndexes(
        snapshot.bundle_id, domains, checks, evidence, addresses, states,
        snapshot.accepted, content_hash(body, prefix="release-assurance-indexes"),
    )


def _unique(values: Iterable[ReleaseAssuranceIndexEntry]) -> bool:
    rows = tuple(values)
    return len(rows) == len({(item.key, item.reference) for item in rows})


def audit_release_assurance_indexes(
    snapshot: ReleaseAssuranceSnapshot,
    indexes: ReleaseAssuranceIndexes,
) -> ReleaseAssuranceIndexAudit:
    """Audit coverage, uniqueness, and address ordering for every index."""

    checks = [
        check("indexes:domain-count", "indexes", ReleaseAssurancePlane.CROSS_PLANE,
              len(indexes.by_domain_id) == len(snapshot.domains), len(indexes.by_domain_id),
              len(snapshot.domains), "domain index covers every domain"),
        check("indexes:check-count", "indexes", ReleaseAssurancePlane.CROSS_PLANE,
              len(indexes.by_check_id) == len(snapshot.checks), len(indexes.by_check_id),
              len(snapshot.checks), "check index covers every check"),
        check("indexes:evidence-count", "indexes", ReleaseAssurancePlane.CROSS_PLANE,
              len(indexes.by_evidence_id) == len(snapshot.evidence), len(indexes.by_evidence_id),
              len(snapshot.evidence), "evidence index covers every link"),
    ]
    for name, values in (("domain", indexes.by_domain_id), ("check", indexes.by_check_id),
                         ("evidence", indexes.by_evidence_id), ("address", indexes.by_content_address)):
        checks.append(check(
            f"indexes:{name}-unique", "indexes", ReleaseAssurancePlane.CROSS_PLANE,
            _unique(values), len(values), "unique key/reference pairs",
            f"{name} index is collision-free",
        ))
    checks.extend((
        check("indexes:address-order", "indexes", ReleaseAssurancePlane.CROSS_PLANE,
              tuple(item.key for item in indexes.by_content_address) == tuple(sorted(item.key for item in indexes.by_content_address)),
              tuple(item.key for item in indexes.by_content_address[:3]), "lexicographic",
              "address index is deterministic"),
        check("indexes:accepted", "indexes", ReleaseAssurancePlane.CROSS_PLANE,
              indexes.accepted == snapshot.accepted, indexes.accepted, snapshot.accepted,
              "index acceptance follows snapshot"),
    ))
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": snapshot.bundle_id, "checks": checks, "accepted": accepted}
    return ReleaseAssuranceIndexAudit(
        snapshot.bundle_id, tuple(checks), accepted,
        content_hash(body, prefix="release-assurance-index-audit"),
    )


__all__ = ["audit_release_assurance_indexes", "build_release_assurance_indexes"]

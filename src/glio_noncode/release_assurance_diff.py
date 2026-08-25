"""Address-only comparison of whole-product release-assurance snapshots."""

from __future__ import annotations

from .release_assurance_contracts import (
    ReleaseAssuranceCheck,
    ReleaseAssuranceDiff,
    ReleaseAssurancePlane,
    ReleaseAssuranceSnapshot,
    check,
)
from .release_assurance_support import forbidden_keys
from .serialization import content_hash


def _map(values, key: str) -> dict[str, object]:
    return {str(getattr(item, key)): item for item in values}


def build_release_assurance_diff(
    left: ReleaseAssuranceSnapshot,
    right: ReleaseAssuranceSnapshot,
) -> ReleaseAssuranceDiff:
    """Compare two snapshots without retaining their source records."""

    left_domains = _map(left.domains, "domain_id")
    right_domains = _map(right.domains, "domain_id")
    left_checks = _map(left.checks, "check_id")
    right_checks = _map(right.checks, "check_id")
    shared_domains = sorted(set(left_domains) & set(right_domains))
    shared_checks = sorted(set(left_checks) & set(right_checks))
    added_domains = tuple(sorted(set(right_domains) - set(left_domains)))
    removed_domains = tuple(sorted(set(left_domains) - set(right_domains)))
    changed_domains = tuple(
        item for item in shared_domains
        if left_domains[item].content_address != right_domains[item].content_address
    )
    added_checks = tuple(sorted(set(right_checks) - set(left_checks)))
    removed_checks = tuple(sorted(set(left_checks) - set(right_checks)))
    changed_checks = tuple(
        item for item in shared_checks
        if left_checks[item].content_address != right_checks[item].content_address
    )
    changed_addresses = tuple(sorted({
        left_domains[item].content_address for item in changed_domains
    } | {
        right_domains[item].content_address for item in changed_domains
    } | {
        left_checks[item].content_address for item in changed_checks
    } | {
        right_checks[item].content_address for item in changed_checks
    }))
    identical = left.content_address == right.content_address
    body = {
        "left_bundle_id": left.bundle_id,
        "right_bundle_id": right.bundle_id,
        "left_address": left.content_address,
        "right_address": right.content_address,
        "added_domain_ids": added_domains,
        "removed_domain_ids": removed_domains,
        "changed_domain_ids": changed_domains,
        "added_check_ids": added_checks,
        "removed_check_ids": removed_checks,
        "changed_check_ids": changed_checks,
        "changed_addresses": changed_addresses,
        "identical": identical,
        "accepted": left.accepted and right.accepted and not forbidden_keys({"left": left, "right": right}),
    }
    return ReleaseAssuranceDiff(
        **body,
        content_address=content_hash(body, prefix="release-assurance-diff"),
    )


def audit_release_assurance_diff(
    diff: ReleaseAssuranceDiff,
    left: ReleaseAssuranceSnapshot,
    right: ReleaseAssuranceSnapshot,
) -> tuple[ReleaseAssuranceCheck, ...]:
    """Audit comparison identity, addresses, and public-boundary closure."""

    checks = (
        check("diff:left-address", "diff", ReleaseAssurancePlane.CROSS_PLANE,
              diff.left_address == left.content_address, diff.left_address, left.content_address,
              "left address is retained"),
        check("diff:right-address", "diff", ReleaseAssurancePlane.CROSS_PLANE,
              diff.right_address == right.content_address, diff.right_address, right.content_address,
              "right address is retained"),
        check("diff:identical", "diff", ReleaseAssurancePlane.CROSS_PLANE,
              diff.identical == (left.content_address == right.content_address),
              diff.identical, left.content_address == right.content_address,
              "identical status follows content addresses"),
        check("diff:domain-partition", "diff", ReleaseAssurancePlane.CROSS_PLANE,
              not (set(diff.added_domain_ids) & set(diff.removed_domain_ids)),
              len(set(diff.added_domain_ids) & set(diff.removed_domain_ids)), 0,
              "domain additions and removals are disjoint"),
        check("diff:check-partition", "diff", ReleaseAssurancePlane.CROSS_PLANE,
              not (set(diff.added_check_ids) & set(diff.removed_check_ids)),
              len(set(diff.added_check_ids) & set(diff.removed_check_ids)), 0,
              "check additions and removals are disjoint"),
        check("diff:changed-addresses", "diff", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              len(diff.changed_addresses) == len(set(diff.changed_addresses)),
              len(diff.changed_addresses), len(set(diff.changed_addresses)),
              "changed address list is unique"),
        check("diff:public-boundary", "diff", ReleaseAssurancePlane.PUBLIC_BOUNDARY,
              not forbidden_keys(diff.to_dict()), forbidden_keys(diff.to_dict()), (),
              "diff carries no prohibited metadata"),
    )
    return checks


def diff_release_assurance_snapshots(
    left: ReleaseAssuranceSnapshot,
    right: ReleaseAssuranceSnapshot,
) -> ReleaseAssuranceDiff:
    """Named comparison entry point for API, CLI, and offline clients."""

    return build_release_assurance_diff(left, right)


__all__ = [
    "audit_release_assurance_diff",
    "build_release_assurance_diff",
    "diff_release_assurance_snapshots",
]

"""Live certification of every row in the public capability catalog.

The certification path is deliberately independent from the static state in
the catalog.  It resolves every declared implementation and test reference,
rechecks the sixteen-domain denominator, and makes an explicit distinction
between a catalog row that is labelled verified and a row whose evidence is
currently executable.  The result is deterministic and safe to publish: it
contains reference receipts and paths, never imported objects or raw values.
"""

from __future__ import annotations

from functools import cache
from typing import Any

from .capability_certification_contracts import (
    CapabilityCertificate,
    CapabilityCertificationCategory,
    CapabilityCertificationCheck,
    CapabilityCertificationReport,
    CapabilityCertificationState,
    CapabilityDomainSummary,
    addressed,
)
from .capability_registry import CapabilityRecord, CapabilityRegistry, default_capability_registry
from .errors import ValidationError
from .module_fabric_contracts import (
    FabricReferenceKind,
    FabricReferenceReceipt,
    FabricReferenceState,
)
from .module_fabric_support import contains_private_key, parse_capability_id, reference_set_receipts
from .serialization import content_hash

CATALOG_CAPABILITY_COUNT = 256
CATALOG_DOMAIN_COUNT = 16
CAPABILITIES_PER_DOMAIN = 16
CATALOG_MVP_COUNT = 64
CHECKS_PER_CAPABILITY = 10
GLOBAL_CHECK_COUNT = 12


def _check(
    capability_id: str,
    check_id: str,
    category: CapabilityCertificationCategory,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> CapabilityCertificationCheck:
    body = {
        "check_id": f"{capability_id}:{check_id}",
        "capability_id": capability_id,
        "category": category,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CapabilityCertificationCheck(
        **body,
        content_address=addressed(body, "capability-certification-check"),
    )


def _global_check(
    check_id: str,
    category: CapabilityCertificationCategory,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> CapabilityCertificationCheck:
    return _check("__catalog__", check_id, category, passed, observed, required, detail)


def _failed_receipt(reference: str, kind: FabricReferenceKind, detail: str) -> FabricReferenceReceipt:
    body = {
        "reference": str(reference),
        "kind": kind,
        "module_name": str(reference).rsplit(".", 1)[0] if "." in str(reference) else str(reference),
        "symbol_name": str(reference).rsplit(".", 1)[-1] if "." in str(reference) else None,
        "state": FabricReferenceState.FAILED,
        "detail": detail,
    }
    return FabricReferenceReceipt(**body, content_address=content_hash(body, prefix="capability-reference"))


@cache
def _cached_receipt(reference: str, kind: FabricReferenceKind) -> FabricReferenceReceipt:
    try:
        return reference_set_receipts((reference,), kind)[0]
    except (TypeError, ValueError, ValidationError) as exc:
        return _failed_receipt(reference, kind, f"{type(exc).__name__}: {exc}")


def _receipts(references: tuple[str, ...], kind: FabricReferenceKind) -> tuple[FabricReferenceReceipt, ...]:
    return tuple(_cached_receipt(str(reference), kind) for reference in references)


def _certificate(record: CapabilityRecord) -> CapabilityCertificate:
    spec = record.spec
    capability_id = spec.capability_id
    implementation = _receipts(record.implementation_modules, FabricReferenceKind.IMPLEMENTATION)
    tests = _receipts(record.test_modules, FabricReferenceKind.TEST)
    try:
        parsed_domain, parsed_order = parse_capability_id(capability_id)
        identifier_valid = parsed_domain == spec.domain_id and parsed_order == spec.capability_order
    except ValidationError:
        parsed_domain, parsed_order = "", -1
        identifier_valid = False
    implementation_failed = tuple(item.reference for item in implementation if item.state is FabricReferenceState.FAILED)
    test_failed = tuple(item.reference for item in tests if item.state is FabricReferenceState.FAILED)
    checks = (
        _check(
            capability_id,
            "identifier-valid",
            CapabilityCertificationCategory.IDENTITY,
            identifier_valid,
            {"domain_id": parsed_domain, "capability_order": parsed_order},
            {"domain_id": spec.domain_id, "capability_order": spec.capability_order},
            "catalog identifier parses to its declared domain and order",
        ),
        _check(
            capability_id,
            "domain-format",
            CapabilityCertificationCategory.DOMAIN,
            spec.domain_id.startswith("D") and len(spec.domain_id) == 3,
            spec.domain_id,
            "D01..D16",
            "domain identifiers remain in the closed sixteen-domain format",
        ),
        _check(
            capability_id,
            "order-range",
            CapabilityCertificationCategory.DOMAIN,
            1 <= spec.capability_order <= CAPABILITIES_PER_DOMAIN,
            spec.capability_order,
            f"1..{CAPABILITIES_PER_DOMAIN}",
            "capability order is addressable within its domain",
        ),
        _check(
            capability_id,
            "registry-state-verified",
            CapabilityCertificationCategory.CATALOG,
            record.state.value == "verified",
            record.state.value,
            "verified",
            "live certification only accepts catalog rows with declared verified evidence",
        ),
        _check(
            capability_id,
            "implementation-surface-present",
            CapabilityCertificationCategory.IMPLEMENTATION,
            bool(implementation),
            len(implementation),
            ">=1",
            "the row declares at least one implementation reference",
        ),
        _check(
            capability_id,
            "implementation-references-resolve",
            CapabilityCertificationCategory.IMPLEMENTATION,
            bool(implementation) and not implementation_failed,
            {"total": len(implementation), "failed": len(implementation_failed)},
            {"failed": 0},
            "every implementation reference resolves in the current checkout",
        ),
        _check(
            capability_id,
            "test-surface-present",
            CapabilityCertificationCategory.TEST_SURFACE,
            bool(tests),
            len(tests),
            ">=1",
            "the row declares at least one test reference",
        ),
        _check(
            capability_id,
            "test-references-resolve",
            CapabilityCertificationCategory.TEST_SURFACE,
            bool(tests) and not test_failed,
            {"total": len(tests), "failed": len(test_failed)},
            {"failed": 0},
            "every test reference resolves in the current checkout",
        ),
        _check(
            capability_id,
            "release-wave-present",
            CapabilityCertificationCategory.CATALOG,
            bool(spec.release_wave.strip()),
            spec.release_wave,
            "non-empty release wave",
            "release planning remains explicit for every certified row",
        ),
        _check(
            capability_id,
            "public-projection-safe",
            CapabilityCertificationCategory.PUBLIC_BOUNDARY,
            not contains_private_key(
                {
                    "capability_id": capability_id,
                    "domain_id": spec.domain_id,
                    "implementation_references": implementation,
                    "test_references": tests,
                }
            ),
            (),
            "no private field keys",
            "the certificate projection contains only public capability evidence",
        ),
    )
    state = CapabilityCertificationState.ACCEPTED if all(item.passed for item in checks) else CapabilityCertificationState.REVIEW
    body = {
        "capability_id": capability_id,
        "domain_id": spec.domain_id,
        "domain": spec.domain,
        "layer": spec.layer,
        "capability_order": spec.capability_order,
        "capability": spec.capability,
        "kind": spec.kind,
        "release_wave": spec.release_wave,
        "mvp_64": spec.mvp_64,
        "registry_state": record.state.value,
        "implementation_receipts": implementation,
        "test_receipts": tests,
        "checks": checks,
        "state": state,
    }
    return CapabilityCertificate(**body, content_address=addressed(body, "capability-certificate"))


def _domain_summary(domain_id: str, certificates: tuple[CapabilityCertificate, ...]) -> CapabilityDomainSummary:
    domain = certificates[0].domain if certificates else ""
    body = {
        "domain_id": domain_id,
        "domain": domain,
        "capability_count": len(certificates),
        "mvp_count": sum(item.mvp_64 for item in certificates),
        "accepted_count": sum(item.state is CapabilityCertificationState.ACCEPTED for item in certificates),
        "review_count": sum(item.state is CapabilityCertificationState.REVIEW for item in certificates),
        "blocked_count": sum(item.state is CapabilityCertificationState.BLOCKED for item in certificates),
        "implementation_references": sum(item.implementation_count for item in certificates),
        "test_references": sum(item.test_count for item in certificates),
        "failed_checks": sum(item.failed_checks for item in certificates),
    }
    return CapabilityDomainSummary(**body, content_address=addressed(body, "capability-domain-summary"))


def _global_checks(
    certificates: tuple[CapabilityCertificate, ...],
    summaries: tuple[CapabilityDomainSummary, ...],
) -> tuple[CapabilityCertificationCheck, ...]:
    ids = tuple(item.capability_id for item in certificates)
    by_domain = {domain_id: tuple(item for item in certificates if item.domain_id == domain_id) for domain_id in sorted({item.domain_id for item in certificates})}
    mvp_count = sum(item.mvp_64 for item in certificates)
    return (
        _global_check("catalog-cardinality", CapabilityCertificationCategory.CATALOG, len(certificates) == CATALOG_CAPABILITY_COUNT, len(certificates), CATALOG_CAPABILITY_COUNT, "the live denominator contains all catalog rows"),
        _global_check("catalog-identities-unique", CapabilityCertificationCategory.IDENTITY, len(ids) == len(set(ids)), len(ids), len(set(ids)), "capability identifiers are unique"),
        _global_check("domain-cardinality", CapabilityCertificationCategory.DOMAIN, len(by_domain) == CATALOG_DOMAIN_COUNT, len(by_domain), CATALOG_DOMAIN_COUNT, "all sixteen domains are represented"),
        _global_check("domain-row-balance", CapabilityCertificationCategory.DOMAIN, all(len(items) == CAPABILITIES_PER_DOMAIN for items in by_domain.values()), {key: len(value) for key, value in by_domain.items()}, {"each": CAPABILITIES_PER_DOMAIN}, "each domain has sixteen rows"),
        _global_check("domain-order-closure", CapabilityCertificationCategory.DOMAIN, all(tuple(sorted(item.capability_order for item in items)) == tuple(range(1, CAPABILITIES_PER_DOMAIN + 1)) for items in by_domain.values()), True, True, "each domain closes its ordered capability range"),
        _global_check("mvp-denominator", CapabilityCertificationCategory.CATALOG, mvp_count == CATALOG_MVP_COUNT, mvp_count, CATALOG_MVP_COUNT, "MVP rows retain the catalog denominator"),
        _global_check("all-certificates-accepted", CapabilityCertificationCategory.RUNTIME, all(item.state is CapabilityCertificationState.ACCEPTED for item in certificates), sum(item.state is CapabilityCertificationState.ACCEPTED for item in certificates), len(certificates), "all catalog rows pass live certification"),
        _global_check("all-summaries-addressed", CapabilityCertificationCategory.RUNTIME, all(item.content_address.startswith("capability-domain-summary:") for item in summaries), sum(item.content_address.startswith("capability-domain-summary:") for item in summaries), len(summaries), "each domain summary is content-addressed"),
        _global_check("implementation-receipts-addressed", CapabilityCertificationCategory.IMPLEMENTATION, all(receipt.content_address for item in certificates for receipt in item.implementation_receipts), True, True, "implementation receipts retain content addresses"),
        _global_check("test-receipts-addressed", CapabilityCertificationCategory.TEST_SURFACE, all(receipt.content_address for item in certificates for receipt in item.test_receipts), True, True, "test receipts retain content addresses"),
        _global_check("check-addresses-closed", CapabilityCertificationCategory.RUNTIME, all(check.content_address.startswith("capability-certification-check:") for item in certificates for check in item.checks), True, True, "row checks retain content addresses"),
        _global_check("public-report-safe", CapabilityCertificationCategory.PUBLIC_BOUNDARY, not contains_private_key({"certificates": certificates, "summaries": summaries}), True, True, "the published report remains safe for public projection"),
    )


def certify_capability_catalog(
    registry: CapabilityRegistry | None = None,
) -> CapabilityCertificationReport:
    """Certify every capability against the current repository evidence."""

    catalog = registry or default_capability_registry()
    records = catalog.records()
    certificates = tuple(_certificate(record) for record in records)
    summaries = tuple(
        _domain_summary(domain_id, tuple(item for item in certificates if item.domain_id == domain_id))
        for domain_id in sorted({item.domain_id for item in certificates})
    )
    checks = _global_checks(certificates, summaries)
    state = CapabilityCertificationState.ACCEPTED if all(item.passed for item in checks) and all(item.state is CapabilityCertificationState.ACCEPTED for item in certificates) else CapabilityCertificationState.REVIEW
    catalog_address = content_hash([record.spec.to_dict() for record in records], prefix="capability-catalog")
    body = {
        "report_id": f"capability-certification-{catalog_address.split(':', 1)[1][:16]}",
        "catalog_version": "blueprint-2026-08-20",
        "catalog_address": catalog_address,
        "certificates": certificates,
        "domain_summaries": summaries,
        "checks": checks,
        "state": state,
    }
    return CapabilityCertificationReport(**body, content_address=addressed(body, "capability-certification-report"))


def capability_certification_percent(report: CapabilityCertificationReport) -> float:
    """Return accepted capability percentage using the full 256-row denominator."""

    return round(100.0 * sum(item.state is CapabilityCertificationState.ACCEPTED for item in report.certificates) / max(1, report.capability_count), 2)


def capability_certification_domain_matrix(report: CapabilityCertificationReport) -> tuple[dict[str, Any], ...]:
    """Return stable dashboard rows without exposing mutable domain objects."""

    return tuple(
        {
            "domain_id": item.domain_id,
            "domain": item.domain,
            "capability_count": item.capability_count,
            "mvp_count": item.mvp_count,
            "accepted_count": item.accepted_count,
            "review_count": item.review_count,
            "readiness_percent": item.readiness_percent,
            "implementation_references": item.implementation_references,
            "test_references": item.test_references,
            "failed_checks": item.failed_checks,
            "content_address": item.content_address,
        }
        for item in report.domain_summaries
    )


def query_capability_certification(
    report: CapabilityCertificationReport,
    *,
    capability_id: str | None = None,
    domain_id: str | None = None,
    mvp_only: bool = False,
    state: CapabilityCertificationState | None = None,
    text: str | None = None,
) -> tuple[CapabilityCertificate, ...]:
    """Filter certificates by identity, release scope, state, or capability text."""

    normalized = text.strip().lower() if text else None
    return tuple(
        item
        for item in report.certificates
        if (capability_id is None or item.capability_id == capability_id)
        and (domain_id is None or item.domain_id == domain_id)
        and (not mvp_only or item.mvp_64)
        and (state is None or item.state is state)
        and (normalized is None or normalized in f"{item.capability_id} {item.domain} {item.capability}".lower())
    )


def diff_capability_certifications(
    left: CapabilityCertificationReport,
    right: CapabilityCertificationReport,
) -> dict[str, Any]:
    """Compare two reports by row and preserve only public certification fields."""

    left_map = {item.capability_id: item for item in left.certificates}
    right_map = {item.capability_id: item for item in right.certificates}
    added = sorted(set(right_map) - set(left_map))
    removed = sorted(set(left_map) - set(right_map))
    changed: list[dict[str, Any]] = []
    for capability_id in sorted(set(left_map) & set(right_map)):
        before = left_map[capability_id]
        after = right_map[capability_id]
        if before.content_address != after.content_address:
            changed.append(
                {
                    "capability_id": capability_id,
                    "before_address": before.content_address,
                    "after_address": after.content_address,
                    "before_state": before.state.value,
                    "after_state": after.state.value,
                }
            )
    return {
        "left_address": left.content_address,
        "right_address": right.content_address,
        "added": added,
        "removed": removed,
        "changed": changed,
        "changed_count": len(changed),
        "content_address": content_hash({"left": left.content_address, "right": right.content_address, "added": added, "removed": removed, "changed": changed}, prefix="capability-certification-diff"),
    }


__all__ = [
    "CAPABILITIES_PER_DOMAIN",
    "CATALOG_CAPABILITY_COUNT",
    "CATALOG_DOMAIN_COUNT",
    "CATALOG_MVP_COUNT",
    "CHECKS_PER_CAPABILITY",
    "GLOBAL_CHECK_COUNT",
    "capability_certification_domain_matrix",
    "capability_certification_percent",
    "certify_capability_catalog",
    "diff_capability_certifications",
    "query_capability_certification",
]

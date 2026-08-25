"""Build the whole-product release-assurance snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .capability_certification_contracts import CapabilityCertificationState
from .public_surface_audit import PublicSurfaceAudit, build_default_public_surface_audit
from .serialization import content_hash, jsonable, require_non_empty
from .service_release_bundle import build_service_release_snapshot
from .service_release_contracts import ServiceReleaseSnapshot
from .service_surface import ServiceSurfaceSnapshot, build_service_surface_snapshot
from .release_assurance_contracts import (
    RELEASE_ASSURANCE_CHECK_COUNT,
    RELEASE_ASSURANCE_DOMAIN_IDS,
    RELEASE_ASSURANCE_DOMAIN_COUNT,
    RELEASE_ASSURANCE_EVIDENCE_LINKS_PER_DOMAIN,
    RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT,
    ReleaseAssuranceDomain,
    ReleaseAssuranceEvidenceLink,
    ReleaseAssurancePlane,
    ReleaseAssuranceSnapshot,
    check,
)
from .release_assurance_support import forbidden_keys


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(dict(body), prefix=prefix)


def _domain_inputs(
    source: ServiceSurfaceSnapshot,
    service_release: ServiceReleaseSnapshot,
    public_audit: PublicSurfaceAudit,
) -> tuple[dict[str, Any], ...]:
    capability = source.capability_report
    architecture = source.program_runtime
    return (
        {
            "domain_id": "capability-catalog",
            "title": "Capability catalog certification",
            "denominator": len(capability.certificates),
            "accepted_count": sum(item.state is CapabilityCertificationState.ACCEPTED for item in capability.certificates),
            "source_address": capability.content_address,
            "evidence_addresses": (capability.content_address, capability.catalog_address),
            "accepted": capability.accepted,
            "limitations": ("catalog certification is implementation evidence, not a clinical claim",),
        },
        {
            "domain_id": "architecture-program",
            "title": "D01-D16 architecture program",
            "denominator": len(architecture.report.receipts),
            "accepted_count": sum(item.accepted for item in architecture.report.receipts),
            "source_address": architecture.content_address,
            "evidence_addresses": (architecture.content_address, architecture.report.content_address),
            "accepted": architecture.accepted,
            "limitations": ("architecture receipts preserve research-use boundaries",),
        },
        {
            "domain_id": "service-release",
            "title": "Public service-release registry",
            "denominator": len(service_release.surfaces),
            "accepted_count": sum(item.accepted for item in service_release.surfaces),
            "source_address": service_release.content_address,
            "evidence_addresses": (service_release.content_address, source.program_release.content_address),
            "accepted": service_release.accepted,
            "limitations": ("service-release acceptance covers aggregate projections and exact-byte handoff",),
        },
        {
            "domain_id": "public-surface",
            "title": "Repository public-surface audit",
            "denominator": public_audit.surface_count,
            "accepted_count": public_audit.passed_surface_count,
            "source_address": public_audit.content_address,
            "evidence_addresses": (public_audit.content_address, source.content_address),
            "accepted": public_audit.accepted,
            "limitations": ("public-boundary audit does not certify scientific validity",),
        },
    )


def _make_evidence(domain: Mapping[str, Any]) -> tuple[ReleaseAssuranceEvidenceLink, ...]:
    values = tuple(domain["evidence_addresses"])
    roles = ("primary", "summary", "boundary", "replay", "release")
    result: list[ReleaseAssuranceEvidenceLink] = []
    for index in range(RELEASE_ASSURANCE_EVIDENCE_LINKS_PER_DOMAIN):
        source_address = values[index % len(values)]
        body = {
            "link_id": f"evidence:{domain['domain_id']}:{roles[index]}",
            "domain_id": domain["domain_id"],
            "evidence_type": roles[index],
            "source_address": source_address,
            "role": roles[index],
            "accepted": bool(domain["accepted"]),
        }
        result.append(
            ReleaseAssuranceEvidenceLink(
                **body,
                content_address=_address(body, "release-assurance-evidence"),
            )
        )
    return tuple(result)


def _domain_checks(
    domain: Mapping[str, Any],
    evidence: tuple[ReleaseAssuranceEvidenceLink, ...],
) -> tuple:
    addresses = tuple(item.content_address for item in evidence)
    domain_id = str(domain["domain_id"])
    return (
        check(
            f"{domain_id}:source-address",
            domain_id,
            ReleaseAssurancePlane.CROSS_PLANE,
            bool(domain["source_address"]),
            domain["source_address"],
            "non-empty immutable address",
            addresses,
        ),
        check(
            f"{domain_id}:denominator",
            domain_id,
            ReleaseAssurancePlane.CROSS_PLANE,
            int(domain["denominator"]) > 0,
            domain["denominator"],
            ">0",
            addresses,
        ),
        check(
            f"{domain_id}:accepted-partition",
            domain_id,
            ReleaseAssurancePlane.CROSS_PLANE,
            0 <= int(domain["accepted_count"]) <= int(domain["denominator"]),
            domain["accepted_count"],
            f"0..{domain['denominator']}",
            addresses,
        ),
        check(
            f"{domain_id}:evidence-coverage",
            domain_id,
            ReleaseAssurancePlane.CROSS_PLANE,
            len(evidence) == RELEASE_ASSURANCE_EVIDENCE_LINKS_PER_DOMAIN
            and all(item.accepted for item in evidence),
            len(evidence),
            RELEASE_ASSURANCE_EVIDENCE_LINKS_PER_DOMAIN,
            addresses,
        ),
        check(
            f"{domain_id}:readiness",
            domain_id,
            ReleaseAssurancePlane.CROSS_PLANE,
            bool(domain["accepted"]),
            domain["accepted"],
            True,
            addresses,
        ),
    )


def _cross_checks(
    source: ServiceSurfaceSnapshot,
    service_release: ServiceReleaseSnapshot,
    public_audit: PublicSurfaceAudit,
    domains: tuple[ReleaseAssuranceDomain, ...],
) -> tuple:
    evidence = tuple(
        address
        for domain in domains
        for address in (domain.source_address, source.content_address)
    )
    denominator = sum(item.denominator for item in domains)
    accepted = sum(item.accepted_count for item in domains)
    return (
        check(
            "cross:domain-closure",
            "cross-plane",
            ReleaseAssurancePlane.CROSS_PLANE,
            tuple(item.domain_id for item in domains) == RELEASE_ASSURANCE_DOMAIN_IDS,
            tuple(item.domain_id for item in domains),
            RELEASE_ASSURANCE_DOMAIN_IDS,
            evidence,
        ),
        check(
            "cross:domain-count",
            "cross-plane",
            ReleaseAssurancePlane.CROSS_PLANE,
            len(domains) == RELEASE_ASSURANCE_DOMAIN_COUNT,
            len(domains),
            RELEASE_ASSURANCE_DOMAIN_COUNT,
            evidence,
        ),
        check(
            "cross:service-source",
            "cross-plane",
            ReleaseAssurancePlane.SERVICE,
            service_release.service_address == source.content_address,
            service_release.service_address,
            source.content_address,
            evidence,
        ),
        check(
            "cross:program-release-source",
            "cross-plane",
            ReleaseAssurancePlane.ARCHITECTURE,
            source.program_release.content_address == next(item.source_address for item in service_release.surfaces if item.surface_id == "program-release"),
            source.program_release.content_address,
            "registered D01-D16 source address",
            evidence,
        ),
        check(
            "cross:public-audit",
            "cross-plane",
            ReleaseAssurancePlane.PUBLIC_BOUNDARY,
            public_audit.surface_count == 25 and public_audit.passed_surface_count == 25,
            public_audit.surface_count,
            25,
            (public_audit.content_address,),
        ),
        check(
            "cross:accepted-total",
            "cross-plane",
            ReleaseAssurancePlane.CROSS_PLANE,
            accepted == denominator,
            {"accepted": accepted, "denominator": denominator},
            {"accepted": denominator},
            evidence,
        ),
        check(
            "cross:service-accepted",
            "cross-plane",
            ReleaseAssurancePlane.SERVICE,
            source.accepted and service_release.accepted,
            {"service": service_release.accepted, "source": source.accepted},
            {"service": True, "source": True},
            evidence,
        ),
        check(
            "cross:public-boundary",
            "cross-plane",
            ReleaseAssurancePlane.PUBLIC_BOUNDARY,
            not forbidden_keys(source.program_release.to_dict())
            and not forbidden_keys(service_release.to_dict())
            and not forbidden_keys(public_audit.to_dict()),
            (),
            "no forbidden public metadata paths",
            evidence,
        ),
    )


def build_release_assurance_snapshot(
    source_snapshot: ServiceSurfaceSnapshot | None = None,
    *,
    public_audit: PublicSurfaceAudit | None = None,
    service_release: ServiceReleaseSnapshot | None = None,
    bundle_id: str = "glio-noncode-release-assurance",
    run_id: str = "glio-noncode-release-assurance-run",
) -> ReleaseAssuranceSnapshot:
    """Build one addressable whole-product release-assurance snapshot."""

    require_non_empty(bundle_id, "bundle_id")
    require_non_empty(run_id, "run_id")
    source = source_snapshot or build_service_surface_snapshot()
    release = service_release or build_service_release_snapshot(source)
    audit = public_audit or build_default_public_surface_audit(snapshot=source)
    domain_values = _domain_inputs(source, release, audit)
    domains: list[ReleaseAssuranceDomain] = []
    evidence_values: list[ReleaseAssuranceEvidenceLink] = []
    checks: list = []
    for value in domain_values:
        evidence = _make_evidence(value)
        evidence_values.extend(evidence)
        readiness = round(100.0 * int(value["accepted_count"]) / max(1, int(value["denominator"])), 2)
        body = {
            "domain_id": value["domain_id"],
            "title": value["title"],
            "denominator": int(value["denominator"]),
            "accepted_count": int(value["accepted_count"]),
            "readiness_percent": readiness,
            "source_address": value["source_address"],
            "evidence_count": len(evidence),
            "accepted": bool(value["accepted"]),
            "limitations": tuple(value["limitations"]),
        }
        domains.append(
            ReleaseAssuranceDomain(
                **body,
                content_address=_address(body, "release-assurance-domain"),
            )
        )
        checks.extend(_domain_checks(value, evidence))
    domain_tuple = tuple(domains)
    checks.extend(_cross_checks(source, release, audit, domain_tuple))
    evidence_tuple = tuple(evidence_values)
    overall = round(
        sum(item.readiness_percent for item in domain_tuple) / max(1, len(domain_tuple)),
        2,
    )
    accepted = (
        source.accepted
        and release.accepted
        and audit.accepted
        and len(domain_tuple) == RELEASE_ASSURANCE_DOMAIN_COUNT
        and len(evidence_tuple) == RELEASE_ASSURANCE_EVIDENCE_LINK_COUNT
        and len(checks) == RELEASE_ASSURANCE_CHECK_COUNT
        and all(item.passed for item in checks)
        and not forbidden_keys(jsonable({"domains": domain_tuple, "evidence": evidence_tuple, "checks": checks}))
    )
    body = {
        "bundle_id": bundle_id,
        "run_id": run_id,
        "service_snapshot_address": source.content_address,
        "public_audit_address": audit.content_address,
        "domains": domain_tuple,
        "evidence": evidence_tuple,
        "checks": tuple(checks),
        "overall_percent": overall,
        "accepted": accepted,
    }
    return ReleaseAssuranceSnapshot(
        bundle_id=bundle_id,
        run_id=run_id,
        service_snapshot_address=source.content_address,
        public_audit_address=audit.content_address,
        domains=domain_tuple,
        evidence=evidence_tuple,
        checks=tuple(checks),
        overall_percent=overall,
        accepted=accepted,
        content_address=_address(body, "release-assurance-snapshot"),
    )


def release_assurance_snapshot_counts(snapshot: ReleaseAssuranceSnapshot) -> dict[str, int | float | bool]:
    """Return conserved counters for status, summaries, and exports."""

    return {
        "domain_count": len(snapshot.domains),
        "evidence_count": len(snapshot.evidence),
        "check_count": len(snapshot.checks),
        "passed_check_count": snapshot.passed_check_count,
        "accepted_domain_count": sum(item.accepted for item in snapshot.domains),
        "overall_percent": snapshot.overall_percent,
        "accepted": snapshot.accepted,
    }


def release_assurance_snapshot_rows(snapshot: ReleaseAssuranceSnapshot) -> dict[str, list[dict[str, Any]]]:
    """Expose stable rows for bounded queries and table exports."""

    return {
        "domains": [item.to_dict() for item in snapshot.domains],
        "checks": [item.to_dict() for item in snapshot.checks],
        "evidence": [item.to_dict() for item in snapshot.evidence],
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("RELEASE_ASSURANCE")
    or name.startswith("ReleaseAssurance")
    or name.startswith("build_release_assurance")
    or name.startswith("release_assurance_snapshot")
]

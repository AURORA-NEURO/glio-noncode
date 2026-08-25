"""Per-domain certification receipts for the aggregate release."""

from __future__ import annotations

from typing import Any

from .program_release_closure_contracts import (
    PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT,
    PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECKS_PER_DOMAIN,
    PROGRAM_RELEASE_CLOSURE_CERTIFICATION_VERSION,
    ProgramReleaseCertification,
    ProgramReleaseCertificationCheck,
    ProgramReleaseSnapshot,
)
from .serialization import content_hash


def _cert(
    domain_id: str,
    ordinal: int,
    plane: str,
    passed: bool,
    observed: Any,
    expected: Any,
    references: tuple[str, ...],
) -> ProgramReleaseCertificationCheck:
    body = {
        "certification_id": f"certification:{domain_id}:{ordinal:02d}",
        "domain_id": domain_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "expected": expected,
        "references": references,
    }
    return ProgramReleaseCertificationCheck(
        **body, content_address=content_hash(body, prefix="program-release-certification-check")
    )


def certify_program_release_closure(
    snapshot: ProgramReleaseSnapshot,
) -> ProgramReleaseCertification:
    """Issue six independent receipts for each domain's release contribution."""

    checks: list[ProgramReleaseCertificationCheck] = []
    for domain in snapshot.domains:
        domain_gates = tuple(item for item in snapshot.gates if item.domain_id == domain.domain_id)
        checks.extend(
            (
                _cert(
                    domain.domain_id,
                    1,
                    "source_acceptance",
                    domain.accepted,
                    domain.accepted,
                    True,
                    (domain.source_receipt_address,),
                ),
                _cert(
                    domain.domain_id,
                    2,
                    "runtime_address",
                    bool(domain.source_runtime_address),
                    domain.source_runtime_address,
                    "addressed",
                    (domain.content_address,),
                ),
                _cert(
                    domain.domain_id,
                    3,
                    "runtime_depth",
                    domain.stage_count > 0,
                    domain.stage_count,
                    ">0",
                    (domain.source_runtime_address,),
                ),
                _cert(
                    domain.domain_id,
                    4,
                    "evaluation_contribution",
                    domain.evaluation_check_count > 0,
                    domain.evaluation_check_count,
                    ">0",
                    (domain.source_receipt_address,),
                ),
                _cert(
                    domain.domain_id,
                    5,
                    "artifact_contribution",
                    domain.source_artifact_count > 0,
                    domain.source_artifact_count,
                    ">0",
                    (domain.source_receipt_address,),
                ),
                _cert(
                    domain.domain_id,
                    6,
                    "gate_partition",
                    len(domain_gates) == PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECKS_PER_DOMAIN,
                    len(domain_gates),
                    6,
                    tuple(item.content_address for item in domain_gates),
                ),
            )
        )
    body = {
        "bundle_id": snapshot.bundle_id,
        "version": PROGRAM_RELEASE_CLOSURE_CERTIFICATION_VERSION,
        "checks": tuple(checks),
        "accepted": all(item.passed for item in checks),
    }
    return ProgramReleaseCertification(
        snapshot.bundle_id,
        PROGRAM_RELEASE_CLOSURE_CERTIFICATION_VERSION,
        tuple(checks),
        body["accepted"],
        content_hash(body, prefix="program-release-certification"),
    )


def audit_program_release_certification(
    certification: ProgramReleaseCertification, snapshot: ProgramReleaseSnapshot
) -> dict[str, Any]:
    by_domain = {
        domain_id: tuple(item for item in certification.checks if item.domain_id == domain_id)
        for domain_id in sorted({item.domain_id for item in certification.checks})
    }
    checks = {
        "accepted": certification.accepted,
        "check_count": certification.check_count
        == PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT,
        "domain_count": len(by_domain) == len(snapshot.domains),
        "per_domain_count": all(
            len(items) == PROGRAM_RELEASE_CLOSURE_CERTIFICATION_CHECKS_PER_DOMAIN
            for items in by_domain.values()
        ),
        "coverage_percent": certification.coverage_percent == 100.0,
    }
    body = {
        "bundle_id": certification.bundle_id,
        "checks": checks,
        "accepted": all(checks.values()),
        "coverage_percent": certification.coverage_percent,
    }
    body["content_address"] = content_hash(body, prefix="program-release-certification-audit")
    return body


__all__ = [
    name
    for name in globals()
    if name.startswith("PROGRAM_RELEASE")
    or name.startswith("certify_program_release")
    or name.startswith("audit_program_release")
    or name.startswith("ProgramRelease")
]

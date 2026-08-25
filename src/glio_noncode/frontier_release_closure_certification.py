"""Eight-domain certification for the cross-domain release package."""

from __future__ import annotations

from typing import Any

from .frontier_release_closure_boundary import audit_frontier_release_boundary
from .frontier_release_closure_bundle import FrontierReleaseSnapshot
from .frontier_release_closure_contracts import (
    FRONTIER_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT,
    FRONTIER_RELEASE_CLOSURE_CERTIFICATION_DOMAIN_COUNT,
    FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS,
    FrontierReleaseCertificationCheck,
    FrontierReleaseCertificationDomain,
    FrontierReleaseCertificationReport,
)
from .frontier_release_closure_indexes import (
    audit_frontier_release_indexes,
    build_frontier_release_indexes,
)
from .frontier_release_closure_reconciliation import reconcile_frontier_release
from .frontier_release_closure_summary import (
    audit_frontier_release_summary,
    build_frontier_release_summary,
)
from .frontier_release_closure_schema import (
    audit_frontier_release_schema,
    build_frontier_release_schema,
)
from .serialization import content_hash, jsonable

_CERTIFICATION_DOMAINS = (
    ("manifest", "Manifest identity and release boundary"),
    ("source_domains", "D13-D16 source domain conservation"),
    ("artifacts", "Namespaced artifact address integrity"),
    ("dependencies", "Acyclic release dependency ordering"),
    ("gates", "Per-domain release gate completeness"),
    ("reconciliation", "Cross-domain denominator reconciliation"),
    ("determinism", "Runtime replay determinism"),
    ("public_projection", "Public aggregate projection policy"),
)


def _check(
    check_id: str,
    domain: str,
    passed: bool,
    observed: Any,
    expected: Any,
    refs: tuple[str, ...],
) -> FrontierReleaseCertificationCheck:
    body = {
        "check_id": check_id,
        "domain": domain,
        "plane": domain,
        "passed": bool(passed),
        "observed": jsonable(observed),
        "expected": jsonable(expected),
        "evidence_refs": refs,
    }
    return FrontierReleaseCertificationCheck(
        **body,
        content_address=content_hash(body, prefix="frontier-release-certification-check"),
    )


def _domain_report(
    domain_id: str,
    name: str,
    checks: tuple[FrontierReleaseCertificationCheck, ...],
) -> FrontierReleaseCertificationDomain:
    body = {
        "domain_id": domain_id,
        "name": name,
        "check_count": len(checks),
        "passed_check_count": sum(item.passed for item in checks),
        "coverage_percent": round(100.0 * sum(item.passed for item in checks) / len(checks), 2),
        "accepted": all(item.passed for item in checks),
    }
    return FrontierReleaseCertificationDomain(
        **body,
        content_address=content_hash(body, prefix="frontier-release-certification-domain"),
    )


def certify_frontier_release(
    snapshot: FrontierReleaseSnapshot,
) -> FrontierReleaseCertificationReport:
    boundary = audit_frontier_release_boundary(snapshot)
    indexes = build_frontier_release_indexes(snapshot)
    index_audit = audit_frontier_release_indexes(snapshot, indexes)
    reconciliation = reconcile_frontier_release(snapshot)
    summary = build_frontier_release_summary(snapshot)
    summary_audit = audit_frontier_release_summary(summary)
    schema = build_frontier_release_schema()
    schema_audit = audit_frontier_release_schema(snapshot, schema)
    refs = (
        snapshot.content_address,
        boundary.content_address,
        indexes.content_address,
        index_audit.content_address,
        reconciliation.content_address,
        summary.content_address,
        summary_audit.content_address,
        schema["content_address"],
    )
    counts = summary.counter_map
    domain_values: dict[str, tuple[bool, ...]] = {
        "manifest": (
            snapshot.accepted,
            snapshot.boundary == "public_aggregate_frontier_release_closure_handoff",
            snapshot.content_address.startswith("frontier-release-snapshot:"),
            len(snapshot.domains) == 4,
            len(snapshot.artifacts) == 155,
            len(snapshot.dependencies) == 6,
        ),
        "source_domains": (
            all(item.accepted for item in snapshot.domains),
            tuple(item.domain_id for item in snapshot.domains)
            == FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS,
            counts.get("source_count") == 20,
            counts.get("record_count") == 64,
            counts.get("evaluation_check_count") == 360,
            all(item.bundle_content_address for item in snapshot.domains),
        ),
        "artifacts": (
            len(snapshot.artifacts) == 155,
            len({item.artifact_ref for item in snapshot.artifacts}) == 155,
            all(item.source_content_address for item in snapshot.artifacts),
            all(item.content_address for item in snapshot.artifacts),
            all(
                item.relative_path and "\\" not in item.relative_path for item in snapshot.artifacts
            ),
            len({item.domain_id for item in snapshot.artifacts}) == 4,
        ),
        "dependencies": (
            len(snapshot.dependencies) == 6,
            len({item.dependency_id for item in snapshot.dependencies}) == 6,
            all(item.source_domain_id < item.target_domain_id for item in snapshot.dependencies),
            all(item.required for item in snapshot.dependencies),
            all(item.content_address for item in snapshot.dependencies),
            tuple(item.ordinal for item in snapshot.dependencies) == (1, 2, 3, 4, 5, 6),
        ),
        "gates": (
            len(snapshot.gates) == 24,
            len({item.gate_id for item in snapshot.gates}) == 24,
            all(item.passed for item in snapshot.gates),
            all(item.passed for item in schema_audit),
            all(
                sum(item.domain_id == domain_id for item in snapshot.gates) == 6
                for domain_id in FRONTIER_RELEASE_CLOSURE_DOMAIN_IDS
            ),
            all(item.expected is not None for item in snapshot.gates),
        ),
        "reconciliation": (
            reconciliation.accepted,
            reconciliation.passed_count == len(reconciliation.checks),
            index_audit.accepted,
            summary_audit.accepted,
            summary.accepted,
            all(item.passed for item in reconciliation.checks),
        ),
        "determinism": (
            all(item.deterministic_replay for item in snapshot.domains),
            counts.get("deterministic_domain_count") == 4,
            all(item.runtime_content_address for item in snapshot.domains),
            counts.get("closure_stage_count") == 52,
            all(item.closure_stage_count >= 10 for item in snapshot.domains),
            snapshot.accepted,
        ),
        "public_projection": (
            boundary.accepted,
            not boundary.forbidden_keys,
            boundary.passed_count == len(boundary.checks),
            all(item.content_address for item in snapshot.domains),
            all(item.content_address for item in snapshot.artifacts),
            all(item.content_address for item in snapshot.gates),
        ),
    }
    checks: list[FrontierReleaseCertificationCheck] = []
    domains: list[FrontierReleaseCertificationDomain] = []
    for domain, name in _CERTIFICATION_DOMAINS:
        values = domain_values[domain]
        domain_checks = tuple(
            _check(
                f"release-{domain}-{ordinal:02d}",
                domain,
                passed,
                passed,
                True,
                refs,
            )
            for ordinal, passed in enumerate(values, 1)
        )
        checks.extend(domain_checks)
        domains.append(_domain_report(domain, name, domain_checks))
    accepted = (
        len(checks) == FRONTIER_RELEASE_CLOSURE_CERTIFICATION_CHECK_COUNT
        and len(domains) == FRONTIER_RELEASE_CLOSURE_CERTIFICATION_DOMAIN_COUNT
        and all(item.passed for item in checks)
    )
    body = {
        "version": "frontier-release-certification-v1",
        "bundle_id": snapshot.bundle_id,
        "check_count": len(checks),
        "passed_check_count": sum(item.passed for item in checks),
        "coverage_percent": round(100.0 * sum(item.passed for item in checks) / len(checks), 2),
        "domains": tuple(domains),
        "checks": tuple(checks),
        "accepted": accepted,
    }
    return FrontierReleaseCertificationReport(
        **body,
        content_address=content_hash(body, prefix="frontier-release-certification"),
    )


def frontier_release_certification_markdown(
    report: FrontierReleaseCertificationReport,
) -> str:
    lines = [
        "# Frontier release certification",
        "",
        f"Bundle: `{report.bundle_id}`",
        f"Accepted: `{str(report.accepted).lower()}`",
        f"Coverage: `{report.coverage_percent}%`",
        "",
        "| Domain | Checks | Passed | Coverage | State |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    lines.extend(
        f"| `{item.domain_id}` | {item.check_count} | {item.passed_check_count} | "
        f"{item.coverage_percent}% | `{'pass' if item.accepted else 'hold'}` |"
        for item in report.domains
    )
    return "\n".join(lines) + "\n"


__all__ = ["certify_frontier_release", "frontier_release_certification_markdown"]

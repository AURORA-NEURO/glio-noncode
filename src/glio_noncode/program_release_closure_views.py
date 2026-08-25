"""Joined reviewer views over D01-D16 closure resources.

The primary closure resources remain normalized for transport and exact-byte
verification. This module adds a denormalized view for a reviewer who wants to
see one domain's readiness, dependency fan-in/fan-out, gates, and source
contributions on one screen. It contains aggregate counts and addresses only.
"""

from __future__ import annotations

from .program_release_closure_contracts import (
    ProgramReleaseClosureCheck,
    ProgramReleaseClosurePlane,
    ProgramReleaseDomainView,
    ProgramReleaseReviewViews,
    ProgramReleaseSnapshot,
    program_release_closure_check,
)
from .serialization import content_hash


def build_program_release_review_views(
    snapshot: ProgramReleaseSnapshot,
) -> ProgramReleaseReviewViews:
    """Build one joined readiness view for each ordered domain."""

    views: list[ProgramReleaseDomainView] = []
    for domain in snapshot.domains:
        incoming = sum(item.target_domain_id == domain.domain_id for item in snapshot.dependencies)
        outgoing = sum(item.source_domain_id == domain.domain_id for item in snapshot.dependencies)
        gates = tuple(item for item in snapshot.gates if item.domain_id == domain.domain_id)
        body = {
            "domain_id": domain.domain_id,
            "domain": domain.domain,
            "dependency_order": domain.dependency_order,
            "incoming_dependency_count": incoming,
            "outgoing_dependency_count": outgoing,
            "gate_count": len(gates),
            "passed_gate_count": sum(item.passed for item in gates),
            "stage_count": domain.stage_count,
            "evaluation_check_count": domain.evaluation_check_count,
            "source_artifact_count": domain.source_artifact_count,
            "ready": domain.accepted and all(item.passed for item in gates),
            "source_runtime_address": domain.source_runtime_address,
        }
        views.append(
            ProgramReleaseDomainView(
                **body,
                content_address=content_hash(body, prefix="program-release-domain-view"),
            )
        )
    accepted = (
        snapshot.accepted
        and len(views) == 16
        and all(item.ready for item in views)
        and tuple(item.domain_id for item in views)
        == tuple(item.domain_id for item in snapshot.domains)
    )
    body = {"bundle_id": snapshot.bundle_id, "views": tuple(views), "accepted": accepted}
    return ProgramReleaseReviewViews(
        snapshot.bundle_id,
        tuple(views),
        accepted,
        content_hash(body, prefix="program-release-review-views"),
    )


def audit_program_release_review_views(
    views: ProgramReleaseReviewViews,
    snapshot: ProgramReleaseSnapshot,
) -> tuple[ProgramReleaseClosureCheck, ...]:
    """Check view joins against normalized closure resources."""

    def check(
        check_id: str, passed: bool, observed: object, expected: object, detail: str
    ) -> ProgramReleaseClosureCheck:
        return program_release_closure_check(
            check_id,
            ProgramReleaseClosurePlane.RECONCILIATION,
            passed,
            observed,
            expected,
            detail,
        )

    domain_by_id = {item.domain_id: item for item in snapshot.domains}
    view_by_id = {item.domain_id: item for item in views.views}
    checks = (
        check("view-accepted", views.accepted, views.accepted, True, "joined views are accepted"),
        check(
            "view-count",
            len(views.views) == len(snapshot.domains),
            len(views.views),
            len(snapshot.domains),
            "one view exists per domain",
        ),
        check(
            "view-identities",
            len(view_by_id) == len(views.views),
            len(view_by_id),
            len(views.views),
            "view identities are unique",
        ),
        check(
            "view-order",
            tuple(view_by_id) == tuple(domain_by_id),
            tuple(view_by_id),
            tuple(domain_by_id),
            "view order follows domain order",
        ),
        check(
            "view-addresses",
            all(item.content_address for item in views.views),
            sum(bool(item.content_address) for item in views.views),
            len(views.views),
            "view addresses are present",
        ),
        check(
            "view-runtime-joins",
            all(
                view_by_id[key].source_runtime_address == domain_by_id[key].source_runtime_address
                for key in domain_by_id
            ),
            True,
            True,
            "views retain runtime addresses",
        ),
        check(
            "view-gate-joins",
            all(
                view_by_id[key].gate_count == 6 and view_by_id[key].passed_gate_count == 6
                for key in domain_by_id
            ),
            True,
            True,
            "views retain six passed gates",
        ),
        check(
            "view-dependency-joins",
            all(
                view_by_id[key].incoming_dependency_count
                + view_by_id[key].outgoing_dependency_count
                == 15
                for key in domain_by_id
            ),
            True,
            True,
            "views retain complete dependency fan-in and fan-out",
        ),
        check(
            "view-contributions",
            sum(item.evaluation_check_count for item in views.views)
            == sum(item.evaluation_check_count for item in snapshot.domains),
            True,
            True,
            "views conserve evaluation contributions",
        ),
    )
    return checks


def render_program_release_review_views(views: ProgramReleaseReviewViews) -> bytes:
    """Render a concise public reviewer table."""

    lines = [
        "# Program release domain views",
        "",
        "| Domain | Order | In | Out | Gates | Stages | Evaluations | Artifacts | Ready |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    lines.extend(
        f"| {item.domain_id} | {item.dependency_order} | {item.incoming_dependency_count} | "
        f"{item.outgoing_dependency_count} | {item.passed_gate_count}/{item.gate_count} | "
        f"{item.stage_count} | {item.evaluation_check_count} | {item.source_artifact_count} | "
        f"{'yes' if item.ready else 'no'} |"
        for item in views.views
    )
    return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = [
    name
    for name in globals()
    if name.startswith("build_program_release_review")
    or name.startswith("audit_program_release_review")
    or name.startswith("render_program_release_review")
    or name.startswith("ProgramRelease")
]

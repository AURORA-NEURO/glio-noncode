"""Cross-artifact release control for module certification.

The matrix says what was observed, lineage says where observations came from,
and quality says how the observations aggregate.  This module reconciles those
three independently-addressed artifacts and applies the release-readiness
policy without executing source code or treating a score as a substitute for
review.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_certification_contracts import (
    CertificationCheckKind,
    CertificationState,
    ModuleCertificationMatrix,
)
from .module_certification_lineage_contracts import (
    CertificationLineageTargetKind,
    ModuleCertificationLineage,
)
from .module_certification_quality_contracts import (
    CertificationReadiness,
    ModuleCertificationQualityReport,
)
from .module_certification_release_contracts import (
    MODULE_CERTIFICATION_RELEASE_BOUNDARY,
    MODULE_CERTIFICATION_RELEASE_DEFAULT_LIMIT,
    MODULE_CERTIFICATION_RELEASE_MAX_LIMIT,
    MODULE_CERTIFICATION_RELEASE_VERSION,
    CertificationReleasePlane,
    ModuleCertificationReleaseCheck,
    ModuleCertificationReleaseReport,
    address_module_certification_release_check,
)
from .serialization import canonical_json, content_hash, jsonable

_FORBIDDEN_KEYS = frozenset(
    {
        "agent",
        "agent_id",
        "assistant",
        "author",
        "email",
        "language",
        "model",
        "patient",
        "subject",
    }
)


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key).casefold() in _FORBIDDEN_KEYS or _contains_forbidden(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden(item) for item in value)
    return False


def _check(
    check_id: str,
    plane: CertificationReleasePlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleCertificationReleaseCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ModuleCertificationReleaseCheck(
        **body,
        content_address=_address(body, "module-certification-release-check"),
    )


def _checks(
    matrix: ModuleCertificationMatrix,
    lineage: ModuleCertificationLineage,
    quality: ModuleCertificationQualityReport,
) -> tuple[ModuleCertificationReleaseCheck, ...]:
    module_ids = {item.module_id for item in matrix.rows}
    evidence_ids = {item.evidence_id for item in lineage.evidence}
    source_ids = {item.evidence_id for item in lineage.evidence if item.kind.value == "source"}
    module_edges = [
        item for item in lineage.edges if item.target_kind is CertificationLineageTargetKind.MODULE
    ]
    blocking_rows = {
        row.module_id for row in matrix.rows if row.state is CertificationState.BLOCKED
    }
    check_kinds = {item.kind for item in quality.check_coverage}
    family_total = sum(item.module_count for item in quality.family_coverage)
    checks = [
        _check(
            "address-links",
            CertificationReleasePlane.BOUNDARY,
            bool(matrix.content_address and lineage.content_address and quality.content_address),
            3,
            3,
            "all component addresses are present",
        ),
        _check(
            "module-count-conservation",
            CertificationReleasePlane.MATRIX,
            lineage.module_count == matrix.module_count,
            lineage.module_count,
            matrix.module_count,
            "lineage and matrix module counts agree",
        ),
        _check(
            "source-evidence-conservation",
            CertificationReleasePlane.LINEAGE,
            len(source_ids) == matrix.module_count,
            len(source_ids),
            matrix.module_count,
            "every matrix module has one source evidence identity",
        ),
        _check(
            "evidence-edge-conservation",
            CertificationReleasePlane.LINEAGE,
            all(
                item.target_kind is CertificationLineageTargetKind.EVIDENCE
                and item.target_id in evidence_ids
                for item in lineage.edges
                if item.target_kind is CertificationLineageTargetKind.EVIDENCE
            ),
            sum(
                item.target_kind is CertificationLineageTargetKind.EVIDENCE
                for item in lineage.edges
            ),
            len(evidence_ids),
            "evidence edges point to retained evidence rows",
        ),
        _check(
            "dependency-source-conservation",
            CertificationReleasePlane.LINEAGE,
            all(item.source_module in module_ids for item in module_edges),
            len({item.source_module for item in module_edges}),
            "known module IDs",
            "dependency edges have discovered source modules",
        ),
        _check(
            "dependency-resolution-explicit",
            CertificationReleasePlane.LINEAGE,
            all(isinstance(item.resolved, bool) for item in module_edges),
            sum(item.resolved for item in module_edges),
            len(module_edges),
            "resolved and unresolved dependency states are explicit",
        ),
        _check(
            "check-kind-conservation",
            CertificationReleasePlane.QUALITY,
            check_kinds == {item.value for item in CertificationCheckKind},
            len(check_kinds),
            len(tuple(CertificationCheckKind)),
            "quality covers every certification check kind",
        ),
        _check(
            "family-count-conservation",
            CertificationReleasePlane.QUALITY,
            family_total == matrix.module_count,
            family_total,
            matrix.module_count,
            "family measures partition matrix modules",
        ),
        _check(
            "blocker-reconciliation",
            CertificationReleasePlane.QUALITY,
            set(quality.blocker_modules) == blocking_rows,
            len(quality.blocker_modules),
            len(blocking_rows),
            "quality blocker IDs match blocked matrix rows",
        ),
        _check(
            "quality-address-link",
            CertificationReleasePlane.QUALITY,
            quality.matrix_address == matrix.content_address
            and quality.lineage_address == lineage.content_address,
            (quality.matrix_address, quality.lineage_address),
            (matrix.content_address, lineage.content_address),
            "quality report links the exact matrix and lineage addresses",
        ),
        _check(
            "public-key-boundary",
            CertificationReleasePlane.BOUNDARY,
            not _contains_forbidden(jsonable(matrix.to_dict(include_rows=False)))
            and not _contains_forbidden(jsonable(lineage.to_dict(include_rows=False)))
            and not _contains_forbidden(jsonable(quality.to_dict(include_measures=False))),
            "clean",
            "clean",
            "component summaries expose no forbidden public keys",
        ),
        _check(
            "matrix-check-state-conservation",
            CertificationReleasePlane.MATRIX,
            all(
                row.passed_count + row.failed_count + row.not_applicable_count == len(row.checks)
                for row in matrix.rows
            ),
            sum(len(row.checks) for row in matrix.rows),
            "conserved per row",
            "matrix check counts are conserved",
        ),
        _check(
            "release-readiness-policy",
            CertificationReleasePlane.QUALITY,
            quality.readiness is CertificationReadiness.READY,
            quality.readiness.value,
            CertificationReadiness.READY.value,
            "release eligibility requires ready quality status",
        ),
    ]
    return tuple(sorted(checks, key=lambda item: item.check_id))


def _actions(quality: ModuleCertificationQualityReport) -> tuple[str, ...]:
    actions: set[str] = set()
    if quality.blocker_modules:
        actions.add("resolve blocking module checks")
    if quality.top_gaps:
        actions.add("close prioritized certification gaps")
    if quality.evidence_coverage_percent < 100.0:
        actions.add("add missing test, documentation, or export evidence")
    if not actions:
        actions.add("retain release control and monitor subsequent diffs")
    return tuple(sorted(actions))


def build_module_certification_release(
    matrix: ModuleCertificationMatrix,
    lineage: ModuleCertificationLineage,
    quality: ModuleCertificationQualityReport,
) -> ModuleCertificationReleaseReport:
    """Reconcile certification artifacts and classify release eligibility."""

    if not isinstance(matrix, ModuleCertificationMatrix):
        raise ValidationError("release requires a typed certification matrix")
    if not isinstance(lineage, ModuleCertificationLineage):
        raise ValidationError("release requires a typed certification lineage")
    if not isinstance(quality, ModuleCertificationQualityReport):
        raise ValidationError("release requires a typed certification quality report")
    if quality.matrix_address != matrix.content_address:
        raise ValidationError("release quality does not link to matrix")
    if quality.lineage_address != lineage.content_address:
        raise ValidationError("release quality does not link to lineage")
    checks = _checks(matrix, lineage, quality)
    passed = sum(item.passed for item in checks)
    body = {
        "matrix_address": matrix.content_address,
        "lineage_address": lineage.content_address,
        "quality_address": quality.content_address,
        "checks": checks,
        "passed_count": passed,
        "failed_count": len(checks) - passed,
        "readiness": quality.readiness.value,
        "accepted": all(
            item.passed for item in checks if item.check_id != "release-readiness-policy"
        ),
        "release_eligible": all(item.passed for item in checks),
        "recommended_actions": _actions(quality),
    }
    return ModuleCertificationReleaseReport(
        **body,
        content_address=_address(body, "module-certification-release"),
    )


def verify_module_certification_release(
    value: ModuleCertificationReleaseReport,
) -> ModuleCertificationReleaseReport:
    """Verify release check and aggregate addresses without source access."""

    if not isinstance(value, ModuleCertificationReleaseReport):
        raise ValidationError("release verification requires a typed report")
    for check in value.checks:
        if address_module_certification_release_check(check) != check.content_address:
            raise ValidationError(f"release check address mismatch: {check.check_id}")
    body = {
        "matrix_address": value.matrix_address,
        "lineage_address": value.lineage_address,
        "quality_address": value.quality_address,
        "checks": value.checks,
        "passed_count": value.passed_count,
        "failed_count": value.failed_count,
        "readiness": value.readiness,
        "accepted": value.accepted,
        "release_eligible": value.release_eligible,
        "recommended_actions": value.recommended_actions,
    }
    if _address(body, "module-certification-release") != value.content_address:
        raise ValidationError("module certification release address mismatch")
    return value


def query_module_certification_release(
    value: ModuleCertificationReleaseReport,
    *,
    plane: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_CERTIFICATION_RELEASE_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded page over release reconciliation checks."""

    if not isinstance(value, ModuleCertificationReleaseReport):
        raise ValidationError("release query requires a typed report")
    if offset < 0 or limit < 1 or limit > MODULE_CERTIFICATION_RELEASE_MAX_LIMIT:
        raise ValidationError("release pagination is invalid")
    rows = list(value.checks)
    if plane is not None:
        rows = [item for item in rows if item.plane.value == plane]
    if passed is not None:
        rows = [item for item in rows if item.passed is passed]
    if text:
        rows = [
            item for item in rows if text.casefold() in canonical_json(item.to_dict()).casefold()
        ]
    body = {
        "version": MODULE_CERTIFICATION_RELEASE_VERSION,
        "resource": "checks",
        "query": {"plane": plane, "passed": passed, "text": text, "offset": offset, "limit": limit},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(rows),
        "items": tuple(jsonable(item) for item in rows[offset : offset + limit]),
        "release_address": value.content_address,
        "readiness": value.readiness,
        "accepted": value.accepted,
        "release_eligible": value.release_eligible,
    }
    return body | {"content_address": _address(body, "module-certification-release-query")}


def module_certification_release_json(value: ModuleCertificationReleaseReport) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_certification_release_checks_csv(value: ModuleCertificationReleaseReport) -> str:
    fields = (
        "check_id",
        "plane",
        "passed",
        "observed",
        "required",
        "detail",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_certification_release_markdown(
    value: ModuleCertificationReleaseReport,
) -> str:
    lines = [
        "# Module certification release control",
        "",
        f"- Readiness: **{value.readiness}**",
        f"- Release eligible: **{str(value.release_eligible).lower()}**",
        f"- Checks passed: **{value.passed_count}/{value.check_count}**",
        f"- Accepted artifact: **{str(value.accepted).lower()}**",
        "",
        "| Check | Plane | Passed | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for item in value.checks:
        lines.append(
            f"| `{item.check_id}` | {item.plane.value} | "
            f"{str(item.passed).lower()} | {item.detail} |"
        )
    lines.extend(["", "## Recommended actions", ""])
    lines.extend(f"- {item}" for item in value.recommended_actions)
    return "\n".join(lines) + "\n"


def module_certification_release_schema() -> dict[str, Any]:
    return {
        "version": MODULE_CERTIFICATION_RELEASE_VERSION,
        "boundary": MODULE_CERTIFICATION_RELEASE_BOUNDARY,
        "planes": [item.value for item in CertificationReleasePlane],
        "check_fields": [
            "check_id",
            "plane",
            "passed",
            "observed",
            "required",
            "detail",
            "content_address",
        ],
        "report_fields": [
            "matrix_address",
            "lineage_address",
            "quality_address",
            "checks",
            "passed_count",
            "failed_count",
            "readiness",
            "accepted",
            "release_eligible",
            "recommended_actions",
            "content_address",
        ],
        "readiness": ["ready", "warning", "blocked"],
        "policy": (
            "release_eligible requires every reconciliation check to pass and readiness to be ready"
        ),
        "query_filters": ["plane", "passed", "text"],
    }


def module_certification_release_capabilities() -> dict[str, Any]:
    operations = (
        "link_matrix_lineage_quality",
        "conserve_module_counts",
        "conserve_source_evidence",
        "conserve_evidence_edges",
        "audit_dependency_sources",
        "audit_dependency_resolution",
        "audit_check_kinds",
        "audit_family_counts",
        "reconcile_blocker_modules",
        "audit_quality_links",
        "audit_public_keys",
        "audit_matrix_check_counts",
        "classify_release_eligibility",
        "query_release_checks",
        "export_release_checks_csv",
        "render_release_markdown",
        "verify_release_addresses",
    )
    return {
        "version": MODULE_CERTIFICATION_RELEASE_VERSION,
        "boundary": MODULE_CERTIFICATION_RELEASE_BOUNDARY,
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
        "static_only": True,
        "source_execution": False,
        "release_gate": "release_eligible",
    }


__all__ = [
    "build_module_certification_release",
    "module_certification_release_capabilities",
    "module_certification_release_checks_csv",
    "module_certification_release_json",
    "module_certification_release_schema",
    "query_module_certification_release",
    "render_module_certification_release_markdown",
    "verify_module_certification_release",
]

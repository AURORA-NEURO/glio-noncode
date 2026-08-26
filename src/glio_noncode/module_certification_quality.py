"""Coverage quality and readiness views over certification and lineage data."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_certification_contracts import (
    CertificationCheckKind,
    CertificationCheckState,
    CertificationState,
    ModuleCertificationMatrix,
)
from .module_certification_lineage_contracts import (
    CertificationEvidenceKind,
    ModuleCertificationLineage,
)
from .module_certification_quality_contracts import (
    MODULE_CERTIFICATION_QUALITY_BOUNDARY,
    MODULE_CERTIFICATION_QUALITY_DEFAULT_LIMIT,
    MODULE_CERTIFICATION_QUALITY_MAX_GAPS,
    MODULE_CERTIFICATION_QUALITY_MAX_LIMIT,
    MODULE_CERTIFICATION_QUALITY_VERSION,
    CertificationReadiness,
    ModuleCertificationCoverageMeasure,
    ModuleCertificationFamilyMeasure,
    ModuleCertificationQualityReport,
    address_module_certification_coverage,
    address_module_certification_family,
)
from .serialization import canonical_json, content_hash, jsonable


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _coverage(matrix: ModuleCertificationMatrix) -> tuple[ModuleCertificationCoverageMeasure, ...]:
    rows: list[ModuleCertificationCoverageMeasure] = []
    module_count = matrix.module_count
    for kind in sorted(CertificationCheckKind, key=lambda item: item.value):
        checks = [check for row in matrix.rows for check in row.checks if check.kind is kind]
        passed = sum(check.state is CertificationCheckState.PASSED for check in checks)
        failed = sum(check.state is CertificationCheckState.FAILED for check in checks)
        not_applicable = sum(
            check.state is CertificationCheckState.NOT_APPLICABLE for check in checks
        )
        applicable = passed + failed
        coverage_percent = round(applicable / module_count * 100.0, 2) if module_count else 0.0
        pass_percent = round(passed / applicable * 100.0, 2) if applicable else 0.0
        body = {
            "kind": kind.value,
            "module_count": module_count,
            "applicable_count": applicable,
            "passed_count": passed,
            "failed_count": failed,
            "not_applicable_count": not_applicable,
            "coverage_percent": coverage_percent,
            "pass_percent": pass_percent,
        }
        rows.append(
            ModuleCertificationCoverageMeasure(
                **body,
                content_address=_address(body, "module-certification-coverage"),
            )
        )
    return tuple(rows)


def _families(matrix: ModuleCertificationMatrix) -> tuple[ModuleCertificationFamilyMeasure, ...]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in matrix.rows:
        grouped[row.family].append(row)
    rows: list[ModuleCertificationFamilyMeasure] = []
    for family in sorted(grouped):
        selected = tuple(grouped[family])
        count = len(selected)
        score = round(sum(item.score for item in selected) / count, 6) if count else 0.0
        body = {
            "family": family,
            "module_count": count,
            "certified_count": sum(item.state is CertificationState.CERTIFIED for item in selected),
            "review_count": sum(item.state is CertificationState.REVIEW for item in selected),
            "blocked_count": sum(item.state is CertificationState.BLOCKED for item in selected),
            "uncovered_count": sum(item.state is CertificationState.UNCOVERED for item in selected),
            "overall_score": score,
            "gap_count": sum(item.gap_count for item in selected),
            "coverage_percent": round(
                sum(item.state is CertificationState.CERTIFIED for item in selected)
                / count
                * 100.0,
                2,
            )
            if count
            else 0.0,
        }
        rows.append(
            ModuleCertificationFamilyMeasure(
                **body,
                content_address=_address(body, "module-certification-family"),
            )
        )
    return tuple(rows)


def _blockers(matrix: ModuleCertificationMatrix) -> tuple[str, ...]:
    blocking_kinds = {
        CertificationCheckKind.PARSE,
        CertificationCheckKind.DEPENDENCY,
        CertificationCheckKind.BOUNDARY,
    }
    return tuple(
        sorted(
            row.module_id
            for row in matrix.rows
            if row.state is CertificationState.BLOCKED
            or any(
                check.kind in blocking_kinds and check.state is CertificationCheckState.FAILED
                for check in row.checks
            )
        )
    )


def _readiness(
    matrix: ModuleCertificationMatrix,
    lineage: ModuleCertificationLineage,
    blockers: tuple[str, ...],
) -> CertificationReadiness:
    if blockers or not matrix.accepted or not lineage.accepted:
        return CertificationReadiness.BLOCKED
    if any(row.state is not CertificationState.CERTIFIED for row in matrix.rows):
        return CertificationReadiness.WARNING
    return CertificationReadiness.READY


def build_module_certification_quality(
    matrix: ModuleCertificationMatrix,
    lineage: ModuleCertificationLineage,
) -> ModuleCertificationQualityReport:
    """Build conserved check-kind, family, blocker, and readiness measures."""

    if not isinstance(matrix, ModuleCertificationMatrix):
        raise ValidationError("quality requires a typed certification matrix")
    if not isinstance(lineage, ModuleCertificationLineage):
        raise ValidationError("quality requires a typed certification lineage")
    if lineage.matrix_address != matrix.content_address:
        raise ValidationError("quality lineage does not belong to the matrix")
    check_coverage = _coverage(matrix)
    family_coverage = _families(matrix)
    blockers = _blockers(matrix)
    ranked_gaps = sorted(
        matrix.gaps, key=lambda item: (item.priority, item.module_id, item.kind.value)
    )
    top_gaps = tuple(
        sorted(gap.gap_id for gap in ranked_gaps[:MODULE_CERTIFICATION_QUALITY_MAX_GAPS])
    )
    covered_modules = {
        item.module_id
        for item in lineage.evidence
        if item.kind
        in {
            CertificationEvidenceKind.TEST,
            CertificationEvidenceKind.DOCUMENTATION,
            CertificationEvidenceKind.EXPORT,
        }
    }
    evidence_percent = (
        round(len(covered_modules) / matrix.module_count * 100.0, 2) if matrix.module_count else 0.0
    )
    readiness = _readiness(matrix, lineage, blockers)
    body = {
        "matrix_address": matrix.content_address,
        "lineage_address": lineage.content_address,
        "check_coverage": check_coverage,
        "family_coverage": family_coverage,
        "blocker_modules": blockers,
        "top_gaps": top_gaps,
        "overall_score": matrix.overall_score,
        "evidence_coverage_percent": evidence_percent,
        "readiness": readiness,
        "accepted": matrix.accepted and lineage.accepted,
    }
    return ModuleCertificationQualityReport(
        **body,
        content_address=_address(body, "module-certification-quality"),
    )


def verify_module_certification_quality(
    value: ModuleCertificationQualityReport,
) -> ModuleCertificationQualityReport:
    """Verify measure addresses and the aggregate quality address."""

    if not isinstance(value, ModuleCertificationQualityReport):
        raise ValidationError("quality verification requires a typed report")
    for item in value.check_coverage:
        if address_module_certification_coverage(item) != item.content_address:
            raise ValidationError(f"quality coverage address mismatch: {item.kind}")
    for item in value.family_coverage:
        if address_module_certification_family(item) != item.content_address:
            raise ValidationError(f"quality family address mismatch: {item.family}")
    body = {
        "matrix_address": value.matrix_address,
        "lineage_address": value.lineage_address,
        "check_coverage": value.check_coverage,
        "family_coverage": value.family_coverage,
        "blocker_modules": value.blocker_modules,
        "top_gaps": value.top_gaps,
        "overall_score": value.overall_score,
        "evidence_coverage_percent": value.evidence_coverage_percent,
        "readiness": value.readiness,
        "accepted": value.accepted,
    }
    if _address(body, "module-certification-quality") != value.content_address:
        raise ValidationError("module certification quality address mismatch")
    return value


def _query_rows(value: ModuleCertificationQualityReport, resource: str) -> list[Any]:
    if resource == "checks":
        return list(value.check_coverage)
    if resource == "families":
        return list(value.family_coverage)
    if resource == "blockers":
        return [{"module_id": item} for item in value.blocker_modules]
    if resource == "gaps":
        return [{"gap_id": item} for item in value.top_gaps]
    if resource == "summary":
        return [value.to_dict(include_measures=False)]
    raise ValidationError("quality resource must be checks, families, blockers, gaps, or summary")


def query_module_certification_quality(
    value: ModuleCertificationQualityReport,
    *,
    resource: str = "checks",
    text: str | None = None,
    family: str | None = None,
    kind: str | None = None,
    offset: int = 0,
    limit: int = MODULE_CERTIFICATION_QUALITY_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded quality page for dashboards and release checks."""

    if not isinstance(value, ModuleCertificationQualityReport):
        raise ValidationError("quality query requires a typed report")
    if offset < 0 or limit < 1 or limit > MODULE_CERTIFICATION_QUALITY_MAX_LIMIT:
        raise ValidationError("quality pagination is invalid")
    rows = _query_rows(value, resource)
    if family is not None and resource == "families":
        rows = [item for item in rows if item.family == family]
    if kind is not None and resource == "checks":
        rows = [item for item in rows if item.kind == kind]
    if text:
        rows = [
            item for item in rows if text.casefold() in canonical_json(jsonable(item)).casefold()
        ]
    items = tuple(jsonable(item) for item in rows[offset : offset + limit])
    body = {
        "version": MODULE_CERTIFICATION_QUALITY_VERSION,
        "resource": resource,
        "query": {
            "text": text,
            "family": family,
            "kind": kind,
            "offset": offset,
            "limit": limit,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(rows),
        "items": items,
        "quality_address": value.content_address,
        "readiness": value.readiness.value,
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-certification-quality-query")}


def module_certification_quality_json(value: ModuleCertificationQualityReport) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_certification_quality_csv(value: ModuleCertificationQualityReport) -> str:
    fields = (
        "kind",
        "module_count",
        "applicable_count",
        "passed_count",
        "failed_count",
        "not_applicable_count",
        "coverage_percent",
        "pass_percent",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.check_coverage:
        writer.writerow(item.to_dict())
    return output.getvalue()


def module_certification_family_csv(value: ModuleCertificationQualityReport) -> str:
    fields = (
        "family",
        "module_count",
        "certified_count",
        "review_count",
        "blocked_count",
        "uncovered_count",
        "overall_score",
        "gap_count",
        "coverage_percent",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.family_coverage:
        writer.writerow(item.to_dict())
    return output.getvalue()


def render_module_certification_quality_markdown(
    value: ModuleCertificationQualityReport,
) -> str:
    """Render a release-oriented quality summary without source payloads."""

    lines = [
        "# Module certification quality",
        "",
        f"- Readiness: **{value.readiness.value}**",
        f"- Overall score: **{value.overall_score * 100:.2f}%**",
        f"- Evidence coverage: **{value.evidence_coverage_percent:.2f}%**",
        f"- Blockers: **{len(value.blocker_modules):,}**",
        f"- Accepted: **{str(value.accepted).lower()}**",
        "",
        "| Check kind | Coverage | Pass rate | Passed | Failed | N/A |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in value.check_coverage:
        lines.append(
            f"| {item.kind} | {item.coverage_percent:.2f}% | {item.pass_percent:.2f}% | "
            f"{item.passed_count} | {item.failed_count} | {item.not_applicable_count} |"
        )
    lines.extend(
        [
            "",
            "| Family | Modules | Certified | Review | Blocked | Score | Gaps |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in value.family_coverage:
        lines.append(
            f"| `{item.family}` | {item.module_count} | {item.certified_count} | "
            f"{item.review_count} | {item.blocked_count} | {item.overall_score * 100:.2f}% | "
            f"{item.gap_count} |"
        )
    if value.blocker_modules:
        lines.extend(
            ["", "## Blocking modules", "", *[f"- `{item}`" for item in value.blocker_modules]]
        )
    return "\n".join(lines) + "\n"


def module_certification_quality_schema() -> dict[str, Any]:
    return {
        "version": MODULE_CERTIFICATION_QUALITY_VERSION,
        "boundary": MODULE_CERTIFICATION_QUALITY_BOUNDARY,
        "readiness": [item.value for item in CertificationReadiness],
        "resources": ["checks", "families", "blockers", "gaps", "summary"],
        "coverage_fields": [
            "kind",
            "module_count",
            "applicable_count",
            "passed_count",
            "failed_count",
            "not_applicable_count",
            "coverage_percent",
            "pass_percent",
            "content_address",
        ],
        "family_fields": [
            "family",
            "module_count",
            "certified_count",
            "review_count",
            "blocked_count",
            "uncovered_count",
            "overall_score",
            "gap_count",
            "coverage_percent",
            "content_address",
        ],
        "report_fields": [
            "matrix_address",
            "lineage_address",
            "check_coverage",
            "family_coverage",
            "blocker_modules",
            "top_gaps",
            "overall_score",
            "evidence_coverage_percent",
            "readiness",
            "accepted",
            "content_address",
        ],
        "conservation": [
            "passed plus failed equals applicable per check kind",
            "applicable plus not_applicable equals module count per check kind",
            "family state counts equal family module count",
            "blockers are unique and sorted module IDs",
        ],
        "thresholds": {
            "top_gap_limit": MODULE_CERTIFICATION_QUALITY_MAX_GAPS,
            "query_limit": MODULE_CERTIFICATION_QUALITY_MAX_LIMIT,
        },
    }


def module_certification_quality_capabilities() -> dict[str, Any]:
    operations = (
        "measure_check_kind_coverage",
        "measure_check_pass_rates",
        "measure_family_readiness",
        "identify_blocking_modules",
        "rank_top_gaps",
        "measure_evidence_coverage",
        "classify_release_readiness",
        "query_check_measures",
        "query_family_measures",
        "query_blockers",
        "query_top_gaps",
        "export_quality_csv",
        "export_family_csv",
        "render_quality_markdown",
        "verify_measure_addresses",
    )
    return {
        "version": MODULE_CERTIFICATION_QUALITY_VERSION,
        "boundary": MODULE_CERTIFICATION_QUALITY_BOUNDARY,
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
        "matrix_execution": False,
        "source_execution": False,
        "readiness_values": [item.value for item in CertificationReadiness],
    }


__all__ = [
    "build_module_certification_quality",
    "module_certification_family_csv",
    "module_certification_quality_capabilities",
    "module_certification_quality_csv",
    "module_certification_quality_json",
    "module_certification_quality_schema",
    "query_module_certification_quality",
    "render_module_certification_quality_markdown",
    "verify_module_certification_quality",
]

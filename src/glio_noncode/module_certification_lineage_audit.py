"""Independent graph, coverage, and public-boundary audit for lineage."""

from __future__ import annotations

import csv
import io
from collections import Counter
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_certification_lineage_audit_contracts import (
    MODULE_CERTIFICATION_LINEAGE_AUDIT_BOUNDARY,
    MODULE_CERTIFICATION_LINEAGE_AUDIT_MAX_LIMIT,
    MODULE_CERTIFICATION_LINEAGE_AUDIT_VERSION,
    CertificationLineageAuditPlane,
    ModuleCertificationLineageAudit,
    ModuleCertificationLineageAuditCheck,
    address_module_certification_lineage_audit_check,
)
from .module_certification_lineage_contracts import (
    CertificationEvidenceKind,
    CertificationLineageRelation,
    CertificationLineageTargetKind,
    ModuleCertificationLineage,
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
    plane: CertificationLineageAuditPlane,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ModuleCertificationLineageAuditCheck:
    body = {
        "check_id": check_id,
        "plane": plane,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ModuleCertificationLineageAuditCheck(
        **body,
        content_address=_address(body, "module-certification-lineage-audit-check"),
    )


def _checks(value: ModuleCertificationLineage) -> tuple[ModuleCertificationLineageAuditCheck, ...]:
    evidence_ids = tuple(item.evidence_id for item in value.evidence)
    evidence_set = set(evidence_ids)
    module_ids = {item.module_id for item in value.evidence}
    evidence_edges = [
        item for item in value.edges if item.target_kind is CertificationLineageTargetKind.EVIDENCE
    ]
    module_edges = [
        item for item in value.edges if item.target_kind is CertificationLineageTargetKind.MODULE
    ]
    evidence_edge_targets = {item.target_id for item in evidence_edges}
    source_count = sum(item.kind is CertificationEvidenceKind.SOURCE for item in value.evidence)
    relation_counts = Counter(item.relation.value for item in value.edges)
    expected_counts = {
        kind.value: len({item.module_id for item in value.evidence if item.kind is kind})
        for kind in CertificationEvidenceKind
    }
    expected_relations = {
        relation.value: relation_counts.get(relation.value, 0)
        for relation in CertificationLineageRelation
    }
    checks = [
        _check(
            "evidence-identities-unique",
            CertificationLineageAuditPlane.IDENTITY,
            len(evidence_ids) == len(evidence_set),
            len(evidence_set),
            len(evidence_ids),
            "evidence IDs are unique",
        ),
        _check(
            "evidence-addresses-present",
            CertificationLineageAuditPlane.IDENTITY,
            all(bool(item.content_address) for item in value.evidence),
            len(value.evidence),
            len(value.evidence),
            "every evidence row has a content address",
        ),
        _check(
            "source-module-coverage",
            CertificationLineageAuditPlane.COVERAGE,
            source_count == value.module_count,
            source_count,
            value.module_count,
            "source evidence covers every module row",
        ),
        _check(
            "source-module-uniqueness",
            CertificationLineageAuditPlane.COVERAGE,
            len(
                {
                    item.module_id
                    for item in value.evidence
                    if item.kind is CertificationEvidenceKind.SOURCE
                }
            )
            == source_count,
            len(
                {
                    item.module_id
                    for item in value.evidence
                    if item.kind is CertificationEvidenceKind.SOURCE
                }
            ),
            source_count,
            "source evidence has one row per module",
        ),
        _check(
            "evidence-edge-targets",
            CertificationLineageAuditPlane.GRAPH,
            evidence_edge_targets == evidence_set,
            len(evidence_edge_targets),
            len(evidence_set),
            "every evidence row has one graph target",
        ),
        _check(
            "edge-evidence-references",
            CertificationLineageAuditPlane.GRAPH,
            all(
                identifier in evidence_set
                for item in value.edges
                for identifier in item.evidence_ids
            ),
            sum(len(item.evidence_ids) for item in value.edges),
            "known evidence IDs",
            "edge support references resolve to evidence rows",
        ),
        _check(
            "edge-source-modules",
            CertificationLineageAuditPlane.GRAPH,
            all(item.source_module in module_ids for item in value.edges),
            len({item.source_module for item in value.edges}),
            "known module IDs",
            "all graph edge sources have source evidence",
        ),
        _check(
            "dependency-relations",
            CertificationLineageAuditPlane.GRAPH,
            all(
                item.target_kind is CertificationLineageTargetKind.MODULE
                and item.relation is CertificationLineageRelation.DEPENDS_ON
                for item in module_edges
            ),
            len(module_edges),
            "depends_on module edges",
            "module targets use the dependency relation",
        ),
        _check(
            "evidence-relations",
            CertificationLineageAuditPlane.GRAPH,
            all(
                item.target_kind is CertificationLineageTargetKind.EVIDENCE
                and item.relation
                in {CertificationLineageRelation.SUPPORTS, CertificationLineageRelation.EXPORTS}
                for item in evidence_edges
            ),
            len(evidence_edges),
            "supports or exports evidence edges",
            "evidence targets use a support relation",
        ),
        _check(
            "covered-kind-counts",
            CertificationLineageAuditPlane.COVERAGE,
            dict(value.covered_module_counts) == expected_counts,
            dict(value.covered_module_counts),
            expected_counts,
            "covered module counters match evidence rows",
        ),
        _check(
            "relation-counts",
            CertificationLineageAuditPlane.COVERAGE,
            dict(value.relation_counts) == expected_relations,
            dict(value.relation_counts),
            expected_relations,
            "relation counters match graph edges",
        ),
        _check(
            "safe-evidence-paths",
            CertificationLineageAuditPlane.PUBLIC,
            all(
                not item.relative_path.startswith(("/", "\\"))
                and "\\" not in item.relative_path
                and ".." not in item.relative_path.split("/")
                for item in value.evidence
            ),
            "safe",
            "safe",
            "evidence paths are relative and portable",
        ),
        _check(
            "public-key-boundary",
            CertificationLineageAuditPlane.PUBLIC,
            not _contains_forbidden(jsonable(value.to_dict(include_rows=False))),
            "clean",
            "clean",
            "lineage aggregate has no forbidden public keys",
        ),
        _check(
            "record-count-conservation",
            CertificationLineageAuditPlane.LIMITS,
            value.evidence_count == len(value.evidence) and value.edge_count == len(value.edges),
            (value.evidence_count, value.edge_count),
            (len(value.evidence), len(value.edges)),
            "lineage record counters conserve rows",
        ),
    ]
    return tuple(sorted(checks, key=lambda item: item.check_id))


def build_module_certification_lineage_audit(
    value: ModuleCertificationLineage,
) -> ModuleCertificationLineageAudit:
    """Build independent checks without reading source or trusting flags."""

    if not isinstance(value, ModuleCertificationLineage):
        raise ValidationError("lineage audit requires a typed graph")
    checks = _checks(value)
    passed = sum(item.passed for item in checks)
    body = {
        "lineage_address": value.content_address,
        "checks": checks,
        "passed_count": passed,
        "failed_count": len(checks) - passed,
        "accepted": all(item.passed for item in checks),
    }
    return ModuleCertificationLineageAudit(
        **body,
        content_address=_address(body, "module-certification-lineage-audit"),
    )


def verify_module_certification_lineage_audit(
    value: ModuleCertificationLineageAudit,
) -> ModuleCertificationLineageAudit:
    """Verify audit rows and aggregate address without source access."""

    if not isinstance(value, ModuleCertificationLineageAudit):
        raise ValidationError("lineage audit verification requires a typed audit")
    for item in value.checks:
        if address_module_certification_lineage_audit_check(item) != item.content_address:
            raise ValidationError(f"lineage audit check address mismatch: {item.check_id}")
    body = {
        "lineage_address": value.lineage_address,
        "checks": value.checks,
        "passed_count": value.passed_count,
        "failed_count": value.failed_count,
        "accepted": value.accepted,
    }
    if _address(body, "module-certification-lineage-audit") != value.content_address:
        raise ValidationError("lineage audit aggregate address mismatch")
    return value


def query_module_certification_lineage_audit(
    value: ModuleCertificationLineageAudit,
    *,
    plane: str | None = None,
    passed: bool | None = None,
    offset: int = 0,
    limit: int = MODULE_CERTIFICATION_LINEAGE_AUDIT_MAX_LIMIT,
) -> dict[str, Any]:
    """Return a bounded page over independent lineage checks."""

    if not isinstance(value, ModuleCertificationLineageAudit):
        raise ValidationError("lineage audit query requires a typed audit")
    if offset < 0 or limit < 1 or limit > MODULE_CERTIFICATION_LINEAGE_AUDIT_MAX_LIMIT:
        raise ValidationError("lineage audit pagination is invalid")
    rows = list(value.checks)
    if plane is not None:
        rows = [item for item in rows if item.plane.value == plane]
    if passed is not None:
        rows = [item for item in rows if item.passed is passed]
    body = {
        "version": MODULE_CERTIFICATION_LINEAGE_AUDIT_VERSION,
        "resource": "checks",
        "query": {"plane": plane, "passed": passed, "offset": offset, "limit": limit},
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "has_more": offset + limit < len(rows),
        "items": tuple(jsonable(item) for item in rows[offset : offset + limit]),
        "audit_address": value.content_address,
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-certification-lineage-audit-query")}


def module_certification_lineage_audit_json(value: ModuleCertificationLineageAudit) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_certification_lineage_audit_csv(value: ModuleCertificationLineageAudit) -> str:
    fields = ("check_id", "plane", "passed", "observed", "required", "detail", "content_address")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.checks:
        writer.writerow(item.to_dict())
    return output.getvalue()


def module_certification_lineage_audit_schema() -> dict[str, Any]:
    return {
        "version": MODULE_CERTIFICATION_LINEAGE_AUDIT_VERSION,
        "boundary": MODULE_CERTIFICATION_LINEAGE_AUDIT_BOUNDARY,
        "planes": [item.value for item in CertificationLineageAuditPlane],
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
            "lineage_address",
            "checks",
            "passed_count",
            "failed_count",
            "accepted",
            "content_address",
        ],
        "query_filters": ["plane", "passed"],
        "independence": "recomputes graph counters, targets, relations, paths, and public keys",
    }


def module_certification_lineage_audit_capabilities() -> dict[str, Any]:
    operations = (
        "audit_evidence_identities",
        "audit_source_coverage",
        "audit_evidence_edge_targets",
        "audit_edge_evidence_references",
        "audit_edge_source_modules",
        "audit_dependency_relations",
        "audit_evidence_relations",
        "recompute_covered_kind_counts",
        "recompute_relation_counts",
        "audit_relative_paths",
        "audit_public_keys",
        "audit_record_counts",
        "query_audit_checks",
        "export_audit_csv",
        "verify_audit_addresses",
    )
    return {
        "version": MODULE_CERTIFICATION_LINEAGE_AUDIT_VERSION,
        "boundary": MODULE_CERTIFICATION_LINEAGE_AUDIT_BOUNDARY,
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
        "source_execution": False,
        "independent": True,
    }


__all__ = [
    "build_module_certification_lineage_audit",
    "module_certification_lineage_audit_capabilities",
    "module_certification_lineage_audit_csv",
    "module_certification_lineage_audit_json",
    "module_certification_lineage_audit_schema",
    "query_module_certification_lineage_audit",
    "verify_module_certification_lineage_audit",
]

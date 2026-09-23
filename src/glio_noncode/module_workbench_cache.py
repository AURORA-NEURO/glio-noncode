"""Verified durable snapshots for the static module workbench."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from typing import Any

from .errors import ValidationError
from .module_certification import verify_module_certification
from .module_certification_contracts import (
    CertificationCheckKind,
    CertificationCheckState,
    CertificationState,
    ModuleCertificationCheck,
    ModuleCertificationGap,
    ModuleCertificationMatrix,
    ModuleCertificationRow,
)
from .module_certification_lineage import verify_module_certification_lineage
from .module_certification_lineage_contracts import (
    CertificationEvidenceKind,
    CertificationLineageRelation,
    CertificationLineageTargetKind,
    ModuleCertificationEvidence,
    ModuleCertificationLineage,
    ModuleCertificationLineageEdge,
)
from .module_certification_quality import verify_module_certification_quality
from .module_certification_quality_contracts import (
    CertificationReadiness,
    ModuleCertificationCoverageMeasure,
    ModuleCertificationFamilyMeasure,
    ModuleCertificationQualityReport,
)
from .module_inventory import verify_module_inventory
from .module_inventory_contracts import ModuleInventory
from .module_inventory_query import inventory_from_mapping
from .module_workbench import verify_module_workbench
from .module_workbench_contracts import (
    ModuleWorkbenchAssessment,
    ModuleWorkbenchDepthBand,
    ModuleWorkbenchDimension,
    ModuleWorkbenchFamilyRollup,
    ModuleWorkbenchReport,
    ModuleWorkbenchRisk,
    ModuleWorkbenchTask,
    ModuleWorkbenchTaskKind,
)
from .serialization import canonical_json

MODULE_WORKBENCH_CACHE_SCHEMA = "module-workbench-cache-v1"


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str) -> Sequence[Any]:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} must be an array")
    return value


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text")
    return value


def _tuple_text(value: Any, field: str) -> tuple[str, ...]:
    return tuple(_text(item, f"{field}[]") for item in _sequence(value, field))


def _check(value: Mapping[str, Any]) -> ModuleCertificationCheck:
    return ModuleCertificationCheck(
        kind=CertificationCheckKind(_text(value.get("kind"), "check.kind")),
        state=CertificationCheckState(_text(value.get("state"), "check.state")),
        observed=value.get("observed"),
        required=value.get("required"),
        detail=_text(value.get("detail"), "check.detail"),
        evidence=_tuple_text(value.get("evidence", ()), "check.evidence"),
        content_address=_text(value.get("content_address"), "check.content_address"),
    )


def _matrix(value: Mapping[str, Any]) -> ModuleCertificationMatrix:
    rows = []
    for raw in _sequence(value.get("rows", ()), "matrix.rows"):
        row = _mapping(raw, "matrix.row")
        rows.append(
            ModuleCertificationRow(
                module_id=_text(row.get("module_id"), "row.module_id"),
                family=_text(row.get("family"), "row.family"),
                role=_text(row.get("role"), "row.role"),
                physical_lines=int(row.get("physical_lines", 0)),
                public_symbol_count=int(row.get("public_symbol_count", 0)),
                checks=tuple(_check(_mapping(item, "row.check")) for item in _sequence(row.get("checks", ()), "row.checks")),
                passed_count=int(row.get("passed_count", 0)),
                failed_count=int(row.get("failed_count", 0)),
                not_applicable_count=int(row.get("not_applicable_count", 0)),
                score=float(row.get("score", 0.0)),
                state=CertificationState(_text(row.get("state"), "row.state")),
                gap_count=int(row.get("gap_count", 0)),
                content_address=_text(row.get("content_address"), "row.content_address"),
            )
        )
    gaps = []
    for raw in _sequence(value.get("gaps", ()), "matrix.gaps"):
        gap = _mapping(raw, "matrix.gap")
        gaps.append(
            ModuleCertificationGap(
                gap_id=_text(gap.get("gap_id"), "gap.gap_id"),
                module_id=_text(gap.get("module_id"), "gap.module_id"),
                kind=CertificationCheckKind(_text(gap.get("kind"), "gap.kind")),
                priority=int(gap.get("priority", 0)),
                detail=_text(gap.get("detail"), "gap.detail"),
                next_action=_text(gap.get("next_action"), "gap.next_action"),
                evidence=_tuple_text(gap.get("evidence", ()), "gap.evidence"),
                content_address=_text(gap.get("content_address"), "gap.content_address"),
            )
        )
    result = ModuleCertificationMatrix(
        inventory_address=_text(value.get("inventory_address"), "matrix.inventory_address"),
        rows=tuple(rows),
        gaps=tuple(gaps),
        check_kind_count=int(value.get("check_kind_count", 0)),
        module_count=int(value.get("module_count", 0)),
        certified_count=int(value.get("certified_count", 0)),
        review_count=int(value.get("review_count", 0)),
        blocked_count=int(value.get("blocked_count", 0)),
        uncovered_count=int(value.get("uncovered_count", 0)),
        overall_score=float(value.get("overall_score", 0.0)),
        overall_percent=float(value.get("overall_percent", 0.0)),
        accepted=bool(value.get("accepted", False)),
        content_address=_text(value.get("content_address"), "matrix.content_address"),
    )
    return result


def _lineage(value: Mapping[str, Any]) -> ModuleCertificationLineage:
    evidence = []
    for raw in _sequence(value.get("evidence", ()), "lineage.evidence"):
        item = _mapping(raw, "lineage.evidence.item")
        evidence.append(
            ModuleCertificationEvidence(
                evidence_id=_text(item.get("evidence_id"), "evidence.evidence_id"),
                module_id=_text(item.get("module_id"), "evidence.module_id"),
                kind=CertificationEvidenceKind(_text(item.get("kind"), "evidence.kind")),
                relative_path=_text(item.get("relative_path"), "evidence.relative_path"),
                relation=CertificationLineageRelation(_text(item.get("relation"), "evidence.relation")),
                detail=_text(item.get("detail"), "evidence.detail"),
                source_digest=_text(item.get("source_digest"), "evidence.source_digest"),
                line_count=int(item.get("line_count", 0)),
                content_address=_text(item.get("content_address"), "evidence.content_address"),
            )
        )
    edges = []
    for raw in _sequence(value.get("edges", ()), "lineage.edges"):
        item = _mapping(raw, "lineage.edge")
        edges.append(
            ModuleCertificationLineageEdge(
                source_module=_text(item.get("source_module"), "edge.source_module"),
                target_kind=CertificationLineageTargetKind(_text(item.get("target_kind"), "edge.target_kind")),
                target_id=_text(item.get("target_id"), "edge.target_id"),
                relation=CertificationLineageRelation(_text(item.get("relation"), "edge.relation")),
                resolved=bool(item.get("resolved", False)),
                evidence_ids=_tuple_text(item.get("evidence_ids", ()), "edge.evidence_ids"),
                content_address=_text(item.get("content_address"), "edge.content_address"),
            )
        )
    result = ModuleCertificationLineage(
        inventory_address=_text(value.get("inventory_address"), "lineage.inventory_address"),
        matrix_address=_text(value.get("matrix_address"), "lineage.matrix_address"),
        evidence=tuple(evidence),
        edges=tuple(edges),
        module_count=int(value.get("module_count", 0)),
        evidence_count=int(value.get("evidence_count", 0)),
        edge_count=int(value.get("edge_count", 0)),
        covered_module_counts=dict(_mapping(value.get("covered_module_counts", {}), "lineage.covered_module_counts")),
        relation_counts=dict(_mapping(value.get("relation_counts", {}), "lineage.relation_counts")),
        accepted=bool(value.get("accepted", False)),
        content_address=_text(value.get("content_address"), "lineage.content_address"),
    )
    return result


def _quality(value: Mapping[str, Any]) -> ModuleCertificationQualityReport:
    coverage = []
    for raw in _sequence(value.get("check_coverage", ()), "quality.check_coverage"):
        item = _mapping(raw, "quality.coverage")
        coverage.append(ModuleCertificationCoverageMeasure(**{
            "kind": _text(item.get("kind"), "coverage.kind"),
            "module_count": int(item.get("module_count", 0)),
            "applicable_count": int(item.get("applicable_count", 0)),
            "passed_count": int(item.get("passed_count", 0)),
            "failed_count": int(item.get("failed_count", 0)),
            "not_applicable_count": int(item.get("not_applicable_count", 0)),
            "coverage_percent": float(item.get("coverage_percent", 0.0)),
            "pass_percent": float(item.get("pass_percent", 0.0)),
            "content_address": _text(item.get("content_address"), "coverage.content_address"),
        }))
    families = []
    for raw in _sequence(value.get("family_coverage", ()), "quality.family_coverage"):
        item = _mapping(raw, "quality.family")
        families.append(ModuleCertificationFamilyMeasure(**{
            "family": _text(item.get("family"), "family.family"),
            "module_count": int(item.get("module_count", 0)),
            "certified_count": int(item.get("certified_count", 0)),
            "review_count": int(item.get("review_count", 0)),
            "blocked_count": int(item.get("blocked_count", 0)),
            "uncovered_count": int(item.get("uncovered_count", 0)),
            "overall_score": float(item.get("overall_score", 0.0)),
            "gap_count": int(item.get("gap_count", 0)),
            "coverage_percent": float(item.get("coverage_percent", 0.0)),
            "content_address": _text(item.get("content_address"), "family.content_address"),
        }))
    result = ModuleCertificationQualityReport(
        matrix_address=_text(value.get("matrix_address"), "quality.matrix_address"),
        lineage_address=_text(value.get("lineage_address"), "quality.lineage_address"),
        check_coverage=tuple(coverage),
        family_coverage=tuple(families),
        blocker_modules=_tuple_text(value.get("blocker_modules", ()), "quality.blocker_modules"),
        top_gaps=_tuple_text(value.get("top_gaps", ()), "quality.top_gaps"),
        overall_score=float(value.get("overall_score", 0.0)),
        evidence_coverage_percent=float(value.get("evidence_coverage_percent", 0.0)),
        readiness=CertificationReadiness(_text(value.get("readiness"), "quality.readiness")),
        accepted=bool(value.get("accepted", False)),
        content_address=_text(value.get("content_address"), "quality.content_address"),
    )
    return result


def _workbench(value: Mapping[str, Any]) -> ModuleWorkbenchReport:
    dimensions = lambda raw: ModuleWorkbenchDimension(
        name=_text(raw.get("name"), "dimension.name"),
        score=float(raw.get("score", 0.0)),
        observed=int(raw.get("observed", 0)),
        target=int(raw.get("target", 0)),
        detail=_text(raw.get("detail"), "dimension.detail"),
        content_address=_text(raw.get("content_address"), "dimension.content_address"),
    )
    assessments = []
    for raw in _sequence(value.get("assessments", ()), "workbench.assessments"):
        item = _mapping(raw, "workbench.assessment")
        assessments.append(ModuleWorkbenchAssessment(
            module_id=_text(item.get("module_id"), "assessment.module_id"),
            family=_text(item.get("family"), "assessment.family"),
            role=_text(item.get("role"), "assessment.role"),
            state=_text(item.get("state"), "assessment.state"),
            physical_lines=int(item.get("physical_lines", 0)), nonblank_lines=int(item.get("nonblank_lines", 0)),
            public_symbol_count=int(item.get("public_symbol_count", 0)), function_count=int(item.get("function_count", 0)),
            class_count=int(item.get("class_count", 0)), import_count=int(item.get("import_count", 0)),
            local_dependency_count=int(item.get("local_dependency_count", 0)), fan_in=int(item.get("fan_in", 0)),
            fan_out=int(item.get("fan_out", 0)), test_reference_count=int(item.get("test_reference_count", 0)),
            evidence_count=int(item.get("evidence_count", 0)), evidence_kinds=_tuple_text(item.get("evidence_kinds", ()), "assessment.evidence_kinds"),
            dimensions=tuple(dimensions(_mapping(part, "assessment.dimension")) for part in _sequence(item.get("dimensions", ()), "assessment.dimensions")),
            score=float(item.get("score", 0.0)), depth_band=ModuleWorkbenchDepthBand(_text(item.get("depth_band"), "assessment.depth_band")),
            risk=ModuleWorkbenchRisk(_text(item.get("risk"), "assessment.risk")), blockers=_tuple_text(item.get("blockers", ()), "assessment.blockers"),
            strengths=_tuple_text(item.get("strengths", ()), "assessment.strengths"), source_address=_text(item.get("source_address"), "assessment.source_address"),
            content_address=_text(item.get("content_address"), "assessment.content_address"),
        ))
    tasks = []
    for raw in _sequence(value.get("tasks", ()), "workbench.tasks"):
        item = _mapping(raw, "workbench.task")
        tasks.append(ModuleWorkbenchTask(
            task_id=_text(item.get("task_id"), "task.task_id"), module_id=_text(item.get("module_id"), "task.module_id"),
            kind=ModuleWorkbenchTaskKind(_text(item.get("kind"), "task.kind")), priority=int(item.get("priority", 0)),
            title=_text(item.get("title"), "task.title"), rationale=_text(item.get("rationale"), "task.rationale"),
            acceptance=_text(item.get("acceptance"), "task.acceptance"), estimated_impact=float(item.get("estimated_impact", 0.0)),
            evidence=_tuple_text(item.get("evidence", ()), "task.evidence"), content_address=_text(item.get("content_address"), "task.content_address"),
        ))
    families = []
    for raw in _sequence(value.get("families", ()), "workbench.families"):
        item = _mapping(raw, "workbench.family")
        families.append(ModuleWorkbenchFamilyRollup(
            family=_text(item.get("family"), "family.family"), module_count=int(item.get("module_count", 0)),
            deep_count=int(item.get("deep_count", 0)), comprehensive_count=int(item.get("comprehensive_count", 0)),
            blocked_count=int(item.get("blocked_count", 0)), high_risk_count=int(item.get("high_risk_count", 0)),
            average_score=float(item.get("average_score", 0.0)), average_test_references=float(item.get("average_test_references", 0.0)),
            average_evidence=float(item.get("average_evidence", 0.0)), average_fan_out=float(item.get("average_fan_out", 0.0)),
            top_task_kinds=_tuple_text(item.get("top_task_kinds", ()), "family.top_task_kinds"),
            content_address=_text(item.get("content_address"), "family.content_address"),
        ))
    result = ModuleWorkbenchReport(
        inventory_address=_text(value.get("inventory_address"), "workbench.inventory_address"),
        matrix_address=_text(value.get("matrix_address"), "workbench.matrix_address"),
        lineage_address=_text(value.get("lineage_address"), "workbench.lineage_address"),
        quality_address=_text(value.get("quality_address"), "workbench.quality_address"),
        assessments=tuple(assessments), tasks=tuple(tasks), families=tuple(families),
        overall_score=float(value.get("overall_score", 0.0)), overall_percent=float(value.get("overall_percent", 0.0)),
        depth_percent=float(value.get("depth_percent", 0.0)), deep_count=int(value.get("deep_count", 0)),
        comprehensive_count=int(value.get("comprehensive_count", 0)), starter_count=int(value.get("starter_count", 0)),
        blocked_count=int(value.get("blocked_count", 0)), high_risk_count=int(value.get("high_risk_count", 0)),
        risk_counts=dict(_mapping(value.get("risk_counts", {}), "workbench.risk_counts")), accepted=bool(value.get("accepted", False)),
        content_address=_text(value.get("content_address"), "workbench.content_address"),
    )
    return result


def snapshot_payload(
    signature: tuple[tuple[str, int, int], ...],
    inventory: ModuleInventory,
    matrix: ModuleCertificationMatrix,
    lineage: ModuleCertificationLineage,
    quality: ModuleCertificationQualityReport,
    workbench: ModuleWorkbenchReport,
) -> dict[str, Any]:
    """Return a JSON-safe snapshot whose rows remain independently addressed."""

    body = {
        "schema": MODULE_WORKBENCH_CACHE_SCHEMA,
        "signature": [list(item) for item in signature],
        "inventory": inventory.to_dict(include_rows=True),
        "matrix": matrix.to_dict(include_rows=True),
        "lineage": lineage.to_dict(include_rows=True),
        "quality": quality.to_dict(include_measures=True),
        "workbench": workbench.to_dict(include_rows=True),
    }
    body["payload_digest"] = hashlib.sha256(
        canonical_json(body).encode("utf-8")
    ).hexdigest()
    return body


def snapshot_from_mapping(
    value: Mapping[str, Any],
    signature: tuple[tuple[str, int, int], ...],
    *,
    verify_nested: bool = True,
) -> tuple[ModuleInventory, ModuleCertificationMatrix, ModuleCertificationLineage, ModuleCertificationQualityReport, ModuleWorkbenchReport]:
    """Hydrate and independently verify a durable snapshot before use."""

    if _text(value.get("schema"), "cache.schema") != MODULE_WORKBENCH_CACHE_SCHEMA:
        raise ValidationError("module workbench cache schema is unsupported")
    payload_digest = _text(value.get("payload_digest"), "cache.payload_digest")
    unsigned = {key: item for key, item in value.items() if key != "payload_digest"}
    expected_digest = hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()
    if payload_digest != expected_digest:
        raise ValidationError("module workbench cache payload digest is invalid")
    raw_signature = _sequence(value.get("signature", ()), "cache.signature")
    normalized_signature = tuple(tuple(item) for item in raw_signature)
    if normalized_signature != signature:
        raise ValidationError("module workbench cache source signature is stale")
    inventory = inventory_from_mapping(_mapping(value.get("inventory"), "cache.inventory"))
    if verify_nested:
        inventory = verify_module_inventory(inventory)
    matrix = _matrix(_mapping(value.get("matrix"), "cache.matrix"))
    lineage = _lineage(_mapping(value.get("lineage"), "cache.lineage"))
    quality = _quality(_mapping(value.get("quality"), "cache.quality"))
    workbench = _workbench(_mapping(value.get("workbench"), "cache.workbench"))
    if verify_nested:
        matrix = verify_module_certification(matrix)
        lineage = verify_module_certification_lineage(lineage)
        quality = verify_module_certification_quality(quality)
        workbench = verify_module_workbench(workbench)
    if matrix.inventory_address != inventory.content_address:
        raise ValidationError("module workbench cache matrix does not belong to inventory")
    if lineage.inventory_address != inventory.content_address or lineage.matrix_address != matrix.content_address:
        raise ValidationError("module workbench cache lineage does not belong to upstream objects")
    if quality.matrix_address != matrix.content_address or quality.lineage_address != lineage.content_address:
        raise ValidationError("module workbench cache quality does not belong to upstream objects")
    if (
        workbench.inventory_address != inventory.content_address
        or workbench.matrix_address != matrix.content_address
        or workbench.lineage_address != lineage.content_address
        or workbench.quality_address != quality.content_address
    ):
        raise ValidationError("module workbench cache report does not conserve upstream objects")
    return inventory, matrix, lineage, quality, workbench


__all__ = ["MODULE_WORKBENCH_CACHE_SCHEMA", "snapshot_from_mapping", "snapshot_payload"]

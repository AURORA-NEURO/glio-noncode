"""Rank module review work by explainable static implementation pressure."""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_certification_contracts import ModuleCertificationMatrix
from .module_certification_lineage_contracts import ModuleCertificationLineage
from .module_certification_quality_contracts import ModuleCertificationQualityReport
from .module_workbench_contracts import ModuleWorkbenchReport
from .module_workbench_triage_contracts import (
    MODULE_WORKBENCH_TRIAGE_VERSION,
    ModuleWorkbenchTriageItem,
    ModuleWorkbenchTriageReport,
    address_module_workbench_triage,
    address_module_workbench_triage_item,
)
from .serialization import canonical_json, content_hash

_RISK_PRESSURE = {"blocker": 1.0, "high": 0.8, "medium": 0.45, "low": 0.15}
_DEPTH_PRESSURE = {
    "blocked": 1.0,
    "starter": 0.78,
    "established": 0.48,
    "deep": 0.2,
    "comprehensive": 0.04,
}


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _priority_score(
    *,
    risk: str,
    depth_band: str,
    score: float,
    gap_count: int,
    unresolved_edge_count: int,
    fan_in: int,
    test_reference_count: int,
    task_count: int,
) -> float:
    pressure = (
        _RISK_PRESSURE.get(risk, 0.3) * 0.28
        + _DEPTH_PRESSURE.get(depth_band, 0.5) * 0.22
        + min(gap_count / 4.0, 1.0) * 0.16
        + min(unresolved_edge_count / 4.0, 1.0) * 0.12
        + min(fan_in / 10.0, 1.0) * 0.09
        + (0.08 if test_reference_count == 0 else 0.0)
        + (1.0 - score) * 0.08
        + min(task_count / 4.0, 1.0) * 0.05
    )
    return round(min(max(pressure, 0.0), 1.0), 6)


def _reasons(
    *,
    risk: str,
    depth_band: str,
    score: float,
    gap_count: int,
    unresolved_edge_count: int,
    fan_in: int,
    test_reference_count: int,
) -> tuple[str, ...]:
    values: list[str] = []
    if risk == "blocker":
        values.append("blocker_risk")
    elif risk == "high":
        values.append("high_risk")
    if depth_band in {"blocked", "starter"}:
        values.append("shallow_depth")
    if gap_count:
        values.append("certification_gap")
    if unresolved_edge_count:
        values.append("unresolved_lineage")
    if fan_in >= 5:
        values.append("high_fan_in")
    if test_reference_count == 0:
        values.append("missing_test_reference")
    if score < 0.5:
        values.append("low_score")
    return tuple(values)


def build_module_workbench_triage(
    workbench: ModuleWorkbenchReport,
    matrix: ModuleCertificationMatrix,
    lineage: ModuleCertificationLineage,
    quality: ModuleCertificationQualityReport,
) -> ModuleWorkbenchTriageReport:
    """Build one ranked row for every module in the verified workbench."""

    expected_types = {
        "workbench": ModuleWorkbenchReport,
        "matrix": ModuleCertificationMatrix,
        "lineage": ModuleCertificationLineage,
        "quality": ModuleCertificationQualityReport,
    }
    for name, value in (
        ("workbench", workbench),
        ("matrix", matrix),
        ("lineage", lineage),
        ("quality", quality),
    ):
        if not isinstance(value, expected_types[name]):
            raise ValidationError(f"triage requires a typed {name}")
    if (
        matrix.inventory_address != workbench.inventory_address
        or lineage.inventory_address != workbench.inventory_address
        or lineage.matrix_address != matrix.content_address
        or quality.matrix_address != matrix.content_address
        or quality.lineage_address != lineage.content_address
        or workbench.lineage_address != lineage.content_address
        or workbench.quality_address != quality.content_address
    ):
        raise ValidationError("triage upstream addresses do not belong together")

    matrix_rows = {item.module_id: item for item in matrix.rows}
    evidence_counts = Counter(item.module_id for item in lineage.evidence)
    outgoing = Counter[str]()
    incoming = Counter[str]()
    unresolved = Counter[str]()
    for edge in lineage.edges:
        if edge.source_module in matrix_rows:
            outgoing[edge.source_module] += 1
            if not edge.resolved:
                unresolved[edge.source_module] += 1
        if edge.target_kind.value == "module" and edge.target_id in matrix_rows:
            incoming[edge.target_id] += 1
            if not edge.resolved:
                unresolved[edge.target_id] += 1
    tasks_by_module: dict[str, list[Any]] = defaultdict(list)
    for task in workbench.tasks:
        tasks_by_module[task.module_id].append(task)

    provisional_rows: list[dict[str, Any]] = []
    for assessment in workbench.assessments:
        certification = matrix_rows.get(assessment.module_id)
        if certification is None:
            raise ValidationError(f"triage is missing certification row: {assessment.module_id}")
        module_tasks = sorted(
            tasks_by_module.get(assessment.module_id, ()),
            key=lambda item: (item.priority, -item.estimated_impact, item.task_id),
        )
        gap_count = certification.gap_count
        evidence_count = evidence_counts[assessment.module_id]
        unresolved_count = unresolved[assessment.module_id]
        priority_score = _priority_score(
            risk=assessment.risk.value,
            depth_band=assessment.depth_band.value,
            score=assessment.score,
            gap_count=gap_count,
            unresolved_edge_count=unresolved_count,
            fan_in=assessment.fan_in,
            test_reference_count=assessment.test_reference_count,
            task_count=len(module_tasks),
        )
        provisional_rows.append(
            {
                "module_id": assessment.module_id,
                "family": assessment.family,
                "role": assessment.role,
                "risk": assessment.risk.value,
                "depth_band": assessment.depth_band.value,
                "score": assessment.score,
                "priority_score": priority_score,
                "fan_in": assessment.fan_in,
                "fan_out": assessment.fan_out,
                "gap_count": gap_count,
                "evidence_count": evidence_count,
                "unresolved_edge_count": unresolved_count,
                "task_count": len(module_tasks),
                "reasons": _reasons(
                    risk=assessment.risk.value,
                    depth_band=assessment.depth_band.value,
                    score=assessment.score,
                    gap_count=gap_count,
                    unresolved_edge_count=unresolved_count,
                    fan_in=assessment.fan_in,
                    test_reference_count=assessment.test_reference_count,
                ),
                "recommended_task_ids": tuple(item.task_id for item in module_tasks[:3]),
            }
        )
    provisional_rows.sort(
        key=lambda item: (
            -item["priority_score"],
            -_RISK_PRESSURE.get(item["risk"], 0.0),
            -item["fan_in"],
            -item["gap_count"],
            item["module_id"],
        )
    )
    items: list[ModuleWorkbenchTriageItem] = []
    reasons = Counter[str]()
    risks = Counter[str]()
    for rank, row in enumerate(provisional_rows, start=1):
        provisional = ModuleWorkbenchTriageItem(rank=rank, content_address="pending", **row)
        item = ModuleWorkbenchTriageItem(
            rank=rank,
            content_address=address_module_workbench_triage_item(provisional),
            **row,
        )
        items.append(item)
        reasons.update(item.reasons)
        risks[item.risk] += 1
    body = {
        "workbench_address": workbench.content_address,
        "matrix_address": matrix.content_address,
        "lineage_address": lineage.content_address,
        "quality_address": quality.content_address,
        "items": tuple(items),
        "reason_counts": dict(sorted(reasons.items())),
        "risk_counts": dict(sorted(risks.items())),
        "accepted": workbench.accepted and matrix.accepted and lineage.accepted and quality.accepted,
    }
    provisional = ModuleWorkbenchTriageReport(content_address="pending", **body)
    return ModuleWorkbenchTriageReport(
        content_address=address_module_workbench_triage(provisional),
        **body,
    )


def verify_module_workbench_triage(value: ModuleWorkbenchTriageReport) -> ModuleWorkbenchTriageReport:
    """Verify every row and the aggregate triage address."""

    if not isinstance(value, ModuleWorkbenchTriageReport):
        raise ValidationError("triage verification requires a typed report")
    for item in value.items:
        if address_module_workbench_triage_item(item) != item.content_address:
            raise ValidationError(f"triage item address mismatch: {item.module_id}")
    if address_module_workbench_triage(value) != value.content_address:
        raise ValidationError("triage report address mismatch")
    return value


def query_module_workbench_triage(
    value: ModuleWorkbenchTriageReport,
    *,
    module_id: str | None = None,
    risk: str | None = None,
    depth_band: str | None = None,
    reason: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, Any]:
    """Return a bounded, explainable triage page."""

    if not isinstance(value, ModuleWorkbenchTriageReport):
        raise ValidationError("triage query requires a typed report")
    if offset < 0 or limit < 1 or limit > 512:
        raise ValidationError("triage paging is invalid")
    rows = [item.to_dict() for item in value.items]
    if module_id:
        rows = [item for item in rows if item["module_id"] == module_id]
    if risk:
        rows = [item for item in rows if item["risk"] == risk]
    if depth_band:
        rows = [item for item in rows if item["depth_band"] == depth_band]
    if reason:
        rows = [item for item in rows if reason in item["reasons"]]
    if text:
        rows = [item for item in rows if text.casefold() in canonical_json(item).casefold()]
    body = {
        "triage_address": value.content_address,
        "query": {
            "module_id": module_id,
            "risk": risk,
            "depth_band": depth_band,
            "reason": reason,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-triage-query")}


def module_workbench_triage_json(value: ModuleWorkbenchTriageReport) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_triage_csv(value: ModuleWorkbenchTriageReport) -> str:
    fields = (
        "rank",
        "module_id",
        "family",
        "role",
        "risk",
        "depth_band",
        "score",
        "priority_score",
        "fan_in",
        "fan_out",
        "gap_count",
        "evidence_count",
        "unresolved_edge_count",
        "task_count",
        "reasons",
        "recommended_task_ids",
        "content_address",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for item in value.items:
        row = item.to_dict()
        row["reasons"] = ",".join(item.reasons)
        row["recommended_task_ids"] = ",".join(item.recommended_task_ids)
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_triage_markdown(value: ModuleWorkbenchTriageReport) -> str:
    lines = [
        "# Module workbench triage",
        "",
        f"- Items: {len(value.items)}",
        f"- Accepted: {'yes' if value.accepted else 'no'}",
        f"- Address: `{value.content_address}`",
        "",
        "| Rank | Module | Priority | Risk | Depth | Gaps | Unresolved | Reasons |",
        "| ---: | --- | ---: | --- | --- | ---: | ---: | --- |",
    ]
    for item in value.items:
        reasons = ", ".join(item.reasons) or "none"
        lines.append(
            f"| {item.rank} | `{item.module_id}` | {item.priority_score:.3f} | {item.risk} | {item.depth_band} | {item.gap_count} | {item.unresolved_edge_count} | {reasons} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_triage_schema() -> dict[str, Any]:
    return {
        "version": MODULE_WORKBENCH_TRIAGE_VERSION,
        "boundary": "public_aggregate_module_workbench_triage",
        "resources": ["items"],
        "reason_codes": [
            "blocker_risk",
            "high_risk",
            "shallow_depth",
            "certification_gap",
            "unresolved_lineage",
            "high_fan_in",
            "missing_test_reference",
            "low_score",
        ],
        "ordering": "priority score descending, risk pressure, fan-in, gap count, module ID",
        "path_free": True,
        "timestamp_free": True,
        "read_only": True,
    }


def module_workbench_triage_capabilities() -> dict[str, Any]:
    operations = (
        "rank_modules_by_review_pressure",
        "explain_priority_with_reason_codes",
        "include_dependency_pressure",
        "include_certification_gaps",
        "include_recommended_tasks",
        "filter_module",
        "filter_risk",
        "filter_depth_band",
        "filter_reason",
        "query_bounded_pages",
        "export_json",
        "export_csv",
        "export_markdown",
        "verify_address",
    )
    return {
        "version": MODULE_WORKBENCH_TRIAGE_VERSION,
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench_triage",
    "module_workbench_triage_capabilities",
    "module_workbench_triage_csv",
    "module_workbench_triage_json",
    "module_workbench_triage_schema",
    "query_module_workbench_triage",
    "render_module_workbench_triage_markdown",
    "verify_module_workbench_triage",
]

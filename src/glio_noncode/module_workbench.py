"""Build and query the module-by-module implementation workbench."""

from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

from .errors import ValidationError
from .module_certification_contracts import (
    CertificationState,
    ModuleCertificationMatrix,
)
from .module_certification_lineage_contracts import ModuleCertificationLineage
from .module_certification_quality_contracts import ModuleCertificationQualityReport
from .module_inventory_contracts import ModuleInventory, ModuleRecord, ModuleState
from .module_inventory_query import inventory_from_mapping
from .module_workbench_contracts import (
    MODULE_WORKBENCH_DEFAULT_LIMIT,
    MODULE_WORKBENCH_MAX_LIMIT,
    ModuleWorkbenchAssessment,
    ModuleWorkbenchDepthBand,
    ModuleWorkbenchDimension,
    ModuleWorkbenchFamilyRollup,
    ModuleWorkbenchReport,
    ModuleWorkbenchRisk,
    ModuleWorkbenchTask,
    ModuleWorkbenchTaskKind,
    address_module_workbench_assessment,
    address_module_workbench_dimension,
    address_module_workbench_family,
    address_module_workbench_task,
)
from .serialization import canonical_json, content_hash


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(body, prefix=prefix)


def _dimension(
    name: str,
    score: float,
    observed: int,
    target: int,
    detail: str,
) -> ModuleWorkbenchDimension:
    body = {
        "name": name,
        "score": round(max(0.0, min(1.0, score)), 6),
        "observed": max(0, observed),
        "target": max(0, target),
        "detail": detail,
    }
    return ModuleWorkbenchDimension(
        **body,
        content_address=_address(body, "module-workbench-dimension"),
    )


def _fan_counts(inventory: ModuleInventory) -> tuple[dict[str, int], dict[str, int]]:
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    for dependency in inventory.dependencies:
        if not dependency.resolved or dependency.source_module == dependency.target_module:
            continue
        outgoing[dependency.source_module].add(dependency.target_module)
        incoming[dependency.target_module].add(dependency.source_module)
    return (
        {module_id: len(values) for module_id, values in outgoing.items()},
        {module_id: len(values) for module_id, values in incoming.items()},
    )


def _evidence_index(lineage: ModuleCertificationLineage) -> dict[str, tuple[Any, ...]]:
    grouped: dict[str, list[Any]] = defaultdict(list)
    for evidence in lineage.evidence:
        grouped[evidence.module_id].append(evidence)
    return {
        module_id: tuple(sorted(rows, key=lambda item: item.evidence_id))
        for module_id, rows in grouped.items()
    }


def _row_index(matrix: ModuleCertificationMatrix) -> dict[str, Any]:
    return {row.module_id: row for row in matrix.rows}


def _quality_blockers(quality: ModuleCertificationQualityReport) -> set[str]:
    return set(quality.blocker_modules)


def _assessment(
    module: ModuleRecord,
    certification: Any,
    evidence: tuple[Any, ...],
    fan_in: int,
    fan_out: int,
    quality_blockers: set[str],
) -> ModuleWorkbenchAssessment:
    parse_score = 1.0 if module.state is ModuleState.PARSED else 0.0
    test_score = min(1.0, module.test_reference_count / 2.0)
    public_score = min(1.0, module.public_symbol_count / 5.0)
    implementation_score = min(1.0, module.nonblank_lines / 240.0)
    dependency_score = (
        1.0
        if module.import_count == 0
        else min(1.0, module.local_dependency_count / module.import_count)
    )
    connectivity_score = min(1.0, (fan_in + fan_out) / 6.0)
    evidence_score = min(1.0, len(evidence) / 3.0)
    dimensions = tuple(
        sorted(
            (
                _dimension(
                    "connectivity",
                    connectivity_score,
                    fan_in + fan_out,
                    6,
                    f"{fan_in} incoming and {fan_out} outgoing resolved module links",
                ),
                _dimension(
                    "dependency_resolution",
                    dependency_score,
                    module.local_dependency_count,
                    module.import_count,
                    f"{module.local_dependency_count} of {module.import_count} imports "
                    "resolve locally",
                ),
                _dimension(
                    "evidence",
                    evidence_score,
                    len(evidence),
                    3,
                    f"{len(evidence)} lineage artifacts reference this module",
                ),
                _dimension(
                    "implementation_scale",
                    implementation_score,
                    module.nonblank_lines,
                    240,
                    f"{module.nonblank_lines} nonblank source lines measure implementation depth",
                ),
                _dimension(
                    "parse",
                    parse_score,
                    int(module.state is ModuleState.PARSED),
                    1,
                    f"static parser state is {module.state.value}",
                ),
                _dimension(
                    "public_contract",
                    public_score,
                    module.public_symbol_count,
                    5,
                    f"{module.public_symbol_count} public symbols are visible in the "
                    "static surface",
                ),
                _dimension(
                    "test_references",
                    test_score,
                    module.test_reference_count,
                    2,
                    f"{module.test_reference_count} test references were found",
                ),
            ),
            key=lambda item: item.name,
        )
    )
    score = round(
        sum(
            (
                parse_score,
                test_score,
                public_score,
                implementation_score,
                dependency_score,
                connectivity_score,
                evidence_score,
            )
        )
        / len(dimensions),
        6,
    )
    blockers: set[str] = set()
    if module.state is ModuleState.PARSE_ERROR:
        blockers.add("parse_error")
    if module.import_count and module.local_dependency_count < module.import_count:
        blockers.add("unresolved_local_import")
    if certification is None or certification.state is CertificationState.BLOCKED:
        blockers.add("certification_blocked")
    if module.module_id in quality_blockers:
        blockers.add("quality_blocker")
    if blockers:
        depth_band = ModuleWorkbenchDepthBand.BLOCKED
    elif score < 0.35:
        depth_band = ModuleWorkbenchDepthBand.STARTER
    elif score < 0.62:
        depth_band = ModuleWorkbenchDepthBand.ESTABLISHED
    elif score < 0.84:
        depth_band = ModuleWorkbenchDepthBand.DEEP
    else:
        depth_band = ModuleWorkbenchDepthBand.COMPREHENSIVE
    if blockers:
        risk = ModuleWorkbenchRisk.BLOCKER
    elif score < 0.55 or module.state is not ModuleState.PARSED:
        risk = ModuleWorkbenchRisk.HIGH
    elif score < 0.76 or fan_out > 16 or module.nonblank_lines > 900:
        risk = ModuleWorkbenchRisk.MEDIUM
    else:
        risk = ModuleWorkbenchRisk.LOW
    strengths: set[str] = set()
    if module.state is ModuleState.PARSED:
        strengths.add("parsed")
    if module.test_reference_count:
        strengths.add("test_referenced")
    if module.public_symbol_count >= 5:
        strengths.add("public_contract")
    if not module.import_count or module.local_dependency_count == module.import_count:
        strengths.add("imports_resolved")
    if len(evidence) >= 3:
        strengths.add("evidence_linked")
    if 20 <= module.nonblank_lines <= 900:
        strengths.add("bounded_size")
    if fan_in + fan_out >= 3:
        strengths.add("connected")
    evidence_kinds = tuple(sorted({item.kind.value for item in evidence}))
    body = {
        "module_id": module.module_id,
        "family": module.family,
        "role": module.role,
        "state": module.state,
        "physical_lines": module.physical_lines,
        "nonblank_lines": module.nonblank_lines,
        "public_symbol_count": module.public_symbol_count,
        "function_count": module.function_count,
        "class_count": module.class_count,
        "import_count": module.import_count,
        "local_dependency_count": module.local_dependency_count,
        "fan_in": fan_in,
        "fan_out": fan_out,
        "test_reference_count": module.test_reference_count,
        "evidence_count": len(evidence),
        "evidence_kinds": evidence_kinds,
        "dimensions": dimensions,
        "score": score,
        "depth_band": depth_band,
        "risk": risk,
        "blockers": tuple(sorted(blockers)),
        "strengths": tuple(sorted(strengths)),
        "source_address": module.content_address,
    }
    return ModuleWorkbenchAssessment(
        **body,
        content_address=address_module_workbench_assessment(
            ModuleWorkbenchAssessment(**body, content_address="pending")
        ),
    )


def _task(
    module: ModuleWorkbenchAssessment,
    kind: ModuleWorkbenchTaskKind,
    priority: int,
    title: str,
    rationale: str,
    acceptance: str,
    impact: float,
    evidence: tuple[str, ...],
) -> ModuleWorkbenchTask:
    body = {
        "task_id": f"{module.module_id}:{kind.value}",
        "module_id": module.module_id,
        "kind": kind,
        "priority": max(0, min(100, priority)),
        "title": title,
        "rationale": rationale,
        "acceptance": acceptance,
        "estimated_impact": round(max(0.0, min(1.0, impact)), 6),
        "evidence": tuple(sorted(set(evidence))),
    }
    return ModuleWorkbenchTask(
        **body,
        content_address=address_module_workbench_task(
            ModuleWorkbenchTask(**body, content_address="pending")
        ),
    )


def _tasks(
    assessment: ModuleWorkbenchAssessment,
    certification: Any,
    evidence: tuple[Any, ...],
) -> tuple[ModuleWorkbenchTask, ...]:
    refs = tuple(sorted({assessment.source_address, *(item.content_address for item in evidence)}))
    tasks: list[ModuleWorkbenchTask] = []
    if "parse_error" in assessment.blockers:
        tasks.append(
            _task(
                assessment,
                ModuleWorkbenchTaskKind.REPAIR_PARSE,
                0,
                "Repair static parsing",
                "The module cannot contribute reliable symbols or dependency evidence "
                "while parsing fails.",
                "The module parses successfully and its source digest is refreshed.",
                1.0,
                refs,
            )
        )
    if "unresolved_local_import" in assessment.blockers:
        tasks.append(
            _task(
                assessment,
                ModuleWorkbenchTaskKind.RESOLVE_DEPENDENCY,
                5,
                "Resolve local dependency edges",
                "Unresolved imports weaken closure, certification, and downstream impact analysis.",
                "Every package-local import is represented by a resolved inventory edge "
                "or explicitly external.",
                0.9,
                refs,
            )
        )
    if assessment.test_reference_count < 2:
        tasks.append(
            _task(
                assessment,
                ModuleWorkbenchTaskKind.ADD_TEST,
                20 if assessment.test_reference_count else 15,
                "Deepen executable coverage",
                f"The static index found {assessment.test_reference_count} test references; "
                "two or more independent references provide a stronger depth signal.",
                "Focused tests exercise the module's primary public behavior and appear "
                "in the evidence lineage.",
                0.65,
                refs,
            )
        )
    if "documentation" not in assessment.evidence_kinds:
        tasks.append(
            _task(
                assessment,
                ModuleWorkbenchTaskKind.ADD_DOCUMENTATION,
                35,
                "Document module contract",
                "No documentation artifact is linked to this module in the static lineage graph.",
                "A stable documentation reference explains inputs, outputs, failure "
                "behavior, and operating boundaries.",
                0.45,
                refs,
            )
        )
    if assessment.public_symbol_count < 5:
        tasks.append(
            _task(
                assessment,
                ModuleWorkbenchTaskKind.EXPAND_PUBLIC_CONTRACT,
                45,
                "Clarify the public contract",
                f"The module exposes {assessment.public_symbol_count} public symbols, "
                "leaving limited statically visible contract surface.",
                "The intended public surface is explicit, documented, and covered "
                "without exporting incidental helpers.",
                0.4,
                refs,
            )
        )
    if assessment.nonblank_lines > 900:
        tasks.append(
            _task(
                assessment,
                ModuleWorkbenchTaskKind.DECOMPOSE_OVERSIZED,
                50,
                "Decompose oversized implementation",
                f"The module contains {assessment.nonblank_lines} nonblank lines, "
                "increasing review and change-impact concentration.",
                "Responsibilities are separated into cohesive modules with preserved "
                "public behavior and explicit dependency edges.",
                0.55,
                refs,
            )
        )
    if assessment.fan_in >= 8 or assessment.fan_out >= 16:
        tasks.append(
            _task(
                assessment,
                ModuleWorkbenchTaskKind.REVIEW_INTEGRATION,
                55,
                "Review integration boundaries",
                f"The module has {assessment.fan_in} incoming and {assessment.fan_out} "
                "outgoing resolved links, so changes may propagate widely.",
                "High-impact callers and callees have contract tests, compatibility "
                "notes, and bounded change impact.",
                0.5,
                refs,
            )
        )
    if certification is None or certification.state is not CertificationState.CERTIFIED:
        tasks.append(
            _task(
                assessment,
                ModuleWorkbenchTaskKind.CLOSE_CERTIFICATION,
                65,
                "Close remaining certification gaps",
                "The module is not currently certified across the static contract checks.",
                "The certification row is certified and each failed check has linked evidence.",
                0.7,
                refs,
            )
        )
    return tuple(sorted(tasks, key=lambda item: item.task_id))


def _family_rollups(
    assessments: tuple[ModuleWorkbenchAssessment, ...],
    tasks: tuple[ModuleWorkbenchTask, ...],
) -> tuple[ModuleWorkbenchFamilyRollup, ...]:
    grouped: dict[str, list[ModuleWorkbenchAssessment]] = defaultdict(list)
    task_kinds: dict[str, Counter[str]] = defaultdict(Counter)
    for assessment in assessments:
        grouped[assessment.family].append(assessment)
    for task in tasks:
        family = next(
            (item.family for item in assessments if item.module_id == task.module_id),
            "core",
        )
        task_kinds[family][task.kind.value] += 1
    rows: list[ModuleWorkbenchFamilyRollup] = []
    for family in sorted(grouped):
        selected = grouped[family]
        body = {
            "family": family,
            "module_count": len(selected),
            "deep_count": sum(
                item.depth_band is ModuleWorkbenchDepthBand.DEEP for item in selected
            ),
            "comprehensive_count": sum(
                item.depth_band is ModuleWorkbenchDepthBand.COMPREHENSIVE for item in selected
            ),
            "blocked_count": sum(
                item.depth_band is ModuleWorkbenchDepthBand.BLOCKED for item in selected
            ),
            "high_risk_count": sum(
                item.risk in {ModuleWorkbenchRisk.BLOCKER, ModuleWorkbenchRisk.HIGH}
                for item in selected
            ),
            "average_score": round(sum(item.score for item in selected) / len(selected), 6),
            "average_test_references": round(
                sum(item.test_reference_count for item in selected) / len(selected), 6
            ),
            "average_evidence": round(
                sum(item.evidence_count for item in selected) / len(selected), 6
            ),
            "average_fan_out": round(sum(item.fan_out for item in selected) / len(selected), 6),
            "top_task_kinds": tuple(
                sorted(
                    (kind for kind, _ in task_kinds[family].most_common(3)),
                )
            ),
        }
        provisional = ModuleWorkbenchFamilyRollup(**body, content_address="pending")
        rows.append(
            ModuleWorkbenchFamilyRollup(
                **body,
                content_address=address_module_workbench_family(provisional),
            )
        )
    return tuple(rows)


def build_module_workbench(
    inventory: ModuleInventory | Mapping[str, Any],
    matrix: ModuleCertificationMatrix,
    lineage: ModuleCertificationLineage,
    quality: ModuleCertificationQualityReport,
) -> ModuleWorkbenchReport:
    """Build a deterministic depth assessment and actionable task queue."""

    selected_inventory = (
        inventory if isinstance(inventory, ModuleInventory) else inventory_from_mapping(inventory)
    )
    if not isinstance(matrix, ModuleCertificationMatrix):
        raise ValidationError("workbench requires a typed certification matrix")
    if not isinstance(lineage, ModuleCertificationLineage):
        raise ValidationError("workbench requires a typed certification lineage")
    if not isinstance(quality, ModuleCertificationQualityReport):
        raise ValidationError("workbench requires a typed certification quality report")
    if matrix.inventory_address != selected_inventory.content_address:
        raise ValidationError("workbench matrix does not belong to inventory")
    if (
        lineage.inventory_address != selected_inventory.content_address
        or lineage.matrix_address != matrix.content_address
    ):
        raise ValidationError("workbench lineage does not belong to inventory and matrix")
    if (
        quality.matrix_address != matrix.content_address
        or quality.lineage_address != lineage.content_address
    ):
        raise ValidationError("workbench quality does not belong to matrix and lineage")
    outgoing, incoming = _fan_counts(selected_inventory)
    evidence_by_module = _evidence_index(lineage)
    certifications = _row_index(matrix)
    blockers = _quality_blockers(quality)
    assessments = tuple(
        sorted(
            (
                _assessment(
                    module,
                    certifications.get(module.module_id),
                    evidence_by_module.get(module.module_id, ()),
                    incoming.get(module.module_id, 0),
                    outgoing.get(module.module_id, 0),
                    blockers,
                )
                for module in selected_inventory.modules
            ),
            key=lambda item: item.module_id,
        )
    )
    task_rows = tuple(
        sorted(
            (
                task
                for assessment in assessments
                for task in _tasks(
                    assessment,
                    certifications.get(assessment.module_id),
                    evidence_by_module.get(assessment.module_id, ()),
                )
            ),
            key=lambda item: (item.priority, item.module_id, item.task_id),
        )
    )
    # The contract stores tasks by stable ID, while the query planner uses the
    # explicit priority field to present the most valuable work first.
    task_rows = tuple(sorted(task_rows, key=lambda item: item.task_id))
    families = _family_rollups(assessments, task_rows)
    overall = round(
        sum(item.score for item in assessments) / len(assessments) if assessments else 0.0,
        6,
    )
    deep_count = sum(item.depth_band is ModuleWorkbenchDepthBand.DEEP for item in assessments)
    comprehensive_count = sum(
        item.depth_band is ModuleWorkbenchDepthBand.COMPREHENSIVE for item in assessments
    )
    body = {
        "inventory_address": selected_inventory.content_address,
        "matrix_address": matrix.content_address,
        "lineage_address": lineage.content_address,
        "quality_address": quality.content_address,
        "assessments": assessments,
        "tasks": task_rows,
        "families": families,
        "overall_score": overall,
        "overall_percent": round(overall * 100.0, 2),
        "depth_percent": round((deep_count + comprehensive_count) / len(assessments) * 100.0, 2)
        if assessments
        else 0.0,
        "deep_count": deep_count,
        "comprehensive_count": comprehensive_count,
        "starter_count": sum(
            item.depth_band is ModuleWorkbenchDepthBand.STARTER for item in assessments
        ),
        "blocked_count": sum(
            item.depth_band is ModuleWorkbenchDepthBand.BLOCKED for item in assessments
        ),
        "high_risk_count": sum(
            item.risk in {ModuleWorkbenchRisk.BLOCKER, ModuleWorkbenchRisk.HIGH}
            for item in assessments
        ),
        "risk_counts": dict(
            sorted(
                (
                    risk.value,
                    sum(item.risk is risk for item in assessments),
                )
                for risk in ModuleWorkbenchRisk
            )
        ),
        "accepted": selected_inventory.accepted
        and matrix.accepted
        and lineage.accepted
        and quality.accepted,
    }
    provisional = ModuleWorkbenchReport(**body, content_address="pending")
    report_body = provisional.to_dict()
    report_body.pop("content_address", None)
    return ModuleWorkbenchReport(
        **body,
        content_address=_address(report_body, "module-workbench-report"),
    )


def verify_module_workbench(value: ModuleWorkbenchReport) -> ModuleWorkbenchReport:
    """Verify all nested addresses and aggregate conservation fields."""

    if not isinstance(value, ModuleWorkbenchReport):
        raise ValidationError("workbench verification requires a typed report")
    for assessment in value.assessments:
        for dimension in assessment.dimensions:
            if address_module_workbench_dimension(dimension) != dimension.content_address:
                raise ValidationError(f"workbench dimension address mismatch: {dimension.name}")
        if address_module_workbench_assessment(assessment) != assessment.content_address:
            raise ValidationError(f"workbench assessment address mismatch: {assessment.module_id}")
    for task in value.tasks:
        if address_module_workbench_task(task) != task.content_address:
            raise ValidationError(f"workbench task address mismatch: {task.task_id}")
    for family in value.families:
        if address_module_workbench_family(family) != family.content_address:
            raise ValidationError(f"workbench family address mismatch: {family.family}")
    body = value.to_dict()
    address_body = dict(body)
    address_body.pop("content_address", None)
    if _address(address_body, "module-workbench-report") != value.content_address:
        raise ValidationError("module workbench report address mismatch")
    return value


def _query_rows(value: ModuleWorkbenchReport, resource: str) -> list[dict[str, Any]]:
    if resource == "modules":
        return [item.to_dict() for item in value.assessments]
    if resource == "tasks":
        return [item.to_dict() for item in value.tasks]
    if resource == "families":
        return [item.to_dict() for item in value.families]
    if resource == "risks":
        return [{"risk": key, "count": count} for key, count in value.risk_counts.items()]
    if resource == "summary":
        return [value.to_dict(include_rows=False)]
    raise ValidationError("workbench resource must be modules, tasks, families, risks, or summary")


def query_module_workbench(
    value: ModuleWorkbenchReport,
    *,
    resource: str = "modules",
    module_id: str | None = None,
    family: str | None = None,
    depth_band: str | None = None,
    risk: str | None = None,
    kind: str | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return a bounded module, family, risk, or task page."""

    if not isinstance(value, ModuleWorkbenchReport):
        raise ValidationError("workbench query requires a typed report")
    if offset < 0 or limit < 1 or limit > MODULE_WORKBENCH_MAX_LIMIT:
        raise ValidationError("workbench paging is invalid")
    rows = _query_rows(value, resource)
    if module_id and resource in {"modules", "tasks"}:
        rows = [item for item in rows if item.get("module_id") == module_id]
    if family and resource == "families":
        rows = [item for item in rows if item.get("family") == family]
    if depth_band and resource == "modules":
        rows = [item for item in rows if item.get("depth_band") == depth_band]
    if risk and resource in {"modules", "risks"}:
        rows = [item for item in rows if item.get("risk") == risk]
    if kind and resource == "tasks":
        rows = [item for item in rows if item.get("kind") == kind]
    if text:
        needle = text.casefold()
        rows = [item for item in rows if needle in canonical_json(item).casefold()]
    body = {
        "workbench_address": value.content_address,
        "query": {
            "resource": resource,
            "module_id": module_id,
            "family": family,
            "depth_band": depth_band,
            "risk": risk,
            "kind": kind,
            "text": text,
        },
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset : offset + limit],
        "accepted": value.accepted,
    }
    return body | {"content_address": _address(body, "module-workbench-query")}


def module_workbench_csv(value: ModuleWorkbenchReport, resource: str = "modules") -> str:
    """Export a stable flat CSV projection for a selected workbench resource."""

    rows = _query_rows(value, resource)
    if resource == "modules":
        fields = (
            "module_id",
            "family",
            "role",
            "state",
            "score",
            "depth_band",
            "risk",
            "physical_lines",
            "nonblank_lines",
            "public_symbol_count",
            "function_count",
            "class_count",
            "import_count",
            "local_dependency_count",
            "fan_in",
            "fan_out",
            "test_reference_count",
            "evidence_count",
            "blockers",
            "strengths",
            "content_address",
        )
    elif resource == "tasks":
        fields = (
            "task_id",
            "module_id",
            "kind",
            "priority",
            "title",
            "rationale",
            "acceptance",
            "estimated_impact",
            "evidence",
            "content_address",
        )
    elif resource == "families":
        fields = tuple(rows[0].keys()) if rows else ("family",)
    elif resource == "risks":
        fields = ("risk", "count")
    else:
        raise ValidationError("workbench CSV resource must be modules, tasks, families, or risks")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: ";".join(str(item) for item in row.get(field, ()))
                if isinstance(row.get(field), (list, tuple))
                else row.get(field, "")
                for field in fields
            }
        )
    return output.getvalue()


def module_workbench_json(value: ModuleWorkbenchReport) -> str:
    return canonical_json(value.to_dict()) + "\n"


def render_module_workbench_markdown(value: ModuleWorkbenchReport, *, max_rows: int = 100) -> str:
    """Render a bounded operator report for module-by-module implementation work."""

    if max_rows < 1:
        raise ValidationError("max_rows must be positive")
    lines = [
        "# Module implementation workbench",
        "",
        "Static, deterministic depth and action planning over the repository module graph.",
        "",
        f"- Workbench address: `{value.content_address}`",
        f"- Modules: **{len(value.assessments):,}**",
        f"- Tasks: **{len(value.tasks):,}**",
        f"- Overall depth signal: **{value.overall_percent:.2f}%**",
        f"- Deep or comprehensive modules: **{value.deep_count + value.comprehensive_count:,} "
        f"({value.depth_percent:.2f}%)**",
        f"- Blocked / high risk: **{value.blocked_count:,} / {value.high_risk_count:,}**",
        f"- Accepted inputs: **{str(value.accepted).lower()}**",
        "",
        "## Family rollups",
        "",
        "| Family | Modules | Deep | Comprehensive | Blocked | High risk | "
        "Score | Tests | Evidence |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for family in value.families[:max_rows]:
        lines.append(
            f"| {family.family} | {family.module_count:,} | {family.deep_count:,} | "
            f"{family.comprehensive_count:,} | {family.blocked_count:,} | "
            f"{family.high_risk_count:,} | {family.average_score * 100:.2f}% | "
            f"{family.average_test_references:.2f} | {family.average_evidence:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Priority task queue",
            "",
            "| Priority | Module | Kind | Impact | Acceptance |",
            "| ---: | --- | --- | ---: | --- |",
        ]
    )
    for task in sorted(value.tasks, key=lambda item: (item.priority, item.module_id, item.task_id))[
        :max_rows
    ]:
        lines.append(
            f"| {task.priority} | `{task.module_id}` | {task.kind.value} | "
            f"{task.estimated_impact * 100:.0f}% | {task.acceptance} |"
        )
    if len(value.tasks) > max_rows:
        lines.append(f"| … | … | … | … | {len(value.tasks) - max_rows:,} more tasks |")
    lines.extend(
        [
            "",
            "## Module depth sample",
            "",
            "| Module | Family | Score | Band | Risk | Lines | Fan in/out | Tests | Evidence |",
            "| --- | --- | ---: | --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in value.assessments[:max_rows]:
        lines.append(
            f"| `{item.module_id}` | {item.family} | {item.score * 100:.2f}% | "
            f"{item.depth_band.value} | {item.risk.value} | {item.nonblank_lines:,} | "
            f"{item.fan_in}/{item.fan_out} | {item.test_reference_count} | {item.evidence_count} |"
        )
    if len(value.assessments) > max_rows:
        lines.append(
            f"| … | … | … | … | … | … | … | … | "
            f"{len(value.assessments) - max_rows:,} more modules |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_schema() -> dict[str, Any]:
    return {
        "version": "module-workbench-v1",
        "boundary": "public_aggregate_module_workbench",
        "resources": ["modules", "tasks", "families", "risks", "summary"],
        "depth_bands": [item.value for item in ModuleWorkbenchDepthBand],
        "risks": [item.value for item in ModuleWorkbenchRisk],
        "task_kinds": [item.value for item in ModuleWorkbenchTaskKind],
        "dimensions": [
            "connectivity",
            "dependency_resolution",
            "evidence",
            "implementation_scale",
            "parse",
            "public_contract",
            "test_references",
        ],
        "ranges": {
            "score": [0.0, 1.0],
            "percent": [0.0, 100.0],
            "priority": [0, 100],
        },
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_capabilities() -> dict[str, Any]:
    operations = (
        "assess_module_depth",
        "measure_fan_in_and_fan_out",
        "classify_depth_band",
        "classify_delivery_risk",
        "plan_test_work",
        "plan_documentation_work",
        "plan_dependency_work",
        "plan_contract_work",
        "plan_decomposition_work",
        "plan_integration_review",
        "plan_certification_closure",
        "roll_up_families",
        "query_modules",
        "query_tasks",
        "query_families",
        "query_risks",
        "export_json",
        "export_csv",
        "render_markdown",
        "verify_content_addresses",
    )
    return {
        "version": "module-workbench-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "deterministic": True,
        "read_only": True,
    }


__all__ = [
    "build_module_workbench",
    "module_workbench_capabilities",
    "module_workbench_csv",
    "module_workbench_json",
    "module_workbench_schema",
    "query_module_workbench",
    "render_module_workbench_markdown",
    "verify_module_workbench",
]

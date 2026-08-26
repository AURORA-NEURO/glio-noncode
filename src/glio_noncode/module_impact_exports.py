"""Deterministic projections for module-impact review and handoff."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from typing import Any

from .module_impact_contracts import (
    ModuleImpactDiff,
    ModuleImpactGate,
    ModuleImpactReport,
    ModuleImpactVerificationPlan,
)
from .serialization import canonical_json, content_hash


def _csv(rows: Iterable[dict[str, Any]], fields: tuple[str, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: ";".join(str(item) for item in row.get(field, ()))
                if isinstance(row.get(field), (tuple, list))
                else row.get(field, "")
                for field in fields
            }
        )
    return output.getvalue()


def module_impact_diff_json(value: ModuleImpactDiff) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_impact_report_json(value: ModuleImpactReport) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_impact_gate_json(value: ModuleImpactGate) -> str:
    return canonical_json(value.to_dict()) + "\n"


def module_impact_changes_csv(value: ModuleImpactDiff) -> str:
    return _csv(
        (item.to_dict() for item in value.changes),
        (
            "module_id",
            "kind",
            "left_address",
            "right_address",
            "physical_delta",
            "nonblank_delta",
            "public_symbol_delta",
            "import_delta",
            "test_reference_delta",
            "added_symbols",
            "removed_symbols",
            "changed_symbols",
            "added_dependencies",
            "removed_dependencies",
            "severity",
            "content_address",
        ),
    )


def module_impact_dependencies_csv(value: ModuleImpactDiff) -> str:
    return _csv(
        (item.to_dict() for item in value.dependencies),
        (
            "source_module",
            "target_module",
            "import_name",
            "kind",
            "relative",
            "left_resolved",
            "right_resolved",
            "content_address",
        ),
    )


def module_impact_assessments_csv(value: ModuleImpactReport) -> str:
    return _csv(
        (item.to_dict() for item in value.assessments),
        (
            "module_id",
            "propagation",
            "distance",
            "severity",
            "risk_score",
            "direct_change_kind",
            "changed_sources",
            "paths",
            "reasons",
            "content_address",
        ),
    )


def module_impact_tasks_csv(value: ModuleImpactVerificationPlan) -> str:
    return _csv(
        (item.to_dict() for item in value.tasks),
        (
            "task_id",
            "module_id",
            "kind",
            "priority",
            "reason",
            "source_modules",
            "evidence",
            "content_address",
        ),
    )


def module_impact_summary(
    diff: ModuleImpactDiff,
    report: ModuleImpactReport,
    plan: ModuleImpactVerificationPlan,
    gate: ModuleImpactGate,
) -> dict[str, Any]:
    """Return aggregate counters suitable for dashboards and CI output."""

    body = {
        "version": "module-impact-summary-v1",
        "left_inventory_address": diff.left_inventory_address,
        "right_inventory_address": diff.right_inventory_address,
        "diff_address": diff.content_address,
        "impact_address": report.content_address,
        "plan_address": plan.content_address,
        "gate_address": gate.content_address,
        "change_count": diff.change_count,
        "added_count": diff.added_count,
        "removed_count": diff.removed_count,
        "changed_count": diff.changed_count,
        "dependency_change_count": diff.dependency_change_count,
        "impact_count": report.impact_count,
        "direct_count": report.direct_count,
        "dependent_count": report.dependent_count,
        "transitive_count": report.transitive_count,
        "critical_count": report.critical_count,
        "high_count": report.high_count,
        "verification_task_count": plan.task_count,
        "gate_check_count": len(gate.checks),
        "gate_passed_count": gate.passed_count,
        "accepted": gate.accepted,
    }
    return body | {"content_address": content_hash(body, prefix="module-impact-summary")}


def render_module_impact_markdown(
    diff: ModuleImpactDiff,
    report: ModuleImpactReport,
    plan: ModuleImpactVerificationPlan,
    gate: ModuleImpactGate,
    *,
    row_limit: int = 100,
) -> str:
    """Render bounded human review while retaining addressed machine artifacts."""

    if row_limit < 1:
        raise ValueError("row_limit must be positive")
    lines = [
        "# Module impact assessment",
        "",
        f"- Decision: **{gate.state.value}**",
        (
            f"- Changes: {diff.change_count} ({diff.added_count} added, "
            f"{diff.removed_count} removed, {diff.changed_count} changed)"
        ),
        (
            f"- Impact closure: {report.impact_count} ({report.direct_count} direct, "
            f"{report.dependent_count} dependent, {report.transitive_count} transitive)"
        ),
        f"- Verification tasks: {plan.task_count}",
        f"- Policy checks: {gate.passed_count}/{len(gate.checks)} passed",
        "",
        "## Highest-risk modules",
        "",
        "| Module | Propagation | Severity | Risk | Sources | Reasons |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    ranked = sorted(
        report.assessments,
        key=lambda item: (-item.risk_score, item.module_id),
    )[:row_limit]
    for item in ranked:
        lines.append(
            f"| `{item.module_id}` | {item.propagation.value} | {item.severity.value} | "
            f"{item.risk_score:.2f} | {', '.join(item.changed_sources)} | "
            f"{'; '.join(item.reasons)} |"
        )
    lines.extend(("", "## Policy checks", "", "| Check | State | Detail |", "| --- | --- | --- |"))
    for item in gate.checks:
        lines.append(f"| `{item.check_id}` | {'pass' if item.passed else 'fail'} | {item.detail} |")
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "module_impact_assessments_csv",
    "module_impact_changes_csv",
    "module_impact_dependencies_csv",
    "module_impact_diff_json",
    "module_impact_gate_json",
    "module_impact_report_json",
    "module_impact_summary",
    "module_impact_tasks_csv",
    "render_module_impact_markdown",
]

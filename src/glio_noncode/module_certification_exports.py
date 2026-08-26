"""Human and machine-readable projections of certification results."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from .module_certification_contracts import ModuleCertificationMatrix
from .module_certification_tasks import (
    module_certification_gaps_csv,
    module_certification_tasks_csv,
)
from .serialization import canonical_json, jsonable


def _matrix(value: ModuleCertificationMatrix | Mapping[str, Any]) -> ModuleCertificationMatrix:
    if isinstance(value, ModuleCertificationMatrix):
        return value
    raise TypeError("certification exports require a typed matrix")


def module_certification_summary(value: ModuleCertificationMatrix) -> dict[str, Any]:
    """Return a compact aggregate for dashboards and release reports."""

    selected = _matrix(value)
    family: dict[str, list[Any]] = defaultdict(list)
    for row in selected.rows:
        family[row.family].append(row)
    family_rows = []
    for name in sorted(family):
        rows = family[name]
        family_rows.append(
            {
                "family": name,
                "module_count": len(rows),
                "certified_count": sum(item.state.value == "certified" for item in rows),
                "review_count": sum(item.state.value == "review" for item in rows),
                "blocked_count": sum(item.state.value == "blocked" for item in rows),
                "overall_score": round(sum(item.score for item in rows) / len(rows), 6),
                "gap_count": sum(item.gap_count for item in rows),
            }
        )
    return jsonable(
        {
            "version": "module-certification-v1",
            "matrix_address": selected.content_address,
            "module_count": selected.module_count,
            "check_kind_count": selected.check_kind_count,
            "check_count": selected.module_count * selected.check_kind_count,
            "gap_count": selected.gap_count,
            "certified_count": selected.certified_count,
            "review_count": selected.review_count,
            "blocked_count": selected.blocked_count,
            "uncovered_count": selected.uncovered_count,
            "overall_score": selected.overall_score,
            "overall_percent": selected.overall_percent,
            "families": family_rows,
            "accepted": selected.accepted,
        }
    )


def _csv(rows: list[Mapping[str, Any]], fields: tuple[str, ...]) -> str:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
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


def module_certification_rows_csv(value: ModuleCertificationMatrix) -> str:
    fields = (
        "module_id",
        "family",
        "role",
        "physical_lines",
        "public_symbol_count",
        "passed_count",
        "failed_count",
        "not_applicable_count",
        "score",
        "state",
        "gap_count",
        "content_address",
    )
    return _csv([row.to_dict() for row in _matrix(value).rows], fields)


def module_certification_checks_csv(value: ModuleCertificationMatrix) -> str:
    rows = []
    for row in _matrix(value).rows:
        for check in row.checks:
            body = check.to_dict()
            body["module_id"] = row.module_id
            rows.append(body)
    fields = (
        "module_id",
        "kind",
        "state",
        "observed",
        "required",
        "detail",
        "evidence",
        "content_address",
    )
    return _csv(rows, fields)


def module_certification_matrix_json(value: ModuleCertificationMatrix) -> str:
    return canonical_json(_matrix(value).to_dict()) + "\n"


def render_module_certification_markdown(
    value: ModuleCertificationMatrix,
    *,
    max_rows: int = 100,
) -> str:
    """Render a bounded readable summary with explicit coverage totals."""

    selected = _matrix(value)
    if max_rows < 1:
        raise ValueError("max_rows must be positive")
    lines = [
        "# Module certification matrix",
        "",
        "This report is generated from static inventory, test, documentation, and package "
        "evidence. "
        "It does not import or execute discovered source modules.",
        "",
        f"- Matrix address: `{selected.content_address}`",
        f"- Modules: **{selected.module_count:,}**",
        f"- Checks per module: **{selected.check_kind_count}**",
        f"- Gaps: **{selected.gap_count:,}**",
        f"- Overall score: **{selected.overall_percent:.2f}%**",
        f"- Certified / review / blocked / uncovered: **{selected.certified_count:,} / "
        f"{selected.review_count:,} / {selected.blocked_count:,} / "
        f"{selected.uncovered_count:,}**",
        f"- Accepted input: **{str(selected.accepted).lower()}**",
        "",
        "## Family summary",
        "",
        "| Family | Modules | Certified | Review | Blocked | Score | Gaps |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for family in module_certification_summary(selected)["families"]:
        lines.append(
            f"| {family['family']} | {family['module_count']:,} | {family['certified_count']:,} | "
            f"{family['review_count']:,} | {family['blocked_count']:,} | "
            f"{family['overall_score'] * 100:.2f}% | {family['gap_count']:,} |"
        )
    lines.extend(
        [
            "",
            "## Module rows",
            "",
            "| Module | Role | Score | State | Passed | Failed | N/A | Gaps |",
            "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in selected.rows[:max_rows]:
        lines.append(
            f"| `{row.module_id}` | {row.role} | {row.score * 100:.2f}% | {row.state.value} | "
            f"{row.passed_count} | {row.failed_count} | {row.not_applicable_count} | "
            f"{row.gap_count} |"
        )
    if len(selected.rows) > max_rows:
        lines.append(
            f"| … | … | … | truncated | … | … | … | {len(selected.rows) - max_rows:,} more rows |"
        )
    lines.extend(
        [
            "",
            "## Gap queue",
            "",
            "| Priority | Module | Check | Next action |",
            "| ---: | --- | --- | --- |",
        ]
    )
    for gap in selected.gaps[:max_rows]:
        lines.append(
            f"| {gap.priority} | `{gap.module_id}` | {gap.kind.value} | {gap.next_action} |"
        )
    if len(selected.gaps) > max_rows:
        lines.append(f"| … | … | … | {len(selected.gaps) - max_rows:,} more gaps |")
    return "\n".join(lines) + "\n"


def module_certification_exports_schema() -> dict[str, Any]:
    return {
        "version": "module-certification-exports-v1",
        "boundary": "public_aggregate_module_certification_exports",
        "formats": ["json", "csv", "markdown"],
        "operations": [
            "summary",
            "matrix_json",
            "rows_csv",
            "checks_csv",
            "gaps_csv",
            "tasks_csv",
            "markdown_report",
        ],
        "path_free": True,
        "timestamp_free": True,
    }


def module_certification_exports_capabilities() -> dict[str, Any]:
    operations = (
        "summarize_families",
        "export_matrix_json",
        "export_rows_csv",
        "export_checks_csv",
        "export_gaps_csv",
        "export_tasks_csv",
        "render_markdown",
    )
    return {
        "version": "module-certification-exports-v1",
        "operation_count": len(operations),
        "operations": list(operations),
        "read_only": True,
        "deterministic": True,
    }


__all__ = [
    "module_certification_checks_csv",
    "module_certification_exports_capabilities",
    "module_certification_exports_schema",
    "module_certification_gaps_csv",
    "module_certification_matrix_json",
    "module_certification_rows_csv",
    "module_certification_summary",
    "module_certification_tasks_csv",
    "render_module_certification_markdown",
]

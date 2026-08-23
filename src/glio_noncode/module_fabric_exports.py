"""Stable aggregate projections for module-fabric consumers."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from .module_fabric_contracts import FabricEvaluation, FabricFixture, FabricRuntimeReport
from .module_fabric_fixture_eval import evaluate_module_fabric_fixture
from .module_fabric_public_data import default_module_fabric_fixture
from .serialization import canonical_json


def module_fabric_review_rows(
    fixture: FabricFixture | None = None,
    evaluation: FabricEvaluation | None = None,
) -> tuple[dict[str, Any], ...]:
    value = fixture or default_module_fabric_fixture()
    report = evaluation or evaluate_module_fabric_fixture(value)
    rows = []
    for record, execution in zip(value.records, report.executions, strict=True):
        rows.append(
            {
                "record_id": record.record_id,
                "domain_id": record.domain_id,
                "capability_id": record.capability_id,
                "role": record.role.value,
                "expected_state": record.expected_state.value,
                "observed_state": execution.observed_state.value,
                "issue_codes": ";".join(execution.issue_codes),
                "implementation_reference_count": len(execution.implementation_receipts),
                "test_reference_count": len(execution.test_receipts),
                "failed_reference_count": sum(item.state.value == "failed" for item in (*execution.implementation_receipts, *execution.test_receipts)),
                "execution_address": execution.content_address,
            }
        )
    return tuple(rows)


def export_module_fabric_review_csv(
    fixture: FabricFixture | None = None,
    evaluation: FabricEvaluation | None = None,
) -> str:
    rows = module_fabric_review_rows(fixture, evaluation)
    fields = tuple(rows[0]) if rows else ("record_id", "domain_id", "capability_id", "observed_state")
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def module_fabric_json(
    fixture: FabricFixture | None = None,
    evaluation: FabricEvaluation | None = None,
) -> str:
    value = fixture or default_module_fabric_fixture()
    report = evaluation or evaluate_module_fabric_fixture(value)
    return canonical_json(
        {
            "fixture_id": value.fixture_id,
            "evaluation": report,
            "review_rows": module_fabric_review_rows(value, report),
        }
    ) + "\n"


def module_fabric_runtime_json(report: FabricRuntimeReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_module_fabric_review_markdown(
    fixture: FabricFixture | None = None,
    evaluation: FabricEvaluation | None = None,
) -> str:
    rows = module_fabric_review_rows(fixture, evaluation)
    lines = [
        "# Module Fabric Review",
        "",
        "This projection contains public aggregate module-reference metadata only.",
        "",
        "| Domain | Capability | Role | Expected | Observed | Issues | Failed refs |",
        "| --- | --- | --- | --- | --- | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['domain_id']} | {row['capability_id']} | {row['role']} | {row['expected_state']} | {row['observed_state']} | {row['issue_codes'] or '—'} | {row['failed_reference_count']} |"
        )
    return "\n".join(lines) + "\n"


def module_fabric_summary(
    fixture: FabricFixture | None = None,
    evaluation: FabricEvaluation | None = None,
) -> dict[str, Any]:
    value = fixture or default_module_fabric_fixture()
    report = evaluation or evaluate_module_fabric_fixture(value)
    return {
        "fixture_id": value.fixture_id,
        "record_count": len(value.records),
        "positive_count": len(value.positive_records),
        "control_count": len(value.control_records),
        "domain_count": len(value.domain_ids),
        "accepted": report.accepted,
        "passed_checks": report.passed_checks,
        "failed_checks": report.failed_checks,
        "evaluation_address": report.content_address,
    }


__all__ = [
    "export_module_fabric_review_csv",
    "module_fabric_json",
    "module_fabric_review_rows",
    "module_fabric_runtime_json",
    "module_fabric_summary",
    "render_module_fabric_review_markdown",
]

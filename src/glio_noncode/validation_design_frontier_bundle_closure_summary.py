"""Compact operational summaries for the D13 closure handoff."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .serialization import content_hash
from .validation_design_frontier_bundle_closure_contracts import (
    ValidationDesignClosureDomainSummary,
    ValidationDesignClosurePlane,
    ValidationDesignClosureSummary,
    ValidationDesignClosureSummaryAudit,
    validation_design_closure_check,
)
from .validation_design_frontier_bundle_closure_support import (
    all_rows,
    bundle_count_map,
    csv_text,
    markdown_table,
)
from .validation_design_frontier_bundle_contracts import ValidationDesignBundle


def _operation_summaries(
    bundle: ValidationDesignBundle,
) -> tuple[ValidationDesignClosureDomainSummary, ...]:
    rows = all_rows(bundle)
    records = rows["records"]
    checks = rows["checks"]
    by_operation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    check_by_record: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        by_operation[str(row.get("operation"))].append(row)
    for row in checks:
        check_by_record[str(row.get("record_id"))].append(row)
    summaries: list[ValidationDesignClosureDomainSummary] = []
    for operation, operation_rows in sorted(by_operation.items()):
        positive = sum(str(row.get("role")) == "positive" for row in operation_rows)
        control = len(operation_rows) - positive
        operation_checks = [
            check
            for row in operation_rows
            for check in check_by_record.get(str(row.get("record_id")), ())
        ]
        passed = sum(bool(check.get("passed")) for check in operation_checks)
        issues = sorted(
            {str(code) for row in operation_rows for code in row.get("issue_codes", ())}
        )
        accepted = sum(str(row.get("observed_state")) == "ready" for row in operation_rows)
        blocked = len(operation_rows) - accepted
        body = {
            "operation": operation,
            "record_count": len(operation_rows),
            "positive_count": positive,
            "control_count": control,
            "passed_check_count": passed,
            "failed_check_count": len(operation_checks) - passed,
            "accepted_count": accepted,
            "blocked_count": blocked,
            "issue_codes": tuple(issues),
        }
        summaries.append(
            ValidationDesignClosureDomainSummary(
                **body,
                content_address=content_hash(body, prefix="validation-design-closure-domain"),
            )
        )
    return tuple(summaries)


def build_validation_design_closure_summary(
    bundle: ValidationDesignBundle,
) -> ValidationDesignClosureSummary:
    rows = all_rows(bundle)
    counters = bundle_count_map(bundle)
    counters.update(
        {
            "passed_manifest_checks": bundle.passed_check_count,
            "failed_manifest_checks": bundle.failed_check_count,
            "passed_evaluation_checks": sum(bool(row.get("passed")) for row in rows["checks"]),
            "failed_evaluation_checks": sum(not bool(row.get("passed")) for row in rows["checks"]),
            "accepted_planes": sum(bool(row.get("accepted")) for row in rows["planes"]),
            "ready_records": sum(row.get("observed_state") == "ready" for row in rows["records"]),
            "blocked_records": sum(row.get("observed_state") != "ready" for row in rows["records"]),
            "addressed_stages": sum(
                bool(row.get("output_address", "").startswith("sha256:")) for row in rows["stages"]
            ),
            "addressed_rows": sum(
                bool(row.get("content_address", ""))
                for resource in rows.values()
                for row in resource
            ),
        }
    )
    state_counts = Counter(str(row.get("observed_state", "unknown")) for row in rows["records"])
    states = tuple(
        {"state": state, "record_count": count} for state, count in sorted(state_counts.items())
    )
    planes = tuple(
        {
            "plane_id": row.get("plane_id"),
            "accepted": bool(row.get("accepted")),
            "ordinal": row.get("ordinal"),
        }
        for row in rows["planes"]
    )
    operations = _operation_summaries(bundle)
    accepted = bundle.accepted and all(bool(row.get("accepted")) for row in rows["planes"])
    body = {
        "bundle_id": bundle.bundle_id,
        "counters": tuple(sorted(counters.items())),
        "operations": operations,
        "states": states,
        "planes": planes,
        "accepted": accepted,
    }
    return ValidationDesignClosureSummary(
        bundle_id=bundle.bundle_id,
        counters=tuple(sorted(counters.items())),
        operations=operations,
        states=states,
        planes=planes,
        accepted=accepted,
        content_address=content_hash(body, prefix="validation-design-closure-summary"),
    )


def audit_validation_design_closure_summary(
    bundle: ValidationDesignBundle, summary: ValidationDesignClosureSummary | None = None
) -> ValidationDesignClosureSummaryAudit:
    value = summary or build_validation_design_closure_summary(bundle)
    counts = bundle_count_map(bundle)
    checks = [
        validation_design_closure_check(
            "summary-bundle-id",
            ValidationDesignClosurePlane.SUMMARY,
            value.bundle_id == bundle.bundle_id,
            value.bundle_id,
            bundle.bundle_id,
            "summary points to the source bundle",
        ),
        validation_design_closure_check(
            "summary-artifacts",
            ValidationDesignClosurePlane.SUMMARY,
            value.counter_map.get("artifacts") == counts["artifacts"],
            value.counter_map.get("artifacts"),
            counts["artifacts"],
            "artifact counter is conserved",
        ),
        validation_design_closure_check(
            "summary-records",
            ValidationDesignClosurePlane.SUMMARY,
            value.counter_map.get("records") == counts["records"],
            value.counter_map.get("records"),
            counts["records"],
            "record counter is conserved",
        ),
        validation_design_closure_check(
            "summary-executions",
            ValidationDesignClosurePlane.SUMMARY,
            value.counter_map.get("executions") == counts["executions"],
            value.counter_map.get("executions"),
            counts["executions"],
            "execution counter is conserved",
        ),
        validation_design_closure_check(
            "summary-checks",
            ValidationDesignClosurePlane.SUMMARY,
            value.counter_map.get("checks") == counts["checks"],
            value.counter_map.get("checks"),
            counts["checks"],
            "evaluation check counter is conserved",
        ),
        validation_design_closure_check(
            "summary-sources",
            ValidationDesignClosurePlane.SUMMARY,
            value.counter_map.get("sources") == counts["sources"],
            value.counter_map.get("sources"),
            counts["sources"],
            "source counter is conserved",
        ),
        validation_design_closure_check(
            "summary-stages",
            ValidationDesignClosurePlane.SUMMARY,
            value.counter_map.get("stages") == counts["stages"],
            value.counter_map.get("stages"),
            counts["stages"],
            "stage counter is conserved",
        ),
        validation_design_closure_check(
            "summary-planes",
            ValidationDesignClosurePlane.SUMMARY,
            len(value.planes) == counts["planes"],
            len(value.planes),
            counts["planes"],
            "plane rows are conserved",
        ),
        validation_design_closure_check(
            "summary-operations",
            ValidationDesignClosurePlane.SUMMARY,
            len(value.operations) == counts["operations"],
            len(value.operations),
            counts["operations"],
            "operation rows are conserved",
        ),
        validation_design_closure_check(
            "summary-states",
            ValidationDesignClosurePlane.SUMMARY,
            sum(int(row["record_count"]) for row in value.states) == counts["records"],
            sum(int(row["record_count"]) for row in value.states),
            counts["records"],
            "state partition conserves records",
        ),
        validation_design_closure_check(
            "summary-operation-records",
            ValidationDesignClosurePlane.SUMMARY,
            sum(item.record_count for item in value.operations) == counts["records"],
            sum(item.record_count for item in value.operations),
            counts["records"],
            "operation partition conserves records",
        ),
        validation_design_closure_check(
            "summary-operation-checks",
            ValidationDesignClosurePlane.SUMMARY,
            sum(item.passed_check_count + item.failed_check_count for item in value.operations)
            == counts["checks"],
            sum(item.passed_check_count + item.failed_check_count for item in value.operations),
            counts["checks"],
            "operation partition conserves evaluation checks",
        ),
        validation_design_closure_check(
            "summary-plane-acceptance",
            ValidationDesignClosurePlane.SUMMARY,
            all(bool(row.get("accepted")) for row in value.planes),
            sum(bool(row.get("accepted")) for row in value.planes),
            len(value.planes),
            "all plane summaries are accepted",
        ),
        validation_design_closure_check(
            "summary-address",
            ValidationDesignClosurePlane.SUMMARY,
            value.content_address.startswith("validation-design-closure-summary:"),
            value.content_address,
            "validation-design-closure-summary:",
            "summary carries a stable address",
        ),
        validation_design_closure_check(
            "summary-accepted",
            ValidationDesignClosurePlane.SUMMARY,
            value.accepted,
            value.accepted,
            True,
            "summary accepted",
        ),
    ]
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": bundle.bundle_id, "checks": tuple(checks), "accepted": accepted}
    return ValidationDesignClosureSummaryAudit(
        bundle.bundle_id,
        tuple(checks),
        accepted,
        content_hash(body, prefix="validation-design-closure-summary-audit"),
    )


def export_validation_design_closure_summary_csv(summary: ValidationDesignClosureSummary) -> str:
    rows = [
        {"resource": "counter", "name": name, "value": value} for name, value in summary.counters
    ] + [item.to_dict() | {"resource": "operation"} for item in summary.operations]
    return csv_text(rows)


def export_validation_design_closure_summary_markdown(
    summary: ValidationDesignClosureSummary,
) -> str:
    rows = [{"name": name, "value": value} for name, value in summary.counters]
    return markdown_table(rows, "D13 validation-design closure summary")


__all__ = [
    "audit_validation_design_closure_summary",
    "build_validation_design_closure_summary",
    "export_validation_design_closure_summary_csv",
    "export_validation_design_closure_summary_markdown",
]

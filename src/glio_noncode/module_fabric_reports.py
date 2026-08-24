"""Human-readable reports for module-fabric release review."""

from __future__ import annotations

from typing import Any

from .module_fabric_contracts import FabricRuntimeReport
from .module_fabric_data_dictionary import default_module_fabric_data_dictionary
from .module_fabric_governance import (
    build_module_fabric_review_queue,
    default_module_fabric_claim_boundary,
)
from .module_fabric_observability import build_module_fabric_trace
from .module_fabric_public_data import default_module_fabric_fixture
from .module_fabric_schema import default_module_fabric_schema, validate_module_fabric_schema


def module_fabric_report(report: FabricRuntimeReport) -> dict[str, Any]:
    trace = build_module_fabric_trace(report)
    queue = build_module_fabric_review_queue(default_module_fabric_fixture(), report.evaluation)
    return {
        "run_id": report.run_id,
        "state": report.state.value,
        "stage_count": len(report.stages),
        "record_count": report.metrics.record_count,
        "domain_count": report.metrics.domain_count,
        "reference_failure_count": report.metrics.failed_reference_count,
        "evaluation_check_count": len(report.evaluation.checks),
        "compliance_check_count": len(report.compliance.checks) if report.compliance else 0,
        "evaluation_address": report.evaluation.content_address,
        "depth_address": report.depth.content_address,
        "quality_address": report.quality.content_address,
        "release_address": report.release.content_address,
        "trace_address": trace.content_address,
        "review_queue_count": len(queue.items),
        "claim_boundary": default_module_fabric_claim_boundary().to_dict(),
        "schema_issues": validate_module_fabric_schema(default_module_fabric_schema()),
        "dictionary_address": default_module_fabric_data_dictionary().content_address,
    }


def render_module_fabric_runtime_markdown(report: FabricRuntimeReport) -> str:
    summary = module_fabric_report(report)
    lines = [
        "# Module Fabric Runtime Report",
        "",
        f"- Run: `{summary['run_id']}`",
        f"- State: `{summary['state']}`",
        f"- Domains: `{summary['domain_count']}`",
        f"- Records: `{summary['record_count']}`",
        f"- Runtime stages: `{summary['stage_count']}`",
        f"- Evaluation checks: `{summary['evaluation_check_count']}`",
        f"- Compliance checks: `{summary['compliance_check_count']}`",
        f"- Failed references: `{summary['reference_failure_count']}`",
        f"- Release address: `{summary['release_address']}`",
        "",
        "The report is an integration receipt for declared module references; it is not a scientific or clinical conclusion.",
        "",
        "## Stage ledger",
        "",
        "| Ordinal | Stage | State | Input | Output |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for stage in report.stages:
        lines.append(f"| {stage.ordinal} | {stage.stage_id} | {stage.state.value} | `{stage.input_address[:18]}` | `{stage.output_address[:18]}` |")
    return "\n".join(lines) + "\n"


__all__ = ["module_fabric_report", "render_module_fabric_runtime_markdown"]

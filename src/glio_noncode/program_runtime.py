"""Execute and reconcile the sixteen canonical architecture runtimes."""

from __future__ import annotations

from functools import cache
from typing import Any

from .errors import ValidationError
from .module_fabric_contracts import MODULE_FABRIC_DOMAIN_NAMES
from .module_fabric_support import contains_private_key, resolve_reference
from .program_runtime_contracts import (
    ArchitectureProgramReceipt,
    ArchitectureProgramReport,
    ArchitectureProgramSpec,
    ProgramRuntimeCheck,
    ProgramRuntimeCheckCategory,
    ProgramRuntimeState,
    addressed,
)

PROGRAM_DOMAIN_COUNT = 16
PROGRAM_CHECKS_PER_DOMAIN = 10
PROGRAM_GLOBAL_CHECK_COUNT = 12


_PROGRAM_REFERENCE_ROWS = (
    ("D01", "intake_architecture_public_data.default_intake_architecture_fixture", "intake_architecture_runtime.run_intake_architecture", "public_aggregate_variant_identity_and_intake"),
    ("D02", "structural_architecture_public_data.default_structural_architecture_fixture", "structural_architecture_runtime.run_structural_architecture", "public_aggregate_structural_variation_and_haplotype"),
    ("D03", "specimen_architecture_public_data.default_specimen_architecture_fixture", "specimen_architecture_runtime.run_specimen_architecture", "public_aggregate_specimen_origin_and_lineage"),
    ("D04", "reference_architecture_public_data.default_reference_architecture_fixture", "reference_architecture_runtime.run_reference_architecture", "public_aggregate_reference_annotation_governance"),
    ("D05", "atlas_architecture_public_data.default_atlas_architecture_fixture", "atlas_architecture_runtime.run_atlas_architecture", "public_aggregate_regulatory_atlas"),
    ("D06", "sequence_architecture_public_data.default_sequence_architecture_fixture", "sequence_architecture_runtime.run_sequence_architecture", "public_aggregate_sequence_grammar_and_effect"),
    ("D07", "chromatin_architecture_public_data.default_chromatin_architecture_fixture", "chromatin_architecture_runtime.run_chromatin_architecture", "public_aggregate_chromatin_accessibility_and_methylation"),
    ("D08", "cell_state_architecture_public_data.default_cell_state_architecture_fixture", "cell_state_architecture_runtime.run_cell_state_architecture", "public_aggregate_cell_state_and_territory"),
    ("D09", "topology_architecture_public_data.default_topology_architecture_fixture", "topology_architecture_runtime.run_topology_architecture", "public_aggregate_regulatory_topology"),
    ("D10", "link_graph_architecture_public_data.default_link_graph_architecture_fixture", "link_graph_architecture_runtime.run_link_graph_architecture", "public_aggregate_variant_element_gene_linking"),
    ("D11", "causal_architecture_public_data.default_causal_architecture_fixture", "causal_architecture_runtime.run_causal_architecture", "public_aggregate_causal_driver_inference"),
    ("D12", "cohort_architecture_public_data.default_cohort_architecture_fixture", "cohort_architecture_runtime.run_cohort_architecture", "public_aggregate_cohort_longitudinal_discovery"),
    ("D13", "planning_architecture_public_data.default_planning_architecture_fixture", "planning_architecture_runtime.run_planning_architecture", "public_aggregate_validation_and_experiment_design"),
    ("D14", "evidence_architecture_public_data.default_evidence_architecture_fixture", "evidence_architecture_runtime.run_evidence_architecture", "public_aggregate_evidence_review_and_reclassification"),
    ("D15", "workbench_architecture_public_data.default_workbench_architecture_fixture", "workbench_architecture_runtime.run_workbench_architecture", "public_aggregate_research_workbench"),
    ("D16", "platform_execution_architecture_public_data.default_platform_execution_fixture", "platform_execution_architecture_runtime.run_platform_execution_architecture", "public_aggregate_platform_execution"),
)


def _module_reference(value: str) -> str:
    return f"glio_noncode.{value}"


def default_architecture_program_specs() -> tuple[ArchitectureProgramSpec, ...]:
    """Return the closed, ordered fixture/runtime adapter catalog."""

    specs: list[ArchitectureProgramSpec] = []
    for order, (domain_id, fixture, runtime, boundary) in enumerate(_PROGRAM_REFERENCE_ROWS, 1):
        body = {
            "domain_id": domain_id,
            "domain": MODULE_FABRIC_DOMAIN_NAMES[domain_id],
            "fixture_reference": _module_reference(fixture),
            "runtime_reference": _module_reference(runtime),
            "dependency_order": order,
            "boundary": boundary,
        }
        specs.append(ArchitectureProgramSpec(**body, content_address=addressed(body, "architecture-program-spec")))
    return tuple(specs)


@cache
def _resolve(value: str) -> tuple[str, Any, str]:
    try:
        resolution = resolve_reference(value)
    except (TypeError, ValueError, ValidationError) as exc:
        return "failed", None, f"{type(exc).__name__}: {exc}"
    return resolution.state.value, resolution.symbol, resolution.detail


def _address(value: Any, prefix: str) -> str:
    candidate = getattr(value, "content_address", None)
    if isinstance(candidate, str) and ":" in candidate:
        return candidate
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return addressed(value, prefix)


def _runtime_projection(value: Any) -> dict[str, Any]:
    projection = value.to_dict() if hasattr(value, "to_dict") else value
    return projection if isinstance(projection, dict) else {"value_type": type(value).__name__}


def _count_checks(value: Any) -> int:
    checks = getattr(value, "checks", None)
    if checks is not None:
        return len(checks)
    evaluation = getattr(value, "evaluation", None)
    checks = getattr(evaluation, "checks", None) if evaluation is not None else None
    return len(checks) if checks is not None else 0


def _receipt(spec: ArchitectureProgramSpec) -> ArchitectureProgramReceipt:
    fixture_state, fixture_factory, fixture_detail = _resolve(spec.fixture_reference)
    runtime_state, runtime_runner, runtime_detail = _resolve(spec.runtime_reference)
    issue_codes: list[str] = []
    fixture_address = ""
    runtime_address = ""
    accepted = False
    runtime_state_value = "review"
    stage_count = 0
    evaluation_check_count = 0
    artifact_count = 0
    if fixture_state != "resolved" or not callable(fixture_factory):
        issue_codes.append("fixture_reference_failed")
    if runtime_state != "resolved" or not callable(runtime_runner):
        issue_codes.append("runtime_reference_failed")
    try:
        if not issue_codes:
            fixture = fixture_factory()
            fixture_address = _address(fixture, "architecture-program-fixture")
            runtime = runtime_runner(fixture)
            projection = _runtime_projection(runtime)
            runtime_address = _address(runtime, "architecture-program-runtime")
            raw_state = getattr(runtime, "state", None)
            raw_state = getattr(raw_state, "value", raw_state)
            raw_accepted = getattr(runtime, "accepted", None)
            accepted = bool(raw_accepted) if raw_accepted is not None else raw_state in {"accepted", "published"}
            runtime_state_value = str(raw_state or ("accepted" if accepted else "review"))
            stage_count = len(getattr(runtime, "stages", ()))
            evaluation_check_count = _count_checks(runtime)
            artifact_count = len(getattr(runtime, "artifacts", ()))
            if not accepted:
                issue_codes.append("runtime_not_accepted")
            if stage_count < 1:
                issue_codes.append("missing_stage_receipts")
            if ":" not in fixture_address:
                issue_codes.append("fixture_address_missing")
            if ":" not in runtime_address:
                issue_codes.append("runtime_address_missing")
            if contains_private_key(projection):
                issue_codes.append("private_projection_key")
        else:
            fixture_detail = fixture_detail or "fixture resolution failed"
            runtime_detail = runtime_detail or "runtime resolution failed"
    except Exception as exc:
        issue_codes.append("execution_exception")
        runtime_state_value = "blocked"
        fixture_detail = f"{fixture_detail}; execution={type(exc).__name__}"
    body = {
        "domain_id": spec.domain_id,
        "domain": spec.domain,
        "fixture_reference": spec.fixture_reference,
        "runtime_reference": spec.runtime_reference,
        "fixture_resolution": fixture_detail,
        "runtime_resolution": runtime_detail,
        "fixture_address": fixture_address,
        "runtime_address": runtime_address,
        "runtime_state": runtime_state_value,
        "accepted": accepted,
        "stage_count": stage_count,
        "evaluation_check_count": evaluation_check_count,
        "artifact_count": artifact_count,
        "issue_codes": tuple(sorted(set(issue_codes))),
    }
    return ArchitectureProgramReceipt(**body, content_address=addressed(body, "architecture-program-receipt"))


def _check(
    domain_id: str,
    check_id: str,
    category: ProgramRuntimeCheckCategory,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ProgramRuntimeCheck:
    body = {
        "check_id": f"{domain_id}:{check_id}",
        "domain_id": domain_id,
        "category": category,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ProgramRuntimeCheck(**body, content_address=addressed(body, "architecture-program-check"))


def _receipt_checks(spec: ArchitectureProgramSpec, receipt: ArchitectureProgramReceipt) -> tuple[ProgramRuntimeCheck, ...]:
    return (
        _check(spec.domain_id, "fixture-reference-resolved", ProgramRuntimeCheckCategory.RESOLUTION, receipt.fixture_resolution.startswith("resolved"), receipt.fixture_resolution, "resolved fixture factory", "the canonical fixture factory resolves"),
        _check(spec.domain_id, "runtime-reference-resolved", ProgramRuntimeCheckCategory.RESOLUTION, receipt.runtime_resolution.startswith("resolved"), receipt.runtime_resolution, "resolved runtime function", "the canonical runtime function resolves"),
        _check(spec.domain_id, "fixture-addressed", ProgramRuntimeCheckCategory.INTEGRITY, bool(receipt.fixture_address), receipt.fixture_address, "content address", "fixture output is content-addressed"),
        _check(spec.domain_id, "runtime-addressed", ProgramRuntimeCheckCategory.INTEGRITY, bool(receipt.runtime_address), receipt.runtime_address, "content address", "runtime output is content-addressed"),
        _check(spec.domain_id, "runtime-accepted", ProgramRuntimeCheckCategory.EXECUTION, receipt.accepted, receipt.runtime_state, "accepted or published", "the domain runtime reaches its accepted publication state"),
        _check(spec.domain_id, "stages-present", ProgramRuntimeCheckCategory.EXECUTION, receipt.stage_count > 0, receipt.stage_count, ">0", "runtime stages are observable"),
        _check(spec.domain_id, "evaluation-checks-present", ProgramRuntimeCheckCategory.RECONCILIATION, receipt.evaluation_check_count > 0, receipt.evaluation_check_count, ">0", "domain evaluation checks are retained"),
        _check(spec.domain_id, "artifacts-present", ProgramRuntimeCheckCategory.RECONCILIATION, receipt.artifact_count > 0, receipt.artifact_count, ">0", "domain release artifacts are retained"),
        _check(spec.domain_id, "issue-free", ProgramRuntimeCheckCategory.RUNTIME, not receipt.issue_codes, receipt.issue_codes, (), "no orchestration issue code is present"),
        _check(spec.domain_id, "receipt-addressed", ProgramRuntimeCheckCategory.INTEGRITY, receipt.content_address.startswith("architecture-program-receipt:"), receipt.content_address, "architecture-program-receipt:<digest>", "normalized domain receipt is addressed"),
    )


def _global_checks(specs: tuple[ArchitectureProgramSpec, ...], receipts: tuple[ArchitectureProgramReceipt, ...]) -> tuple[ProgramRuntimeCheck, ...]:
    ids = tuple(item.domain_id for item in specs)
    receipt_ids = tuple(item.domain_id for item in receipts)
    return (
        _check("__program__", "spec-cardinality", ProgramRuntimeCheckCategory.CATALOG, len(specs) == PROGRAM_DOMAIN_COUNT, len(specs), PROGRAM_DOMAIN_COUNT, "the program contains all sixteen domain specs"),
        _check("__program__", "receipt-cardinality", ProgramRuntimeCheckCategory.RECONCILIATION, len(receipts) == PROGRAM_DOMAIN_COUNT, len(receipts), PROGRAM_DOMAIN_COUNT, "every domain produces one receipt"),
        _check("__program__", "spec-identities-unique", ProgramRuntimeCheckCategory.CATALOG, len(ids) == len(set(ids)), len(ids), len(set(ids)), "domain specs are unique"),
        _check("__program__", "receipt-identities-unique", ProgramRuntimeCheckCategory.RECONCILIATION, len(receipt_ids) == len(set(receipt_ids)), len(receipt_ids), len(set(receipt_ids)), "domain receipts are unique"),
        _check("__program__", "domain-order-closed", ProgramRuntimeCheckCategory.CATALOG, tuple(item.domain_id for item in specs) == tuple(f"D{i:02d}" for i in range(1, 17)), tuple(item.domain_id for item in specs), tuple(f"D{i:02d}" for i in range(1, 17)), "domain execution follows canonical order"),
        _check("__program__", "all-fixtures-resolved", ProgramRuntimeCheckCategory.RESOLUTION, all(item.fixture_resolution.startswith("resolved") for item in receipts), sum(item.fixture_resolution.startswith("resolved") for item in receipts), len(receipts), "all fixture factories resolve"),
        _check("__program__", "all-runtimes-resolved", ProgramRuntimeCheckCategory.RESOLUTION, all(item.runtime_resolution.startswith("resolved") for item in receipts), sum(item.runtime_resolution.startswith("resolved") for item in receipts), len(receipts), "all runtime functions resolve"),
        _check("__program__", "all-domains-accepted", ProgramRuntimeCheckCategory.EXECUTION, all(item.accepted for item in receipts), sum(item.accepted for item in receipts), len(receipts), "all domain runtimes reach acceptance"),
        _check("__program__", "all-stage-denominators", ProgramRuntimeCheckCategory.EXECUTION, all(item.stage_count > 0 for item in receipts), min((item.stage_count for item in receipts), default=0), ">0", "every domain exposes runtime stages"),
        _check("__program__", "all-evaluation-denominators", ProgramRuntimeCheckCategory.RECONCILIATION, all(item.evaluation_check_count > 0 for item in receipts), min((item.evaluation_check_count for item in receipts), default=0), ">0", "every domain exposes evaluation checks"),
        _check("__program__", "all-public-projections", ProgramRuntimeCheckCategory.PUBLIC_BOUNDARY, all(not item.issue_codes or "private_projection_key" not in item.issue_codes for item in receipts), True, True, "domain projections retain the public boundary"),
        _check("__program__", "program-receipts-addressed", ProgramRuntimeCheckCategory.INTEGRITY, all(item.content_address.startswith("architecture-program-receipt:") for item in receipts), len(receipts), len(receipts), "all normalized receipts are addressed"),
    )


def run_architecture_program(
    specs: tuple[ArchitectureProgramSpec, ...] | None = None,
) -> ArchitectureProgramReport:
    """Execute each canonical domain runtime and reconcile the results."""

    catalog = specs or default_architecture_program_specs()
    ordered = tuple(sorted(catalog, key=lambda item: item.dependency_order))
    receipts = tuple(_receipt(spec) for spec in ordered)
    checks = tuple(
        item
        for spec, receipt in zip(ordered, receipts, strict=True)
        for item in _receipt_checks(spec, receipt)
    ) + _global_checks(ordered, receipts)
    state = ProgramRuntimeState.ACCEPTED if all(item.passed for item in checks) else ProgramRuntimeState.REVIEW
    body = {
        "report_id": "architecture-program-report",
        "specs": ordered,
        "receipts": receipts,
        "checks": checks,
        "state": state,
    }
    return ArchitectureProgramReport(**body, content_address=addressed(body, "architecture-program-report"))


def architecture_program_percent(report: ArchitectureProgramReport) -> float:
    """Return accepted-domain percentage using the sixteen-domain denominator."""

    return round(100.0 * sum(item.accepted for item in report.receipts) / max(1, len(report.receipts)), 2)


def architecture_program_domain_matrix(report: ArchitectureProgramReport) -> tuple[dict[str, Any], ...]:
    """Return compact dashboard rows for all domain runtimes."""

    return tuple(
        {
            "domain_id": item.domain_id,
            "domain": item.domain,
            "accepted": item.accepted,
            "runtime_state": item.runtime_state,
            "stage_count": item.stage_count,
            "evaluation_check_count": item.evaluation_check_count,
            "artifact_count": item.artifact_count,
            "issue_codes": list(item.issue_codes),
            "runtime_address": item.runtime_address,
            "content_address": item.content_address,
        }
        for item in report.receipts
    )


def query_architecture_program(
    report: ArchitectureProgramReport,
    *,
    domain_id: str | None = None,
    accepted_only: bool = False,
    text: str | None = None,
) -> tuple[ArchitectureProgramReceipt, ...]:
    """Filter normalized domain receipts for operational review."""

    normalized = text.strip().lower() if text else None
    return tuple(
        item
        for item in report.receipts
        if (domain_id is None or item.domain_id == domain_id)
        and (not accepted_only or item.accepted)
        and (normalized is None or normalized in f"{item.domain_id} {item.domain}".lower())
    )


__all__ = [
    "PROGRAM_CHECKS_PER_DOMAIN",
    "PROGRAM_DOMAIN_COUNT",
    "PROGRAM_GLOBAL_CHECK_COUNT",
    "architecture_program_domain_matrix",
    "architecture_program_percent",
    "default_architecture_program_specs",
    "query_architecture_program",
    "run_architecture_program",
]

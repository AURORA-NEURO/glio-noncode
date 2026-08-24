"""D13 public aggregate assembly from four deterministic planning families."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .editing_design_frontier_fixture_eval import evaluate_editing_design_fixture
from .editing_design_frontier_public_data import default_editing_design_frontier_fixture
from .planning_architecture_contracts import (
    PLANNING_ARCHITECTURE_BOUNDARY,
    PLANNING_ARCHITECTURE_CASE_COUNT,
    PLANNING_ARCHITECTURE_CASES_PER_OPERATION,
    PLANNING_ARCHITECTURE_CONTEXT,
    PLANNING_ARCHITECTURE_FOREIGN_CONTEXT,
    PLANNING_ARCHITECTURE_OPERATION_COUNT,
    PLANNING_ARCHITECTURE_SOURCE_COUNT,
    PLANNING_ARCHITECTURE_VERSION,
    PlanningArchitectureCase,
    PlanningArchitectureCheck,
    PlanningArchitectureCheckKind,
    PlanningArchitectureDataAudit,
    PlanningArchitectureFamily,
    PlanningArchitectureFixture,
    PlanningArchitectureOperation,
    PlanningArchitectureOperationSpec,
    PlanningArchitecturePlane,
    PlanningArchitectureScenario,
    PlanningArchitectureSource,
    PlanningArchitectureState,
    addressed,
)
from .planning_frontier_fixture_eval import evaluate_planning_fixture
from .planning_frontier_public_data import default_planning_frontier_fixture
from .serialization import jsonable
from .validation_design_frontier_fixture_eval import evaluate_validation_design_fixture
from .validation_design_frontier_public_data import default_validation_design_frontier_fixture
from .validation_release_frontier_fixture_eval import evaluate_validation_release_fixture
from .validation_release_frontier_public_data import default_validation_release_frontier_fixture


@dataclass(frozen=True, slots=True)
class _FamilySpec:
    family: PlanningArchitectureFamily
    plane: PlanningArchitecturePlane
    fixture_loader: Any
    evaluator: Any
    source_kind: str
    source_prefix: str


_FAMILY_SPECS = (
    _FamilySpec(
        PlanningArchitectureFamily.VALIDATION_DESIGN,
        PlanningArchitecturePlane.VALIDATION_DESIGN,
        default_validation_design_frontier_fixture,
        evaluate_validation_design_fixture,
        "public_validation_design_receipt",
        "D13-validation-design",
    ),
    _FamilySpec(
        PlanningArchitectureFamily.EDITING_DESIGN,
        PlanningArchitecturePlane.EDITING_DESIGN,
        default_editing_design_frontier_fixture,
        evaluate_editing_design_fixture,
        "public_editing_design_receipt",
        "D13-editing-design",
    ),
    _FamilySpec(
        PlanningArchitectureFamily.PLANNING,
        PlanningArchitecturePlane.PLANNING,
        default_planning_frontier_fixture,
        evaluate_planning_fixture,
        "public_planning_receipt",
        "D13-planning",
    ),
    _FamilySpec(
        PlanningArchitectureFamily.VALIDATION_RELEASE,
        PlanningArchitecturePlane.VALIDATION_RELEASE,
        default_validation_release_frontier_fixture,
        evaluate_validation_release_fixture,
        "public_validation_release_receipt",
        "D13-validation-release",
    ),
)


_OPERATIONS = (
    (
        "D13-C01",
        "GNC-D13-C01",
        PlanningArchitectureOperation.EVIDENCE_GAP,
        "gap_analysis",
        PlanningArchitectureFamily.VALIDATION_DESIGN,
        "validation_design",
        "validation_design.gap_input.v1",
        "planning.gap_output.v1",
        (),
        "retain_missing_dimensions_and_context_controls",
    ),
    (
        "D13-C02",
        "GNC-D13-C02",
        PlanningArchitectureOperation.ASSAY_ELIGIBILITY,
        "assay_eligibility",
        PlanningArchitectureFamily.VALIDATION_DESIGN,
        "validation_design",
        "validation_design.assay_input.v1",
        "planning.assay_route.v1",
        ("D13-C01",),
        "retain_assay_support_and_route_holds",
    ),
    (
        "D13-C03",
        "GNC-D13-C03",
        PlanningArchitectureOperation.MPRA_CONSTRUCT,
        "mpra_package",
        PlanningArchitectureFamily.VALIDATION_DESIGN,
        "validation_design",
        "validation_design.mpra_input.v1",
        "planning.mpra_package.v1",
        ("D13-C01", "D13-C02"),
        "retain_allele_and_construct_budget_controls",
    ),
    (
        "D13-C04",
        "GNC-D13-C04",
        PlanningArchitectureOperation.STARRSEQ_CONSTRUCT,
        "starrseq_package",
        PlanningArchitectureFamily.VALIDATION_DESIGN,
        "validation_design",
        "validation_design.starrseq_input.v1",
        "planning.starrseq_package.v1",
        ("D13-C01", "D13-C02"),
        "retain_construct_fields_and_context_controls",
    ),
    (
        "D13-C05",
        "GNC-D13-C05",
        PlanningArchitectureOperation.CRISPR_DESIGN,
        "crispr_design",
        PlanningArchitectureFamily.EDITING_DESIGN,
        "editing_design",
        "editing_design.crispr_input.v1",
        "editing.crispr_design.v1",
        ("D13-C02",),
        "retain_mode_target_control_and_readout_constraints",
    ),
    (
        "D13-C06",
        "GNC-D13-C06",
        PlanningArchitectureOperation.BASE_EDITING,
        "base_editing",
        PlanningArchitectureFamily.EDITING_DESIGN,
        "editing_design",
        "editing_design.base_input.v1",
        "editing.base_design.v1",
        ("D13-C05",),
        "retain_single_base_substitution_and_target_controls",
    ),
    (
        "D13-C07",
        "GNC-D13-C07",
        PlanningArchitectureOperation.PRIME_EDITING,
        "prime_editing",
        PlanningArchitectureFamily.EDITING_DESIGN,
        "editing_design",
        "editing_design.prime_input.v1",
        "editing.prime_design.v1",
        ("D13-C05",),
        "retain_edit_length_flank_and_context_controls",
    ),
    (
        "D13-C08",
        "GNC-D13-C08",
        PlanningArchitectureOperation.ALLELE_REPORTER,
        "allele_specific_reporter",
        PlanningArchitectureFamily.EDITING_DESIGN,
        "editing_design",
        "editing_design.reporter_input.v1",
        "editing.allele_reporter.v1",
        ("D13-C05", "D13-C06"),
        "retain_allele_pair_construct_and_budget_controls",
    ),
    (
        "D13-C09",
        "GNC-D13-C09",
        PlanningArchitectureOperation.MODEL_ELIGIBILITY,
        "model_system_eligibility",
        PlanningArchitectureFamily.PLANNING,
        "planning",
        "planning.model_input.v1",
        "planning.model_eligibility.v1",
        ("D13-C01", "D13-C05"),
        "retain_context_evidence_blocker_and_model_controls",
    ),
    (
        "D13-C10",
        "GNC-D13-C10",
        PlanningArchitectureOperation.GUIDE_ADAPTATION,
        "guide_oligo_adaptation",
        PlanningArchitectureFamily.PLANNING,
        "planning",
        "planning.guide_input.v1",
        "planning.guide_adaptation.v1",
        ("D13-C06",),
        "retain_format_row_identity_and_empty_input_controls",
    ),
    (
        "D13-C11",
        "GNC-D13-C11",
        PlanningArchitectureOperation.CONTROLS_RANDOMIZATION,
        "controls_randomization",
        PlanningArchitectureFamily.PLANNING,
        "planning",
        "planning.randomization_input.v1",
        "planning.randomization_output.v1",
        ("D13-C05", "D13-C09"),
        "retain_seed_target_inventory_and_empty_target_controls",
    ),
    (
        "D13-C12",
        "GNC-D13-C12",
        PlanningArchitectureOperation.POWER_REPLICATION,
        "power_replication",
        PlanningArchitectureFamily.PLANNING,
        "planning",
        "planning.power_input.v1",
        "planning.power_output.v1",
        ("D13-C09", "D13-C11"),
        "retain_power_assumptions_replicate_and_empty_input_controls",
    ),
    (
        "D13-C13",
        "GNC-D13-C13",
        PlanningArchitectureOperation.OFF_TARGET_RISK,
        "off_target_risk",
        PlanningArchitectureFamily.VALIDATION_RELEASE,
        "validation_release",
        "validation_release.off_target_input.v1",
        "validation.off_target_summary.v1",
        ("D13-C06", "D13-C07"),
        "retain_burden_threshold_and_malformed_score_controls",
    ),
    (
        "D13-C14",
        "GNC-D13-C14",
        PlanningArchitectureOperation.VALUE_OF_INFORMATION,
        "value_of_information",
        PlanningArchitectureFamily.VALIDATION_RELEASE,
        "validation_release",
        "validation.voi_input.v1",
        "validation.voi_selection.v1",
        ("D13-C09", "D13-C12"),
        "retain_budget_prerequisite_cycle_and_context_controls",
    ),
    (
        "D13-C15",
        "GNC-D13-C15",
        PlanningArchitectureOperation.EXPERIMENT_PACKAGE,
        "experiment_package",
        PlanningArchitectureFamily.VALIDATION_RELEASE,
        "validation_release",
        "validation_release.package_input.v1",
        "validation.package_manifest.v1",
        ("D13-C03", "D13-C04", "D13-C14"),
        "retain_manifest_identity_and_empty_package_controls",
    ),
    (
        "D13-C16",
        "GNC-D13-C16",
        PlanningArchitectureOperation.CLAIM_UPDATE,
        "claim_update",
        PlanningArchitectureFamily.VALIDATION_RELEASE,
        "validation_release",
        "validation_release.claim_input.v1",
        "validation.claim_update.v1",
        ("D13-C13", "D13-C15"),
        "retain_claim_identity_evidence_and_context_controls",
    ),
)


@lru_cache(maxsize=1)
def _family_objects() -> tuple[tuple[_FamilySpec, Any, Any], ...]:
    return tuple(
        (spec, fixture, spec.evaluator(fixture))
        for spec in _FAMILY_SPECS
        for fixture in (spec.fixture_loader(),)
    )


def _source_id(spec: _FamilySpec, delegate_source_id: str) -> str:
    return f"{spec.source_prefix}:{delegate_source_id}"


def _source_map(spec: _FamilySpec, fixture: Any) -> dict[str, str]:
    return {item.source_id: _source_id(spec, item.source_id) for item in fixture.sources}


def _sources() -> tuple[PlanningArchitectureSource, ...]:
    rows: list[PlanningArchitectureSource] = []
    for spec, fixture, _evaluation in _family_objects():
        for source in fixture.sources:
            body = {
                "source_id": _source_id(spec, source.source_id),
                "family": spec.family,
                "source_kind": spec.source_kind,
                "source_version": str(source.version),
                "uri": str(source.uri),
                "source_context_key": fixture.context_key,
                "delegate_source_id": source.source_id,
                "delegate_fixture_id": fixture.fixture_id,
                "public_aggregate": True,
                "delegate_content_address": source.content_address,
            }
            rows.append(
                PlanningArchitectureSource(
                    **body,
                    content_address=addressed(body, "planning-source"),
                )
            )
    return tuple(rows)


def _operation_specs(
    source_by_family: Mapping[PlanningArchitectureFamily, tuple[PlanningArchitectureSource, ...]],
) -> tuple[PlanningArchitectureOperationSpec, ...]:
    rows: list[PlanningArchitectureOperationSpec] = []
    for ordinal, item in enumerate(_OPERATIONS, start=1):
        (
            operation_id,
            capability_id,
            operation,
            delegate_operation,
            family,
            plane_name,
            input_contract,
            output_contract,
            dependencies,
            control_policy,
        ) = item
        source_ids = tuple(source.source_id for source in source_by_family[family])
        body = {
            "operation_id": operation_id,
            "capability_id": capability_id,
            "ordinal": ordinal,
            "operation": operation,
            "delegate_operation": delegate_operation,
            "family": family,
            "plane": PlanningArchitecturePlane(plane_name),
            "input_contract": input_contract,
            "output_contract": output_contract,
            "dependencies": dependencies,
            "source_ids": source_ids,
            "control_policy": control_policy,
        }
        rows.append(
            PlanningArchitectureOperationSpec(
                **body,
                content_address=addressed(body, "planning-operation"),
            )
        )
    return tuple(rows)


@lru_cache(maxsize=1)
def _delegate_rows() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for spec, fixture, evaluation in _family_objects():
        source_map = _source_map(spec, fixture)
        executions = {item.record_id: item for item in evaluation.executions}
        for record in fixture.records:
            execution = executions[record.record_id]
            output = execution.output if isinstance(execution.output, Mapping) else {}
            rows.append(
                {
                    "family": spec.family,
                    "plane": spec.plane,
                    "fixture": fixture,
                    "record": record,
                    "execution": execution,
                    "source_map": source_map,
                    "payload": jsonable(record.payload),
                    "output": jsonable(output),
                    "delegate_context_key": str(record.context_key),
                    "observed_state": str(execution.observed_state.value),
                    "issue_codes": tuple(str(item) for item in execution.issue_codes),
                    "output_address": str(execution.content_address),
                    "expected_record_state": str(record.expected_state.value),
                    "expected_record_issue_codes": tuple(
                        str(item) for item in record.expected_issue_codes
                    ),
                }
            )
    return tuple(rows)


def planning_architecture_delegate_rows() -> tuple[dict[str, Any], ...]:
    """Return evaluator-backed rows used by the aggregate evaluator and tests."""

    return _delegate_rows()


def _scenario_for(record: Any, control_ordinals: dict[str, int]) -> PlanningArchitectureScenario:
    if str(record.role.value) == "positive":
        return PlanningArchitectureScenario.POSITIVE
    ordinal = control_ordinals.get(str(record.operation.value), 0) + 1
    control_ordinals[str(record.operation.value)] = ordinal
    return PlanningArchitectureScenario(f"control_{chr(96 + ordinal)}")


def _case_id(operation_id: str, delegate_record_id: str) -> str:
    if delegate_record_id.startswith("D13-"):
        return delegate_record_id
    suffix = delegate_record_id.split("-", 1)[1]
    return f"{operation_id}-{suffix}"


def _expected_counts(row: Mapping[str, Any]) -> dict[str, int]:
    payload = row["payload"] if isinstance(row["payload"], Mapping) else {}
    output = row["output"] if isinstance(row["output"], Mapping) else {}
    return {
        "source_count": len(row["record"].source_ids),
        "payload_field_count": len(payload),
        "output_field_count": len(output),
        "issue_count": len(row["issue_codes"]),
    }


def _cases(
    operations: tuple[PlanningArchitectureOperationSpec, ...],
    sources: tuple[PlanningArchitectureSource, ...],
) -> tuple[PlanningArchitectureCase, ...]:
    rows = planning_architecture_delegate_rows()
    source_by_delegate = {
        (source.family, source.delegate_source_id): source.source_id for source in sources
    }
    control_ordinals: dict[str, int] = {}
    cases: list[PlanningArchitectureCase] = []
    for operation in operations:
        row_group = [
            row
            for row in rows
            if row["family"] is operation.family
            and row["record"].operation.value == operation.delegate_operation
        ]
        row_group.sort(
            key=lambda row: (
                0 if str(row["record"].role.value) == "positive" else 1,
                row["record"].record_id,
            )
        )
        for row in row_group:
            record = row["record"]
            scenario = _scenario_for(record, control_ordinals)
            mapped_sources = tuple(
                source_by_delegate[(operation.family, source_id)] for source_id in record.source_ids
            )
            expected_counts = _expected_counts(row)
            body = {
                "case_id": _case_id(operation.operation_id, record.record_id),
                "operation_id": operation.operation_id,
                "operation": operation.operation,
                "family": operation.family,
                "plane": operation.plane,
                "scenario": scenario,
                "aggregate_context_key": PLANNING_ARCHITECTURE_CONTEXT,
                "delegate_context_key": row["delegate_context_key"],
                "delegate_fixture_id": row["fixture"].fixture_id,
                "delegate_record_id": record.record_id,
                "delegate_class": type(record).__name__,
                "source_ids": mapped_sources,
                "payload": row["payload"],
                "expected_state": PlanningArchitectureState(row["observed_state"]),
                "expected_issue_codes": row["issue_codes"],
                "expected_counts": expected_counts,
                "description": (
                    f"{operation.capability_id} retains the {scenario.value} path from "
                    f"{operation.family.value} with delegate state {row['observed_state']}"
                ),
            }
            cases.append(
                PlanningArchitectureCase(
                    **body,
                    content_address=addressed(body, "planning-case"),
                )
            )
    return tuple(cases)


def _fixture_body(
    sources: tuple[PlanningArchitectureSource, ...],
    operations: tuple[PlanningArchitectureOperationSpec, ...],
    cases: tuple[PlanningArchitectureCase, ...],
    family_contexts: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "fixture_id": "planning-architecture-public-aggregate-001",
        "version": PLANNING_ARCHITECTURE_VERSION,
        "boundary": PLANNING_ARCHITECTURE_BOUNDARY,
        "context_key": PLANNING_ARCHITECTURE_CONTEXT,
        "foreign_context_key": PLANNING_ARCHITECTURE_FOREIGN_CONTEXT,
        "family_contexts": family_contexts,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }


def default_planning_architecture_fixture() -> PlanningArchitectureFixture:
    sources = _sources()
    grouped_sources: dict[PlanningArchitectureFamily, tuple[PlanningArchitectureSource, ...]] = {
        family: tuple(item for item in sources if item.family is family)
        for family in PlanningArchitectureFamily
    }
    operations = _operation_specs(grouped_sources)
    cases = _cases(operations, sources)
    family_contexts = {
        spec.family.value: fixture.context_key for spec, fixture, _evaluation in _family_objects()
    }
    body = _fixture_body(sources, operations, cases, family_contexts)
    return PlanningArchitectureFixture(
        body["fixture_id"],
        body["version"],
        body["boundary"],
        body["context_key"],
        body["foreign_context_key"],
        family_contexts,
        sources,
        operations,
        cases,
        addressed(body, "planning-fixture"),
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    kind: PlanningArchitectureCheckKind,
) -> PlanningArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return PlanningArchitectureCheck(
        **body,
        content_address=addressed(body, "planning-data-check"),
    )


def audit_planning_architecture_data(
    fixture: PlanningArchitectureFixture,
) -> PlanningArchitectureDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    checks = (
        _check(
            "audit:source-count",
            len(fixture.sources) == PLANNING_ARCHITECTURE_SOURCE_COUNT,
            len(fixture.sources),
            PLANNING_ARCHITECTURE_SOURCE_COUNT,
            "all four delegate source registries are retained",
            PlanningArchitectureCheckKind.SOURCE,
        ),
        _check(
            "audit:operation-count",
            len(fixture.operations) == PLANNING_ARCHITECTURE_OPERATION_COUNT,
            len(fixture.operations),
            PLANNING_ARCHITECTURE_OPERATION_COUNT,
            "all D13 capability operations are declared",
            PlanningArchitectureCheckKind.OPERATION,
        ),
        _check(
            "audit:case-count",
            len(fixture.cases) == PLANNING_ARCHITECTURE_CASE_COUNT,
            len(fixture.cases),
            PLANNING_ARCHITECTURE_CASE_COUNT,
            "four scenarios are retained for every capability",
            PlanningArchitectureCheckKind.CASE,
        ),
        _check(
            "audit:all-public",
            all(item.public_aggregate for item in fixture.sources),
            all(item.public_aggregate for item in fixture.sources),
            True,
            "source receipts declare a public aggregate boundary",
            PlanningArchitectureCheckKind.SAFETY,
        ),
        _check(
            "audit:family-contexts",
            len(fixture.family_contexts) == len(PlanningArchitectureFamily)
            and all(value for value in fixture.family_contexts.values()),
            fixture.family_contexts,
            {"family_count": len(PlanningArchitectureFamily)},
            "one exact delegate context is retained per family",
            PlanningArchitectureCheckKind.SOURCE,
        ),
        _check(
            "audit:operation-ordinals",
            tuple(item.ordinal for item in fixture.operations)
            == tuple(range(1, PLANNING_ARCHITECTURE_OPERATION_COUNT + 1)),
            tuple(item.ordinal for item in fixture.operations),
            tuple(range(1, PLANNING_ARCHITECTURE_OPERATION_COUNT + 1)),
            "operation order is contiguous and deterministic",
            PlanningArchitectureCheckKind.OPERATION,
        ),
        _check(
            "audit:source-joins",
            all(set(item.source_ids) <= source_ids for item in fixture.cases)
            and all(set(item.source_ids) <= source_ids for item in fixture.operations),
            True,
            True,
            "case and operation source joins resolve",
            PlanningArchitectureCheckKind.SOURCE,
        ),
        _check(
            "audit:operation-joins",
            all(item.operation_id in operation_ids for item in fixture.cases),
            True,
            True,
            "every case resolves to a declared operation",
            PlanningArchitectureCheckKind.OPERATION,
        ),
        _check(
            "audit:scenario-balance",
            all(
                sum(item.operation_id == operation.operation_id for item in fixture.cases)
                == PLANNING_ARCHITECTURE_CASES_PER_OPERATION
                for operation in fixture.operations
            ),
            len(fixture.cases),
            PLANNING_ARCHITECTURE_CASE_COUNT,
            "each operation has one positive and three controls",
            PlanningArchitectureCheckKind.CONTROL,
        ),
        _check(
            "audit:foreign-control",
            fixture.foreign_context_key == PLANNING_ARCHITECTURE_FOREIGN_CONTEXT,
            fixture.foreign_context_key,
            PLANNING_ARCHITECTURE_FOREIGN_CONTEXT,
            "foreign context is reserved as a negative control label",
            PlanningArchitectureCheckKind.SAFETY,
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return PlanningArchitectureDataAudit(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "planning-data-audit"),
    )


def load_planning_architecture_fixture(path: str | Path) -> PlanningArchitectureFixture:
    return PlanningArchitectureFixture.from_file(path)


def planning_architecture_fixture_json(
    fixture: PlanningArchitectureFixture | None = None,
) -> str:
    selected = fixture or default_planning_architecture_fixture()
    return json.dumps(jsonable(selected.to_dict()), indent=2, sort_keys=True) + "\n"


__all__ = [
    "audit_planning_architecture_data",
    "default_planning_architecture_fixture",
    "load_planning_architecture_fixture",
    "planning_architecture_delegate_rows",
    "planning_architecture_fixture_json",
]

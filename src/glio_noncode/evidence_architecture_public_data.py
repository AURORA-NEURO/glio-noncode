"""D14 public aggregate assembly from lifecycle and release delegates."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .evidence_architecture_contracts import (
    EVIDENCE_ARCHITECTURE_BOUNDARY,
    EVIDENCE_ARCHITECTURE_CASE_COUNT,
    EVIDENCE_ARCHITECTURE_CASES_PER_OPERATION,
    EVIDENCE_ARCHITECTURE_CONTEXT,
    EVIDENCE_ARCHITECTURE_FOREIGN_CONTEXT,
    EVIDENCE_ARCHITECTURE_OPERATION_COUNT,
    EVIDENCE_ARCHITECTURE_SOURCE_COUNT,
    EVIDENCE_ARCHITECTURE_VERSION,
    EvidenceArchitectureCase,
    EvidenceArchitectureCheck,
    EvidenceArchitectureCheckKind,
    EvidenceArchitectureDataAudit,
    EvidenceArchitectureFamily,
    EvidenceArchitectureFixture,
    EvidenceArchitectureOperation,
    EvidenceArchitectureOperationSpec,
    EvidenceArchitecturePlane,
    EvidenceArchitectureScenario,
    EvidenceArchitectureSource,
    EvidenceArchitectureState,
    addressed,
)
from .evidence_lifecycle_frontier_fixture_eval import evaluate_evidence_lifecycle_fixture
from .evidence_lifecycle_frontier_public_data import default_evidence_lifecycle_fixture
from .evidence_release_frontier_fixture_eval import evaluate_evidence_release_fixture
from .evidence_release_frontier_public_data import default_evidence_release_frontier_fixture
from .lifecycle_beta_frontier_fixture_eval import evaluate_lifecycle_beta_frontier_fixture
from .lifecycle_beta_frontier_public_data import default_lifecycle_beta_frontier_fixture
from .serialization import jsonable


@dataclass(frozen=True, slots=True)
class _FamilySpec:
    family: EvidenceArchitectureFamily
    plane: EvidenceArchitecturePlane
    fixture_loader: Any
    evaluator: Any
    source_kind: str
    source_prefix: str


_FAMILY_SPECS = (
    _FamilySpec(
        EvidenceArchitectureFamily.LIFECYCLE_FOUNDATION,
        EvidenceArchitecturePlane.LIFECYCLE_FOUNDATION,
        default_evidence_lifecycle_fixture,
        evaluate_evidence_lifecycle_fixture,
        "public_lifecycle_foundation_receipt",
        "D14-lifecycle-foundation",
    ),
    _FamilySpec(
        EvidenceArchitectureFamily.LIFECYCLE_BETA,
        EvidenceArchitecturePlane.LIFECYCLE_ADJUDICATION,
        default_lifecycle_beta_frontier_fixture,
        evaluate_lifecycle_beta_frontier_fixture,
        "public_lifecycle_adjudication_receipt",
        "D14-lifecycle-beta",
    ),
    _FamilySpec(
        EvidenceArchitectureFamily.EVIDENCE_RELEASE,
        EvidenceArchitecturePlane.EVIDENCE_RELEASE,
        default_evidence_release_frontier_fixture,
        evaluate_evidence_release_fixture,
        "public_evidence_release_receipt",
        "D14-evidence-release",
    ),
)


_OPERATIONS = (
    (
        "D14-C01",
        "GNC-D14-C01",
        EvidenceArchitectureOperation.CITATION_RESOLUTION,
        "citation_resolution",
        EvidenceArchitectureFamily.LIFECYCLE_FOUNDATION,
        "lifecycle_foundation",
        "lifecycle.citation_input.v1",
        "lifecycle.citation_output.v1",
        (),
        "retain_valid_rows_and_quarantine_malformed_citations",
    ),
    (
        "D14-C02",
        "GNC-D14-C02",
        EvidenceArchitectureOperation.GRAPH_CONSTRUCTION,
        "graph_construction",
        EvidenceArchitectureFamily.LIFECYCLE_FOUNDATION,
        "lifecycle_foundation",
        "lifecycle.graph_input.v1",
        "lifecycle.graph_output.v1",
        ("D14-C01",),
        "retain_history_orphans_context_and_duplicate_controls",
    ),
    (
        "D14-C03",
        "GNC-D14-C03",
        EvidenceArchitectureOperation.EDGE_VALIDATION,
        "edge_validation",
        EvidenceArchitectureFamily.LIFECYCLE_FOUNDATION,
        "lifecycle_foundation",
        "lifecycle.edge_input.v1",
        "lifecycle.edge_output.v1",
        ("D14-C01", "D14-C02"),
        "retain_source_context_absence_and_contradiction_controls",
    ),
    (
        "D14-C04",
        "GNC-D14-C04",
        EvidenceArchitectureOperation.DISAGREEMENT_TRACKING,
        "disagreement_tracking",
        EvidenceArchitectureFamily.LIFECYCLE_FOUNDATION,
        "lifecycle_foundation",
        "lifecycle.disagreement_input.v1",
        "lifecycle.disagreement_output.v1",
        ("D14-C02", "D14-C03"),
        "retain_positive_negative_incomplete_and_domain_controls",
    ),
    (
        "D14-C05",
        "GNC-D14-C05",
        EvidenceArchitectureOperation.TIER_ADJUDICATION,
        "tier_adjudication",
        EvidenceArchitectureFamily.LIFECYCLE_BETA,
        "lifecycle_adjudication",
        "lifecycle.tier_input.v1",
        "lifecycle.tier_output.v1",
        ("D14-C02", "D14-C04"),
        "retain_direction_conflict_context_and_unclassified_tier_controls",
    ),
    (
        "D14-C06",
        "GNC-D14-C06",
        EvidenceArchitectureOperation.PROVENANCE_LINEAGE,
        "provenance_lineage",
        EvidenceArchitectureFamily.LIFECYCLE_BETA,
        "lifecycle_adjudication",
        "lifecycle.provenance_input.v1",
        "lifecycle.provenance_output.v1",
        ("D14-C02",),
        "retain_parent_context_and_empty_claim_controls",
    ),
    (
        "D14-C07",
        "GNC-D14-C07",
        EvidenceArchitectureOperation.UNCERTAINTY_LEDGER,
        "uncertainty_ledger",
        EvidenceArchitectureFamily.LIFECYCLE_BETA,
        "lifecycle_adjudication",
        "lifecycle.uncertainty_input.v1",
        "lifecycle.uncertainty_output.v1",
        ("D14-C03", "D14-C06"),
        "retain_context_empty_entry_and_invalid_measurement_controls",
    ),
    (
        "D14-C08",
        "GNC-D14-C08",
        EvidenceArchitectureOperation.REVIEW_ROUTING,
        "review_routing",
        EvidenceArchitectureFamily.LIFECYCLE_BETA,
        "lifecycle_adjudication",
        "lifecycle.review_input.v1",
        "lifecycle.review_output.v1",
        ("D14-C04", "D14-C07"),
        "retain_contradiction_context_empty_claim_and_role_controls",
    ),
    (
        "D14-C09",
        "GNC-D14-C09",
        EvidenceArchitectureOperation.BLINDED_ADJUDICATION,
        "blinded_adjudication",
        EvidenceArchitectureFamily.LIFECYCLE_BETA,
        "lifecycle_adjudication",
        "lifecycle.blinded_input.v1",
        "lifecycle.blinded_output.v1",
        ("D14-C08",),
        "retain_split_decision_required_count_and_context_controls",
    ),
    (
        "D14-C10",
        "GNC-D14-C10",
        EvidenceArchitectureOperation.COMMENT_CHANGE_LOG,
        "comment_change_log",
        EvidenceArchitectureFamily.LIFECYCLE_BETA,
        "lifecycle_adjudication",
        "lifecycle.comment_input.v1",
        "lifecycle.comment_output.v1",
        ("D14-C08", "D14-C09"),
        "retain_duplicate_context_and_empty_review_controls",
    ),
    (
        "D14-C11",
        "GNC-D14-C11",
        EvidenceArchitectureOperation.RELEASE_DECISION,
        "release_decision",
        EvidenceArchitectureFamily.LIFECYCLE_BETA,
        "lifecycle_adjudication",
        "lifecycle.decision_input.v1",
        "lifecycle.decision_output.v1",
        ("D14-C08", "D14-C10"),
        "retain_gate_rejection_and_context_controls",
    ),
    (
        "D14-C12",
        "GNC-D14-C12",
        EvidenceArchitectureOperation.EVIDENCE_DELTA,
        "evidence_delta",
        EvidenceArchitectureFamily.LIFECYCLE_BETA,
        "lifecycle_adjudication",
        "lifecycle.delta_input.v1",
        "lifecycle.delta_output.v1",
        ("D14-C02", "D14-C06", "D14-C11"),
        "retain_added_changed_context_and_ready controls",
    ),
    (
        "D14-C13",
        "GNC-D14-C13",
        EvidenceArchitectureOperation.RECLASSIFICATION,
        "reclassification",
        EvidenceArchitectureFamily.EVIDENCE_RELEASE,
        "evidence_release",
        "release.reclassification_input.v1",
        "release.reclassification_output.v1",
        ("D14-C05", "D14-C11"),
        "retain_score_reviewer_source_and_context_controls",
    ),
    (
        "D14-C14",
        "GNC-D14-C14",
        EvidenceArchitectureOperation.SUPERSESSION,
        "supersession",
        EvidenceArchitectureFamily.EVIDENCE_RELEASE,
        "evidence_release",
        "release.supersession_input.v1",
        "release.supersession_output.v1",
        ("D14-C02", "D14-C13"),
        "retain_target_self_cycle_and_context controls",
    ),
    (
        "D14-C15",
        "GNC-D14-C15",
        EvidenceArchitectureOperation.REPRODUCIBILITY_BUNDLE,
        "reproducibility_bundle",
        EvidenceArchitectureFamily.EVIDENCE_RELEASE,
        "evidence_release",
        "release.bundle_input.v1",
        "release.bundle_output.v1",
        ("D14-C10", "D14-C11", "D14-C13"),
        "retain_section_identity_address_and_context controls",
    ),
    (
        "D14-C16",
        "GNC-D14-C16",
        EvidenceArchitectureOperation.SIGNED_DOSSIER,
        "signed_dossier",
        EvidenceArchitectureFamily.EVIDENCE_RELEASE,
        "evidence_release",
        "release.dossier_input.v1",
        "release.dossier_output.v1",
        ("D14-C13", "D14-C15"),
        "retain_expiry_audience_payload_and_context controls",
    ),
)


def _state_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _family_objects() -> tuple[tuple[_FamilySpec, Any, Any], ...]:
    return tuple(
        (spec, fixture, spec.evaluator(fixture))
        for spec in _FAMILY_SPECS
        for fixture in (spec.fixture_loader(),)
    )


_family_objects = lru_cache(maxsize=1)(_family_objects)


def _source_id(spec: _FamilySpec, delegate_source_id: str) -> str:
    return f"{spec.source_prefix}:{delegate_source_id}"


def _sources() -> tuple[EvidenceArchitectureSource, ...]:
    rows: list[EvidenceArchitectureSource] = []
    for spec, fixture, _evaluation in _family_objects():
        for source in fixture.sources:
            body = {
                "source_id": _source_id(spec, source.source_id),
                "family": spec.family,
                "source_kind": spec.source_kind,
                "source_version": str(getattr(source, "version", fixture.fixture_version)),
                "uri": str(source.uri),
                "source_context_key": fixture.context_key,
                "delegate_source_id": source.source_id,
                "delegate_fixture_id": fixture.fixture_id,
                "public_aggregate": True,
                "delegate_content_address": source.content_address,
            }
            rows.append(
                EvidenceArchitectureSource(
                    **body, content_address=addressed(body, "evidence-source")
                )
            )
    return tuple(rows)


def _operation_specs(
    source_by_family: Mapping[EvidenceArchitectureFamily, tuple[EvidenceArchitectureSource, ...]],
) -> tuple[EvidenceArchitectureOperationSpec, ...]:
    rows: list[EvidenceArchitectureOperationSpec] = []
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
            "plane": EvidenceArchitecturePlane(plane_name),
            "input_contract": input_contract,
            "output_contract": output_contract,
            "dependencies": dependencies,
            "source_ids": source_ids,
            "control_policy": control_policy,
        }
        rows.append(
            EvidenceArchitectureOperationSpec(
                **body, content_address=addressed(body, "evidence-operation")
            )
        )
    return tuple(rows)


def _execution_issue_codes(execution: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in getattr(execution, "issue_codes", ()))


def _execution_state(execution: Any) -> str:
    value = getattr(execution, "observed_state", getattr(execution, "state", None))
    return _state_value(value)


@lru_cache(maxsize=1)
def _delegate_rows() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for spec, fixture, evaluation in _family_objects():
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
                    "payload": jsonable(record.payload),
                    "output": jsonable(output),
                    "delegate_context_key": str(record.context_key),
                    "observed_state": _execution_state(execution),
                    "issue_codes": _execution_issue_codes(execution),
                    "output_address": str(execution.content_address),
                    "expected_record_state": _state_value(record.expected_state),
                    "expected_record_issue_codes": tuple(
                        str(item) for item in record.expected_issue_codes
                    ),
                }
            )
    return tuple(rows)


def evidence_architecture_delegate_rows() -> tuple[dict[str, Any], ...]:
    """Return the three evaluator-backed D14 family row collections."""

    return _delegate_rows()


def _scenario_for(record: Any, control_ordinals: dict[str, int]) -> EvidenceArchitectureScenario:
    if str(record.role.value) == "positive":
        return EvidenceArchitectureScenario.POSITIVE
    ordinal = control_ordinals.get(str(record.operation.value), 0) + 1
    control_ordinals[str(record.operation.value)] = ordinal
    return EvidenceArchitectureScenario(f"control_{chr(96 + ordinal)}")


def _case_id(operation_id: str, delegate_record_id: str) -> str:
    return (
        delegate_record_id if delegate_record_id.startswith("D14-") else f"D14-{delegate_record_id}"
    )


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
    operations: tuple[EvidenceArchitectureOperationSpec, ...],
    sources: tuple[EvidenceArchitectureSource, ...],
) -> tuple[EvidenceArchitectureCase, ...]:
    rows = evidence_architecture_delegate_rows()
    source_by_delegate = {
        (source.family, source.delegate_source_id): source.source_id for source in sources
    }
    control_ordinals: dict[str, int] = {}
    cases: list[EvidenceArchitectureCase] = []
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
                "aggregate_context_key": EVIDENCE_ARCHITECTURE_CONTEXT,
                "delegate_context_key": row["delegate_context_key"],
                "delegate_fixture_id": row["fixture"].fixture_id,
                "delegate_record_id": record.record_id,
                "delegate_class": type(record).__name__,
                "source_ids": mapped_sources,
                "payload": row["payload"],
                "expected_state": EvidenceArchitectureState(row["observed_state"]),
                "expected_issue_codes": row["issue_codes"],
                "expected_counts": expected_counts,
                "description": (
                    f"{operation.capability_id} retains the {scenario.value} path from "
                    f"{operation.family.value} with state {row['observed_state']}"
                ),
            }
            cases.append(
                EvidenceArchitectureCase(**body, content_address=addressed(body, "evidence-case"))
            )
    return tuple(cases)


def _fixture_body(
    sources: tuple[EvidenceArchitectureSource, ...],
    operations: tuple[EvidenceArchitectureOperationSpec, ...],
    cases: tuple[EvidenceArchitectureCase, ...],
    family_contexts: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "fixture_id": "evidence-architecture-public-aggregate-001",
        "version": EVIDENCE_ARCHITECTURE_VERSION,
        "boundary": EVIDENCE_ARCHITECTURE_BOUNDARY,
        "context_key": EVIDENCE_ARCHITECTURE_CONTEXT,
        "foreign_context_key": EVIDENCE_ARCHITECTURE_FOREIGN_CONTEXT,
        "family_contexts": family_contexts,
        "sources": sources,
        "operations": operations,
        "cases": cases,
    }


def default_evidence_architecture_fixture() -> EvidenceArchitectureFixture:
    sources = _sources()
    grouped_sources: dict[EvidenceArchitectureFamily, tuple[EvidenceArchitectureSource, ...]] = {
        family: tuple(item for item in sources if item.family is family)
        for family in EvidenceArchitectureFamily
    }
    operations = _operation_specs(grouped_sources)
    cases = _cases(operations, sources)
    family_contexts = {
        spec.family.value: fixture.context_key for spec, fixture, _evaluation in _family_objects()
    }
    body = _fixture_body(sources, operations, cases, family_contexts)
    return EvidenceArchitectureFixture(
        body["fixture_id"],
        body["version"],
        body["boundary"],
        body["context_key"],
        body["foreign_context_key"],
        family_contexts,
        sources,
        operations,
        cases,
        addressed(body, "evidence-fixture"),
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    kind: EvidenceArchitectureCheckKind,
) -> EvidenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return EvidenceArchitectureCheck(**body, content_address=addressed(body, "evidence-data-check"))


def audit_evidence_architecture_data(
    fixture: EvidenceArchitectureFixture,
) -> EvidenceArchitectureDataAudit:
    source_ids = {item.source_id for item in fixture.sources}
    operation_ids = {item.operation_id for item in fixture.operations}
    operation_counts = {
        operation.operation_id: sum(
            item.operation_id == operation.operation_id for item in fixture.cases
        )
        for operation in fixture.operations
    }
    checks = (
        _check(
            "audit:source-count",
            len(fixture.sources) == EVIDENCE_ARCHITECTURE_SOURCE_COUNT,
            len(fixture.sources),
            EVIDENCE_ARCHITECTURE_SOURCE_COUNT,
            "three delegate source registries are retained",
            EvidenceArchitectureCheckKind.SOURCE,
        ),
        _check(
            "audit:operation-count",
            len(fixture.operations) == EVIDENCE_ARCHITECTURE_OPERATION_COUNT,
            len(fixture.operations),
            EVIDENCE_ARCHITECTURE_OPERATION_COUNT,
            "all D14 capability operations are declared",
            EvidenceArchitectureCheckKind.OPERATION,
        ),
        _check(
            "audit:case-count",
            len(fixture.cases) == EVIDENCE_ARCHITECTURE_CASE_COUNT,
            len(fixture.cases),
            EVIDENCE_ARCHITECTURE_CASE_COUNT,
            "four scenarios are retained per operation",
            EvidenceArchitectureCheckKind.CASE,
        ),
        _check(
            "audit:family-contexts",
            len(fixture.family_contexts) == 3 and all(fixture.family_contexts.values()),
            fixture.family_contexts,
            "three exact delegate contexts",
            "family contexts remain visible",
            EvidenceArchitectureCheckKind.SOURCE,
        ),
        _check(
            "audit:all-public",
            all(item.public_aggregate for item in fixture.sources),
            all(item.public_aggregate for item in fixture.sources),
            True,
            "all source receipts are public aggregate",
            EvidenceArchitectureCheckKind.SAFETY,
        ),
        _check(
            "audit:ordinals",
            tuple(item.ordinal for item in fixture.operations)
            == tuple(range(1, EVIDENCE_ARCHITECTURE_OPERATION_COUNT + 1)),
            tuple(item.ordinal for item in fixture.operations),
            tuple(range(1, EVIDENCE_ARCHITECTURE_OPERATION_COUNT + 1)),
            "operation order is contiguous",
            EvidenceArchitectureCheckKind.OPERATION,
        ),
        _check(
            "audit:source-joins",
            all(set(item.source_ids) <= source_ids for item in fixture.cases)
            and all(set(item.source_ids) <= source_ids for item in fixture.operations),
            True,
            True,
            "case and operation source joins resolve",
            EvidenceArchitectureCheckKind.SOURCE,
        ),
        _check(
            "audit:operation-joins",
            all(item.operation_id in operation_ids for item in fixture.cases),
            True,
            True,
            "every case resolves to an operation",
            EvidenceArchitectureCheckKind.OPERATION,
        ),
        _check(
            "audit:operation-balance",
            set(operation_counts.values()) == {EVIDENCE_ARCHITECTURE_CASES_PER_OPERATION},
            operation_counts,
            EVIDENCE_ARCHITECTURE_CASES_PER_OPERATION,
            "every capability contributes four cases",
            EvidenceArchitectureCheckKind.CONTROL,
        ),
        _check(
            "audit:foreign-control",
            fixture.foreign_context_key == EVIDENCE_ARCHITECTURE_FOREIGN_CONTEXT,
            fixture.foreign_context_key,
            EVIDENCE_ARCHITECTURE_FOREIGN_CONTEXT,
            "foreign context is a reserved control label",
            EvidenceArchitectureCheckKind.SAFETY,
        ),
    )
    body = {"fixture_id": fixture.fixture_id, "checks": checks}
    return EvidenceArchitectureDataAudit(
        fixture.fixture_id,
        checks,
        all(item.passed for item in checks),
        addressed(body, "evidence-data-audit"),
    )


def load_evidence_architecture_fixture(path: str | Path) -> EvidenceArchitectureFixture:
    return EvidenceArchitectureFixture.from_file(path)


def evidence_architecture_fixture_json(fixture: EvidenceArchitectureFixture | None = None) -> str:
    selected = fixture or default_evidence_architecture_fixture()
    return json.dumps(jsonable(selected.to_dict()), indent=2, sort_keys=True) + "\n"


__all__ = [
    "audit_evidence_architecture_data",
    "default_evidence_architecture_fixture",
    "evidence_architecture_delegate_rows",
    "evidence_architecture_fixture_json",
    "load_evidence_architecture_fixture",
]

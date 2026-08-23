"""Compose the four typed D05 atlas families behind one boundary."""

from __future__ import annotations

import json
from typing import Any

from .atlas_alpha_evidence_fixture_eval import _execute as execute_alpha
from .atlas_alpha_evidence_public_data import (
    AtlasAlphaEvidenceOperation,
    AtlasAlphaEvidenceRecord,
    AtlasAlphaEvidenceRole,
)
from .atlas_architecture_contracts import (
    AtlasArchitectureCase,
    AtlasArchitectureCaseReceipt,
    AtlasArchitectureCheck,
    AtlasArchitectureCheckKind,
    AtlasArchitectureEvaluation,
    AtlasArchitectureExecution,
    AtlasArchitectureFamily,
    AtlasArchitectureFixture,
    AtlasArchitectureOperation,
    AtlasArchitectureScenario,
    AtlasArchitectureState,
    addressed,
)
from .errors import ValidationError
from .frontier_atlas_fixture_eval import _execute as execute_frontier
from .frontier_atlas_public_data import (
    FrontierAtlasOperation,
    FrontierAtlasRecord,
    FrontierAtlasRole,
)
from .molecular_atlas_fixture_eval import _execute_record as execute_molecular
from .molecular_atlas_public_data import (
    MolecularAtlasOperation,
    MolecularAtlasRecord,
    MolecularAtlasRole,
)
from .regulatory_atlas_fixture_eval import _execute_record as execute_regulatory
from .regulatory_atlas_public_data import (
    RegulatoryAtlasOperation,
    RegulatoryAtlasRecord,
    RegulatoryAtlasRole,
)
from .serialization import content_hash

_REGULATORY = {
    AtlasArchitectureOperation.CCRE_TRACK_PARSE,
    AtlasArchitectureOperation.BRAIN_CELL_PROFILE,
    AtlasArchitectureOperation.ADULT_GLIO_PROFILE,
    AtlasArchitectureOperation.PEDIATRIC_GLIO_PROFILE,
}
_MOLECULAR = {
    AtlasArchitectureOperation.IDH_MUTANT_PROFILE,
    AtlasArchitectureOperation.IDH_WILDTYPE_PROFILE,
    AtlasArchitectureOperation.H3K27_PROFILE,
    AtlasArchitectureOperation.HISTONE_HARMONIZATION,
}
_ALPHA = {
    AtlasArchitectureOperation.OPEN_CHROMATIN_HARMONIZATION,
    AtlasArchitectureOperation.METHYLATION_HARMONIZATION,
    AtlasArchitectureOperation.REGULATORY_ROLE_CLASSIFICATION,
    AtlasArchitectureOperation.SUPER_ENHANCER_ATLAS,
}
_FRONTIER = {
    AtlasArchitectureOperation.BOUNDARY_ATLAS,
    AtlasArchitectureOperation.HOTSPOT_ATLAS,
    AtlasArchitectureOperation.EVIDENCE_TIER,
    AtlasArchitectureOperation.SNAPSHOT_PUBLISH,
}
_SUCCESSFUL_RESULT_STATES = {"supported", "accepted", "published"}


def evaluate_atlas_architecture_fixture(
    fixture: AtlasArchitectureFixture | str,
) -> AtlasArchitectureEvaluation:
    """Execute all positive family records and hold all boundary controls."""

    from .atlas_architecture_public_data import default_atlas_architecture_fixture

    selected = default_atlas_architecture_fixture(fixture) if isinstance(fixture, str) else fixture
    receipts: list[AtlasArchitectureCaseReceipt] = []
    checks: list[AtlasArchitectureCheck] = []
    for case in selected.cases:
        execution = execute_atlas_architecture_case(case, selected.context_key)
        case_checks = _case_checks(case, execution)
        checks.extend(case_checks)
        passed = all(item.passed for item in case_checks)
        receipt_body = {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "family": case.family,
            "expected_state": case.expected_state,
            "observed_state": execution.observed_state,
            "expected_result_state": case.expected_result_state,
            "observed_result_state": execution.observed_result_state,
            "expected_issue_codes": case.expected_issue_codes,
            "observed_issue_codes": execution.issue_codes,
            "expected_counts": case.expected_counts,
            "observed_counts": execution.counts,
            "passed": passed,
            "output_address": execution.output_address,
        }
        receipts.append(
            AtlasArchitectureCaseReceipt(
                case_id=case.case_id,
                operation_id=case.operation_id,
                family=case.family,
                expected_state=case.expected_state,
                observed_state=execution.observed_state,
                expected_result_state=case.expected_result_state,
                observed_result_state=execution.observed_result_state,
                expected_issue_codes=case.expected_issue_codes,
                observed_issue_codes=execution.issue_codes,
                expected_counts=case.expected_counts,
                observed_counts=execution.counts,
                passed=passed,
                output_address=execution.output_address,
                detail=execution.detail,
                content_address=addressed(receipt_body, "atlas-receipt"),
            )
        )
    checks.extend(_global_checks(selected, receipts))
    state = (
        AtlasArchitectureState.ACCEPTED
        if all(item.passed for item in checks)
        else AtlasArchitectureState.REVIEW
    )
    body = {
        "fixture_id": selected.fixture_id,
        "context_key": selected.context_key,
        "state": state,
        "receipts": receipts,
        "checks": checks,
    }
    return AtlasArchitectureEvaluation(
        selected.fixture_id,
        selected.context_key,
        state,
        tuple(receipts),
        tuple(checks),
        addressed(body, "atlas-evaluation"),
    )


def execute_atlas_architecture_case(
    case: AtlasArchitectureCase,
    context_key: str,
) -> AtlasArchitectureExecution:
    """Apply the D05 policy before delegating a positive family record."""

    if case.scenario is not AtlasArchitectureScenario.POSITIVE:
        return _control_execution(case)
    if case.context_key != context_key:
        return _failed(
            case, "context_mismatch", "positive context differs from the runtime", "out_of_domain"
        )
    try:
        result_state, primary, secondary, issue_codes, summary = _execute_positive(case)
    except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        return _failed(case, "adapter_error", f"typed atlas adapter failed: {exc}", "invalid")
    normalized_issues = tuple(dict.fromkeys(str(item) for item in issue_codes))
    counts = {"primary_count": int(primary), "secondary_count": int(secondary)}
    observed_state = (
        AtlasArchitectureState.ACCEPTED
        if result_state in _SUCCESSFUL_RESULT_STATES
        else AtlasArchitectureState.REVIEW
    )
    output_address = content_hash(
        {
            "case_id": case.case_id,
            "result_state": result_state,
            "counts": counts,
            "summary": summary,
        }
    )
    return AtlasArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        family=case.family,
        scenario=case.scenario,
        observed_state=observed_state,
        observed_result_state=str(result_state),
        issue_codes=normalized_issues,
        counts=counts,
        output_address=output_address,
        summary={"family": case.family.value, "operation": case.operation.value, **dict(summary)},
        detail="typed D05 family adapter receipt normalized",
    )


def _execute_positive(
    case: AtlasArchitectureCase,
) -> tuple[str, int, int, tuple[str, ...], dict[str, Any]]:
    if case.operation in _REGULATORY:
        record = RegulatoryAtlasRecord(
            record_id=case.case_id,
            operation=RegulatoryAtlasOperation(case.operation.value),
            role=RegulatoryAtlasRole.POSITIVE,
            context_key=case.context_key,
            source_ids=case.source_ids,
            payload=dict(case.payload),
            expected_state=case.expected_result_state,
            expected_issue_codes=case.expected_issue_codes,
            description=case.description,
            content_address=content_hash({"case_id": case.case_id, "payload": case.payload}),
        )
        return execute_regulatory(record)
    if case.operation in _MOLECULAR:
        record = MolecularAtlasRecord(
            record_id=case.case_id,
            operation=MolecularAtlasOperation(case.operation.value),
            role=MolecularAtlasRole.POSITIVE,
            context_key=case.context_key,
            source_ids=case.source_ids,
            payload=dict(case.payload),
            expected_state=case.expected_result_state,
            expected_issue_codes=case.expected_issue_codes,
            description=case.description,
            content_address=content_hash({"case_id": case.case_id, "payload": case.payload}),
        )
        return execute_molecular(record)
    if case.operation in _ALPHA:
        record = AtlasAlphaEvidenceRecord(
            record_id=case.case_id,
            operation=AtlasAlphaEvidenceOperation(case.operation.value),
            role=AtlasAlphaEvidenceRole.POSITIVE,
            context_key=case.context_key,
            source_ids=case.source_ids,
            payload=dict(case.payload),
            expected_state=case.expected_result_state,
            expected_issue_codes=case.expected_issue_codes,
            description=case.description,
            content_address=content_hash({"case_id": case.case_id, "payload": case.payload}),
        )
        return execute_alpha(record)
    if case.operation in _FRONTIER:
        record = FrontierAtlasRecord(
            record_id=case.case_id,
            operation=FrontierAtlasOperation(case.operation.value),
            role=FrontierAtlasRole.POSITIVE,
            context_key=case.context_key,
            source_ids=case.source_ids,
            payload=dict(case.payload),
            expected_state=case.expected_result_state,
            expected_issue_codes=case.expected_issue_codes,
            description=case.description,
            content_address=content_hash({"case_id": case.case_id, "payload": case.payload}),
        )
        return execute_frontier(record)
    raise ValidationError(f"unsupported D05 operation: {case.operation.value}")


def _control_execution(case: AtlasArchitectureCase) -> AtlasArchitectureExecution:
    issue = {
        AtlasArchitectureScenario.FOREIGN_CONTEXT: "context_mismatch",
        AtlasArchitectureScenario.MALFORMED_INPUT: "malformed_input",
        AtlasArchitectureScenario.IDENTITY_CONFLICT: "identity_conflict",
    }[case.scenario]
    result = {
        AtlasArchitectureScenario.FOREIGN_CONTEXT: "out_of_domain",
        AtlasArchitectureScenario.MALFORMED_INPUT: "invalid",
        AtlasArchitectureScenario.IDENTITY_CONFLICT: "contradictory",
    }[case.scenario]
    summary = {
        "family": case.family.value,
        "operation": case.operation.value,
        "scenario": case.scenario.value,
        "held_before_adapter": True,
        "aggregate_only": bool(case.payload.get("aggregate_only", False)),
    }
    return AtlasArchitectureExecution(
        case.case_id,
        case.operation,
        case.family,
        case.scenario,
        AtlasArchitectureState.REVIEW,
        result,
        (issue,),
        {},
        content_hash({"case_id": case.case_id, "summary": summary}),
        summary,
        "D05 control held at the architecture boundary",
    )


def _failed(
    case: AtlasArchitectureCase,
    issue: str,
    detail: str,
    result: str,
) -> AtlasArchitectureExecution:
    return AtlasArchitectureExecution(
        case.case_id,
        case.operation,
        case.family,
        case.scenario,
        AtlasArchitectureState.REVIEW,
        result,
        (issue,),
        {},
        content_hash({"case_id": case.case_id, "issue": issue}),
        {"failure": issue},
        detail,
    )


def _case_checks(
    case: AtlasArchitectureCase,
    execution: AtlasArchitectureExecution,
) -> tuple[AtlasArchitectureCheck, ...]:
    checks: list[AtlasArchitectureCheck] = []
    values = (
        (
            "state",
            execution.observed_state,
            case.expected_state,
            "architecture state follows policy",
        ),
        (
            "result",
            execution.observed_result_state,
            case.expected_result_state,
            "family result is deterministic",
        ),
        (
            "issues",
            tuple(sorted(execution.issue_codes)),
            tuple(sorted(case.expected_issue_codes)),
            "issue codes are retained",
        ),
        ("counts", dict(execution.counts), dict(case.expected_counts), "bounded counts match"),
        (
            "address",
            execution.output_address.startswith("sha256:"),
            True,
            "execution is content addressed",
        ),
    )
    for name, observed, required, detail in values:
        body = {
            "check_id": f"{case.case_id}:{name}",
            "kind": AtlasArchitectureCheckKind.OPERATION,
            "passed": observed == required,
            "observed": observed,
            "required": required,
            "detail": detail,
        }
        checks.append(
            AtlasArchitectureCheck(
                body["check_id"],
                AtlasArchitectureCheckKind.OPERATION,
                body["passed"],
                observed,
                required,
                detail,
                addressed(body, "atlas-operation-check"),
            )
        )
    return tuple(checks)


def _global_checks(
    fixture: AtlasArchitectureFixture,
    receipts: list[AtlasArchitectureCaseReceipt],
) -> tuple[AtlasArchitectureCheck, ...]:
    values = (
        (
            "receipt-count",
            len(receipts) == len(fixture.cases),
            len(receipts),
            len(fixture.cases),
            "one receipt per case",
        ),
        (
            "receipt-identity",
            len({item.case_id for item in receipts}) == len(receipts),
            len({item.case_id for item in receipts}),
            len(receipts),
            "receipt IDs are unique",
        ),
        (
            "positive-count",
            sum(item.expected_state is AtlasArchitectureState.ACCEPTED for item in receipts) == 16,
            sum(item.expected_state is AtlasArchitectureState.ACCEPTED for item in receipts),
            16,
            "sixteen positive family records",
        ),
        (
            "control-count",
            sum(item.expected_state is AtlasArchitectureState.REVIEW for item in receipts) == 48,
            sum(item.expected_state is AtlasArchitectureState.REVIEW for item in receipts),
            48,
            "forty-eight boundary controls",
        ),
        (
            "case-closure",
            all(item.passed for item in receipts),
            all(item.passed for item in receipts),
            True,
            "all expected receipts close",
        ),
    )
    result: list[AtlasArchitectureCheck] = []
    for check_id, passed, observed, required, detail in values:
        body = {
            "check_id": check_id,
            "kind": AtlasArchitectureCheckKind.INVARIANT,
            "passed": passed,
            "observed": observed,
            "required": required,
            "detail": detail,
        }
        result.append(
            AtlasArchitectureCheck(
                check_id,
                AtlasArchitectureCheckKind.INVARIANT,
                passed,
                observed,
                required,
                detail,
                addressed(body, "atlas-global-check"),
            )
        )
    return tuple(result)


def family_for_operation(operation: AtlasArchitectureOperation) -> AtlasArchitectureFamily:
    if operation in _REGULATORY:
        return AtlasArchitectureFamily.REGULATORY
    if operation in _MOLECULAR:
        return AtlasArchitectureFamily.MOLECULAR
    if operation in _ALPHA:
        return AtlasArchitectureFamily.ALPHA_EVIDENCE
    if operation in _FRONTIER:
        return AtlasArchitectureFamily.FRONTIER
    raise ValidationError(f"unknown D05 operation: {operation}")


__all__ = [
    "evaluate_atlas_architecture_fixture",
    "execute_atlas_architecture_case",
    "family_for_operation",
]

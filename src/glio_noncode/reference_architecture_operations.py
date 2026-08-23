"""Compose D04 reference operations through the existing typed planes."""

from __future__ import annotations

from typing import Any

from .errors import ValidationError
from .reference_annotation_fixture_eval import _execute_record as execute_annotation
from .reference_annotation_public_data import (
    ReferenceAnnotationOperation,
    ReferenceAnnotationRecord,
    ReferenceAnnotationRole,
)
from .reference_architecture_contracts import (
    ReferenceArchitectureCase,
    ReferenceArchitectureCaseReceipt,
    ReferenceArchitectureCheck,
    ReferenceArchitectureCheckKind,
    ReferenceArchitectureEvaluation,
    ReferenceArchitectureExecution,
    ReferenceArchitectureFixture,
    ReferenceArchitectureOperation,
    ReferenceArchitectureScenario,
    ReferenceArchitectureState,
    addressed,
)
from .reference_coordinate_fixture_eval import ReferenceCoordinateFixtureEvaluator
from .reference_coordinate_public_data import (
    ReferenceCoordinateRecord,
    ReferenceCoordinateRole,
)
from .reference_extensions import ReferenceExtensionState
from .reference_governance_fixture_eval import _execute_record as execute_governance
from .reference_governance_public_data import (
    ReferenceGovernanceOperation,
    ReferenceGovernanceRecord,
    ReferenceGovernanceRole,
)
from .reference_release_frontier_fixture_eval import execute_reference_release_record
from .reference_release_frontier_public_data import (
    ReferenceReleaseOperation,
    ReferenceReleaseRecord,
    ReferenceReleaseRole,
)
from .serialization import content_hash

_COORDINATE = {
    ReferenceArchitectureOperation.REFERENCE_REGISTRY,
    ReferenceArchitectureOperation.LIFTOVER_CHAIN,
    ReferenceArchitectureOperation.LIFTOVER_AMBIGUITY,
    ReferenceArchitectureOperation.PANGENOME_COORDINATE,
}
_ANNOTATION = {
    ReferenceArchitectureOperation.GENCODE_TRANSCRIPT,
    ReferenceArchitectureOperation.MANE_TRANSCRIPT,
    ReferenceArchitectureOperation.REGULATORY_ONTOLOGY,
    ReferenceArchitectureOperation.DISEASE_ONTOLOGY,
}
_GOVERNANCE = {
    ReferenceArchitectureOperation.GENE_ALIAS,
    ReferenceArchitectureOperation.POPULATION_FREQUENCY,
    ReferenceArchitectureOperation.REFERENCE_SNAPSHOT,
    ReferenceArchitectureOperation.LICENSE_RESTRICTION,
}
_RELEASE = {
    ReferenceArchitectureOperation.PROVENANCE_CHECK,
    ReferenceArchitectureOperation.ANNOTATION_DRIFT,
    ReferenceArchitectureOperation.REFERENCE_BUNDLE,
    ReferenceArchitectureOperation.RELEASE_GATE,
}


def evaluate_reference_architecture_fixture(
    fixture: ReferenceArchitectureFixture | str,
) -> ReferenceArchitectureEvaluation:
    """Execute all 64 cases and close expected-versus-observed receipts."""

    from .reference_architecture_public_data import default_reference_architecture_fixture

    value = default_reference_architecture_fixture(fixture) if isinstance(fixture, str) else fixture
    receipts: list[ReferenceArchitectureCaseReceipt] = []
    checks: list[ReferenceArchitectureCheck] = []
    for case in value.cases:
        execution = execute_reference_architecture_case(case, value.context_key)
        case_checks = _checks_for_case(case, execution)
        checks.extend(case_checks)
        body = {
            "case_id": case.case_id,
            "operation_id": case.operation_id,
            "expected_state": case.expected_state,
            "observed_state": execution.observed_state,
            "expected_result_state": case.expected_result_state,
            "observed_result_state": execution.observed_result_state,
            "expected_issue_codes": case.expected_issue_codes,
            "observed_issue_codes": execution.issue_codes,
            "expected_counts": case.expected_counts,
            "observed_counts": execution.counts,
            "passed": all(item.passed for item in case_checks),
            "output_address": execution.output_address,
        }
        receipts.append(
            ReferenceArchitectureCaseReceipt(
                case_id=case.case_id,
                operation_id=case.operation_id,
                expected_state=case.expected_state,
                observed_state=execution.observed_state,
                expected_result_state=case.expected_result_state,
                observed_result_state=execution.observed_result_state,
                expected_issue_codes=case.expected_issue_codes,
                observed_issue_codes=execution.issue_codes,
                expected_counts=case.expected_counts,
                observed_counts=execution.counts,
                passed=all(item.passed for item in case_checks),
                output_address=execution.output_address,
                detail=execution.detail,
                content_address=content_hash(body),
            )
        )
    checks.extend(_global_checks(value, receipts))
    state = (
        ReferenceArchitectureState.ACCEPTED
        if all(item.passed for item in checks)
        else ReferenceArchitectureState.REVIEW
    )
    body = {
        "fixture_id": value.fixture_id,
        "context_key": value.context_key,
        "state": state,
        "receipts": receipts,
        "checks": checks,
    }
    return ReferenceArchitectureEvaluation(
        value.fixture_id,
        value.context_key,
        state,
        tuple(receipts),
        tuple(checks),
        addressed(body, "reference-evaluation"),
    )


def execute_reference_architecture_case(
    case: ReferenceArchitectureCase,
    context_key: str,
) -> ReferenceArchitectureExecution:
    """Apply architecture policy first, then delegate one positive case."""

    if case.scenario is not ReferenceArchitectureScenario.POSITIVE:
        return _control_execution(case)
    if case.context_key != context_key:
        return _failed(
            case, "context_mismatch", "positive reference context differs", "out_of_domain"
        )
    try:
        domain = _execute_positive(case)
    except (TypeError, ValueError, ValidationError, KeyError) as exc:
        return _failed(
            case, "validation_error", f"reference adapter validation failed: {exc}", "invalid"
        )
    result_state = str(domain["result_state"])
    issue_codes = tuple(sorted(str(item) for item in domain["issue_codes"]))
    counts = {str(key): int(value) for key, value in domain["counts"].items()}
    accepted_states = {"supported", "accepted", "published"}
    observed_state = (
        ReferenceArchitectureState.ACCEPTED
        if result_state in accepted_states
        else ReferenceArchitectureState.REVIEW
    )
    return ReferenceArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        scenario=case.scenario,
        observed_state=observed_state,
        observed_result_state=result_state,
        issue_codes=issue_codes,
        counts=counts,
        output_address=str(domain["output_address"]),
        summary={
            "family": _family(case.operation),
            "result_state": result_state,
            "counts": counts,
            "issue_codes": issue_codes,
            **dict(domain["summary"]),
        },
        detail=str(domain["detail"]),
    )


def _execute_positive(case: ReferenceArchitectureCase) -> dict[str, Any]:
    if case.operation in _COORDINATE:
        record = ReferenceCoordinateRecord.from_mapping(
            {
                "record_id": case.case_id,
                "operation": case.operation.value,
                "role": ReferenceCoordinateRole.POSITIVE.value,
                "expected_state": ReferenceExtensionState.SUPPORTED.value,
                "context_key": case.context_key,
                "source_ids": list(case.source_ids),
                "expected_issue_codes": list(case.expected_issue_codes),
                "payload": dict(case.payload),
            }
        )
        receipt, execution_issues = ReferenceCoordinateFixtureEvaluator()._execute(record)
        issues = tuple(receipt.issue_codes) if receipt.issue_codes else tuple(execution_issues)
        return {
            "result_state": receipt.state.value,
            "issue_codes": issues,
            "counts": {"summary_fields": len(receipt.result_summary)},
            "output_address": receipt.content_address,
            "summary": dict(receipt.result_summary),
            "detail": "coordinate adapter receipt normalized",
        }
    if case.operation in _ANNOTATION:
        record = _annotation_record(case)
        catalog_state, catalog_count, result_state, match_count, issues, summary = (
            execute_annotation(record)
        )
        return {
            "result_state": result_state,
            "issue_codes": tuple(issues),
            "counts": {"catalog_count": int(catalog_count), "match_count": int(match_count)},
            "output_address": content_hash({"case_id": case.case_id, "summary": summary}),
            "summary": summary,
            "detail": f"annotation adapter catalog={catalog_state}",
        }
    if case.operation in _GOVERNANCE:
        record = _governance_record(case)
        adapter_state, primary_count, secondary_count, issues, summary = execute_governance(record)
        return {
            "result_state": str(adapter_state),
            "issue_codes": tuple(issues),
            "counts": {
                "primary_count": int(primary_count),
                "secondary_count": int(secondary_count),
            },
            "output_address": content_hash({"case_id": case.case_id, "summary": summary}),
            "summary": summary,
            "detail": "governance adapter receipt normalized",
        }
    if case.operation in _RELEASE:
        record = _release_record(case)
        execution = execute_reference_release_record(record, context_key=case.context_key)
        return {
            "result_state": execution.state,
            "issue_codes": tuple(execution.issue_codes),
            "counts": {"output_fields": len(execution.output)},
            "output_address": execution.content_address,
            "summary": execution.output,
            "detail": "reference release adapter receipt normalized",
        }
    raise ValidationError(f"unsupported reference architecture operation: {case.operation.value}")


def _annotation_record(case: ReferenceArchitectureCase) -> Any:
    return ReferenceAnnotationRecord(
        record_id=case.case_id,
        operation=ReferenceAnnotationOperation(case.operation.value),
        role=ReferenceAnnotationRole.POSITIVE,
        context_key=case.context_key,
        source_ids=case.source_ids,
        payload=dict(case.payload),
        expected_state=case.expected_result_state,
        expected_issue_codes=case.expected_issue_codes,
        description=case.description or "architecture positive",
        content_address=content_hash({"case_id": case.case_id, "payload": case.payload}),
    )


def _governance_record(case: ReferenceArchitectureCase) -> Any:
    return ReferenceGovernanceRecord(
        record_id=case.case_id,
        operation=ReferenceGovernanceOperation(case.operation.value),
        role=ReferenceGovernanceRole.POSITIVE,
        context_key=case.context_key,
        source_ids=case.source_ids,
        payload=dict(case.payload),
        expected_state=case.expected_result_state,
        expected_issue_codes=case.expected_issue_codes,
        description=case.description or "architecture positive",
        content_address=content_hash({"case_id": case.case_id, "payload": case.payload}),
    )


def _release_record(case: ReferenceArchitectureCase) -> Any:
    return ReferenceReleaseRecord(
        record_id=case.case_id,
        operation=ReferenceReleaseOperation(case.operation.value),
        role=ReferenceReleaseRole.POSITIVE,
        context_key=case.context_key,
        source_ids=case.source_ids,
        payload=dict(case.payload),
        expected_state=case.expected_result_state,
        expected_issue_codes=case.expected_issue_codes,
        description=case.description or "architecture positive",
        content_address=content_hash({"case_id": case.case_id, "payload": case.payload}),
    )


def _control_execution(case: ReferenceArchitectureCase) -> ReferenceArchitectureExecution:
    issue = {
        ReferenceArchitectureScenario.FOREIGN_CONTEXT: "context_mismatch",
        ReferenceArchitectureScenario.MALFORMED_INPUT: "malformed_input",
        ReferenceArchitectureScenario.IDENTITY_CONFLICT: "identity_conflict",
    }[case.scenario]
    result = {
        ReferenceArchitectureScenario.FOREIGN_CONTEXT: "out_of_domain",
        ReferenceArchitectureScenario.MALFORMED_INPUT: "invalid",
        ReferenceArchitectureScenario.IDENTITY_CONFLICT: "contradictory",
    }[case.scenario]
    summary = {
        "family": _family(case.operation),
        "scenario": case.scenario.value,
        "held_before_adapter": True,
        "aggregate_only": bool(case.payload.get("aggregate_only", False)),
    }
    return ReferenceArchitectureExecution(
        case.case_id,
        case.operation,
        case.scenario,
        ReferenceArchitectureState.REVIEW,
        result,
        (issue,),
        {},
        content_hash({"case_id": case.case_id, "summary": summary}),
        summary,
        "control held at reference architecture boundary",
    )


def _failed(
    case: ReferenceArchitectureCase, issue: str, detail: str, result: str
) -> ReferenceArchitectureExecution:
    return ReferenceArchitectureExecution(
        case.case_id,
        case.operation,
        case.scenario,
        ReferenceArchitectureState.REVIEW,
        result,
        (issue,),
        {},
        content_hash({"case_id": case.case_id, "issue": issue}),
        {"failure": issue},
        detail,
    )


def _checks_for_case(
    case: ReferenceArchitectureCase, execution: ReferenceArchitectureExecution
) -> tuple[ReferenceArchitectureCheck, ...]:
    checks = []
    for name, observed, expected, detail in (
        (
            "state",
            execution.observed_state,
            case.expected_state,
            "architecture state follows the case contract",
        ),
        (
            "result",
            execution.observed_result_state,
            case.expected_result_state,
            "reference result state is deterministic",
        ),
        (
            "issues",
            tuple(sorted(execution.issue_codes)),
            tuple(sorted(case.expected_issue_codes)),
            "issue codes are retained",
        ),
        (
            "counts",
            dict(execution.counts),
            dict(case.expected_counts),
            "bounded result counts match",
        ),
        (
            "address",
            execution.output_address.startswith("sha256:"),
            True,
            "execution output is content addressed",
        ),
    ):
        checks.append(
            _check(
                f"{case.case_id}:{name}",
                ReferenceArchitectureCheckKind.OPERATION,
                observed == expected,
                observed,
                expected,
                detail,
            )
        )
    return tuple(checks)


def _global_checks(
    fixture: ReferenceArchitectureFixture, receipts: list[ReferenceArchitectureCaseReceipt]
) -> tuple[ReferenceArchitectureCheck, ...]:
    return (
        _check(
            "global-receipt-count",
            ReferenceArchitectureCheckKind.INVARIANT,
            len(receipts) == len(fixture.cases),
            len(receipts),
            len(fixture.cases),
            "one receipt per case",
        ),
        _check(
            "global-receipt-identity",
            ReferenceArchitectureCheckKind.INVARIANT,
            len({item.case_id for item in receipts}) == len(receipts),
            len({item.case_id for item in receipts}),
            len(receipts),
            "receipt IDs are unique",
        ),
        _check(
            "global-positive-count",
            ReferenceArchitectureCheckKind.INVARIANT,
            sum(item.expected_state is ReferenceArchitectureState.ACCEPTED for item in receipts)
            == 16,
            sum(item.expected_state is ReferenceArchitectureState.ACCEPTED for item in receipts),
            16,
            "sixteen positive reference cases",
        ),
        _check(
            "global-control-count",
            ReferenceArchitectureCheckKind.INVARIANT,
            sum(item.expected_state is ReferenceArchitectureState.REVIEW for item in receipts)
            == 48,
            sum(item.expected_state is ReferenceArchitectureState.REVIEW for item in receipts),
            48,
            "forty-eight controls remain review",
        ),
        _check(
            "global-case-closure",
            ReferenceArchitectureCheckKind.INVARIANT,
            all(item.passed for item in receipts),
            all(item.passed for item in receipts),
            True,
            "all expected-versus-observed receipts close",
        ),
    )


def _check(
    check_id: str,
    kind: ReferenceArchitectureCheckKind,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ReferenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ReferenceArchitectureCheck(
        check_id,
        kind,
        passed,
        observed,
        required,
        detail,
        addressed(body, "reference-operation-check"),
    )


def _family(operation: ReferenceArchitectureOperation) -> str:
    if operation in _COORDINATE:
        return "coordinate"
    if operation in _ANNOTATION:
        return "annotation"
    if operation in _GOVERNANCE:
        return "governance"
    if operation in _RELEASE:
        return "release"
    return "unknown"


__all__ = ["evaluate_reference_architecture_fixture", "execute_reference_architecture_case"]

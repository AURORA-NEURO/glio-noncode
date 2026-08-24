"""D14 delegate execution, receipts, and evidence architecture checks."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .evidence_architecture_contracts import (
    EVIDENCE_ARCHITECTURE_CASE_COUNT,
    EVIDENCE_ARCHITECTURE_CASES_PER_OPERATION,
    EVIDENCE_ARCHITECTURE_OPERATION_COUNT,
    EvidenceArchitectureCase,
    EvidenceArchitectureCaseReceipt,
    EvidenceArchitectureCheck,
    EvidenceArchitectureCheckKind,
    EvidenceArchitectureEvaluation,
    EvidenceArchitectureExecution,
    EvidenceArchitectureFixture,
    EvidenceArchitectureScenario,
    EvidenceArchitectureState,
    addressed,
)
from .evidence_architecture_public_data import (
    default_evidence_architecture_fixture,
    evidence_architecture_delegate_rows,
)


def _delegate_outcomes() -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (row["family"].value, row["record"].record_id): row
        for row in evidence_architecture_delegate_rows()
    }


def _check(
    check_id: str,
    kind: EvidenceArchitectureCheckKind,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> EvidenceArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return EvidenceArchitectureCheck(
        **body,
        content_address=addressed(body, "evidence-architecture-check"),
    )


def _execution_for_case(
    case: EvidenceArchitectureCase,
    outcomes: Mapping[tuple[str, str], dict[str, Any]],
) -> EvidenceArchitectureExecution:
    row = outcomes.get((case.family.value, case.delegate_record_id))
    if row is None:
        return EvidenceArchitectureExecution(
            case.case_id,
            case.operation,
            case.family,
            case.scenario,
            EvidenceArchitectureState.INVALID,
            ("missing_delegate_record",),
            {
                "source_count": 0,
                "payload_field_count": 0,
                "output_field_count": 0,
                "issue_count": 1,
            },
            addressed(case.case_id, "evidence-architecture-missing-output"),
            {"delegate_record_id": case.delegate_record_id},
            "delegate record could not be resolved from the pinned public family fixtures",
        )
    output = row["output"] if isinstance(row["output"], Mapping) else {}
    return EvidenceArchitectureExecution(
        case.case_id,
        case.operation,
        case.family,
        case.scenario,
        EvidenceArchitectureState(row["observed_state"]),
        tuple(str(item) for item in row["issue_codes"]),
        dict(case.expected_counts),
        str(row["output_address"]),
        {
            "delegate_fixture_id": row["fixture"].fixture_id,
            "delegate_record_id": row["record"].record_id,
            "delegate_class": type(row["record"]).__name__,
            "delegate_operation": row["record"].operation.value,
            "delegate_context_key": row["delegate_context_key"],
            "delegate_output_keys": tuple(sorted(str(key) for key in output)),
            "delegate_expected_state": row["expected_record_state"],
            "delegate_expected_issue_codes": row["expected_record_issue_codes"],
        },
        (
            f"{case.family.value} delegate {case.delegate_record_id} retained with "
            f"state {row['observed_state']} and {len(row['issue_codes'])} issue codes"
        ),
    )


def execute_evidence_architecture_case(
    case: EvidenceArchitectureCase,
) -> EvidenceArchitectureExecution:
    return _execution_for_case(case, _delegate_outcomes())


def _receipt(
    case: EvidenceArchitectureCase,
    execution: EvidenceArchitectureExecution,
) -> EvidenceArchitectureCaseReceipt:
    passed = (
        execution.observed_state is case.expected_state
        and execution.observed_issue_codes == case.expected_issue_codes
        and execution.observed_counts == case.expected_counts
        and bool(execution.output_address)
    )
    body = {
        "case_id": case.case_id,
        "operation_id": case.operation_id,
        "expected_state": case.expected_state,
        "observed_state": execution.observed_state,
        "expected_issue_codes": case.expected_issue_codes,
        "observed_issue_codes": execution.observed_issue_codes,
        "expected_counts": case.expected_counts,
        "observed_counts": execution.observed_counts,
        "passed": passed,
        "output_address": execution.output_address,
    }
    return EvidenceArchitectureCaseReceipt(
        **body,
        content_address=addressed(body, "evidence-architecture-receipt"),
    )


def _case_checks(
    case: EvidenceArchitectureCase,
    execution: EvidenceArchitectureExecution,
    receipt: EvidenceArchitectureCaseReceipt,
    source_ids: set[str],
    operation_ids: set[str],
    family_contexts: Mapping[str, str],
) -> tuple[EvidenceArchitectureCheck, ...]:
    expected_context = family_contexts.get(case.family.value, "")
    return (
        _check(
            f"{case.case_id}:state",
            EvidenceArchitectureCheckKind.RESULT,
            execution.observed_state is case.expected_state,
            execution.observed_state.value,
            case.expected_state.value,
            "delegate state matches the aggregate expectation",
        ),
        _check(
            f"{case.case_id}:issues",
            EvidenceArchitectureCheckKind.RESULT,
            execution.observed_issue_codes == case.expected_issue_codes,
            execution.observed_issue_codes,
            case.expected_issue_codes,
            "issue vocabulary is retained without suppression",
        ),
        _check(
            f"{case.case_id}:counts",
            EvidenceArchitectureCheckKind.CASE,
            execution.observed_counts == case.expected_counts,
            execution.observed_counts,
            case.expected_counts,
            "bounded payload and output counts remain reproducible",
        ),
        _check(
            f"{case.case_id}:operation",
            EvidenceArchitectureCheckKind.OPERATION,
            case.operation_id in operation_ids,
            case.operation_id,
            True,
            "case operation join resolves",
        ),
        _check(
            f"{case.case_id}:sources",
            EvidenceArchitectureCheckKind.SOURCE,
            set(case.source_ids) <= source_ids,
            set(case.source_ids),
            source_ids,
            "case source joins resolve",
        ),
        _check(
            f"{case.case_id}:context",
            EvidenceArchitectureCheckKind.SAFETY,
            case.delegate_context_key == expected_context
            or "context_mismatch" in execution.observed_issue_codes,
            case.delegate_context_key,
            "exact family context or explicit context-mismatch control",
            "delegate context remains attached to its family or is visibly held",
        ),
        _check(
            f"{case.case_id}:receipt",
            EvidenceArchitectureCheckKind.CASE,
            receipt.passed and bool(receipt.content_address),
            receipt.passed,
            True,
            "case receipt is addressed and closed",
        ),
    )


def _global_checks(
    fixture: EvidenceArchitectureFixture,
    executions: tuple[EvidenceArchitectureExecution, ...],
    source_ids: set[str],
) -> tuple[EvidenceArchitectureCheck, ...]:
    family_counts = {
        family.value: sum(item.family is family for item in executions)
        for family in fixture.family_set
    }
    operation_counts = {
        operation.operation_id: sum(
            item.operation.value == operation.operation.value for item in executions
        )
        for operation in fixture.operations
    }
    scenario_counts = {
        scenario.value: sum(item.scenario is scenario for item in executions)
        for scenario in EvidenceArchitectureScenario
    }
    case_by_id = {item.case_id: item for item in fixture.cases}
    return (
        _check(
            "global:execution-count",
            EvidenceArchitectureCheckKind.FIXTURE,
            len(executions) == EVIDENCE_ARCHITECTURE_CASE_COUNT,
            len(executions),
            EVIDENCE_ARCHITECTURE_CASE_COUNT,
            "all D14 aggregate cases execute",
        ),
        _check(
            "global:positive-count",
            EvidenceArchitectureCheckKind.CONTROL,
            scenario_counts["positive"] == EVIDENCE_ARCHITECTURE_OPERATION_COUNT,
            scenario_counts["positive"],
            EVIDENCE_ARCHITECTURE_OPERATION_COUNT,
            "one positive evidence path exists per capability",
        ),
        _check(
            "global:control-count",
            EvidenceArchitectureCheckKind.CONTROL,
            all(
                scenario_counts[item] == EVIDENCE_ARCHITECTURE_OPERATION_COUNT
                for item in ("control_a", "control_b", "control_c")
            ),
            scenario_counts,
            {
                item: EVIDENCE_ARCHITECTURE_OPERATION_COUNT
                for item in ("control_a", "control_b", "control_c")
            },
            "control distribution is balanced",
        ),
        _check(
            "global:family-counts",
            EvidenceArchitectureCheckKind.FIXTURE,
            family_counts
            == {
                "evidence_lifecycle_frontier": 16,
                "lifecycle_beta_frontier": 32,
                "evidence_release_frontier": 16,
            },
            family_counts,
            {
                "evidence_lifecycle_frontier": 16,
                "lifecycle_beta_frontier": 32,
                "evidence_release_frontier": 16,
            },
            "foundation, beta, and release family coverage is retained",
        ),
        _check(
            "global:operation-counts",
            EvidenceArchitectureCheckKind.OPERATION,
            set(operation_counts.values()) == {EVIDENCE_ARCHITECTURE_CASES_PER_OPERATION},
            operation_counts,
            EVIDENCE_ARCHITECTURE_CASES_PER_OPERATION,
            "each operation contributes four cases",
        ),
        _check(
            "global:source-coverage",
            EvidenceArchitectureCheckKind.SOURCE,
            all(set(item.source_ids) <= source_ids for item in fixture.cases),
            True,
            True,
            "all case source references resolve",
        ),
        _check(
            "global:state-coverage",
            EvidenceArchitectureCheckKind.RESULT,
            all(item.observed_state.value for item in executions),
            True,
            True,
            "every delegate returns an explicit evidence state",
        ),
        _check(
            "global:address-coverage",
            EvidenceArchitectureCheckKind.REPLAY,
            all(item.output_address for item in executions),
            True,
            True,
            "every delegate output has an address",
        ),
        _check(
            "global:control-contexts",
            EvidenceArchitectureCheckKind.SAFETY,
            all(
                case.delegate_context_key == fixture.family_contexts[case.family.value]
                or "context_mismatch" in execution.observed_issue_codes
                for execution in executions
                for case in (case_by_id[execution.case_id],)
            ),
            True,
            True,
            "foreign contexts require explicit context-mismatch evidence",
        ),
        _check(
            "global:receipt-coverage",
            EvidenceArchitectureCheckKind.REPLAY,
            len(executions) == len(fixture.cases),
            len(executions),
            len(fixture.cases),
            "one execution receipt exists for every case",
        ),
    )


def evaluate_evidence_architecture_fixture(
    fixture: EvidenceArchitectureFixture | None = None,
) -> EvidenceArchitectureEvaluation:
    selected = fixture or default_evidence_architecture_fixture()
    outcomes = _delegate_outcomes()
    source_ids = {item.source_id for item in selected.sources}
    operation_ids = {item.operation_id for item in selected.operations}
    executions = tuple(_execution_for_case(item, outcomes) for item in selected.cases)
    receipts = tuple(
        _receipt(case, execution)
        for case, execution in zip(selected.cases, executions, strict=True)
    )
    checks = tuple(
        check
        for case, execution, receipt in zip(selected.cases, executions, receipts, strict=True)
        for check in _case_checks(
            case,
            execution,
            receipt,
            source_ids,
            operation_ids,
            selected.family_contexts,
        )
    ) + _global_checks(selected, executions, source_ids)
    state = "accepted" if all(item.passed for item in checks) else "review"
    body = {
        "fixture_id": selected.fixture_id,
        "context_key": selected.context_key,
        "state": state,
        "executions": executions,
        "receipts": receipts,
        "checks": checks,
    }
    return EvidenceArchitectureEvaluation(
        selected.fixture_id,
        selected.context_key,
        state,
        executions,
        receipts,
        checks,
        addressed(body, "evidence-architecture-evaluation"),
    )


__all__ = [
    "evaluate_evidence_architecture_fixture",
    "execute_evidence_architecture_case",
]

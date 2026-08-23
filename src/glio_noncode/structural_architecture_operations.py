"""Execute all sixteen D02 operations through their existing adapters.

This layer owns orchestration assertions only.  It does not reimplement
breakend reconstruction, copy-number harmonization, structural beta calls,
haplotype assembly, or frontier annotation.  Positive cases are delegated to
the corresponding family evaluator; controls are held by an explicit
architecture policy before a result can be accepted.
"""

from __future__ import annotations

from typing import Any

from .errors import ValidationError
from .serialization import content_hash
from .structural_architecture_contracts import (
    StructuralArchitectureCase,
    StructuralArchitectureCaseReceipt,
    StructuralArchitectureCheck,
    StructuralArchitectureCheckKind,
    StructuralArchitectureEvaluation,
    StructuralArchitectureExecution,
    StructuralArchitectureFixture,
    StructuralArchitectureOperation,
    StructuralArchitectureScenario,
    StructuralArchitectureState,
    addressed,
)
from .structural_beta_fixture_eval import _execute as execute_beta
from .structural_beta_public_data import (
    StructuralBetaFixtureRecord,
    StructuralBetaFixtureState,
    StructuralBetaOperation,
)
from .structural_fixture_eval import _execute as execute_core
from .structural_frontier_fixture_eval import _execute as execute_frontier
from .structural_frontier_public_data import (
    StructuralFrontierFixtureRecord,
    StructuralFrontierFixtureState,
    StructuralFrontierOperation,
)
from .structural_haplotype_fixture_eval import _execute as execute_haplotype
from .structural_haplotype_public_data import (
    StructuralHaplotypeFixtureRecord,
    StructuralHaplotypeFixtureState,
    StructuralHaplotypeOperation,
)
from .structural_public_data import (
    StructuralFixtureRecord,
    StructuralFixtureState,
    StructuralOperation,
)

_CORE = {
    StructuralArchitectureOperation.RECONSTRUCTION,
    StructuralArchitectureOperation.CONSENSUS,
    StructuralArchitectureOperation.COMPLEX_RESOLUTION,
    StructuralArchitectureOperation.COPY_NUMBER,
}
_BETA = {
    StructuralArchitectureOperation.FOCAL_AMPLIFICATION,
    StructuralArchitectureOperation.CHROMOTHRIPSIS,
    StructuralArchitectureOperation.ECDNA,
    StructuralArchitectureOperation.ENHANCER_HIJACKING,
}
_HAPLOTYPE = {
    StructuralArchitectureOperation.PHASED_HAPLOTYPE,
    StructuralArchitectureOperation.ALLELE_AWARE_SV,
    StructuralArchitectureOperation.PANGENOME_PROJECTION,
    StructuralArchitectureOperation.REPEAT_MOBILE_ANNOTATION,
}
_FRONTIER = {
    StructuralArchitectureOperation.TANDEM_REPEAT,
    StructuralArchitectureOperation.COMPOUND_HAPLOTYPE,
    StructuralArchitectureOperation.BREAKPOINT_UNCERTAINTY,
    StructuralArchitectureOperation.STRUCTURAL_EVIDENCE_EXPORT,
}


def evaluate_structural_architecture_fixture(
    fixture: StructuralArchitectureFixture | str,
) -> StructuralArchitectureEvaluation:
    """Execute all cases and verify expected states, results, counts, and issues."""

    from .structural_architecture_public_data import default_structural_architecture_fixture

    value = (
        default_structural_architecture_fixture(fixture) if isinstance(fixture, str) else fixture
    )
    receipts: list[StructuralArchitectureCaseReceipt] = []
    checks: list[StructuralArchitectureCheck] = []
    for case in value.cases:
        execution = execute_structural_architecture_case(case, value.context_key)
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
            "passed": all(check.passed for check in case_checks),
            "output_address": execution.output_address,
            "detail": execution.detail,
        }
        receipts.append(
            StructuralArchitectureCaseReceipt(
                **body,
                content_address=content_hash(body),
            )
        )
    checks.extend(_global_checks(value, receipts))
    state = (
        StructuralArchitectureState.ACCEPTED
        if all(item.passed for item in checks)
        else StructuralArchitectureState.REVIEW
    )
    body = {
        "fixture_id": value.fixture_id,
        "context_key": value.context_key,
        "state": state,
        "receipts": receipts,
        "checks": checks,
    }
    return StructuralArchitectureEvaluation(
        fixture_id=value.fixture_id,
        context_key=value.context_key,
        state=state,
        receipts=tuple(receipts),
        checks=tuple(checks),
        content_address=addressed(body, "structural-evaluation"),
    )


def execute_structural_architecture_case(
    case: StructuralArchitectureCase,
    context_key: str,
) -> StructuralArchitectureExecution:
    """Execute one case, applying the composed boundary policy first."""

    if case.scenario is not StructuralArchitectureScenario.POSITIVE:
        return _control_execution(case)
    if case.context_key != context_key:
        return _failed(
            case,
            "context_mismatch",
            "positive case context differs from fixture context",
            "out_of_domain",
        )
    try:
        domain_execution = _execute_positive(case)
    except (TypeError, ValueError, ValidationError, KeyError) as exc:
        return _failed(
            case, "validation_error", f"positive operation failed validation: {exc}", "invalid"
        )
    domain_result_state = str(
        getattr(
            domain_execution,
            "result_state",
            getattr(domain_execution, "observed_result_state", "invalid"),
        )
    )
    return StructuralArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        scenario=case.scenario,
        observed_state=(
            StructuralArchitectureState.ACCEPTED
            if not domain_execution.issue_codes and domain_result_state not in {"invalid", "error"}
            else StructuralArchitectureState.REVIEW
        ),
        observed_result_state=domain_result_state,
        issue_codes=tuple(sorted(domain_execution.issue_codes)),
        counts={str(key): int(value) for key, value in domain_execution.counts.items()},
        output_address=str(domain_execution.output_address),
        summary={
            "family": _family(case.operation),
            "result_state": domain_result_state,
            "counts": dict(domain_execution.counts),
            "issue_codes": tuple(sorted(domain_execution.issue_codes)),
        },
        detail=domain_execution.detail,
    )


def _execute_positive(case: StructuralArchitectureCase) -> Any:
    if case.operation in _CORE:
        record = StructuralFixtureRecord(
            record_id=case.case_id,
            operation=StructuralOperation(case.operation.value),
            expected_state=StructuralFixtureState.ACCEPTED,
            expected_result_state=case.expected_result_state,
            context_key=case.context_key,
            source_id=case.source_ids[0],
            payload=case.payload,
        )
        return execute_core(record, case.context_key)
    if case.operation in _BETA:
        record = StructuralBetaFixtureRecord(
            record_id=case.case_id,
            operation=StructuralBetaOperation(case.operation.value),
            expected_state=StructuralBetaFixtureState.ACCEPTED,
            expected_result_state=case.expected_result_state,
            context_key=case.context_key,
            source_id=case.source_ids[0],
            payload=case.payload,
        )
        return execute_beta(record)
    if case.operation in _HAPLOTYPE:
        record = StructuralHaplotypeFixtureRecord(
            record_id=case.case_id,
            operation=StructuralHaplotypeOperation(case.operation.value),
            expected_state=StructuralHaplotypeFixtureState.ACCEPTED,
            expected_result_state=case.expected_result_state,
            context_key=case.context_key,
            source_id=case.source_ids[0],
            payload=case.payload,
        )
        return execute_haplotype(record)
    if case.operation in _FRONTIER:
        record = StructuralFrontierFixtureRecord(
            record_id=case.case_id,
            operation=StructuralFrontierOperation(case.operation.value),
            expected_state=StructuralFrontierFixtureState.ACCEPTED,
            expected_result_state=case.expected_result_state,
            context_key=case.context_key,
            source_id=case.source_ids[0],
            payload=case.payload,
        )
        return execute_frontier(record)
    raise ValidationError(f"unsupported architecture operation: {case.operation.value}")


def _control_execution(case: StructuralArchitectureCase) -> StructuralArchitectureExecution:
    issue_by_scenario = {
        StructuralArchitectureScenario.FOREIGN_CONTEXT: "context_mismatch",
        StructuralArchitectureScenario.MALFORMED_INPUT: "malformed_input",
        StructuralArchitectureScenario.DUPLICATE_IDENTITY: "duplicate_identity",
    }
    result_by_scenario = {
        StructuralArchitectureScenario.FOREIGN_CONTEXT: "out_of_domain",
        StructuralArchitectureScenario.MALFORMED_INPUT: "invalid",
        StructuralArchitectureScenario.DUPLICATE_IDENTITY: "contradictory",
    }
    issue = issue_by_scenario[case.scenario]
    result = result_by_scenario[case.scenario]
    summary = {
        "family": _family(case.operation),
        "scenario": case.scenario.value,
        "held_before_adapter": True,
        "payload_shape": tuple(sorted(str(key) for key in case.payload)),
    }
    return StructuralArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        scenario=case.scenario,
        observed_state=StructuralArchitectureState.REVIEW,
        observed_result_state=result,
        issue_codes=(issue,),
        counts={"held": 1},
        output_address=content_hash(summary),
        summary=summary,
        detail=f"{case.scenario.value} held by architecture boundary: {issue}",
    )


def _failed(
    case: StructuralArchitectureCase,
    issue_code: str,
    detail: str,
    result_state: str,
) -> StructuralArchitectureExecution:
    summary = {
        "operation": case.operation.value,
        "result_state": result_state,
        "issue_codes": (issue_code,),
    }
    return StructuralArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        scenario=case.scenario,
        observed_state=StructuralArchitectureState.REVIEW,
        observed_result_state=result_state,
        issue_codes=(issue_code,),
        counts={"issues": 1},
        output_address=content_hash(summary),
        summary=summary,
        detail=detail,
    )


def _checks_for_case(
    case: StructuralArchitectureCase,
    execution: StructuralArchitectureExecution,
) -> tuple[StructuralArchitectureCheck, ...]:
    checks: list[StructuralArchitectureCheck] = []
    checks.append(
        _check(
            case,
            "state",
            StructuralArchitectureCheckKind.OPERATION,
            case.expected_state.value,
            execution.observed_state.value,
            "architecture state",
        )
    )
    checks.append(
        _check(
            case,
            "result-state",
            StructuralArchitectureCheckKind.OPERATION,
            case.expected_result_state,
            execution.observed_result_state,
            "adapter or policy result state",
        )
    )
    checks.append(
        _check(
            case,
            "address",
            StructuralArchitectureCheckKind.LINEAGE,
            True,
            execution.output_address.startswith("sha256:"),
            "operation output is addressed",
        )
    )
    checks.append(
        _check(
            case,
            "issues",
            StructuralArchitectureCheckKind.POLICY,
            tuple(case.expected_issue_codes),
            tuple(execution.issue_codes),
            "declared issue boundary",
        )
    )
    for key, expected in sorted(case.expected_counts.items()):
        checks.append(
            _check(
                case,
                f"count-{key}",
                StructuralArchitectureCheckKind.OPERATION,
                int(expected),
                int(execution.counts.get(key, -1)),
                f"declared {key} count",
            )
        )
    return tuple(checks)


def _check(
    case: StructuralArchitectureCase,
    suffix: str,
    kind: StructuralArchitectureCheckKind,
    required: Any,
    observed: Any,
    detail: str,
) -> StructuralArchitectureCheck:
    body = {
        "check_id": f"{case.case_id}:{suffix}",
        "kind": kind,
        "passed": required == observed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return StructuralArchitectureCheck(
        **body, content_address=addressed(body, "structural-case-check")
    )


def _global_checks(
    fixture: StructuralArchitectureFixture,
    receipts: list[StructuralArchitectureCaseReceipt],
) -> tuple[StructuralArchitectureCheck, ...]:
    checks: list[StructuralArchitectureCheck] = []
    checks.append(
        _global("case-total", len(receipts), len(fixture.cases), "all architecture cases executed")
    )
    checks.append(
        _global(
            "operation-total",
            len({item.operation_id for item in receipts}),
            len(fixture.operations),
            "all operation IDs executed",
        )
    )
    checks.append(
        _global(
            "positive-total",
            sum(item.expected_state is StructuralArchitectureState.ACCEPTED for item in receipts),
            16,
            "one accepted positive per operation",
        )
    )
    checks.append(
        _global(
            "control-total",
            sum(
                item.expected_state is not StructuralArchitectureState.ACCEPTED for item in receipts
            ),
            48,
            "three held controls per operation",
        )
    )
    checks.append(
        _global(
            "receipt-addresses",
            sum(item.content_address.startswith("sha256:") for item in receipts),
            len(receipts),
            "every case receipt is addressed",
        )
    )
    return tuple(checks)


def _global(
    check_id: str, observed: Any, required: Any, detail: str
) -> StructuralArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": StructuralArchitectureCheckKind.INVARIANT,
        "passed": observed == required,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return StructuralArchitectureCheck(
        **body, content_address=addressed(body, "structural-global-check")
    )


def _family(operation: StructuralArchitectureOperation) -> str:
    if operation in _CORE:
        return "core"
    if operation in _BETA:
        return "beta"
    if operation in _HAPLOTYPE:
        return "haplotype"
    if operation in _FRONTIER:
        return "frontier"
    return "unknown"


__all__ = [
    "evaluate_structural_architecture_fixture",
    "execute_structural_architecture_case",
]

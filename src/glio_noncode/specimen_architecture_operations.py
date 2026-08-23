"""Compose the sixteen specimen operations without duplicating their science.

The adapter map is intentionally explicit.  Each positive case crosses one
typed plane, while each control is handled by the architecture boundary and
never reaches a scientific adapter with an invalid contract.
"""

from __future__ import annotations

from typing import Any

from .errors import ValidationError
from .serialization import content_hash
from .specimen_architecture_contracts import (
    SpecimenArchitectureCase,
    SpecimenArchitectureCaseReceipt,
    SpecimenArchitectureCheck,
    SpecimenArchitectureCheckKind,
    SpecimenArchitectureEvaluation,
    SpecimenArchitectureExecution,
    SpecimenArchitectureFixture,
    SpecimenArchitectureOperation,
    SpecimenArchitectureScenario,
    SpecimenArchitectureState,
    addressed,
)
from .specimen_beta_frontier_fixture_eval import SpecimenBetaFrontierFixtureEvaluator
from .specimen_beta_frontier_public_data import (
    SpecimenBetaFrontierFixtureRecord,
    SpecimenBetaFrontierFixtureState,
    SpecimenBetaFrontierOperation,
)
from .specimen_frontier_fixture_eval import _execute as execute_core
from .specimen_frontier_public_data import (
    SpecimenFrontierFixtureRecord,
    SpecimenFrontierFixtureState,
    SpecimenFrontierOperation,
)
from .specimen_lineage_fixture_eval import SpecimenLineageFixtureEvaluator
from .specimen_lineage_public_data import (
    SpecimenLineageFixtureRecord,
    SpecimenLineageFixtureState,
    SpecimenLineageOperation,
)
from .specimen_preanalytic_fixture_eval import _evaluate_record as evaluate_preanalytic_record
from .specimen_preanalytic_public_data import (
    SpecimenPreanalyticFixtureCatalog,
    SpecimenPreanalyticRecord,
)

_CORE = {
    SpecimenArchitectureOperation.ONTOLOGY_MAPPING,
    SpecimenArchitectureOperation.MATCHED_NORMAL,
    SpecimenArchitectureOperation.PURITY_PLOIDY,
    SpecimenArchitectureOperation.SAMPLE_INTEGRITY,
}
_BETA = {
    SpecimenArchitectureOperation.ORIGIN,
    SpecimenArchitectureOperation.MOSAICISM,
    SpecimenArchitectureOperation.CANCER_CELL_FRACTION,
    SpecimenArchitectureOperation.SUBCLONE,
}
_LINEAGE = {
    SpecimenArchitectureOperation.REGION_LINEAGE,
    SpecimenArchitectureOperation.LONGITUDINAL_LINKING,
    SpecimenArchitectureOperation.PHASE_MAPPING,
    SpecimenArchitectureOperation.TREATMENT_CONTEXT,
}
_PREANALYTIC = {
    SpecimenArchitectureOperation.PREANALYTIC_QUALITY,
    SpecimenArchitectureOperation.ASSAY_LINEAGE,
    SpecimenArchitectureOperation.IDENTITY_ADJUDICATION,
    SpecimenArchitectureOperation.CONTEXT_ENVELOPE,
}


def evaluate_specimen_architecture_fixture(
    fixture: SpecimenArchitectureFixture | str,
) -> SpecimenArchitectureEvaluation:
    """Execute every positive and policy control with explicit receipts."""

    from .specimen_architecture_public_data import default_specimen_architecture_fixture

    value = default_specimen_architecture_fixture(fixture) if isinstance(fixture, str) else fixture
    receipts: list[SpecimenArchitectureCaseReceipt] = []
    checks: list[SpecimenArchitectureCheck] = []
    for case in value.cases:
        execution = execute_specimen_architecture_case(case, value.context_key)
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
            "detail": execution.detail,
        }
        receipts.append(
            SpecimenArchitectureCaseReceipt(
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
        SpecimenArchitectureState.ACCEPTED
        if all(item.passed for item in checks)
        else SpecimenArchitectureState.REVIEW
    )
    body = {
        "fixture_id": value.fixture_id,
        "context_key": value.context_key,
        "state": state,
        "receipts": receipts,
        "checks": checks,
    }
    return SpecimenArchitectureEvaluation(
        fixture_id=value.fixture_id,
        context_key=value.context_key,
        state=state,
        receipts=tuple(receipts),
        checks=tuple(checks),
        content_address=addressed(body, "specimen-evaluation"),
    )


def execute_specimen_architecture_case(
    case: SpecimenArchitectureCase,
    context_key: str,
) -> SpecimenArchitectureExecution:
    """Apply boundary policy, then dispatch positive cases to one adapter."""

    if case.scenario is not SpecimenArchitectureScenario.POSITIVE:
        return _control_execution(case)
    if case.context_key != context_key:
        return _failed(case, "context_mismatch", "positive case context differs", "out_of_domain")
    try:
        domain_execution = _execute_positive(case)
    except (TypeError, ValueError, ValidationError, KeyError) as exc:
        return _failed(
            case, "validation_error", f"positive adapter validation failed: {exc}", "invalid"
        )
    observed_result_state = str(
        getattr(
            domain_execution,
            "observed_result_state",
            getattr(domain_execution, "result_state", "invalid"),
        )
    )
    issue_codes = tuple(sorted(str(item) for item in getattr(domain_execution, "issue_codes", ())))
    counts = {
        str(key): int(value) for key, value in getattr(domain_execution, "counts", {}).items()
    }
    observed_state = (
        SpecimenArchitectureState.ACCEPTED
        if not issue_codes and observed_result_state not in {"invalid", "error"}
        else SpecimenArchitectureState.REVIEW
    )
    return SpecimenArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        scenario=case.scenario,
        observed_state=observed_state,
        observed_result_state=observed_result_state,
        issue_codes=issue_codes,
        counts=counts,
        output_address=str(domain_execution.output_address),
        summary={
            "adapter_family": _family(case.operation),
            "result_state": observed_result_state,
            "counts": counts,
            "issue_codes": issue_codes,
        },
        detail=str(getattr(domain_execution, "detail", "typed adapter execution complete")),
    )


def _execute_positive(case: SpecimenArchitectureCase) -> Any:
    if case.operation in _CORE:
        parameters = dict(case.parameters)
        parameters["expected_counts"] = dict(case.expected_counts)
        parameters["required_issue_codes"] = list(case.expected_issue_codes)
        record = SpecimenFrontierFixtureRecord(
            record_id=case.case_id,
            operation=SpecimenFrontierOperation(case.operation.value),
            source_id=case.source_ids[0],
            context_key=case.context_key,
            expected_state=SpecimenFrontierFixtureState.ACCEPTED,
            expected_result_state=case.expected_result_state,
            payload=case.payload,
            parameters=parameters,
        )
        return execute_core(record)
    if case.operation in _BETA:
        record = SpecimenBetaFrontierFixtureRecord(
            record_id=case.case_id,
            operation=SpecimenBetaFrontierOperation(case.operation.value),
            source_ids=case.source_ids,
            context_key=case.context_key,
            expected_fixture_state=SpecimenBetaFrontierFixtureState.ACCEPTED,
            expected_result_state=case.expected_result_state,
            payload=case.payload,
            parameters=case.parameters,
            expected_issue_codes=case.expected_issue_codes,
            expected_counts=case.expected_counts,
        )
        return SpecimenBetaFrontierFixtureEvaluator._execute(record)
    if case.operation in _LINEAGE:
        record = SpecimenLineageFixtureRecord(
            record_id=case.case_id,
            operation=SpecimenLineageOperation(case.operation.value),
            source_ids=case.source_ids,
            context_key=case.context_key,
            expected_fixture_state=SpecimenLineageFixtureState.ACCEPTED,
            expected_result_state=case.expected_result_state,
            payload=case.payload,
            parameters=case.parameters,
            expected_issue_codes=case.expected_issue_codes,
            expected_counts=case.expected_counts,
        )
        return SpecimenLineageFixtureEvaluator._execute(record)
    if case.operation in _PREANALYTIC:
        record = SpecimenPreanalyticRecord.from_mapping(
            {
                "record_id": case.case_id,
                "operation": case.operation.value,
                "role": "positive",
                "expected_state": "accepted",
                "context_key": case.context_key,
                "source_ids": list(case.source_ids),
                "expected_issue_codes": list(case.expected_issue_codes),
                "payload": dict(case.payload),
            }
        )
        catalog = SpecimenPreanalyticFixtureCatalog.from_file(
            _repository_preanalytic_fixture_path()
        )
        receipt, checks = evaluate_preanalytic_record(record, catalog)
        return _PreanalyticExecutionAdapter(receipt, checks)
    raise ValidationError(f"unsupported specimen architecture operation: {case.operation.value}")


class _PreanalyticExecutionAdapter:
    """Small common projection for the preanalytic evaluator's receipt type."""

    def __init__(self, receipt: Any, checks: tuple[Any, ...]) -> None:
        self.observed_result_state = (
            "supported" if receipt.observed_state in {"accepted", "published"} else "review"
        )
        self.issue_codes = tuple(receipt.issue_codes)
        self.counts: dict[str, int] = {}
        self.output_address = receipt.output_address
        self.detail = f"preanalytic checks={len(checks)} passed={receipt.passed}"


def _control_execution(case: SpecimenArchitectureCase) -> SpecimenArchitectureExecution:
    issue_by_scenario = {
        SpecimenArchitectureScenario.FOREIGN_CONTEXT: "context_mismatch",
        SpecimenArchitectureScenario.MALFORMED_INPUT: "malformed_input",
        SpecimenArchitectureScenario.IDENTITY_CONFLICT: "identity_conflict",
    }
    result_by_scenario = {
        SpecimenArchitectureScenario.FOREIGN_CONTEXT: "out_of_domain",
        SpecimenArchitectureScenario.MALFORMED_INPUT: "invalid",
        SpecimenArchitectureScenario.IDENTITY_CONFLICT: "contradictory",
    }
    issue = issue_by_scenario[case.scenario]
    result = result_by_scenario[case.scenario]
    summary = {
        "adapter_family": _family(case.operation),
        "scenario": case.scenario.value,
        "held_before_adapter": True,
        "aggregate_only": bool(case.payload.get("aggregate_only", False)),
    }
    return SpecimenArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        scenario=case.scenario,
        observed_state=SpecimenArchitectureState.REVIEW,
        observed_result_state=result,
        issue_codes=(issue,),
        counts={},
        output_address=content_hash({"case_id": case.case_id, "summary": summary}),
        summary=summary,
        detail="control held at the architecture boundary before typed dispatch",
    )


def _failed(
    case: SpecimenArchitectureCase, issue: str, detail: str, result: str
) -> SpecimenArchitectureExecution:
    return SpecimenArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        scenario=case.scenario,
        observed_state=SpecimenArchitectureState.REVIEW,
        observed_result_state=result,
        issue_codes=(issue,),
        counts={},
        output_address=content_hash({"case_id": case.case_id, "issue": issue}),
        summary={"failure": issue},
        detail=detail,
    )


def _checks_for_case(
    case: SpecimenArchitectureCase,
    execution: SpecimenArchitectureExecution,
) -> tuple[SpecimenArchitectureCheck, ...]:
    return tuple(
        _check(
            f"{case.case_id}:{name}",
            observed == expected,
            observed,
            expected,
            detail,
        )
        for name, observed, expected, detail in (
            (
                "state",
                execution.observed_state,
                case.expected_state,
                "state follows the case contract",
            ),
            (
                "result",
                execution.observed_result_state,
                case.expected_result_state,
                "result state is deterministic",
            ),
            (
                "issues",
                execution.issue_codes,
                tuple(sorted(case.expected_issue_codes)),
                "issue codes are retained",
            ),
            ("counts", dict(execution.counts), dict(case.expected_counts), "bounded counts match"),
            (
                "address",
                execution.output_address.startswith("sha256:"),
                True,
                "execution is content-addressed",
            ),
        )
    )


def _global_checks(
    fixture: SpecimenArchitectureFixture,
    receipts: list[SpecimenArchitectureCaseReceipt],
) -> tuple[SpecimenArchitectureCheck, ...]:
    return (
        _check(
            "global-receipt-count",
            len(receipts) == len(fixture.cases),
            len(receipts),
            len(fixture.cases),
            "one receipt per case",
        ),
        _check(
            "global-receipt-identity",
            len({item.case_id for item in receipts}) == len(receipts),
            len({item.case_id for item in receipts}),
            len(receipts),
            "receipt IDs are unique",
        ),
        _check(
            "global-positive-count",
            sum(item.expected_state is SpecimenArchitectureState.ACCEPTED for item in receipts)
            == 16,
            sum(item.expected_state is SpecimenArchitectureState.ACCEPTED for item in receipts),
            16,
            "sixteen positive cases executed",
        ),
        _check(
            "global-control-count",
            sum(item.expected_state is SpecimenArchitectureState.REVIEW for item in receipts) == 48,
            sum(item.expected_state is SpecimenArchitectureState.REVIEW for item in receipts),
            48,
            "forty-eight controls remain conservative",
        ),
        _check(
            "global-all-case-checks",
            all(item.passed for item in receipts),
            all(item.passed for item in receipts),
            True,
            "all cases satisfy their typed boundary contract",
        ),
    )


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> SpecimenArchitectureCheck:
    kind = (
        SpecimenArchitectureCheckKind.OPERATION
        if ":" in check_id
        else SpecimenArchitectureCheckKind.INVARIANT
    )
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return SpecimenArchitectureCheck(
        check_id=check_id,
        kind=kind,
        passed=passed,
        observed=observed,
        required=required,
        detail=detail,
        content_address=addressed(body, "specimen-operation-check"),
    )


def _family(operation: SpecimenArchitectureOperation) -> str:
    if operation in _CORE:
        return "core"
    if operation in _BETA:
        return "beta"
    if operation in _LINEAGE:
        return "lineage"
    if operation in _PREANALYTIC:
        return "preanalytic"
    return "unknown"


def _repository_preanalytic_fixture_path() -> str:
    from pathlib import Path

    return str(
        Path(__file__).resolve().parents[2]
        / "examples"
        / "specimen-preanalytic-public-aggregate.json"
    )


__all__ = [
    "execute_specimen_architecture_case",
    "evaluate_specimen_architecture_fixture",
]

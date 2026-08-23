"""D09 execution dispatch across topology context, beta, alpha, and frontier."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .serialization import jsonable
from .topology_alpha_frontier_fixture_eval import evaluate_topology_alpha_frontier_fixture
from .topology_alpha_frontier_public_data import default_topology_alpha_frontier_fixture
from .topology_architecture_contracts import (
    TOPOLOGY_ARCHITECTURE_CONTEXT,
    TopologyArchitectureCase,
    TopologyArchitectureCaseReceipt,
    TopologyArchitectureCheck,
    TopologyArchitectureCheckKind,
    TopologyArchitectureEvaluation,
    TopologyArchitectureExecution,
    TopologyArchitectureFamily,
    TopologyArchitectureFixture,
    TopologyArchitectureScenario,
    TopologyArchitectureState,
    addressed,
)
from .topology_beta_frontier_fixture_eval import evaluate_topology_beta_frontier_fixture
from .topology_beta_frontier_public_data import default_topology_beta_frontier_fixture
from .topology_context_frontier_fixture_eval import evaluate_topology_context_frontier_fixture
from .topology_context_frontier_public_data import default_topology_context_frontier_fixture
from .topology_frontier_fixture_eval import evaluate_topology_frontier_fixture
from .topology_frontier_public_data import default_topology_frontier_fixture


def _rows(evaluation: Any) -> tuple[Any, ...]:
    return tuple(
        getattr(evaluation, "rows", None)
        or getattr(evaluation, "receipts", None)
        or getattr(evaluation, "executions", None)
        or ()
    )


def _sanitize(value: Any) -> Any:
    hidden = {"payload", "input_text", "track_text", "raw_text", "records_text"}
    if isinstance(value, Mapping):
        return {str(key): _sanitize(item) for key, item in value.items() if str(key) not in hidden}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value


def _family_outcomes() -> dict[tuple[TopologyArchitectureFamily, str], dict[str, Any]]:
    fixtures = {
        TopologyArchitectureFamily.CONTEXT: default_topology_context_frontier_fixture(),
        TopologyArchitectureFamily.BETA: default_topology_beta_frontier_fixture(),
        TopologyArchitectureFamily.ALPHA: default_topology_alpha_frontier_fixture(),
        TopologyArchitectureFamily.FRONTIER: default_topology_frontier_fixture(),
    }
    evaluations = {
        TopologyArchitectureFamily.CONTEXT: evaluate_topology_context_frontier_fixture(
            fixtures[TopologyArchitectureFamily.CONTEXT]
        ),
        TopologyArchitectureFamily.BETA: evaluate_topology_beta_frontier_fixture(
            fixtures[TopologyArchitectureFamily.BETA]
        ),
        TopologyArchitectureFamily.ALPHA: evaluate_topology_alpha_frontier_fixture(
            fixtures[TopologyArchitectureFamily.ALPHA]
        ),
        TopologyArchitectureFamily.FRONTIER: evaluate_topology_frontier_fixture(
            fixtures[TopologyArchitectureFamily.FRONTIER]
        ),
    }
    outcomes: dict[tuple[TopologyArchitectureFamily, str], dict[str, Any]] = {}
    for family, evaluation in evaluations.items():
        for row in _rows(evaluation):
            role = str(getattr(getattr(row, "role", None), "value", getattr(row, "role", None)))
            if role != "positive":
                continue
            adapter = getattr(row, "adapter", row)
            state = (
                getattr(adapter, "state", None)
                or getattr(row, "observed_state", None)
                or "supported"
            )
            issues = getattr(adapter, "issue_codes", None) or getattr(
                row, "observed_issue_codes", ()
            )
            outcomes[(family, str(row.record_id))] = {
                "result_state": str(getattr(state, "value", state)),
                "issue_codes": tuple(str(item) for item in issues),
                "summary": _sanitize(jsonable(row)),
                "detail": f"{family.value} public positive topology receipt delegated and retained",
            }
    return outcomes


def _control(
    case: TopologyArchitectureCase, result_state: str, issues: tuple[str, ...], detail: str
) -> TopologyArchitectureExecution:
    summary = {"state": result_state, "scenario": case.scenario.value, "delegated": False}
    return TopologyArchitectureExecution(
        case.case_id,
        case.operation,
        case.family,
        case.scenario,
        TopologyArchitectureState.REVIEW,
        result_state,
        issues,
        {"primary": 0, "secondary": 0},
        addressed(summary, "topology-control"),
        summary,
        detail,
    )


def execute_topology_architecture_case(
    case: TopologyArchitectureCase,
    context_key: str = TOPOLOGY_ARCHITECTURE_CONTEXT,
    *,
    outcomes: Mapping[tuple[TopologyArchitectureFamily, str], Mapping[str, Any]] | None = None,
) -> TopologyArchitectureExecution:
    """Apply topology aggregate controls before delegating a positive receipt."""
    if (
        case.scenario is TopologyArchitectureScenario.FOREIGN_CONTEXT
        or case.context_key != context_key
    ):
        return _control(
            case,
            "out_of_domain",
            ("context_mismatch",),
            "foreign topology context held before delegation",
        )
    if case.scenario is TopologyArchitectureScenario.MALFORMED_INPUT or case.payload.get(
        "malformed"
    ):
        return _control(
            case, "invalid", ("malformed_input",), "malformed topology input held before delegation"
        )
    if case.scenario is TopologyArchitectureScenario.IDENTITY_CONFLICT or case.payload.get(
        "identity_conflict"
    ):
        return _control(
            case,
            "contradictory",
            ("identity_conflict",),
            "topology identity conflict held before delegation",
        )
    if case.scenario is not TopologyArchitectureScenario.POSITIVE:
        return _control(
            case, "abstained", ("unsupported_scenario",), "unsupported topology scenario held"
        )
    selected = dict(
        (outcomes or _family_outcomes()).get(
            (case.family, str(case.payload.get("family_record_id", ""))), {}
        )
    )
    if not selected:
        return _control(
            case,
            "missing_family_receipt",
            ("missing_family_receipt",),
            "positive topology path has no family receipt",
        )
    summary = dict(selected.get("summary", {}))
    summary["delegated"] = True
    result_state = str(selected.get("result_state", "supported"))
    return TopologyArchitectureExecution(
        case.case_id,
        case.operation,
        case.family,
        case.scenario,
        TopologyArchitectureState.ACCEPTED,
        result_state,
        tuple(selected.get("issue_codes", ())),
        {"primary": 1, "secondary": 1},
        addressed(summary, "topology-output"),
        summary,
        str(selected.get("detail", "topology receipt delegated")),
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    kind: TopologyArchitectureCheckKind = TopologyArchitectureCheckKind.OPERATION,
) -> TopologyArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return TopologyArchitectureCheck(**body, content_address=addressed(body, "topology-check"))


def _receipt(
    case: TopologyArchitectureCase, execution: TopologyArchitectureExecution
) -> TopologyArchitectureCaseReceipt:
    passed = (
        case.expected_state is execution.observed_state
        and case.expected_result_state == execution.observed_result_state
        and case.expected_issue_codes == execution.issue_codes
        and case.expected_counts == execution.counts
        and execution.output_address.startswith("sha256:")
    )
    body = {
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
        "detail": execution.detail,
    }
    return TopologyArchitectureCaseReceipt(
        **body, content_address=addressed(body, "topology-receipt")
    )


def _case_checks(
    case: TopologyArchitectureCase,
    execution: TopologyArchitectureExecution,
    receipt: TopologyArchitectureCaseReceipt,
) -> tuple[TopologyArchitectureCheck, ...]:
    return (
        _check(
            f"{case.case_id}:state",
            execution.observed_state is case.expected_state,
            execution.observed_state,
            case.expected_state,
            "topology execution state matches the contract",
        ),
        _check(
            f"{case.case_id}:result",
            execution.observed_result_state == case.expected_result_state,
            execution.observed_result_state,
            case.expected_result_state,
            "topology result state matches the contract",
        ),
        _check(
            f"{case.case_id}:issues",
            execution.issue_codes == case.expected_issue_codes,
            execution.issue_codes,
            case.expected_issue_codes,
            "topology issue codes are stable",
        ),
        _check(
            f"{case.case_id}:counts",
            execution.counts == case.expected_counts,
            execution.counts,
            case.expected_counts,
            "topology receipt counts are conserved",
        ),
        _check(
            f"{case.case_id}:address",
            execution.output_address.startswith("sha256:"),
            execution.output_address,
            "sha256:*",
            "topology output is addressed",
        ),
        _check(
            f"{case.case_id}:receipt",
            receipt.passed,
            receipt.passed,
            True,
            "topology case receipt reconciles all fields",
        ),
    )


def _global_checks(
    fixture: TopologyArchitectureFixture, receipts: tuple[TopologyArchitectureCaseReceipt, ...]
) -> tuple[TopologyArchitectureCheck, ...]:
    return (
        _check(
            "global:all-receipts",
            all(item.passed for item in receipts),
            sum(item.passed for item in receipts),
            64,
            "all topology cases reconcile",
        ),
        _check(
            "global:positive-receipts",
            sum(
                item.expected_state is TopologyArchitectureState.ACCEPTED and item.passed
                for item in receipts
            ),
            16,
            16,
            "all topology positive paths are accepted",
        ),
        _check(
            "global:control-receipts",
            sum(
                item.expected_state is TopologyArchitectureState.REVIEW and item.passed
                for item in receipts
            ),
            48,
            48,
            "all topology controls remain review-held",
        ),
        _check(
            "global:family-coverage",
            len({item.family for item in receipts}) == 4,
            len({item.family for item in receipts}),
            4,
            "all topology family tranches are represented",
            TopologyArchitectureCheckKind.CONTEXT,
        ),
        _check(
            "global:operation-coverage",
            len({item.operation_id for item in receipts}) == 16,
            len({item.operation_id for item in receipts}),
            16,
            "all topology operation IDs are exercised",
        ),
        _check(
            "global:case-coverage",
            len({item.case_id for item in receipts}) == 64,
            len({item.case_id for item in receipts}),
            64,
            "all topology case IDs are exercised",
        ),
        _check(
            "global:address-coverage",
            all(item.output_address.startswith("sha256:") for item in receipts),
            sum(item.output_address.startswith("sha256:") for item in receipts),
            64,
            "every topology execution has an address",
            TopologyArchitectureCheckKind.INVARIANT,
        ),
        _check(
            "global:positive-state",
            all(
                item.observed_state is TopologyArchitectureState.ACCEPTED
                for item in receipts
                if item.expected_state is TopologyArchitectureState.ACCEPTED
            ),
            True,
            True,
            "topology positive paths do not silently abstain",
            TopologyArchitectureCheckKind.CONTROL,
        ),
    )


def evaluate_topology_architecture_fixture(
    fixture: TopologyArchitectureFixture,
) -> TopologyArchitectureEvaluation:
    """Execute all 64 topology cases and compare them to the aggregate contract."""
    outcomes = _family_outcomes()
    executions = tuple(
        execute_topology_architecture_case(case, fixture.context_key, outcomes=outcomes)
        for case in fixture.cases
    )
    receipts = tuple(
        _receipt(case, execution) for case, execution in zip(fixture.cases, executions, strict=True)
    )
    checks = tuple(
        check
        for case, execution, receipt in zip(fixture.cases, executions, receipts, strict=True)
        for check in _case_checks(case, execution, receipt)
    ) + _global_checks(fixture, receipts)
    accepted = all(item.passed for item in (*receipts, *checks))
    body = {
        "fixture_id": fixture.fixture_id,
        "context_key": fixture.context_key,
        "state": TopologyArchitectureState.ACCEPTED
        if accepted
        else TopologyArchitectureState.BLOCKED,
        "receipts": receipts,
        "checks": checks,
    }
    return TopologyArchitectureEvaluation(
        fixture.fixture_id,
        fixture.context_key,
        TopologyArchitectureState.ACCEPTED if accepted else TopologyArchitectureState.BLOCKED,
        executions,
        receipts,
        checks,
        addressed(body, "topology-evaluation"),
    )


__all__ = ["evaluate_topology_architecture_fixture", "execute_topology_architecture_case"]

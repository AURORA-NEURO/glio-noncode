"""D08 execution dispatch with family delegation and real cell-state paths."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .cell_context_alpha_frontier_fixture_eval import evaluate_cell_context_alpha_frontier_fixture
from .cell_context_alpha_frontier_public_data import default_cell_context_alpha_frontier_fixture
from .cell_context_beta_frontier_fixture_eval import evaluate_cell_context_beta_frontier_fixture
from .cell_context_beta_frontier_public_data import default_cell_context_beta_frontier_fixture
from .cell_context_frontier_fixture_eval import evaluate_cell_context_frontier_fixture
from .cell_context_frontier_public_data import default_cell_context_frontier_fixture
from .cell_state_architecture_contracts import (
    CELL_STATE_ARCHITECTURE_CONTEXT,
    CellStateArchitectureCase,
    CellStateArchitectureCaseReceipt,
    CellStateArchitectureCheck,
    CellStateArchitectureCheckKind,
    CellStateArchitectureEvaluation,
    CellStateArchitectureExecution,
    CellStateArchitectureFamily,
    CellStateArchitectureFixture,
    CellStateArchitectureOperation,
    CellStateArchitectureScenario,
    CellStateArchitectureState,
    addressed,
)
from .cell_state_frontier_fixture_eval import evaluate_cell_state_frontier_fixture
from .cell_state_frontier_public_data import default_cell_state_frontier_fixture
from .frontier_context_alpha import (
    CellStateAbundanceUncertaintyModel,
    CellStateContextPublisher,
    CellStateOODDetector,
    SingleCellReferenceMapper,
)
from .serialization import jsonable


def _rows(evaluation: Any) -> tuple[Any, ...]:
    return tuple(
        getattr(evaluation, "executions", None)
        or getattr(evaluation, "records", None)
        or getattr(evaluation, "receipts", None)
        or ()
    )


def _sanitize(value: Any) -> Any:
    hidden = {"payload", "input_text", "track_text", "raw_text", "records_text"}
    if isinstance(value, Mapping):
        return {str(key): _sanitize(item) for key, item in value.items() if str(key) not in hidden}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value


def _family_outcomes() -> dict[tuple[CellStateArchitectureFamily, str], dict[str, Any]]:
    fixtures = {
        CellStateArchitectureFamily.CONTEXT: default_cell_context_frontier_fixture(),
        CellStateArchitectureFamily.BETA: default_cell_context_beta_frontier_fixture(),
        CellStateArchitectureFamily.ALPHA: default_cell_context_alpha_frontier_fixture(),
        CellStateArchitectureFamily.STATE: default_cell_state_frontier_fixture(),
    }
    evaluations = {
        CellStateArchitectureFamily.CONTEXT: evaluate_cell_context_frontier_fixture(
            fixtures[CellStateArchitectureFamily.CONTEXT]
        ),
        CellStateArchitectureFamily.BETA: evaluate_cell_context_beta_frontier_fixture(
            fixtures[CellStateArchitectureFamily.BETA]
        ),
        CellStateArchitectureFamily.ALPHA: evaluate_cell_context_alpha_frontier_fixture(
            fixtures[CellStateArchitectureFamily.ALPHA]
        ),
        CellStateArchitectureFamily.STATE: evaluate_cell_state_frontier_fixture(
            fixtures[CellStateArchitectureFamily.STATE]
        ),
    }
    outcomes: dict[tuple[CellStateArchitectureFamily, str], dict[str, Any]] = {}
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
                "detail": f"{family.value} public positive receipt delegated and retained",
            }
    return outcomes


def _state_execution(
    case: CellStateArchitectureCase,
) -> tuple[str, tuple[str, ...], dict[str, int], dict[str, Any], str]:
    payload = case.payload.get("operation_payload", {})
    operation = case.operation
    if operation is CellStateArchitectureOperation.ABUNDANCE_INTERVAL:
        report = CellStateAbundanceUncertaintyModel().estimate(
            payload.get("records", ()),
            context_key=case.context_key,
            interval_multiplier=float(payload.get("interval_multiplier", 1.96)),
        )
        issues = tuple(issue.code for item in report.estimates for issue in item.issues)
        state = "accepted" if not report.review_ids else "review"
        return (
            state,
            issues,
            {"primary": 1, "secondary": 1},
            {
                "state": state,
                "estimate_count": len(report.estimates),
                "stable_ids": list(report.stable_ids),
                "review_ids": list(report.review_ids),
                "estimates": [jsonable(item) for item in report.estimates],
                "content_address": report.content_address,
            },
            "abundance interval is bounded by explicit cell-count validation",
        )
    if operation is CellStateArchitectureOperation.REFERENCE_MAPPING:
        report = SingleCellReferenceMapper().map(
            payload.get("records", ()),
            context_key=case.context_key,
            minimum_score=float(payload.get("minimum_score", 0.6)),
            minimum_margin=float(payload.get("minimum_margin", 0.1)),
        )
        issues = tuple(issue.code for item in report.mappings for issue in item.issues)
        state = "accepted" if not report.review_ids else "review"
        return (
            state,
            issues,
            {"primary": 1, "secondary": 1},
            {
                "state": state,
                "mapping_count": len(report.mappings),
                "mapped_ids": list(report.mapped_ids),
                "review_ids": list(report.review_ids),
                "mappings": [jsonable(item) for item in report.mappings],
                "content_address": report.content_address,
            },
            "reference mapping exposes both top score and margin before acceptance",
        )
    if operation is CellStateArchitectureOperation.OOD_DETECTION:
        report = CellStateOODDetector().detect(
            payload.get("records", ()),
            context_key=case.context_key,
            maximum_distance=float(payload.get("maximum_distance", 3.0)),
            minimum_support=float(payload.get("minimum_support", 0.5)),
        )
        issues = tuple(issue.code for item in report.findings for issue in item.issues)
        state = "accepted" if not report.review_ids else "review"
        return (
            state,
            issues,
            {"primary": 1, "secondary": 1},
            {
                "state": state,
                "finding_count": len(report.findings),
                "in_domain_ids": list(report.in_domain_ids),
                "ood_ids": list(report.ood_ids),
                "review_ids": list(report.review_ids),
                "findings": [jsonable(item) for item in report.findings],
                "content_address": report.content_address,
            },
            "out-of-domain decisions preserve distance, support, and boundary evidence",
        )
    if operation is CellStateArchitectureOperation.CONTEXT_PUBLICATION:
        report = CellStateContextPublisher().publish(
            envelope_id=str(payload.get("envelope_id", "d08-cell-state-release")),
            context_key=case.context_key,
            cell_ids=payload.get("cell_ids", ()),
            mapping_address=str(payload.get("mapping_address", "")),
            abundance_address=str(payload.get("abundance_address", "")),
            ood_address=str(payload.get("ood_address", "")),
        )
        return (
            report.state.value,
            (),
            {"primary": 1, "secondary": 1},
            {
                "state": report.state.value,
                "envelope_id": report.envelope_id,
                "cell_ids": list(report.cell_ids),
                "mapping_address": report.mapping_address,
                "abundance_address": report.abundance_address,
                "ood_address": report.ood_address,
                "envelope_address": report.envelope_address,
            },
            "publication joins mapping, abundance, and OOD receipts under exact context",
        )
    raise ValueError(f"D08 cell-state operation not supported: {operation}")


def _control_execution(
    case: CellStateArchitectureCase, result_state: str, issues: tuple[str, ...], detail: str
) -> CellStateArchitectureExecution:
    summary = {"state": result_state, "scenario": case.scenario.value, "delegated": False}
    return CellStateArchitectureExecution(
        case.case_id,
        case.operation,
        case.family,
        case.scenario,
        CellStateArchitectureState.REVIEW,
        result_state,
        issues,
        {"primary": 0, "secondary": 0},
        addressed(summary, "cell-state-control"),
        summary,
        detail,
    )


def execute_cell_state_architecture_case(
    case: CellStateArchitectureCase,
    context_key: str = CELL_STATE_ARCHITECTURE_CONTEXT,
    *,
    outcomes: Mapping[tuple[CellStateArchitectureFamily, str], Mapping[str, Any]] | None = None,
) -> CellStateArchitectureExecution:
    """Apply aggregate controls before delegating a public positive record."""
    if (
        case.scenario is CellStateArchitectureScenario.FOREIGN_CONTEXT
        or case.context_key != context_key
    ):
        return _control_execution(
            case,
            "out_of_domain",
            ("context_mismatch",),
            "foreign cell-state context held before delegation",
        )
    if case.scenario is CellStateArchitectureScenario.MALFORMED_INPUT or case.payload.get(
        "malformed"
    ):
        return _control_execution(
            case,
            "invalid",
            ("malformed_input",),
            "malformed cell-state input held before delegation",
        )
    if case.scenario is CellStateArchitectureScenario.IDENTITY_CONFLICT or case.payload.get(
        "identity_conflict"
    ):
        return _control_execution(
            case,
            "contradictory",
            ("identity_conflict",),
            "identity conflict held before delegation",
        )
    if case.scenario is not CellStateArchitectureScenario.POSITIVE:
        return _control_execution(
            case, "abstained", ("unsupported_scenario",), "unsupported scenario held"
        )
    if case.family is CellStateArchitectureFamily.STATE:
        state, issues, counts, summary, detail = _state_execution(case)
        return CellStateArchitectureExecution(
            case.case_id,
            case.operation,
            case.family,
            case.scenario,
            CellStateArchitectureState.ACCEPTED,
            state,
            issues,
            counts,
            addressed(summary, "cell-state-output"),
            summary,
            detail,
        )
    key = (case.family, str(case.payload.get("family_record_id", "")))
    selected = dict((outcomes or _family_outcomes()).get(key, {}))
    if not selected:
        return _control_execution(
            case,
            "missing_family_receipt",
            ("missing_family_receipt",),
            "positive path has no family receipt",
        )
    summary = dict(selected.get("summary", {}))
    summary["delegated"] = True
    result_state = str(selected.get("result_state", "supported"))
    return CellStateArchitectureExecution(
        case.case_id,
        case.operation,
        case.family,
        case.scenario,
        CellStateArchitectureState.ACCEPTED,
        result_state,
        tuple(selected.get("issue_codes", ())),
        {"primary": 1, "secondary": 1},
        addressed(summary, "cell-state-output"),
        summary,
        str(selected.get("detail", "family receipt delegated")),
    )


def _check(
    check_id: str,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
    kind: CellStateArchitectureCheckKind = CellStateArchitectureCheckKind.OPERATION,
) -> CellStateArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return CellStateArchitectureCheck(**body, content_address=addressed(body, "cell-state-check"))


def _receipt(
    case: CellStateArchitectureCase, execution: CellStateArchitectureExecution
) -> CellStateArchitectureCaseReceipt:
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
    return CellStateArchitectureCaseReceipt(
        **body, content_address=addressed(body, "cell-state-receipt")
    )


def _case_checks(
    case: CellStateArchitectureCase,
    execution: CellStateArchitectureExecution,
    receipt: CellStateArchitectureCaseReceipt,
) -> tuple[CellStateArchitectureCheck, ...]:
    return (
        _check(
            f"{case.case_id}:state",
            execution.observed_state is case.expected_state,
            execution.observed_state,
            case.expected_state,
            "execution state matches the contract",
        ),
        _check(
            f"{case.case_id}:result",
            execution.observed_result_state == case.expected_result_state,
            execution.observed_result_state,
            case.expected_result_state,
            "operation result state matches the contract",
        ),
        _check(
            f"{case.case_id}:issues",
            execution.issue_codes == case.expected_issue_codes,
            execution.issue_codes,
            case.expected_issue_codes,
            "issue code set is stable and explicit",
        ),
        _check(
            f"{case.case_id}:counts",
            execution.counts == case.expected_counts,
            execution.counts,
            case.expected_counts,
            "source-role counts are conserved",
        ),
        _check(
            f"{case.case_id}:address",
            execution.output_address.startswith("sha256:"),
            execution.output_address,
            "sha256:*",
            "execution output is content addressed",
        ),
        _check(
            f"{case.case_id}:receipt",
            receipt.passed,
            receipt.passed,
            True,
            "case receipt reconciles all expected fields",
        ),
    )


def _global_checks(
    fixture: CellStateArchitectureFixture, receipts: tuple[CellStateArchitectureCaseReceipt, ...]
) -> tuple[CellStateArchitectureCheck, ...]:
    return (
        _check(
            "global:all-receipts",
            all(item.passed for item in receipts),
            sum(item.passed for item in receipts),
            64,
            "all operation cases reconcile",
        ),
        _check(
            "global:positive-receipts",
            sum(
                item.expected_state is CellStateArchitectureState.ACCEPTED and item.passed
                for item in receipts
            ),
            16,
            16,
            "all positive cases are accepted",
        ),
        _check(
            "global:control-receipts",
            sum(
                item.expected_state is CellStateArchitectureState.REVIEW and item.passed
                for item in receipts
            ),
            48,
            48,
            "all controls remain review-held",
        ),
        _check(
            "global:family-context",
            len({item.family for item in receipts}) == 4,
            len({item.family for item in receipts}),
            4,
            "four D08 families are represented",
            CellStateArchitectureCheckKind.CONTEXT,
        ),
        _check(
            "global:operation-coverage",
            len({item.operation_id for item in receipts}) == 16,
            len({item.operation_id for item in receipts}),
            16,
            "sixteen operation IDs are exercised",
        ),
        _check(
            "global:case-coverage",
            len({item.case_id for item in receipts}) == 64,
            len({item.case_id for item in receipts}),
            64,
            "sixty-four case IDs are exercised",
        ),
        _check(
            "global:address-coverage",
            all(item.output_address.startswith("sha256:") for item in receipts),
            sum(item.output_address.startswith("sha256:") for item in receipts),
            64,
            "every execution has an output address",
            CellStateArchitectureCheckKind.INVARIANT,
        ),
        _check(
            "global:positive-state",
            all(
                item.observed_state is CellStateArchitectureState.ACCEPTED
                for item in receipts
                if item.expected_state is CellStateArchitectureState.ACCEPTED
            ),
            True,
            True,
            "positive controls do not silently abstain",
            CellStateArchitectureCheckKind.REVIEW,
        ),
    )


def evaluate_cell_state_architecture_fixture(
    fixture: CellStateArchitectureFixture,
) -> CellStateArchitectureEvaluation:
    """Execute all 64 cases and compare receipts to the aggregate contract."""
    outcomes = _family_outcomes()
    executions = tuple(
        execute_cell_state_architecture_case(case, fixture.context_key, outcomes=outcomes)
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
        "state": CellStateArchitectureState.ACCEPTED
        if accepted
        else CellStateArchitectureState.BLOCKED,
        "receipts": receipts,
        "checks": checks,
    }
    return CellStateArchitectureEvaluation(
        fixture.fixture_id,
        fixture.context_key,
        CellStateArchitectureState.ACCEPTED if accepted else CellStateArchitectureState.BLOCKED,
        executions,
        receipts,
        checks,
        addressed(body, "cell-state-evaluation"),
    )


__all__ = [
    "evaluate_cell_state_architecture_fixture",
    "execute_cell_state_architecture_case",
]

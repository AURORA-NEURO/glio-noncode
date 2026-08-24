"""D07 execution dispatch, family delegation, and bounded control handling."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .chromatin_alpha_frontier_fixture_eval import evaluate_chromatin_alpha_frontier_fixture
from .chromatin_alpha_frontier_public_data import default_chromatin_alpha_frontier_fixture
from .chromatin_architecture_contracts import (
    CHROMATIN_ARCHITECTURE_CONTEXT,
    ChromatinArchitectureCase,
    ChromatinArchitectureCaseReceipt,
    ChromatinArchitectureCheck,
    ChromatinArchitectureCheckKind,
    ChromatinArchitectureEvaluation,
    ChromatinArchitectureExecution,
    ChromatinArchitectureFamily,
    ChromatinArchitectureFixture,
    ChromatinArchitectureOperation,
    ChromatinArchitectureScenario,
    ChromatinArchitectureState,
    addressed,
)
from .chromatin_context_frontier_fixture_eval import evaluate_chromatin_context_frontier_fixture
from .chromatin_context_frontier_public_data import default_chromatin_context_frontier_fixture
from .chromatin_frontier_fixture_eval import evaluate_chromatin_frontier_fixture
from .chromatin_frontier_public_data import default_chromatin_frontier_fixture
from .frontier_context_alpha import (
    AssaySupportCoverageGate,
    ChromatinEvidencePublisher,
    ContextImputationWithConfidence,
    CrossAssayConcordanceAdjudicator,
)
from .methylation_frontier_fixture_eval import evaluate_methylation_frontier_fixture
from .methylation_frontier_public_data import default_methylation_frontier_fixture
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


def _family_outcomes() -> dict[tuple[ChromatinArchitectureFamily, str], dict[str, Any]]:
    fixtures = {
        ChromatinArchitectureFamily.CONTEXT: default_chromatin_context_frontier_fixture(),
        ChromatinArchitectureFamily.METHYLATION: default_methylation_frontier_fixture(),
        ChromatinArchitectureFamily.ALPHA: default_chromatin_alpha_frontier_fixture(),
        ChromatinArchitectureFamily.FRONTIER: default_chromatin_frontier_fixture(),
    }
    evaluations = {
        ChromatinArchitectureFamily.CONTEXT: evaluate_chromatin_context_frontier_fixture(
            fixtures[ChromatinArchitectureFamily.CONTEXT]
        ),
        ChromatinArchitectureFamily.METHYLATION: evaluate_methylation_frontier_fixture(
            fixtures[ChromatinArchitectureFamily.METHYLATION]
        ),
        ChromatinArchitectureFamily.ALPHA: evaluate_chromatin_alpha_frontier_fixture(
            fixtures[ChromatinArchitectureFamily.ALPHA]
        ),
        ChromatinArchitectureFamily.FRONTIER: evaluate_chromatin_frontier_fixture(
            fixtures[ChromatinArchitectureFamily.FRONTIER]
        ),
    }
    outcomes: dict[tuple[ChromatinArchitectureFamily, str], dict[str, Any]] = {}
    for family, evaluation in evaluations.items():
        for row in _rows(evaluation):
            role = getattr(row, "role", None)
            if str(getattr(role, "value", role)) != "positive":
                continue
            adapter = getattr(row, "adapter", row)
            result_state = (
                getattr(adapter, "state", None)
                or getattr(row, "adapter_state", None)
                or getattr(row, "observed_state", None)
            )
            issues = getattr(adapter, "issue_codes", None) or getattr(
                row, "observed_issue_codes", ()
            )
            outcomes[(family, str(row.record_id))] = {
                "result_state": str(getattr(result_state, "value", result_state)),
                "issue_codes": tuple(str(item) for item in issues),
                "summary": _sanitize(jsonable(row)),
                "detail": f"{family.value} public positive receipt delegated and retained",
            }
    return outcomes


def _frontier_execution(
    case: ChromatinArchitectureCase,
) -> tuple[str, tuple[str, ...], dict[str, int], dict[str, Any], str]:
    payload = case.payload.get("operation_payload", {})
    operation = case.operation
    if operation is ChromatinArchitectureOperation.CONTEXT_IMPUTATION:
        report = ContextImputationWithConfidence().impute(
            payload.get("records", ()),
            context_key=case.context_key,
            prior_values=payload.get("prior_values", {}),
            prior_confidence=payload.get("prior_confidence", {}),
            minimum_confidence=float(payload.get("minimum_confidence", 0.7)),
        )
        state = "accepted" if not report.review_ids else "review"
        return (
            state,
            tuple(issue.code for item in report.values for issue in item.issues),
            {"primary": 1, "secondary": 1},
            {
                "state": state,
                "value_count": len(report.values),
                "observed_ids": list(report.observed_ids),
                "imputed_ids": list(report.imputed_ids),
                "review_ids": list(report.review_ids),
                "confidence_values": [item.confidence for item in report.values],
            },
            "declared priors are retained with confidence and review visibility",
        )
    if operation is ChromatinArchitectureOperation.ASSAY_COVERAGE:
        report = AssaySupportCoverageGate().evaluate(
            payload.get("records", ()),
            context_key=case.context_key,
            required_assays=payload.get("required_assays", ()),
            minimum_coverage=float(payload.get("minimum_coverage", 0.75)),
        )
        state = "accepted" if not report.review_ids else "review"
        return (
            state,
            (),
            {"primary": 1, "secondary": 1},
            {
                "state": state,
                "decision_count": len(report.decisions),
                "supported_ids": list(report.supported_ids),
                "review_ids": list(report.review_ids),
                "coverage": [item.coverage for item in report.decisions],
                "missing_assays": [list(item.missing_assays) for item in report.decisions],
            },
            "assay support is gated before cross-assay interpretation",
        )
    if operation is ChromatinArchitectureOperation.ASSAY_CONCORDANCE:
        report = CrossAssayConcordanceAdjudicator().adjudicate(
            payload.get("records", ()),
            context_key=case.context_key,
            minimum_concordance=float(payload.get("minimum_concordance", 0.75)),
        )
        state = "accepted" if not report.review_ids else "review"
        return (
            state,
            tuple(issue.code for item in report.decisions for issue in item.issues),
            {"primary": 1, "secondary": 1},
            {
                "state": state,
                "decision_count": len(report.decisions),
                "concordant_ids": list(report.concordant_ids),
                "review_ids": list(report.review_ids),
                "directions": [dict(item.directions) for item in report.decisions],
                "concordance": [item.concordance for item in report.decisions],
            },
            "direction agreement remains descriptive and thresholded",
        )
    if operation is ChromatinArchitectureOperation.EVIDENCE_PUBLISH:
        report = ChromatinEvidencePublisher().publish(
            payload.get("records", ()),
            bundle_id=str(payload.get("bundle_id", "")),
            context_key=case.context_key,
            assay_ids=payload.get("assay_ids", ()),
        )
        return (
            report.state.value,
            (),
            {"primary": 1, "secondary": 1},
            {
                "state": report.state.value,
                "bundle_id": report.bundle_id,
                "feature_ids": list(report.feature_ids),
                "assay_ids": list(report.assay_ids),
                "records_address": report.records_address,
                "bundle_address": report.bundle_address,
            },
            "exact-context chromatin evidence bundle is published",
        )
    raise ValueError(f"frontier operation not supported: {operation}")


def evaluate_chromatin_architecture_fixture(
    fixture: ChromatinArchitectureFixture,
) -> ChromatinArchitectureEvaluation:
    """Execute all 64 cases and compare receipts to the aggregate contract."""

    outcomes = _family_outcomes()
    executions = tuple(
        execute_chromatin_architecture_case(case, fixture.context_key, outcomes=outcomes)
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
        "state": ChromatinArchitectureState.ACCEPTED
        if accepted
        else ChromatinArchitectureState.BLOCKED,
        "receipts": receipts,
        "checks": checks,
    }
    return ChromatinArchitectureEvaluation(
        fixture_id=fixture.fixture_id,
        context_key=fixture.context_key,
        state=ChromatinArchitectureState.ACCEPTED
        if accepted
        else ChromatinArchitectureState.BLOCKED,
        executions=executions,
        receipts=receipts,
        checks=checks,
        content_address=addressed(body, "chromatin-evaluation"),
    )


def execute_chromatin_architecture_case(
    case: ChromatinArchitectureCase,
    context_key: str = CHROMATIN_ARCHITECTURE_CONTEXT,
    *,
    outcomes: Mapping[tuple[ChromatinArchitectureFamily, str], Mapping[str, Any]] | None = None,
) -> ChromatinArchitectureExecution:
    """Apply aggregate controls before delegating a public positive record."""

    if (
        case.scenario is ChromatinArchitectureScenario.FOREIGN_CONTEXT
        or case.context_key != context_key
    ):
        return _control_execution(
            case,
            "out_of_domain",
            ("context_mismatch",),
            "foreign chromatin context held before delegation",
        )
    if case.scenario is ChromatinArchitectureScenario.MALFORMED_INPUT or case.payload.get(
        "malformed"
    ):
        return _control_execution(
            case,
            "invalid",
            ("malformed_input",),
            "malformed chromatin payload held before delegation",
        )
    if case.scenario is ChromatinArchitectureScenario.IDENTITY_CONFLICT or case.payload.get(
        "identity_conflict"
    ):
        return _control_execution(
            case,
            "contradictory",
            ("identity_conflict",),
            "identity conflict held before delegation",
        )
    if case.family is ChromatinArchitectureFamily.FRONTIER:
        result_state, issues, counts, summary, detail = _frontier_execution(case)
    else:
        selected = outcomes or _family_outcomes()
        record_id = str(case.payload.get("family_record_id", ""))
        outcome = selected.get((case.family, record_id))
        if outcome is None:
            return _control_execution(
                case, "invalid", ("missing_family_receipt",), "positive case has no family receipt"
            )
        result_state = str(outcome["result_state"])
        issues = tuple(str(item) for item in outcome["issue_codes"])
        counts = {"primary": 1, "secondary": 1}
        summary = dict(outcome["summary"])
        detail = str(outcome["detail"])
    summary = dict(summary)
    summary["context_key"] = case.context_key
    summary["delegate_context_key"] = case.delegate_context_key
    observed_state = (
        ChromatinArchitectureState.ACCEPTED
        if result_state in {"supported", "accepted", "published"}
        else ChromatinArchitectureState.REVIEW
    )
    output_address = addressed({"case_id": case.case_id, "summary": summary}, "chromatin-execution")
    return ChromatinArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        family=case.family,
        scenario=case.scenario,
        observed_state=observed_state,
        observed_result_state=result_state,
        issue_codes=issues,
        counts=counts,
        output_address=output_address,
        summary=_sanitize(summary),
        detail=detail,
    )


def _control_execution(
    case: ChromatinArchitectureCase,
    result_state: str,
    issue_codes: tuple[str, ...],
    detail: str,
) -> ChromatinArchitectureExecution:
    body = {
        "case_id": case.case_id,
        "state": ChromatinArchitectureState.REVIEW,
        "result_state": result_state,
        "issue_codes": issue_codes,
        "counts": {"primary": 0, "secondary": 0},
        "detail": detail,
        "context_key": case.context_key,
        "delegate_context_key": case.delegate_context_key,
    }
    return ChromatinArchitectureExecution(
        case_id=case.case_id,
        operation=case.operation,
        family=case.family,
        scenario=case.scenario,
        observed_state=ChromatinArchitectureState.REVIEW,
        observed_result_state=result_state,
        issue_codes=issue_codes,
        counts={"primary": 0, "secondary": 0},
        output_address=addressed(body, "chromatin-control"),
        summary={
            "control": True,
            "detail": detail,
            "context_key": case.context_key,
            "delegate_context_key": case.delegate_context_key,
        },
        detail=detail,
    )


def _receipt(
    case: ChromatinArchitectureCase,
    execution: ChromatinArchitectureExecution,
) -> ChromatinArchitectureCaseReceipt:
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
    }
    return ChromatinArchitectureCaseReceipt(
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
        content_address=addressed(body, "chromatin-receipt"),
    )


def _check(
    check_id: str,
    kind: ChromatinArchitectureCheckKind,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> ChromatinArchitectureCheck:
    body = {
        "check_id": check_id,
        "kind": kind,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return ChromatinArchitectureCheck(**body, content_address=addressed(body, "chromatin-check"))


def _case_checks(
    case: ChromatinArchitectureCase,
    execution: ChromatinArchitectureExecution,
    receipt: ChromatinArchitectureCaseReceipt,
) -> tuple[ChromatinArchitectureCheck, ...]:
    return (
        _check(
            f"{case.case_id}-state",
            ChromatinArchitectureCheckKind.OPERATION,
            case.expected_state is execution.observed_state,
            execution.observed_state.value,
            case.expected_state.value,
            "aggregate state matches control policy",
        ),
        _check(
            f"{case.case_id}-result",
            ChromatinArchitectureCheckKind.OPERATION,
            case.expected_result_state == execution.observed_result_state,
            execution.observed_result_state,
            case.expected_result_state,
            "family result state matches operation contract",
        ),
        _check(
            f"{case.case_id}-issues",
            ChromatinArchitectureCheckKind.CONTEXT,
            case.expected_issue_codes == execution.issue_codes,
            execution.issue_codes,
            case.expected_issue_codes,
            "issue receipt is preserved exactly",
        ),
        _check(
            f"{case.case_id}-counts",
            ChromatinArchitectureCheckKind.OPERATION,
            case.expected_counts == execution.counts,
            execution.counts,
            case.expected_counts,
            "aggregate evidence counts remain bounded",
        ),
        _check(
            f"{case.case_id}-address",
            ChromatinArchitectureCheckKind.IDENTITY,
            receipt.content_address.startswith("sha256:"),
            receipt.content_address,
            "sha256:",
            "case receipt is content addressed",
        ),
        _check(
            f"{case.case_id}-sanitized",
            ChromatinArchitectureCheckKind.REVIEW,
            not any(
                key in jsonable(execution.summary)
                for key in ("payload", "input_text", "track_text")
            ),
            True,
            "review summary excludes raw input",
            "review summary is sanitized",
        ),
        _check(
            f"{case.case_id}-context",
            ChromatinArchitectureCheckKind.CONTEXT,
            bool(execution.summary.get("delegate_context_key"))
            and (
                case.scenario is not ChromatinArchitectureScenario.FOREIGN_CONTEXT
                or "context_mismatch" in execution.issue_codes
            ),
            execution.summary.get("delegate_context_key", ""),
            "retained or explicitly mismatched",
            "delegated context is retained and foreign controls remain explicit",
        ),
    )


def _global_checks(
    fixture: ChromatinArchitectureFixture,
    receipts: tuple[ChromatinArchitectureCaseReceipt, ...],
) -> tuple[ChromatinArchitectureCheck, ...]:
    return (
        _check(
            "global-receipt-count",
            ChromatinArchitectureCheckKind.FIXTURE,
            len(receipts) == 64,
            len(receipts),
            64,
            "all D07 cases have receipts",
        ),
        _check(
            "global-positive-count",
            ChromatinArchitectureCheckKind.FIXTURE,
            sum(item.expected_state is ChromatinArchitectureState.ACCEPTED for item in receipts)
            == 16,
            sum(item.expected_state is ChromatinArchitectureState.ACCEPTED for item in receipts),
            16,
            "one positive path exists per capability",
        ),
        _check(
            "global-control-count",
            ChromatinArchitectureCheckKind.FIXTURE,
            sum(item.expected_state is ChromatinArchitectureState.REVIEW for item in receipts)
            == 48,
            sum(item.expected_state is ChromatinArchitectureState.REVIEW for item in receipts),
            48,
            "three controls exist per capability",
        ),
        _check(
            "global-pass-count",
            ChromatinArchitectureCheckKind.OPERATION,
            sum(item.passed for item in receipts) == 64,
            sum(item.passed for item in receipts),
            64,
            "every D07 receipt passes",
        ),
        _check(
            "global-operation-coverage",
            ChromatinArchitectureCheckKind.OPERATION,
            len({item.operation_id for item in receipts}) == 16,
            len({item.operation_id for item in receipts}),
            16,
            "all operation IDs execute",
        ),
        _check(
            "global-family-coverage",
            ChromatinArchitectureCheckKind.OPERATION,
            len({item.family for item in receipts}) == 4,
            len({item.family for item in receipts}),
            4,
            "all family delegations execute",
        ),
        _check(
            "global-context",
            ChromatinArchitectureCheckKind.CONTEXT,
            fixture.context_key == CHROMATIN_ARCHITECTURE_CONTEXT,
            fixture.context_key,
            CHROMATIN_ARCHITECTURE_CONTEXT,
            "aggregate context remains exact",
        ),
        _check(
            "global-control-policy",
            ChromatinArchitectureCheckKind.REVIEW,
            all(
                item.expected_state is ChromatinArchitectureState.REVIEW
                for item in receipts
                if item.expected_result_state in {"out_of_domain", "invalid", "contradictory"}
            ),
            True,
            "controls remain review-held",
            "foreign, malformed, and identity controls are never accepted",
        ),
        _check(
            "global-operation-balance",
            ChromatinArchitectureCheckKind.OPERATION,
            all(
                sum(item.operation_id == operation_id for item in receipts) == 4
                for operation_id in {item.operation_id for item in receipts}
            ),
            sorted(
                sum(item.operation_id == operation_id for item in receipts)
                for operation_id in {item.operation_id for item in receipts}
            ),
            [4] * 16,
            "each D07 operation has one positive and three controls",
        ),
        _check(
            "global-context-controls",
            ChromatinArchitectureCheckKind.CONTEXT,
            all(
                "context_mismatch" in item.observed_issue_codes
                for item in receipts
                if item.case_id.endswith("-foreign_context")
            )
            and all(
                item.observed_result_state
                for item in receipts
            ),
            True,
            True,
            "delegated contexts and foreign controls are explicit",
        ),
    )


__all__ = [
    "evaluate_chromatin_architecture_fixture",
    "execute_chromatin_architecture_case",
]

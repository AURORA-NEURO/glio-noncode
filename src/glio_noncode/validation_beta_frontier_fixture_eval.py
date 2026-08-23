"""Execution evaluator for the Domain 13 C05-C12 aggregate fixture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .serialization import content_hash, jsonable
from .validation_alpha import (
    ControlsRandomizationPlanner,
    ControlType,
    GuideOligoDesignAdapter,
    ModelSystemEligibilityMatcher,
    PowerReplicationEstimator,
)
from .validation_beta import (
    AlleleSpecificReporterPlanner,
    BaseEditingDesignPlanner,
    CRISPRaDesignPlanner,
    CRISPRiDesignPlanner,
    GuideDesignConstraints,
    PerturbationMode,
    PrimeEditingDesignPlanner,
    ValidationBetaState,
    ValidationBetaTarget,
)
from .validation_beta_frontier_public_data import (
    ValidationBetaFrontierFixture,
    ValidationBetaFrontierOperation,
    ValidationBetaFrontierRecord,
    default_validation_beta_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierEvaluationRow:
    operation: ValidationBetaFrontierOperation
    record_id: str
    expected_state: str
    observed_state: str
    expected_issue_codes: tuple[str, ...]
    observed_issue_codes: tuple[str, ...]
    accepted: bool
    result: Mapping[str, Any]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationBetaFrontierEvaluation:
    fixture_id: str
    context_key: str
    rows: tuple[ValidationBetaFrontierEvaluationRow, ...]
    accepted: bool
    positive_count: int
    control_count: int
    mismatch_count: int
    state_counts: Mapping[str, int]
    content_address: str

    def by_operation(
        self, operation: ValidationBetaFrontierOperation | str
    ) -> tuple[ValidationBetaFrontierEvaluationRow, ...]:
        selected = str(operation.value if isinstance(operation, ValidationBetaFrontierOperation) else operation)
        return tuple(item for item in self.rows if item.operation.value == selected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def _target(value: Mapping[str, Any]) -> ValidationBetaTarget:
    return ValidationBetaTarget.from_mapping(value)


def _constraints(value: Mapping[str, Any]) -> GuideDesignConstraints:
    return GuideDesignConstraints.from_mapping(value, context_key=str(value.get("context_key", "")))


def _issue_codes(result: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for item in result.get("blockers", ()):
        text = str(item)
        values.append(text.rsplit(":", 1)[-1])
    for item in result.get("issues", ()):
        if isinstance(item, Mapping) and item.get("code"):
            values.append(str(item["code"]))
    for item in result.get("results", ()):
        if isinstance(item, Mapping):
            values.extend(
                str(value).rsplit(":", 1)[-1]
                for value in item.get("blockers", ())
            )
    for package in result.get("modes", {}).values():
        if isinstance(package, Mapping):
            values.extend(_issue_codes(package))
    return tuple(dict.fromkeys(values))


def _aggregate_states(states: tuple[str, ...]) -> str:
    if not states:
        return "abstained"
    if "blocked" in states:
        return "blocked"
    if "partial" in states:
        return "partial"
    if "out_of_domain" in states:
        return "out_of_domain"
    if "ambiguous" in states:
        return "ambiguous"
    return "ready_for_review"


def _evaluate_design(record: ValidationBetaFrontierRecord) -> Mapping[str, Any]:
    payload = record.payload
    targets = tuple(_target(item) for item in payload.get("targets", ()))
    constraints = _constraints(payload["constraints"])
    modes = tuple(str(item) for item in payload.get("modes", (constraints.mode.value,)))
    packages: dict[str, Mapping[str, Any]] = {}
    for mode in modes:
        selected = PerturbationMode(mode)
        selected_constraints = constraints
        if selected != constraints.mode:
            selected_constraints = GuideDesignConstraints.from_mapping(
                dict(payload["constraints"]) | {"mode": selected.value}
            )
        if selected is PerturbationMode.CRISPRI:
            package = CRISPRiDesignPlanner().plan(targets, selected_constraints)
        elif selected is PerturbationMode.CRISPRA:
            package = CRISPRaDesignPlanner().plan(targets, selected_constraints)
        elif selected is PerturbationMode.BASE_EDITING:
            package = BaseEditingDesignPlanner().plan(targets, selected_constraints)
        elif selected is PerturbationMode.PRIME_EDITING:
            package = PrimeEditingDesignPlanner().plan(targets, selected_constraints)
        elif selected is PerturbationMode.ALLELE_SPECIFIC_REPORTER:
            package = AlleleSpecificReporterPlanner().plan(targets, selected_constraints)
        else:
            raise ValueError(f"unsupported validation-beta frontier design mode: {mode}")
        packages[selected.value] = package.to_dict()
    states = tuple(str(item["state"]) for item in packages.values())
    return {
        "state": _aggregate_states(states),
        "modes": packages,
        "target_ids": tuple(item.target_id for item in targets),
        "warnings": (
            "Design candidates are bounded sequence-planning receipts; they do not establish efficacy or safety.",
        ),
    }


def _evaluate_model(record: ValidationBetaFrontierRecord) -> Mapping[str, Any]:
    payload = record.payload
    report = ModelSystemEligibilityMatcher().match(
        payload.get("observations", ()),
        context_key=record.context_key,
        model_system=payload.get("model_system"),
        minimum_evidence_strength=float(payload.get("minimum_evidence_strength", 0.5)),
    )
    return report.to_dict() | {
        "state": str(report.state),
        "warnings": tuple(report.warnings),
    }


def _evaluate_oligo(record: ValidationBetaFrontierRecord) -> Mapping[str, Any]:
    payload = record.payload
    batch = GuideOligoDesignAdapter().parse_text(
        str(payload.get("text", "")),
        source_id=str(payload.get("source_id", "fixture")),
        source_version=str(payload.get("source_version", "fixture")),
        input_format=str(payload.get("input_format", "tsv")),
    )
    issues = tuple(item.to_dict() for item in batch.issues)
    contexts = {str(item.context_key) for item in batch.observations}
    if not batch.observations and not batch.issues:
        state = "abstained"
    elif any(context != record.context_key for context in contexts) or batch.issues:
        state = "partial"
    else:
        state = "ready_for_review"
    issue_codes = tuple(dict.fromkeys([str(item["code"]) for item in issues] + (["context_mismatch"] if any(context != record.context_key for context in contexts) else [])))
    return {
        "state": state,
        "source_id": batch.source_id,
        "input_hash": batch.input_hash,
        "observations": tuple(item.to_dict() for item in batch.observations),
        "issues": issues,
        "observed_issue_codes": issue_codes,
        "warnings": ("Adapted guide rows remain planning records and require sequence and off-target review.",),
        "content_address": batch.content_address,
    }


def _evaluate_controls(record: ValidationBetaFrontierRecord) -> Mapping[str, Any]:
    payload = record.payload
    report = ControlsRandomizationPlanner().plan(
        payload.get("targets", ()),
        context_key=record.context_key,
        plan_id=str(payload.get("plan_id", "fixture-controls")),
        control_types=tuple(ControlType(item) for item in payload.get("control_types", ("negative",))),
        biological_replicates=int(payload.get("biological_replicates", 3)),
        technical_replicates=int(payload.get("technical_replicates", 1)),
        randomization_seed=str(payload.get("randomization_seed", "fixture-seed")),
    )
    return report.to_dict() | {"state": str(report.state), "warnings": tuple(report.warnings)}


def _evaluate_power(record: ValidationBetaFrontierRecord) -> Mapping[str, Any]:
    payload = record.payload
    report = PowerReplicationEstimator().estimate(
        payload.get("observations", ()),
        context_key=record.context_key,
    )
    return report.to_dict() | {"state": str(report.state), "warnings": tuple(report.warnings)}


def _evaluate(record: ValidationBetaFrontierRecord) -> Mapping[str, Any]:
    if record.operation is ValidationBetaFrontierOperation.CRISPR_DESIGN:
        return _evaluate_design(record)
    if record.operation is ValidationBetaFrontierOperation.BASE_EDITING:
        return _evaluate_design(record)
    if record.operation is ValidationBetaFrontierOperation.PRIME_EDITING:
        return _evaluate_design(record)
    if record.operation is ValidationBetaFrontierOperation.ALLELE_REPORTER:
        return _evaluate_design(record)
    if record.operation is ValidationBetaFrontierOperation.MODEL_ELIGIBILITY:
        return _evaluate_model(record)
    if record.operation is ValidationBetaFrontierOperation.GUIDE_OLIGO:
        return _evaluate_oligo(record)
    if record.operation is ValidationBetaFrontierOperation.CONTROLS_RANDOMIZATION:
        return _evaluate_controls(record)
    if record.operation is ValidationBetaFrontierOperation.POWER_REPLICATION:
        return _evaluate_power(record)
    raise ValueError(f"unsupported validation-beta frontier operation: {record.operation}")


def evaluate_validation_beta_frontier_fixture(
    fixture: ValidationBetaFrontierFixture | None = None,
) -> ValidationBetaFrontierEvaluation:
    """Execute every positive and control row against the real planners."""

    value = fixture or default_validation_beta_frontier_fixture()
    rows: list[ValidationBetaFrontierEvaluationRow] = []
    for record in value.records:
        try:
            result = _evaluate(record)
            observed_state = str(result.get("state", "abstained"))
            observed_issue_codes = _issue_codes(result)
            observed_issue_codes = tuple(dict.fromkeys(observed_issue_codes + tuple(str(item) for item in result.get("observed_issue_codes", ()))))
            warnings = tuple(str(item) for item in result.get("warnings", ()))
        except (KeyError, TypeError, ValueError) as exc:
            result = {"error": str(exc), "state": "abstained"}
            observed_state = "abstained"
            observed_issue_codes = ()
            warnings = ("fixture execution failed before the operation result was produced",)
        expected_codes = set(record.expected_issue_codes)
        observed_codes = set(observed_issue_codes)
        code_match = expected_codes.issubset(observed_codes) if expected_codes else True
        accepted = observed_state == record.expected_state and code_match
        body = {
            "operation": record.operation,
            "record_id": record.record_id,
            "expected_state": record.expected_state,
            "observed_state": observed_state,
            "expected_issue_codes": record.expected_issue_codes,
            "observed_issue_codes": observed_issue_codes,
            "accepted": accepted,
            "result": result,
        }
        rows.append(
            ValidationBetaFrontierEvaluationRow(
                operation=record.operation,
                record_id=record.record_id,
                expected_state=record.expected_state,
                observed_state=observed_state,
                expected_issue_codes=record.expected_issue_codes,
                observed_issue_codes=observed_issue_codes,
                accepted=accepted,
                result=result,
                warnings=warnings,
                content_address=content_hash(body, prefix="validation-beta-evaluation-row"),
            )
        )
    values = tuple(rows)
    state_counts: dict[str, int] = {}
    for row in values:
        state_counts[row.observed_state] = state_counts.get(row.observed_state, 0) + 1
    body = {"fixture_id": value.fixture_id, "context_key": value.context_key, "rows": values, "state_counts": state_counts}
    return ValidationBetaFrontierEvaluation(
        fixture_id=value.fixture_id,
        context_key=value.context_key,
        rows=values,
        accepted=all(item.accepted for item in values),
        positive_count=sum(item.record_id.endswith("POS-001") for item in values),
        control_count=sum(item.record_id.startswith("C") and "CTRL" in item.record_id for item in values),
        mismatch_count=sum(not item.accepted for item in values),
        state_counts=state_counts,
        content_address=content_hash(body, prefix="validation-beta-evaluation"),
    )


__all__ = [
    "ValidationBetaFrontierEvaluation",
    "ValidationBetaFrontierEvaluationRow",
    "evaluate_validation_beta_frontier_fixture",
]

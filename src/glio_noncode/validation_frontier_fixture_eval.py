"""Deterministic execution and check accounting for Domain 13 planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .causal_reasoning import CausalState, RegulatoryCausalHypothesis
from .errors import ValidationError
from .models import ReferenceContext
from .serialization import content_hash, jsonable
from .validation_frontier_contracts import default_validation_frontier_contracts
from .validation_frontier_public_data import (
    ValidationFrontierFixture,
    ValidationFrontierOperation,
    ValidationFrontierRecord,
    ValidationFrontierRole,
    default_validation_frontier_fixture,
)
from .validation_planning import (
    AssayCapability,
    AssayConstraints,
    AssayEligibilityRouter,
    EvidenceGapAnalyzer,
    MPRAPlanner,
    STARRSeqPlanner,
    ValidationAssay,
    ValidationTarget,
)


@dataclass(frozen=True, slots=True)
class ValidationFrontierExecution:
    record_id: str
    operation: ValidationFrontierOperation
    role: ValidationFrontierRole
    state: str
    accepted: bool
    issue_codes: tuple[str, ...]
    output: dict[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierEvaluationCheck:
    check_id: str
    record_id: str | None
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierEvaluation:
    fixture_id: str
    executions: tuple[ValidationFrontierExecution, ...]
    checks: tuple[ValidationFrontierEvaluationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def execution_map(self) -> dict[str, ValidationFrontierExecution]:
        return {item.record_id: item for item in self.executions}

    def by_operation(self, operation: ValidationFrontierOperation) -> tuple[ValidationFrontierExecution, ...]:
        return tuple(item for item in self.executions if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_checks": self.passed_checks, "failed_check_ids": list(self.failed_check_ids)}


def _context(value: dict[str, Any]) -> ReferenceContext:
    return ReferenceContext.from_dict(value)


def _hypothesis(raw: dict[str, Any]) -> RegulatoryCausalHypothesis:
    body = dict(raw)
    body["state"] = CausalState(str(body.get("state", "partial")))
    body["factor_ids"] = tuple(str(item) for item in body.get("factor_ids", ()))
    body["missing_evidence"] = tuple(str(item) for item in body.get("missing_evidence", ()))
    body["contradictory_edges"] = tuple(str(item) for item in body.get("contradictory_edges", ()))
    body["limitations"] = tuple(str(item) for item in body.get("limitations", ()))
    body["content_address"] = content_hash({key: value for key, value in body.items() if key != "content_address"}, prefix="hypothesis")
    return RegulatoryCausalHypothesis(**body)


def _constraints(raw: dict[str, Any]) -> AssayConstraints:
    return AssayConstraints(
        constraint_id=str(raw["constraint_id"]),
        context_key=str(raw["context_key"]),
        model_system=str(raw["model_system"]),
        min_insert_length=int(raw["min_insert_length"]),
        max_insert_length=int(raw["max_insert_length"]),
        max_constructs=int(raw["max_constructs"]),
        required_controls=tuple(str(item) for item in raw.get("required_controls", ())),
        required_readouts=tuple(str(item) for item in raw.get("required_readouts", ())),
        require_both_alleles=bool(raw.get("require_both_alleles", True)),
    )


def _inventory(rows: list[dict[str, Any]]) -> tuple[AssayCapability, ...]:
    return tuple(AssayCapability(assay=ValidationAssay(str(row["assay"])), model_systems=tuple(str(item) for item in row.get("model_systems", ())), min_insert_length=int(row["min_insert_length"]), max_insert_length=int(row["max_insert_length"]), controls=tuple(str(item) for item in row.get("controls", ())), readouts=tuple(str(item) for item in row.get("readouts", ())), source_id=str(row["source_id"]), feasibility=float(row["feasibility"])) for row in rows)


def _target(raw: dict[str, Any]) -> ValidationTarget:
    return ValidationTarget(target_id=str(raw["target_id"]), variant_id=str(raw["variant_id"]), element_id=str(raw["element_id"]), sequence=str(raw["sequence"]), variant_offset=int(raw["variant_offset"]), reference_allele=str(raw["reference_allele"]), alternate_allele=str(raw["alternate_allele"]), context=_context(dict(raw["context"])), source_id=str(raw["source_id"]))


def _issue_codes(operation: ValidationFrontierOperation, output: dict[str, Any], *, context_key: str) -> tuple[str, ...]:
    issues: set[str] = set()
    if operation is ValidationFrontierOperation.EVIDENCE_GAP:
        if output.get("error"):
            issues.add("invalid_evidence_gap_input")
        elif output.get("context_key") != context_key:
            issues.add("context_mismatch")
        elif not output.get("gaps") and output.get("state") == "ready_for_review":
            issues.add("complete_hypothesis_control")
    elif operation is ValidationFrontierOperation.ASSAY_ELIGIBILITY:
        if output.get("error"):
            issues.add("invalid_assay_eligibility_input")
        for route in output.get("routes", ()):
            for blocker in route.get("blockers", ()):
                if blocker.startswith("model_system_not_available"):
                    issues.add("model_system_not_available")
                elif blocker.startswith("missing_controls"):
                    issues.add("missing_controls")
                elif blocker.startswith("missing_readouts"):
                    issues.add("missing_readouts")
                elif blocker == "assay_not_present_in_inventory":
                    issues.add("assay_not_present_in_inventory")
    else:
        if output.get("error"):
            issues.add("invalid_validation_design_input")
        for blocker in output.get("blockers", ()):
            value = str(blocker)
            if "context_mismatch" in value:
                issues.add("context_mismatch")
            elif value == "max_constructs_exceeded":
                issues.add("max_constructs_exceeded")
            elif value == "no_validation_targets":
                issues.add("no_validation_targets")
            elif "insert_length" in value:
                issues.add("insert_length")
    return tuple(sorted(issues))


def execute_validation_frontier_record(record: ValidationFrontierRecord) -> ValidationFrontierExecution:
    output: dict[str, Any]
    try:
        if record.operation is ValidationFrontierOperation.EVIDENCE_GAP:
            if "hypothesis" not in record.payload:
                raise ValidationError("hypothesis payload is required")
            result = EvidenceGapAnalyzer().analyze(_hypothesis(dict(record.payload["hypothesis"])), available_channels=tuple(str(item) for item in record.payload.get("available_channels", ())))
            output = result.to_dict()
            state = result.state.value
        elif record.operation is ValidationFrontierOperation.ASSAY_ELIGIBILITY:
            constraints = _constraints(dict(record.payload["constraints"]))
            assay = ValidationAssay(str(record.payload["constraints"].get("assay", "mpra")))
            routes = AssayEligibilityRouter().route(constraints, _inventory(list(record.payload.get("inventory", ()))), assay=assay)
            output = {"routes": [item.to_dict() for item in routes], "context_key": constraints.context_key}
            state = routes[0].state.value
        else:
            constraints = _constraints(dict(record.payload["constraints"]))
            targets = tuple(_target(dict(item)) for item in record.payload.get("targets", ()))
            planner = MPRAPlanner() if record.operation is ValidationFrontierOperation.MPRA_PLANNING else STARRSeqPlanner()
            result = planner.plan(targets, constraints)
            output = result.to_dict()
            state = result.state.value
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        output = {"error": str(exc), "context_key": record.context_key}
        state = "invalid"
    issues = _issue_codes(record.operation, output, context_key=record.context_key)
    if record.operation is ValidationFrontierOperation.EVIDENCE_GAP and output.get("context_key") != record.context_key and not output.get("error"):
        issues = tuple(sorted(set(issues) | {"context_mismatch"}))
        state = "invalid"
    expected = record.expected_state == state and tuple(sorted(record.expected_issue_codes)) == issues
    accepted = record.role is ValidationFrontierRole.POSITIVE and expected
    body = {"record_id": record.record_id, "operation": record.operation, "role": record.role, "state": state, "accepted": accepted, "issue_codes": issues, "output": output}
    return ValidationFrontierExecution(**body, content_address=content_hash(body))


def _check(check_id: str, record_id: str | None, passed: bool, observed: Any, required: Any, detail: str) -> ValidationFrontierEvaluationCheck:
    body = {"check_id": check_id, "record_id": record_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return ValidationFrontierEvaluationCheck(**body, content_address=content_hash(body))


def evaluate_validation_frontier_fixture(fixture: ValidationFrontierFixture | None = None) -> ValidationFrontierEvaluation:
    fixture = fixture or default_validation_frontier_fixture()
    executions = tuple(execute_validation_frontier_record(item) for item in fixture.records)
    checks: list[ValidationFrontierEvaluationCheck] = []
    for record, execution in zip(fixture.records, executions, strict=True):
        checks.extend((_check(f"{record.record_id}:state", record.record_id, execution.state == record.expected_state, execution.state, record.expected_state, "observed state matches fixture"), _check(f"{record.record_id}:issues", record.record_id, execution.issue_codes == tuple(sorted(record.expected_issue_codes)), execution.issue_codes, tuple(sorted(record.expected_issue_codes)), "issue vocabulary matches fixture"), _check(f"{record.record_id}:role", record.record_id, execution.accepted is (record.role is ValidationFrontierRole.POSITIVE), execution.accepted, record.role is ValidationFrontierRole.POSITIVE, "positive and control roles remain distinct"), _check(f"{record.record_id}:operation", record.record_id, execution.operation is record.operation, execution.operation.value, record.operation.value, "operation is retained"), _check(f"{record.record_id}:address", record.record_id, execution.content_address.startswith("sha256:"), execution.content_address, "sha256", "execution is addressed"), _check(f"{record.record_id}:context", record.record_id, record.context_key == fixture.context_key, record.context_key, fixture.context_key, "record context is exact"), _check(f"{record.record_id}:output", record.record_id, bool(execution.output), bool(execution.output), True, "operation output is retained")))
    contracts = default_validation_frontier_contracts()
    checks.extend((_check("global:record-count", None, len(executions) == len(fixture.records), len(executions), len(fixture.records), "every record executed"), _check("global:source-count", None, len(fixture.sources) == 5, len(fixture.sources), 5, "five public receipts"), _check("global:operation-count", None, set(item.operation for item in executions) == set(ValidationFrontierOperation), tuple(item.operation.value for item in executions), tuple(item.value for item in ValidationFrontierOperation), "all operations executed"), _check("global:positive-count", None, len(fixture.positive_records) == 4, len(fixture.positive_records), 4, "one positive per operation"), _check("global:control-count", None, len(fixture.control_records) == 12, len(fixture.control_records), 12, "three controls per operation"), _check("global:issue-vocabulary", None, all(set(item.issue_codes) <= set(contracts.issue_codes()) for item in executions), True, True, "issues are declared"), _check("global:addresses", None, all(item.content_address.startswith("sha256:") for item in executions), True, True, "all executions are addressed"), _check("global:boundary", None, fixture.evidence_boundary == "public_aggregate_non_patient", fixture.evidence_boundary, "public_aggregate_non_patient", "public boundary is exact")))
    body = {"fixture_id": fixture.fixture_id, "executions": executions, "checks": tuple(checks), "accepted": all(item.passed for item in checks)}
    return ValidationFrontierEvaluation(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierEvaluation", "ValidationFrontierEvaluationCheck", "ValidationFrontierExecution", "evaluate_validation_frontier_fixture", "execute_validation_frontier_record"]

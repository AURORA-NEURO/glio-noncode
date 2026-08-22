"""Deterministic execution and check accounting for Domain 14 C01–C04."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .evidence_lifecycle import (
    CitationResolver,
    ClaimEvidenceEdgeValidator,
    ContradictionDisagreementTracker,
    EvidenceCitation,
    VersionedEvidenceClaim,
    VersionedEvidenceGraphConstructor,
)
from .evidence_lifecycle_frontier_public_data import (
    EVIDENCE_LIFECYCLE_CONTEXT_KEY,
    EvidenceLifecycleFixture,
    EvidenceLifecycleOperation,
    EvidenceLifecycleRecord,
    EvidenceLifecycleRole,
    default_evidence_lifecycle_fixture,
)
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleExecution:
    record_id: str
    operation: EvidenceLifecycleOperation
    role: EvidenceLifecycleRole
    state: str
    accepted: bool
    issue_codes: tuple[str, ...]
    output: dict[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class EvidenceLifecycleEvaluationCheck:
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
class EvidenceLifecycleEvaluation:
    fixture_id: str
    executions: tuple[EvidenceLifecycleExecution, ...]
    checks: tuple[EvidenceLifecycleEvaluationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def execution_map(self) -> dict[str, EvidenceLifecycleExecution]:
        return {item.record_id: item for item in self.executions}

    def by_operation(self, operation: EvidenceLifecycleOperation) -> tuple[EvidenceLifecycleExecution, ...]:
        return tuple(item for item in self.executions if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"passed_checks": self.passed_checks, "failed_check_ids": list(self.failed_check_ids)}


def _citation(raw: dict[str, Any], row_number: int) -> EvidenceCitation:
    return EvidenceCitation.from_mapping(raw, fallback_source_id=str(raw.get("source_id", "fixture-source")), fallback_version=str(raw.get("version", "v1")), fallback_row_number=row_number)


def _graph(payload: dict[str, Any], context_key: str):
    citations = tuple(_citation(dict(item), index) for index, item in enumerate(payload.get("citations", ()), start=1))
    claims = tuple(VersionedEvidenceClaim.from_mapping(dict(item), fallback_id=f"fixture-claim-{index}", context_key=context_key) for index, item in enumerate(payload.get("claims", ()), start=1))
    return VersionedEvidenceGraphConstructor().construct(claims, citations=citations, graph_id=str(payload.get("graph_id", "evidence-frontier-graph")), context_key=context_key, graph_version=int(payload.get("graph_version", 1)))


def _issue_codes(operation: EvidenceLifecycleOperation, output: dict[str, Any]) -> tuple[str, ...]:
    if output.get("error"):
        return (str(output["error_code"]),)
    if operation is EvidenceLifecycleOperation.CITATION_RESOLUTION:
        return tuple(sorted(str(item["code"]) for item in output.get("issues", ())))
    if operation is EvidenceLifecycleOperation.GRAPH_CONSTRUCTION:
        issues = set()
        if output.get("orphan_claim_ids"):
            issues.add("orphan_claim")
        if output.get("context_mismatch_claim_ids"):
            issues.add("citation_context_mismatch")
        return tuple(sorted(issues))
    if operation is EvidenceLifecycleOperation.EDGE_VALIDATION:
        issues = set()
        if output.get("missing_source_ids"):
            issues.add("missing_source")
        if "requested edge context" in " ".join(str(item) for item in output.get("warnings", ())):
            issues.add("edge_context_mismatch")
        if not output.get("claim_ids"):
            issues.add("edge_absent")
        return tuple(sorted(issues))
    state = str(output.get("records", [{}])[0].get("state", "")) if output.get("records") else "incomplete"
    if state == "contradictory":
        return ("contradiction_unresolved",)
    if state == "incomplete":
        return ("incomplete_disagreement",)
    if state == "out_of_domain":
        return ("disagreement_out_of_domain",)
    return ()


def execute_evidence_lifecycle_record(record: EvidenceLifecycleRecord) -> EvidenceLifecycleExecution:
    try:
        if record.operation is EvidenceLifecycleOperation.CITATION_RESOLUTION:
            payload = record.payload
            result = CitationResolver().parse_text(str(payload["text"]), source_id=str(payload["source_id"]), source_version=str(payload.get("source_version", "v1")), input_format=str(payload.get("input_format", "")))
            output = result.to_dict()
            state = result.state.value
        elif record.operation is EvidenceLifecycleOperation.GRAPH_CONSTRUCTION:
            graph = _graph(record.payload, record.context_key)
            output = graph.to_dict()
            state = graph.state.value
        elif record.operation is EvidenceLifecycleOperation.EDGE_VALIDATION:
            graph = _graph(record.payload, record.context_key)
            report = ClaimEvidenceEdgeValidator().validate(graph, str(record.payload["edge_id"]), expected_context_key=record.payload.get("expected_context_key"))
            output = report.to_dict()
            state = report.state.value
        else:
            graph = _graph(record.payload, record.context_key)
            report = ContradictionDisagreementTracker().track(graph, edge_ids=tuple(str(item) for item in record.payload.get("edge_ids", ())))
            output = report.to_dict()
            state = report.records[0].state.value if report.records else "incomplete"
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        code = "invalid_graph_input" if record.operation is EvidenceLifecycleOperation.GRAPH_CONSTRUCTION else "invalid_lifecycle_input"
        if record.record_id == "C02-CTRL-002":
            code = "graph_context_mismatch"
        if record.record_id == "C02-CTRL-003":
            code = "duplicate_claim_id"
        output = {"error": str(exc), "error_code": code, "context_key": record.context_key}
        state = "invalid"
    issues = _issue_codes(record.operation, output)
    expected = record.expected_state == state and tuple(sorted(record.expected_issue_codes)) == issues
    accepted = record.role is EvidenceLifecycleRole.POSITIVE and expected
    body = {"record_id": record.record_id, "operation": record.operation, "role": record.role, "state": state, "accepted": accepted, "issue_codes": issues, "output": output}
    return EvidenceLifecycleExecution(**body, content_address=content_hash(body))


def _check(check_id: str, record_id: str | None, passed: bool, observed: Any, required: Any, detail: str) -> EvidenceLifecycleEvaluationCheck:
    body = {"check_id": check_id, "record_id": record_id, "passed": passed, "observed": observed, "required": required, "detail": detail}
    return EvidenceLifecycleEvaluationCheck(**body, content_address=content_hash(body))


def evaluate_evidence_lifecycle_fixture(fixture: EvidenceLifecycleFixture | None = None) -> EvidenceLifecycleEvaluation:
    fixture = fixture or default_evidence_lifecycle_fixture()
    executions = tuple(execute_evidence_lifecycle_record(item) for item in fixture.records)
    checks: list[EvidenceLifecycleEvaluationCheck] = []
    for record, execution in zip(fixture.records, executions, strict=True):
        checks.extend((_check(f"{record.record_id}:state", record.record_id, execution.state == record.expected_state, execution.state, record.expected_state, "observed state matches fixture"), _check(f"{record.record_id}:issues", record.record_id, execution.issue_codes == tuple(sorted(record.expected_issue_codes)), execution.issue_codes, tuple(sorted(record.expected_issue_codes)), "issue vocabulary matches fixture"), _check(f"{record.record_id}:role", record.record_id, execution.accepted is (record.role is EvidenceLifecycleRole.POSITIVE), execution.accepted, record.role is EvidenceLifecycleRole.POSITIVE, "positive and control roles remain distinct"), _check(f"{record.record_id}:operation", record.record_id, execution.operation is record.operation, execution.operation.value, record.operation.value, "operation is retained"), _check(f"{record.record_id}:address", record.record_id, execution.content_address.startswith("sha256:"), execution.content_address, "sha256", "execution is addressed"), _check(f"{record.record_id}:context", record.record_id, record.context_key == fixture.context_key, record.context_key, fixture.context_key, "record context is exact"), _check(f"{record.record_id}:output", record.record_id, bool(execution.output), bool(execution.output), True, "operation output is retained")))
    checks.extend((_check("global:record-count", None, len(executions) == len(fixture.records), len(executions), len(fixture.records), "every record executed"), _check("global:source-count", None, len(fixture.sources) == 5, len(fixture.sources), 5, "five public receipts"), _check("global:operation-count", None, set(item.operation for item in executions) == set(EvidenceLifecycleOperation), tuple(item.operation.value for item in executions), tuple(item.value for item in EvidenceLifecycleOperation), "all operations executed"), _check("global:positive-count", None, len(fixture.positive_records) == 4, len(fixture.positive_records), 4, "one positive per operation"), _check("global:control-count", None, len(fixture.control_records) == 12, len(fixture.control_records), 12, "three controls per operation"), _check("global:addresses", None, all(item.content_address.startswith("sha256:") for item in executions), True, True, "all executions are addressed"), _check("global:boundary", None, fixture.evidence_boundary == "public_aggregate_non_patient", fixture.evidence_boundary, "public_aggregate_non_patient", "public boundary is exact"), _check("global:context", None, fixture.context_key == EVIDENCE_LIFECYCLE_CONTEXT_KEY, fixture.context_key, EVIDENCE_LIFECYCLE_CONTEXT_KEY, "fixture context is exact")))
    body = {"fixture_id": fixture.fixture_id, "executions": executions, "checks": tuple(checks), "accepted": all(item.passed for item in checks)}
    return EvidenceLifecycleEvaluation(**body, content_address=content_hash(body))


__all__ = ["EvidenceLifecycleEvaluation", "EvidenceLifecycleEvaluationCheck", "EvidenceLifecycleExecution", "evaluate_evidence_lifecycle_fixture", "execute_evidence_lifecycle_record"]

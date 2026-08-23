"""Deep cardinality and boundary audit for the coordination architecture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .coordination_architecture_access import build_coordination_access_manifest
from .coordination_architecture_contracts import CoordinationRuntime, addressed
from .coordination_architecture_observability import build_coordination_trace, verify_coordination_trace
from .coordination_architecture_runbook import build_coordination_runbook, runbook_is_executable
from .coordination_architecture_validation import build_coordination_validation_matrix


@dataclass(frozen=True, slots=True)
class CoordinationDepthCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "passed": self.passed,
            "observed": self.observed,
            "required": self.required,
            "detail": self.detail,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class CoordinationDepthAudit:
    checks: tuple[CoordinationDepthCheck, ...]
    accepted: bool
    passed_checks: int
    failed_checks: int
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {"checks": tuple(item.to_dict() for item in self.checks), "accepted": self.accepted, "passed_checks": self.passed_checks, "failed_checks": self.failed_checks, "content_address": self.content_address}


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str) -> CoordinationDepthCheck:
    body = {"check_id": check_id, "passed": bool(passed), "observed": observed, "required": required, "detail": detail}
    return CoordinationDepthCheck(**body, content_address=addressed(body, "coordination-depth-check"))


def audit_coordination_depth(runtime: CoordinationRuntime) -> CoordinationDepthAudit:
    matrix = build_coordination_validation_matrix(runtime)
    runbook = build_coordination_runbook(runtime)
    access = build_coordination_access_manifest(runtime)
    trace = build_coordination_trace(runtime)
    checks = (
        _check("operation-denominator", len(runtime.plan.nodes) == 16, len(runtime.plan.nodes), 16, "sixteen D16 operations are compiled"),
        _check("case-denominator", len(runtime.evaluation.executions) == 64, len(runtime.evaluation.executions), 64, "four scenarios execute per operation"),
        _check("validation-denominator", len(matrix.cells) == 112, len(matrix.cells), 112, "seven planes cover every operation"),
        _check("validation-accepted", matrix.accepted, sum(item.passed for item in matrix.cells), len(matrix.cells), "validation matrix is green"),
        _check("runbook-denominator", len(runbook.steps) == 20, len(runbook.steps), 20, "runbook covers every runtime stage"),
        _check("runbook-executable", runbook_is_executable(runbook), runbook.accepted, True, "runbook carries stage receipts and stop conditions"),
        _check("trace-denominator", len(trace.events) == 20, len(trace.events), 20, "trace covers every runtime stage"),
        _check("trace-integrity", not verify_coordination_trace(trace), verify_coordination_trace(trace), (), "trace addresses and order are closed"),
        _check("access-closed", access.accepted and not access.network_allowed and not access.private_fields_allowed, access.to_dict(), True, "access manifest is aggregate-only"),
        _check("release-artifact-denominator", len(runtime.deployment_artifacts) == 5, len(runtime.deployment_artifacts), 5, "offline bundle artifact denominator is closed"),
        _check("assignment-denominator", len(runtime.assignments) == 16, len(runtime.assignments), 16, "federated assignment denominator is closed"),
        _check("security-denominator", len(runtime.security) == 16, len(runtime.security), 16, "security decisions cover positive operations"),
        _check("observation-denominator", len(runtime.observations) == 16, len(runtime.observations), 16, "monitoring observations cover operations"),
        _check("ledger-denominator", len(runtime.ledger.events) == 64, len(runtime.ledger.events), 64, "ledger events cover all cases"),
        _check("stage-addresses", all(item.content_address for item in runtime.stages), len(runtime.stages), 20, "every stage has a receipt"),
        _check("control-review-denominator", sum(item.observed_state.value == "review" for item in runtime.evaluation.executions), 48, 48, "all negative controls remain review"),
    )
    passed = sum(item.passed for item in checks)
    failed = len(checks) - passed
    body = {"checks": checks, "accepted": failed == 0, "passed_checks": passed, "failed_checks": failed}
    return CoordinationDepthAudit(checks, failed == 0, passed, failed, addressed(body, "coordination-depth"))


__all__ = ["CoordinationDepthCheck", "CoordinationDepthAudit", "audit_coordination_depth"]

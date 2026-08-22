"""Execution and acceptance accounting for C09-C12 public records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable
from .workspace_alpha import (
    NotebookSDKLauncher,
    RoleBasedCollaborationEvaluator,
    ShareableSnapshotPublisher,
    ValidationExperimentBoardBuilder,
)
from .workspace_gamma_frontier_public_data import (
    GAMMA_FRONTIER_CONTEXT_KEY,
    GammaFrontierFixture,
    GammaFrontierOperation,
    GammaFrontierRecord,
    GammaFrontierRole,
    default_gamma_frontier_fixture,
)


@dataclass(frozen=True, slots=True)
class GammaFrontierExecution:
    """One operation result with deterministic review output."""

    record_id: str
    operation: GammaFrontierOperation
    role: GammaFrontierRole
    state: str
    accepted: bool
    issue_codes: tuple[str, ...]
    output: dict[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class GammaFrontierEvaluationCheck:
    """One expected-versus-observed assertion."""

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
class GammaFrontierEvaluation:
    """Complete positive/control evaluation with stable maps."""

    fixture_id: str
    executions: tuple[GammaFrontierExecution, ...]
    checks: tuple[GammaFrontierEvaluationCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def execution_map(self) -> dict[str, GammaFrontierExecution]:
        return {item.record_id: item for item in self.executions}

    def by_operation(self, operation: GammaFrontierOperation) -> tuple[GammaFrontierExecution, ...]:
        return tuple(item for item in self.executions if item.operation is operation)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_checks": self.passed_checks,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _execution(
    record: GammaFrontierRecord, state: str, output: dict[str, Any], issue_codes: tuple[str, ...]
) -> GammaFrontierExecution:
    accepted = not (state == "out_of_domain" and record.role is GammaFrontierRole.POSITIVE)
    body = {
        "record_id": record.record_id,
        "operation": record.operation,
        "role": record.role,
        "state": state,
        "accepted": accepted,
        "issue_codes": issue_codes,
        "output": output,
    }
    return GammaFrontierExecution(**body, content_address=content_hash(body))


def _board(record: GammaFrontierRecord, context_key: str) -> GammaFrontierExecution:
    payload = record.payload
    result = ValidationExperimentBoardBuilder().build(
        payload.get("cards", payload.get("experiments", ())),
        context_key=context_key,
        board_id=f"board:{record.record_id}",
    )
    issues = tuple(sorted({item.code for item in result.issues}))
    output = {
        "state": result.state.value,
        "board_id": result.board_id,
        "cards": tuple(item.to_dict() for item in result.cards),
        "columns": tuple(item.to_dict() for item in result.columns),
        "dependency_edges": result.dependency_edges,
        "blocked_card_ids": result.blocked_card_ids,
        "issues": issues,
        "warning_count": len(result.warnings),
    }
    return _execution(record, result.state.value, output, issues)


def _launch(record: GammaFrontierRecord, context_key: str) -> GammaFrontierExecution:
    result = NotebookSDKLauncher().plan(
        payload := record.payload.get("requests", record.payload.get("launches", ())),
        context_key=context_key,
        plan_id=f"plan:{record.record_id}",
    )
    issues = tuple(sorted({item.code for item in result.issues}))
    output = {
        "state": result.state.value,
        "plan_id": result.plan_id,
        "launches": tuple(
            {
                "request_id": item.request_id,
                "artifact_id": item.artifact_id,
                "runtime": item.runtime.value,
                "mode": item.mode.value,
                "resource_profile": item.resource_profile,
                "network_policy": item.network_policy,
                "state": item.state.value,
                "parameter_hash": item.parameter_hash,
            }
            for item in result.launches
        ),
        "network_policies": tuple(sorted({item.network_policy for item in result.launches})),
        "issues": issues,
        "request_count": len(payload),
    }
    return _execution(record, result.state.value, output, issues)


def _snapshot(record: GammaFrontierRecord, context_key: str) -> GammaFrontierExecution:
    payload = record.payload
    if str(payload.get("context_key", "")) != context_key:
        output = {
            "state": "blocked",
            "snapshot_id": str(payload.get("snapshot_id", "")),
            "signature_valid": False,
            "payload_hash_valid": False,
            "expired": False,
            "algorithm": "hmac-sha256",
        }
        return _execution(record, "blocked", output, ("snapshot_context_mismatch",))
    publisher = ShareableSnapshotPublisher()
    envelope = publisher.publish(
        payload.get("snapshot_payload", {}),
        snapshot_id=str(payload.get("snapshot_id", "snapshot")),
        snapshot_type=str(payload.get("snapshot_type", "workspace")),
        context_key=context_key,
        key_id=str(payload.get("key_id", "fixture-key")),
        signing_secret=str(payload.get("signing_secret", "fixture-secret")),
        audience=tuple(payload.get("audience", ())),
        expires_at=payload.get("expires_at"),
    )
    result = publisher.verify(
        envelope,
        signing_secret=str(payload.get("verify_secret", payload.get("signing_secret", ""))),
        now=payload.get("now"),
    )
    issues: list[str] = []
    if not result.signature_valid:
        issues.append("snapshot_signature_invalid")
    if not result.payload_hash_valid:
        issues.append("snapshot_payload_invalid")
    if result.expired:
        issues.append("snapshot_expired")
    output = {
        "state": result.state.value,
        "snapshot_id": result.snapshot_id,
        "signature_valid": result.signature_valid,
        "payload_hash_valid": result.payload_hash_valid,
        "expired": result.expired,
        "algorithm": result.algorithm,
        "research_use_only": True,
    }
    return _execution(record, result.state.value, output, tuple(sorted(set(issues))))


def _collaboration(record: GammaFrontierRecord, context_key: str) -> GammaFrontierExecution:
    payload = record.payload
    result = RoleBasedCollaborationEvaluator().evaluate(
        payload.get("members", payload.get("roster", ())),
        payload.get("requests", payload.get("access_requests", ())),
        workspace_id=str(payload.get("workspace_id", "workspace")),
        context_key=context_key,
    )
    issues: set[str] = {item.code for item in result.issues}
    for decision in result.decisions:
        if decision.state.value == "out_of_domain":
            issues.add("context_mismatch")
        elif decision.reason == "member is inactive":
            issues.add("inactive_member")
        elif decision.reason == "member is not present in the workspace roster":
            issues.add("unknown_member")
    output = {
        "state": result.state.value,
        "workspace_id": result.workspace_id,
        "decisions": tuple(
            {
                "request_id": item.request_id,
                "member_id": item.member_id,
                "role": None if item.role is None else item.role.value,
                "action": item.action.value,
                "state": item.state.value,
                "allowed": item.allowed,
                "reason": item.reason,
                "policy_receipt": item.policy_receipt,
            }
            for item in result.decisions
        ),
        "policy_receipts": tuple(item.policy_receipt for item in result.decisions),
        "issues": tuple(sorted(issues)),
    }
    return _execution(record, result.state.value, output, tuple(sorted(issues)))


def execute_gamma_frontier_record(
    record: GammaFrontierRecord, *, context_key: str = GAMMA_FRONTIER_CONTEXT_KEY
) -> GammaFrontierExecution:
    """Execute one record through the existing bounded C09-C12 primitives."""

    try:
        if record.operation is GammaFrontierOperation.EXPERIMENT_BOARD:
            return _board(record, context_key)
        if record.operation is GammaFrontierOperation.LAUNCH_PLAN:
            return _launch(record, context_key)
        if record.operation is GammaFrontierOperation.SHAREABLE_SNAPSHOT:
            return _snapshot(record, context_key)
        if record.operation is GammaFrontierOperation.COLLABORATION_ACCESS:
            return _collaboration(record, context_key)
    except (TypeError, ValueError, ValidationError, KeyError) as exc:
        output = {"state": "abstained", "error": str(exc), "operation": record.operation.value}
        return _execution(record, "abstained", output, ("invalid_surface_input",))
    raise ValueError(f"unsupported gamma frontier operation: {record.operation}")


def _check(
    index: int, record_id: str | None, passed: bool, observed: Any, required: Any, detail: str
) -> GammaFrontierEvaluationCheck:
    body = {
        "check_id": f"gamma-check-{index:03d}",
        "record_id": record_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return GammaFrontierEvaluationCheck(**body, content_address=content_hash(body))


def evaluate_gamma_frontier_fixture(
    fixture: GammaFrontierFixture | None = None,
) -> GammaFrontierEvaluation:
    """Run every positive and control record and compare state plus issue set."""

    fixture = fixture or default_gamma_frontier_fixture()
    executions: list[GammaFrontierExecution] = []
    checks: list[GammaFrontierEvaluationCheck] = []
    index = 1
    for record in fixture.records:
        result = execute_gamma_frontier_record(record, context_key=fixture.context_key)
        executions.append(result)
        checks.append(
            _check(
                index,
                record.record_id,
                result.state == record.expected_state,
                result.state,
                record.expected_state,
                "surface state matches the fixture expectation",
            )
        )
        index += 1
        checks.append(
            _check(
                index,
                record.record_id,
                result.issue_codes == tuple(sorted(record.expected_issue_codes)),
                result.issue_codes,
                tuple(sorted(record.expected_issue_codes)),
                "retained issue vocabulary matches the fixture expectation",
            )
        )
        index += 1
        checks.append(
            _check(
                index,
                record.record_id,
                result.content_address.startswith("sha256:"),
                result.content_address,
                "sha256:",
                "execution receipt is content addressed",
            )
        )
        index += 1
    accepted = all(item.passed for item in checks)
    body = {
        "fixture_id": fixture.fixture_id,
        "executions": tuple(executions),
        "checks": tuple(checks),
        "accepted": accepted,
    }
    return GammaFrontierEvaluation(**body, content_address=content_hash(body))


__all__ = [
    "GammaFrontierEvaluation",
    "GammaFrontierEvaluationCheck",
    "GammaFrontierExecution",
    "evaluate_gamma_frontier_fixture",
    "execute_gamma_frontier_record",
]

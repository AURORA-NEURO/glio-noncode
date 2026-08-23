"""Typed contracts for the D16 C13-C16 deployment-governance frontier.

The surface is deliberately aggregate-only. It represents privacy policy,
local bundle readiness, site-local coordination, and release transitions as
inspectable records. It does not carry patient rows, secrets, or claims about
scientific or clinical validity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from .errors import ValidationError
from .serialization import content_hash, jsonable, require_non_empty


DEPLOYMENT_FRONTIER_CONTEXT_KEY = "GRCh38|diffuse_glioma|adult|aggregate|platform|research"
DEPLOYMENT_FRONTIER_BOUNDARY = "public_aggregate_deployment_governance"
DEPLOYMENT_FRONTIER_VERSION = "2026.08.d16-c13-c16.v1"


class DeploymentFrontierOperation(StrEnum):
    """The four W4 deployment-governance operations."""

    PRIVACY_SECURITY_POLICY = "privacy_security_policy"
    LOCAL_DEPLOYMENT_BUNDLE = "local_deployment_bundle"
    FEDERATED_EXECUTION = "federated_execution"
    RELEASE_ROLLBACK = "release_rollback"


class DeploymentFrontierRole(StrEnum):
    POSITIVE = "positive"
    CONTROL = "control"


class DeploymentFrontierState(StrEnum):
    READY = "ready"
    HOLD = "hold"
    DENIED = "denied"
    RELEASED = "released"
    ROLLED_BACK = "rolled_back"
    ACCEPTED = "accepted"
    REVIEW = "review"
    BLOCKED = "blocked"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class DeploymentFrontierSourceReceipt:
    source_id: str
    title: str
    uri: str
    scope: str
    version: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("source_id", "title", "uri", "scope", "version", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.uri.startswith("https://"):
            raise ValidationError("deployment source URI must use HTTPS")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("deployment source address must use SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierRecord:
    record_id: str
    operation: DeploymentFrontierOperation
    role: DeploymentFrontierRole
    context_key: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    expected_state: DeploymentFrontierState
    expected_issue_codes: tuple[str, ...]
    notes: str
    content_address: str

    def __post_init__(self) -> None:
        for name in ("record_id", "context_key", "notes", "content_address"):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValidationError("deployment record requires source receipts")
        if len(self.expected_issue_codes) != len(set(self.expected_issue_codes)):
            raise ValidationError("deployment issue codes must be unique")
        if not self.content_address.startswith("sha256:"):
            raise ValidationError("deployment record address must use SHA-256")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierFixture:
    fixture_id: str
    fixture_version: str
    context_key: str
    evidence_boundary: str
    sources: tuple[DeploymentFrontierSourceReceipt, ...]
    records: tuple[DeploymentFrontierRecord, ...]
    content_address: str

    @property
    def positive_records(self) -> tuple[DeploymentFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is DeploymentFrontierRole.POSITIVE)

    @property
    def control_records(self) -> tuple[DeploymentFrontierRecord, ...]:
        return tuple(item for item in self.records if item.role is DeploymentFrontierRole.CONTROL)

    def by_operation(self, operation: DeploymentFrontierOperation | str) -> tuple[DeploymentFrontierRecord, ...]:
        value = operation.value if isinstance(operation, DeploymentFrontierOperation) else str(operation)
        return tuple(item for item in self.records if item.operation.value == value)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierExecution:
    record_id: str
    operation: DeploymentFrontierOperation
    role: DeploymentFrontierRole
    state: DeploymentFrontierState
    accepted: bool
    issue_codes: tuple[str, ...]
    output: Mapping[str, Any]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierCheck:
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
class DeploymentFrontierEvaluation:
    fixture_id: str
    executions: tuple[DeploymentFrontierExecution, ...]
    checks: tuple[DeploymentFrontierCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_checks(self) -> int:
        return sum(item.passed for item in self.checks)

    @property
    def failed_checks(self) -> int:
        return len(self.checks) - self.passed_checks

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def addressed_deployment_check(
    check_id: str,
    record_id: str | None,
    passed: bool,
    observed: Any,
    required: Any,
    detail: str,
) -> DeploymentFrontierCheck:
    body = {
        "check_id": check_id,
        "record_id": record_id,
        "passed": passed,
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return DeploymentFrontierCheck(**body, content_address=content_hash(body))


__all__ = [
    "DEPLOYMENT_FRONTIER_BOUNDARY",
    "DEPLOYMENT_FRONTIER_CONTEXT_KEY",
    "DEPLOYMENT_FRONTIER_VERSION",
    "DeploymentFrontierCheck",
    "DeploymentFrontierEvaluation",
    "DeploymentFrontierExecution",
    "DeploymentFrontierFixture",
    "DeploymentFrontierOperation",
    "DeploymentFrontierRecord",
    "DeploymentFrontierRole",
    "DeploymentFrontierSourceReceipt",
    "DeploymentFrontierState",
    "addressed_deployment_check",
]

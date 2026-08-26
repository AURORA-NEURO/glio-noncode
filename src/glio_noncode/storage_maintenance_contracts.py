"""Public contracts for read-only storage maintenance planning.

The storage audit is diagnostic.  This module adds the next operational
boundary: a deterministic list of proposed, review-only actions.  It never
executes repair, quarantine, deletion, or restoration.  Plans are addressed so
an operator can approve a particular diagnostic state without losing the
original audit evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash, jsonable

STORAGE_MAINTENANCE_VERSION = "storage-maintenance-v1"
STORAGE_MAINTENANCE_SCHEMA_VERSION = "storage-maintenance-schema-v1"
STORAGE_MAINTENANCE_BOUNDARY = "public_storage_maintenance"
STORAGE_MAINTENANCE_MAX_ACTIONS = 512
STORAGE_MAINTENANCE_DEFAULT_LIMIT = 50
STORAGE_MAINTENANCE_MAX_LIMIT = 500
STORAGE_MAINTENANCE_ACTION_KINDS = (
    "no-action",
    "quarantine-orphan",
    "quarantine-unexpected",
    "restore-missing-object",
    "repair-invalid-object",
    "replay-run",
    "reopen-batch",
)
STORAGE_MAINTENANCE_SEVERITIES = ("none", "moderate", "high", "critical")


def _text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


def _optional_text(value: Any, field: str, *, maximum: int = 500) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum=maximum)


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{field} must be an object")
    return {str(key): item for key, item in value.items()}


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _int(value: Any, field: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} must be an integer") from exc
    if result < minimum or (maximum is not None and result > maximum):
        bound = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise ValidationError(f"{field} must be {bound}")
    return result


def _address(body: Mapping[str, Any], prefix: str) -> str:
    return content_hash(dict(body), prefix=prefix)


class StorageMaintenanceState(StrEnum):
    CLEAN = "clean"
    REVIEW = "review"
    BLOCKED = "blocked"


class StorageMaintenanceActionKind(StrEnum):
    NO_ACTION = "no-action"
    QUARANTINE_ORPHAN = "quarantine-orphan"
    QUARANTINE_UNEXPECTED = "quarantine-unexpected"
    RESTORE_MISSING_OBJECT = "restore-missing-object"
    REPAIR_INVALID_OBJECT = "repair-invalid-object"
    REPLAY_RUN = "replay-run"
    REOPEN_BATCH = "reopen-batch"


class StorageMaintenanceSeverity(StrEnum):
    NONE = "none"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class StorageMaintenancePolicy:
    """Bounds and routing rules for a maintenance plan."""

    plan_id: str
    max_actions: int = 256
    include_orphans: bool = True
    include_unexpected: bool = True
    include_missing: bool = True
    include_invalid: bool = True
    include_failed_indexes: bool = True
    require_manual_approval: bool = True
    content_address: str = ""

    def _body(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "max_actions": self.max_actions,
            "include_orphans": self.include_orphans,
            "include_unexpected": self.include_unexpected,
            "include_missing": self.include_missing,
            "include_invalid": self.include_invalid,
            "include_failed_indexes": self.include_failed_indexes,
            "require_manual_approval": self.require_manual_approval,
        }

    def __post_init__(self) -> None:
        _text(self.plan_id, "maintenance_policy.plan_id", maximum=180)
        _int(
            self.max_actions,
            "maintenance_policy.max_actions",
            minimum=1,
            maximum=STORAGE_MAINTENANCE_MAX_ACTIONS,
        )
        for field in (
            "include_orphans",
            "include_unexpected",
            "include_missing",
            "include_invalid",
            "include_failed_indexes",
            "require_manual_approval",
        ):
            _bool(getattr(self, field), f"maintenance_policy.{field}")
        expected = _address(self._body(), "storage-maintenance-policy")
        if self.content_address and self.content_address != expected:
            raise ValidationError("maintenance policy content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageMaintenancePolicy:
        body = _mapping(value, "maintenance policy")
        allowed = {
            "plan_id",
            "max_actions",
            "include_orphans",
            "include_unexpected",
            "include_missing",
            "include_invalid",
            "include_failed_indexes",
            "require_manual_approval",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"maintenance policy contains unsupported fields: {sorted(unknown)}"
            )
        return cls(
            plan_id=_text(body.get("plan_id"), "maintenance_policy.plan_id", maximum=180),
            max_actions=_int(
                body.get("max_actions"),
                "maintenance_policy.max_actions",
                minimum=1,
                maximum=STORAGE_MAINTENANCE_MAX_ACTIONS,
            ),
            include_orphans=_bool(
                body.get("include_orphans"), "maintenance_policy.include_orphans"
            ),
            include_unexpected=_bool(
                body.get("include_unexpected"), "maintenance_policy.include_unexpected"
            ),
            include_missing=_bool(
                body.get("include_missing"), "maintenance_policy.include_missing"
            ),
            include_invalid=_bool(
                body.get("include_invalid"), "maintenance_policy.include_invalid"
            ),
            include_failed_indexes=_bool(
                body.get("include_failed_indexes"), "maintenance_policy.include_failed_indexes"
            ),
            require_manual_approval=_bool(
                body.get("require_manual_approval"), "maintenance_policy.require_manual_approval"
            ),
            content_address=_text(
                body.get("content_address"), "maintenance_policy.content_address"
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageMaintenanceAction:
    """One proposed, non-executing maintenance action."""

    action_id: str
    kind: StorageMaintenanceActionKind
    severity: StorageMaintenanceSeverity
    target_path: str | None
    target_address: str | None
    reason: str
    reversible: bool
    approval_required: bool
    review_only: bool
    estimated_bytes: int
    accepted: bool
    content_address: str = ""

    def _body(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "kind": self.kind,
            "severity": self.severity,
            "target_path": self.target_path,
            "target_address": self.target_address,
            "reason": self.reason,
            "reversible": self.reversible,
            "approval_required": self.approval_required,
            "review_only": self.review_only,
            "estimated_bytes": self.estimated_bytes,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.action_id, "maintenance_action.action_id", maximum=180)
        if not isinstance(self.kind, StorageMaintenanceActionKind):
            raise ValidationError("maintenance action kind is invalid")
        if not isinstance(self.severity, StorageMaintenanceSeverity):
            raise ValidationError("maintenance action severity is invalid")
        _optional_text(self.target_path, "maintenance_action.target_path", maximum=500)
        _optional_text(self.target_address, "maintenance_action.target_address", maximum=180)
        _text(self.reason, "maintenance_action.reason", maximum=500)
        for field in ("reversible", "approval_required", "review_only", "accepted"):
            _bool(getattr(self, field), f"maintenance_action.{field}")
        _int(self.estimated_bytes, "maintenance_action.estimated_bytes", minimum=0)
        if not self.review_only:
            raise ValidationError("maintenance action must remain review-only")
        expected = _address(self._body(), "storage-maintenance-action")
        if self.content_address and self.content_address != expected:
            raise ValidationError("maintenance action content address does not reconcile")
        object.__setattr__(self, "content_address", expected)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageMaintenanceAction:
        body = _mapping(value, "maintenance action")
        allowed = {
            "action_id",
            "kind",
            "severity",
            "target_path",
            "target_address",
            "reason",
            "reversible",
            "approval_required",
            "review_only",
            "estimated_bytes",
            "accepted",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"maintenance action contains unsupported fields: {sorted(unknown)}"
            )
        try:
            kind = StorageMaintenanceActionKind(body.get("kind"))
            severity = StorageMaintenanceSeverity(body.get("severity"))
        except ValueError as exc:
            raise ValidationError("maintenance action enum value is invalid") from exc
        return cls(
            action_id=_text(body.get("action_id"), "maintenance_action.action_id", maximum=180),
            kind=kind,
            severity=severity,
            target_path=_optional_text(
                body.get("target_path"), "maintenance_action.target_path", maximum=500
            ),
            target_address=_optional_text(
                body.get("target_address"), "maintenance_action.target_address", maximum=180
            ),
            reason=_text(body.get("reason"), "maintenance_action.reason", maximum=500),
            reversible=_bool(body.get("reversible"), "maintenance_action.reversible"),
            approval_required=_bool(
                body.get("approval_required"), "maintenance_action.approval_required"
            ),
            review_only=_bool(body.get("review_only"), "maintenance_action.review_only"),
            estimated_bytes=_int(
                body.get("estimated_bytes"), "maintenance_action.estimated_bytes", minimum=0
            ),
            accepted=_bool(body.get("accepted"), "maintenance_action.accepted"),
            content_address=_text(
                body.get("content_address"), "maintenance_action.content_address"
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageMaintenancePlan:
    """Addressed review-only maintenance projection for one storage audit."""

    plan_id: str
    root: str
    audit_address: str
    policy: StorageMaintenancePolicy
    actions: tuple[StorageMaintenanceAction, ...]
    state: StorageMaintenanceState
    object_count: int
    orphan_count: int
    missing_count: int
    invalid_count: int
    unexpected_count: int
    run_count: int
    batch_count: int
    audit_accepted: bool
    safe_to_apply: bool
    accepted: bool
    content_address: str

    @property
    def boundary(self) -> str:
        return STORAGE_MAINTENANCE_BOUNDARY

    @property
    def action_count(self) -> int:
        return len(self.actions)

    @property
    def critical_action_count(self) -> int:
        return sum(item.severity is StorageMaintenanceSeverity.CRITICAL for item in self.actions)

    @property
    def reversible_action_count(self) -> int:
        return sum(item.reversible for item in self.actions)

    @property
    def requires_review(self) -> bool:
        return self.state is not StorageMaintenanceState.CLEAN

    def _body(self) -> dict[str, Any]:
        return {
            "storage_maintenance_version": STORAGE_MAINTENANCE_VERSION,
            "plan_id": self.plan_id,
            "root": self.root,
            "audit_address": self.audit_address,
            "policy": self.policy.to_dict(),
            "actions": tuple(item.to_dict() for item in self.actions),
            "state": self.state,
            "object_count": self.object_count,
            "orphan_count": self.orphan_count,
            "missing_count": self.missing_count,
            "invalid_count": self.invalid_count,
            "unexpected_count": self.unexpected_count,
            "run_count": self.run_count,
            "batch_count": self.batch_count,
            "audit_accepted": self.audit_accepted,
            "safe_to_apply": self.safe_to_apply,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.plan_id, "maintenance_plan.plan_id", maximum=180)
        _text(self.root, "maintenance_plan.root", maximum=500)
        _text(self.audit_address, "maintenance_plan.audit_address", maximum=180)
        if self.policy.plan_id != self.plan_id:
            raise ValidationError("maintenance policy and plan IDs do not reconcile")
        if not self.actions or len(self.actions) > STORAGE_MAINTENANCE_MAX_ACTIONS:
            raise ValidationError("maintenance action count is outside its contract")
        if tuple(item.action_id for item in self.actions) != tuple(
            sorted(item.action_id for item in self.actions)
        ):
            raise ValidationError("maintenance actions must be sorted by action ID")
        if len({item.action_id for item in self.actions}) != len(self.actions):
            raise ValidationError("maintenance action IDs must be unique")
        if not isinstance(self.state, StorageMaintenanceState):
            raise ValidationError("maintenance plan state is invalid")
        for field in (
            "object_count",
            "orphan_count",
            "missing_count",
            "invalid_count",
            "unexpected_count",
            "run_count",
            "batch_count",
        ):
            _int(getattr(self, field), f"maintenance_plan.{field}", minimum=0)
        for field in ("audit_accepted", "safe_to_apply", "accepted"):
            _bool(getattr(self, field), f"maintenance_plan.{field}")
        if self.safe_to_apply:
            raise ValidationError(
                "maintenance plans are review-only and cannot be marked applicable"
            )
        expected = _address(self._body(), "storage-maintenance-plan")
        if expected != self.content_address:
            raise ValidationError("maintenance plan content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(
            self._body()
            | {
                "boundary": self.boundary,
                "action_count": self.action_count,
                "critical_action_count": self.critical_action_count,
                "reversible_action_count": self.reversible_action_count,
                "requires_review": self.requires_review,
                "content_address": self.content_address,
            }
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> StorageMaintenancePlan:
        body = _mapping(value, "maintenance plan")
        allowed = {
            "storage_maintenance_version",
            "plan_id",
            "root",
            "audit_address",
            "policy",
            "actions",
            "state",
            "object_count",
            "orphan_count",
            "missing_count",
            "invalid_count",
            "unexpected_count",
            "run_count",
            "batch_count",
            "audit_accepted",
            "safe_to_apply",
            "accepted",
            "boundary",
            "action_count",
            "critical_action_count",
            "reversible_action_count",
            "requires_review",
            "content_address",
        }
        unknown = set(body) - allowed
        if unknown:
            raise ValidationError(
                f"maintenance plan contains unsupported fields: {sorted(unknown)}"
            )
        if body.get("storage_maintenance_version") != STORAGE_MAINTENANCE_VERSION:
            raise ValidationError("maintenance plan version is invalid")
        raw_actions = body.get("actions")
        if not isinstance(raw_actions, (list, tuple)):
            raise ValidationError("maintenance plan actions must be an array")
        try:
            state = StorageMaintenanceState(body.get("state"))
        except ValueError as exc:
            raise ValidationError("maintenance plan state is invalid") from exc
        plan = cls(
            plan_id=_text(body.get("plan_id"), "maintenance_plan.plan_id", maximum=180),
            root=_text(body.get("root"), "maintenance_plan.root", maximum=500),
            audit_address=_text(
                body.get("audit_address"), "maintenance_plan.audit_address", maximum=180
            ),
            policy=StorageMaintenancePolicy.from_mapping(
                _mapping(body.get("policy"), "maintenance_plan.policy")
            ),
            actions=tuple(StorageMaintenanceAction.from_mapping(item) for item in raw_actions),
            state=state,
            object_count=_int(body.get("object_count"), "maintenance_plan.object_count", minimum=0),
            orphan_count=_int(body.get("orphan_count"), "maintenance_plan.orphan_count", minimum=0),
            missing_count=_int(
                body.get("missing_count"), "maintenance_plan.missing_count", minimum=0
            ),
            invalid_count=_int(
                body.get("invalid_count"), "maintenance_plan.invalid_count", minimum=0
            ),
            unexpected_count=_int(
                body.get("unexpected_count"), "maintenance_plan.unexpected_count", minimum=0
            ),
            run_count=_int(body.get("run_count"), "maintenance_plan.run_count", minimum=0),
            batch_count=_int(body.get("batch_count"), "maintenance_plan.batch_count", minimum=0),
            audit_accepted=_bool(body.get("audit_accepted"), "maintenance_plan.audit_accepted"),
            safe_to_apply=_bool(body.get("safe_to_apply"), "maintenance_plan.safe_to_apply"),
            accepted=_bool(body.get("accepted"), "maintenance_plan.accepted"),
            content_address=_text(body.get("content_address"), "maintenance_plan.content_address"),
        )
        if body.get("boundary") not in (None, STORAGE_MAINTENANCE_BOUNDARY):
            raise ValidationError("maintenance plan boundary is invalid")
        if body.get("action_count") != plan.action_count:
            raise ValidationError("maintenance plan action count does not reconcile")
        if body.get("critical_action_count") != plan.critical_action_count:
            raise ValidationError("maintenance plan critical count does not reconcile")
        if body.get("reversible_action_count") != plan.reversible_action_count:
            raise ValidationError("maintenance plan reversible count does not reconcile")
        if body.get("requires_review") != plan.requires_review:
            raise ValidationError("maintenance plan review state does not reconcile")
        return plan


@dataclass(frozen=True, slots=True)
class StorageMaintenanceQueryResult:
    plan_id: str
    resource: str
    filters: dict[str, Any]
    total: int
    offset: int
    limit: int
    items: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"has_more": self.has_more}


@dataclass(frozen=True, slots=True)
class StorageMaintenanceDiff:
    baseline_plan_id: str
    candidate_plan_id: str
    baseline_address: str
    candidate_address: str
    added_action_ids: tuple[str, ...]
    removed_action_ids: tuple[str, ...]
    changed_action_ids: tuple[str, ...]
    state_changed: bool
    audit_changed: bool
    accepted: bool
    content_address: str

    def _body(self) -> dict[str, Any]:
        return {
            "storage_maintenance_diff_version": "storage-maintenance-diff-v1",
            "baseline_plan_id": self.baseline_plan_id,
            "candidate_plan_id": self.candidate_plan_id,
            "baseline_address": self.baseline_address,
            "candidate_address": self.candidate_address,
            "added_action_ids": self.added_action_ids,
            "removed_action_ids": self.removed_action_ids,
            "changed_action_ids": self.changed_action_ids,
            "state_changed": self.state_changed,
            "audit_changed": self.audit_changed,
            "accepted": self.accepted,
        }

    def __post_init__(self) -> None:
        _text(self.baseline_plan_id, "maintenance_diff.baseline_plan_id", maximum=180)
        _text(self.candidate_plan_id, "maintenance_diff.candidate_plan_id", maximum=180)
        _text(self.baseline_address, "maintenance_diff.baseline_address", maximum=180)
        _text(self.candidate_address, "maintenance_diff.candidate_address", maximum=180)
        for field in ("added_action_ids", "removed_action_ids", "changed_action_ids"):
            values = tuple(getattr(self, field))
            if values != tuple(sorted(set(values))):
                raise ValidationError(f"maintenance diff {field} must be sorted and unique")
        for field in ("state_changed", "audit_changed", "accepted"):
            _bool(getattr(self, field), f"maintenance_diff.{field}")
        expected = _address(self._body(), "storage-maintenance-diff")
        if expected != self.content_address:
            raise ValidationError("maintenance diff content address does not reconcile")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self._body() | {"content_address": self.content_address})


__all__ = [
    name
    for name in globals()
    if name.startswith("STORAGE_MAINTENANCE") or name.startswith("StorageMaintenance")
]

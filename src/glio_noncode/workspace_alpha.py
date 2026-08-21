"""External-alpha research-workspace operations.

Domain 15 external-alpha adds four bounded collaboration surfaces around the
immutable workspace read model: a validation experiment board, a notebook and
SDK launch planner, a shareable HMAC-signed snapshot envelope, and a
deny-by-default role-based access evaluator.  These are deterministic records
for research coordination.  They do not execute notebooks, grant clinical
authorization, publish a public-key identity, or replace institutional access
controls.

Every surface carries exact context, source receipts, content addresses, and
review boundaries.  Unknown records are quarantined, context transport is
explicitly out of domain, and a failed access or signature check is retained
as a result instead of being silently treated as absence.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import canonical_bytes, content_hash, jsonable, require_non_empty, utc_now


class WorkspaceAlphaState(StrEnum):
    """State used by workspace external-alpha artifacts."""

    READY_FOR_REVIEW = "ready_for_review"
    REVIEW_REQUIRED = "review_required"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    OUT_OF_DOMAIN = "out_of_domain"
    ABSTAINED = "abstained"
    ALLOWED = "allowed"
    DENIED = "denied"
    AMBIGUOUS = "ambiguous"
    VERIFIED = "verified"
    EXPIRED = "expired"


class ExperimentStatus(StrEnum):
    """Workflow columns for validation experiment cards."""

    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETE = "complete"
    DEFERRED = "deferred"


class NotebookRuntime(StrEnum):
    """Supported launcher descriptor runtimes."""

    PYTHON = "python"
    R = "r"
    JULIA = "julia"
    NODE = "node"
    SDK = "sdk"


class LaunchMode(StrEnum):
    """Whether a launch descriptor targets a notebook or an SDK entrypoint."""

    NOTEBOOK = "notebook"
    SDK = "sdk"


class CollaborationRole(StrEnum):
    """Research-workspace roles used by the explicit permission matrix."""

    VIEWER = "viewer"
    CONTRIBUTOR = "contributor"
    REVIEWER = "reviewer"
    DATA_STEWARD = "data_steward"
    OWNER = "owner"


class CollaborationAction(StrEnum):
    """Actions checked by the role-based collaboration evaluator."""

    VIEW = "view"
    COMMENT = "comment"
    EDIT = "edit"
    LAUNCH = "launch"
    SHARE = "share"
    APPROVE = "approve"


@dataclass(frozen=True, slots=True)
class WorkspaceAlphaIssue:
    """Retained malformed, foreign-context, or policy issue."""

    code: str
    message: str
    raw_hash: str
    severity: str = "warning"
    row_number: int | None = None
    context_key: str | None = None
    raw_record: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.code, "workspace alpha issue code")
        require_non_empty(self.message, "workspace alpha issue message")
        require_non_empty(self.raw_hash, "workspace alpha issue raw_hash")
        if self.row_number is not None and self.row_number < 1:
            raise ValidationError("workspace alpha issue row_number must be positive")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationExperimentCard:
    """One validation experiment card in an exact-context board."""

    experiment_id: str
    target_id: str
    title: str
    assay_type: str
    status: ExperimentStatus
    context_key: str
    priority: int
    owner: str
    dependencies: tuple[str, ...]
    blockers: tuple[str, ...]
    source_ids: tuple[str, ...]
    readout: str
    due_label: str | None
    notes: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "experiment_id",
            "target_id",
            "title",
            "assay_type",
            "context_key",
            "owner",
            "readout",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not 1 <= self.priority <= 5:
            raise ValidationError("experiment card priority must be between one and five")
        if len(self.dependencies) != len(set(self.dependencies)):
            raise ValidationError("experiment card dependencies must be unique")
        if len(self.blockers) != len(set(self.blockers)):
            raise ValidationError("experiment card blockers must be unique")

    @property
    def column_id(self) -> str:
        return self.status.value

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"column_id": self.column_id}


@dataclass(frozen=True, slots=True)
class ValidationBoardColumn:
    """Accessible board column with deterministic card ordering."""

    column_id: str
    title: str
    order: int
    card_ids: tuple[str, ...]
    accessible_label: str
    description: str

    def __post_init__(self) -> None:
        for name in ("column_id", "title", "accessible_label", "description"):
            require_non_empty(getattr(self, name), name)
        if self.order < 0:
            raise ValidationError("board column order cannot be negative")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationExperimentBoard:
    """Immutable validation experiment board read model."""

    board_id: str
    context_key: str
    state: WorkspaceAlphaState
    cards: tuple[ValidationExperimentCard, ...]
    columns: tuple[ValidationBoardColumn, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    blocked_card_ids: tuple[str, ...]
    issues: tuple[WorkspaceAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        require_non_empty(self.board_id, "board_id")
        require_non_empty(self.context_key, "context_key")
        ids = tuple(card.experiment_id for card in self.cards)
        if len(ids) != len(set(ids)):
            raise ValidationError("validation board experiment IDs must be unique")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ValidationExperimentBoardBuilder:
    """Build a context-gated board without executing or scheduling experiments."""

    _COLUMN_META = (
        (ExperimentStatus.BACKLOG, "Backlog", "Experiments not yet ready for review."),
        (ExperimentStatus.READY, "Ready", "Experiments with declared inputs ready for review."),
        (ExperimentStatus.IN_PROGRESS, "In progress", "Experiments reported as in progress."),
        (ExperimentStatus.BLOCKED, "Blocked", "Experiments with retained blockers."),
        (ExperimentStatus.COMPLETE, "Complete", "Experiments reported as complete."),
        (ExperimentStatus.DEFERRED, "Deferred", "Experiments deferred pending a later decision."),
    )

    def build(
        self,
        experiments: Iterable[ValidationExperimentCard | Mapping[str, Any]],
        *,
        context_key: str,
        board_id: str = "validation-board",
    ) -> ValidationExperimentBoard:
        require_non_empty(context_key, "context_key")
        require_non_empty(board_id, "board_id")
        values = tuple(experiments)
        cards: list[ValidationExperimentCard] = []
        issues: list[WorkspaceAlphaIssue] = []
        seen: set[str] = set()
        for row_number, value in enumerate(values, start=1):
            try:
                card = _coerce_experiment(value)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    WorkspaceAlphaIssue(
                        "invalid_experiment_card",
                        str(exc),
                        content_hash(value),
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            if card.context_key != context_key:
                issues.append(
                    WorkspaceAlphaIssue(
                        "context_mismatch",
                        "experiment card is outside the requested workspace context",
                        card.content_address,
                        row_number=row_number,
                        context_key=card.context_key,
                    )
                )
                continue
            if card.experiment_id in seen:
                issues.append(
                    WorkspaceAlphaIssue(
                        "duplicate_experiment_id",
                        "validation board experiment IDs must be unique",
                        card.content_address,
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            seen.add(card.experiment_id)
            cards.append(card)
        known_ids = {card.experiment_id for card in cards}
        dependency_edges: list[tuple[str, str]] = []
        for card in cards:
            for dependency in card.dependencies:
                if dependency not in known_ids:
                    issues.append(
                        WorkspaceAlphaIssue(
                            "unknown_dependency",
                            f"experiment {card.experiment_id} depends on an absent card",
                            card.content_address,
                            context_key=context_key,
                        )
                    )
                else:
                    dependency_edges.append((dependency, card.experiment_id))
        status_order = {status: order for order, (status, _, _) in enumerate(self._COLUMN_META)}
        ordered_cards = tuple(
            sorted(
                cards,
                key=lambda item: (status_order[item.status], -item.priority, item.experiment_id),
            )
        )
        columns = tuple(
            ValidationBoardColumn(
                column_id=status.value,
                title=title,
                order=order,
                card_ids=tuple(
                    card.experiment_id for card in ordered_cards if card.status == status
                ),
                accessible_label=f"{title} validation experiments",
                description=description,
            )
            for order, (status, title, description) in enumerate(self._COLUMN_META)
        )
        blocked = tuple(
            card.experiment_id
            for card in ordered_cards
            if card.status == ExperimentStatus.BLOCKED or card.blockers
        )
        if not ordered_cards:
            state = (
                WorkspaceAlphaState.OUT_OF_DOMAIN
                if any(issue.code == "context_mismatch" for issue in issues)
                else WorkspaceAlphaState.ABSTAINED
            )
        elif blocked:
            state = WorkspaceAlphaState.BLOCKED
        elif any(issue.severity == "error" for issue in issues):
            state = WorkspaceAlphaState.PARTIAL
        else:
            state = WorkspaceAlphaState.READY_FOR_REVIEW
        return ValidationExperimentBoard(
            board_id=board_id,
            context_key=context_key,
            state=state,
            cards=ordered_cards,
            columns=columns,
            dependency_edges=tuple(sorted(set(dependency_edges))),
            blocked_card_ids=blocked,
            issues=tuple(issues),
            warnings=(
                "The board is a coordination read model; it does not execute, approve, or "
                "validate an experiment.",
                "Status and priority are declared workflow metadata and require owner review.",
            ),
            content_address=content_hash(
                {
                    "board_id": board_id,
                    "context_key": context_key,
                    "state": state,
                    "cards": ordered_cards,
                    "columns": columns,
                    "dependency_edges": tuple(sorted(set(dependency_edges))),
                    "issues": issues,
                }
            ),
        )


@dataclass(frozen=True, slots=True)
class NotebookLaunchRequest:
    """Declarative notebook or SDK launch request."""

    request_id: str
    artifact_id: str
    runtime: NotebookRuntime
    mode: LaunchMode
    context_key: str
    entrypoint: str
    parameters: Mapping[str, Any]
    resource_profile: str
    allow_network: bool
    source_ids: tuple[str, ...]
    raw_hash: str

    def __post_init__(self) -> None:
        for name in (
            "request_id",
            "artifact_id",
            "context_key",
            "entrypoint",
            "resource_profile",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.source_ids:
            raise ValidationError("launch request requires at least one source ID")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class NotebookLaunchSpec:
    """Reproducible launch descriptor that never contains executable code."""

    launch_id: str
    request_id: str
    artifact_id: str
    runtime: NotebookRuntime
    mode: LaunchMode
    context_key: str
    invocation: tuple[str, ...]
    parameter_hash: str
    resource_profile: str
    network_policy: str
    state: WorkspaceAlphaState
    source_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class NotebookLaunchPlan:
    """Batch of bounded notebook/SDK launch descriptors."""

    plan_id: str
    context_key: str
    state: WorkspaceAlphaState
    launches: tuple[NotebookLaunchSpec, ...]
    issues: tuple[WorkspaceAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class NotebookSDKLauncher:
    """Plan allowed launch descriptors without executing a notebook or SDK."""

    _RESOURCE_PROFILES = {"small", "medium", "large"}

    def plan(
        self,
        requests: Iterable[NotebookLaunchRequest | Mapping[str, Any]],
        *,
        context_key: str,
        plan_id: str = "notebook-launch-plan",
        allowed_runtimes: Iterable[NotebookRuntime | str] = tuple(NotebookRuntime),
    ) -> NotebookLaunchPlan:
        require_non_empty(context_key, "context_key")
        require_non_empty(plan_id, "plan_id")
        allowed = {NotebookRuntime(str(item)) for item in allowed_runtimes}
        specs: list[NotebookLaunchSpec] = []
        issues: list[WorkspaceAlphaIssue] = []
        for row_number, value in enumerate(tuple(requests), start=1):
            try:
                request = _coerce_launch_request(value)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    WorkspaceAlphaIssue(
                        "invalid_launch_request",
                        str(exc),
                        content_hash(value),
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            if request.context_key != context_key:
                issues.append(
                    WorkspaceAlphaIssue(
                        "context_mismatch",
                        "launch request is outside the requested context",
                        request.raw_hash,
                        row_number=row_number,
                        context_key=request.context_key,
                    )
                )
                continue
            if request.runtime not in allowed:
                issues.append(
                    WorkspaceAlphaIssue(
                        "runtime_not_allowed",
                        f"runtime {request.runtime.value} is not enabled by this plan",
                        request.raw_hash,
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            if request.resource_profile not in self._RESOURCE_PROFILES:
                issues.append(
                    WorkspaceAlphaIssue(
                        "resource_profile_not_allowed",
                        "resource profile is outside the bounded launcher contract",
                        request.raw_hash,
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            parameter_hash = content_hash(request.parameters, prefix="parameters")
            invocation = self._invocation(request, parameter_hash)
            network_policy = (
                "declared_network_review_required" if request.allow_network else "network_disabled"
            )
            launch_state = (
                WorkspaceAlphaState.REVIEW_REQUIRED
                if request.allow_network
                else WorkspaceAlphaState.READY_FOR_REVIEW
            )
            warnings = (
                "This record is a launch descriptor; it does not execute user code.",
                "Runtime images, dependency locks, credentials, and data permissions require "
                "external review.",
            )
            if request.allow_network:
                warnings += ("Network access was requested and remains review-required.",)
            launch_id = content_hash(
                {
                    "plan_id": plan_id,
                    "request_id": request.request_id,
                    "parameter_hash": parameter_hash,
                },
                prefix="launch",
            )
            specs.append(
                NotebookLaunchSpec(
                    launch_id=launch_id,
                    request_id=request.request_id,
                    artifact_id=request.artifact_id,
                    runtime=request.runtime,
                    mode=request.mode,
                    context_key=context_key,
                    invocation=invocation,
                    parameter_hash=parameter_hash,
                    resource_profile=request.resource_profile,
                    network_policy=network_policy,
                    state=launch_state,
                    source_ids=request.source_ids,
                    warnings=warnings,
                    content_address=content_hash(
                        {"launch_id": launch_id, "request": request, "invocation": invocation}
                    ),
                )
            )
        if not specs:
            state = (
                WorkspaceAlphaState.OUT_OF_DOMAIN
                if any(issue.code == "context_mismatch" for issue in issues)
                else WorkspaceAlphaState.ABSTAINED
            )
        elif any(issue.severity == "error" for issue in issues):
            state = WorkspaceAlphaState.PARTIAL
        elif any(item.state == WorkspaceAlphaState.REVIEW_REQUIRED for item in specs):
            state = WorkspaceAlphaState.REVIEW_REQUIRED
        else:
            state = WorkspaceAlphaState.READY_FOR_REVIEW
        return NotebookLaunchPlan(
            plan_id=plan_id,
            context_key=context_key,
            state=state,
            launches=tuple(sorted(specs, key=lambda item: item.launch_id)),
            issues=tuple(issues),
            warnings=(
                "Launch planning is declarative and does not execute notebooks, SDKs, or "
                "arbitrary commands.",
                "Environment provenance, resource quotas, secrets, and data access require "
                "independent controls.",
            ),
            content_address=content_hash(
                {
                    "plan_id": plan_id,
                    "context_key": context_key,
                    "state": state,
                    "launches": specs,
                    "issues": issues,
                }
            ),
        )

    @staticmethod
    def _invocation(request: NotebookLaunchRequest, parameter_hash: str) -> tuple[str, ...]:
        if request.mode == LaunchMode.NOTEBOOK:
            return (
                request.runtime.value,
                "--notebook",
                request.artifact_id,
                "--parameter-hash",
                parameter_hash,
            )
        return (
            request.runtime.value,
            "--entrypoint",
            request.entrypoint,
            "--parameter-hash",
            parameter_hash,
        )


@dataclass(frozen=True, slots=True)
class ShareableSignedSnapshot:
    """Portable snapshot envelope with an HMAC integrity signature."""

    snapshot_id: str
    snapshot_type: str
    context_key: str
    payload: Any
    payload_hash: str
    key_id: str
    signature: str
    algorithm: str
    issued_at: str
    expires_at: str | None
    audience: tuple[str, ...]
    research_use_only: bool
    limitations: tuple[str, ...]
    content_address: str

    def __post_init__(self) -> None:
        for name in (
            "snapshot_id",
            "snapshot_type",
            "context_key",
            "payload_hash",
            "key_id",
            "signature",
            "algorithm",
            "issued_at",
            "content_address",
        ):
            require_non_empty(str(getattr(self, name)), name)
        if not self.research_use_only:
            raise ValidationError("shareable research snapshot must be research_use_only")

    def signing_body(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_type": self.snapshot_type,
            "context_key": self.context_key,
            "payload_hash": self.payload_hash,
            "key_id": self.key_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "audience": self.audience,
        }

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SnapshotVerification:
    """Result of verifying a shareable HMAC envelope."""

    snapshot_id: str
    state: WorkspaceAlphaState
    signature_valid: bool
    payload_hash_valid: bool
    expired: bool
    algorithm: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ShareableSnapshotPublisher:
    """Publish and verify research-only snapshots with a supplied HMAC key."""

    _ALGORITHM = "hmac-sha256"

    def publish(
        self,
        payload: Any,
        *,
        snapshot_id: str,
        snapshot_type: str,
        context_key: str,
        key_id: str,
        signing_secret: str,
        audience: Iterable[str] = (),
        expires_at: str | None = None,
    ) -> ShareableSignedSnapshot:
        for value, name in (
            (snapshot_id, "snapshot_id"),
            (snapshot_type, "snapshot_type"),
            (context_key, "context_key"),
            (key_id, "key_id"),
            (signing_secret, "signing_secret"),
        ):
            require_non_empty(value, name)
        audience_values = tuple(dict.fromkeys(str(item) for item in audience if str(item).strip()))
        issued_at = utc_now().isoformat()
        payload_hash = content_hash(payload, prefix="payload")
        body = {
            "snapshot_id": snapshot_id,
            "snapshot_type": snapshot_type,
            "context_key": context_key,
            "payload_hash": payload_hash,
            "key_id": key_id,
            "issued_at": issued_at,
            "expires_at": expires_at,
            "audience": audience_values,
        }
        signature = self._sign(body, signing_secret)
        envelope = ShareableSignedSnapshot(
            snapshot_id=snapshot_id,
            snapshot_type=snapshot_type,
            context_key=context_key,
            payload=payload,
            payload_hash=payload_hash,
            key_id=key_id,
            signature=signature,
            algorithm=self._ALGORITHM,
            issued_at=issued_at,
            expires_at=expires_at,
            audience=audience_values,
            research_use_only=True,
            limitations=(
                "HMAC verification proves possession of the shared secret, not public-key "
                "identity.",
                "A signed snapshot preserves content integrity but does not validate scientific "
                "claims or authorize clinical use.",
            ),
            content_address=content_hash(
                {"body": body, "payload_hash": payload_hash, "signature": signature}
            ),
        )
        return envelope

    def verify(
        self,
        envelope: ShareableSignedSnapshot | Mapping[str, Any],
        *,
        signing_secret: str,
        now: str | None = None,
    ) -> SnapshotVerification:
        require_non_empty(signing_secret, "signing_secret")
        item = _coerce_snapshot(envelope)
        expected_payload_hash = content_hash(item.payload, prefix="payload")
        payload_valid = hmac.compare_digest(expected_payload_hash, item.payload_hash)
        expected_signature = self._sign(item.signing_body(), signing_secret)
        signature_valid = hmac.compare_digest(expected_signature, item.signature)
        expired = False
        if item.expires_at:
            try:
                reference = _parse_time(now or utc_now().isoformat())
                expired = reference >= _parse_time(item.expires_at)
            except ValueError:
                expired = True
        if not payload_valid or not signature_valid:
            state = WorkspaceAlphaState.BLOCKED
        elif expired:
            state = WorkspaceAlphaState.EXPIRED
        else:
            state = WorkspaceAlphaState.VERIFIED
        warnings = (
            "Verification checks the supplied HMAC secret and payload address only.",
            "Scientific content, audience authorization, and clinical suitability remain "
            "external review responsibilities.",
        )
        return SnapshotVerification(
            snapshot_id=item.snapshot_id,
            state=state,
            signature_valid=signature_valid,
            payload_hash_valid=payload_valid,
            expired=expired,
            algorithm=item.algorithm,
            warnings=warnings,
            content_address=content_hash(
                {
                    "snapshot_id": item.snapshot_id,
                    "state": state,
                    "signature_valid": signature_valid,
                    "payload_hash_valid": payload_valid,
                    "expired": expired,
                }
            ),
        )

    @classmethod
    def _sign(cls, body: Mapping[str, Any], signing_secret: str) -> str:
        digest = hmac.new(
            signing_secret.encode("utf-8"),
            canonical_bytes(body),
            hashlib.sha256,
        ).hexdigest()
        return f"{cls._ALGORITHM}:{digest}"


@dataclass(frozen=True, slots=True)
class CollaborationMember:
    """One active or inactive workspace collaborator."""

    member_id: str
    display_label: str
    role: CollaborationRole
    context_key: str
    active: bool
    source_id: str
    raw_hash: str

    def __post_init__(self) -> None:
        for name in (
            "member_id",
            "display_label",
            "context_key",
            "source_id",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CollaborationRequest:
    """One access request evaluated against the explicit role matrix."""

    request_id: str
    member_id: str
    action: CollaborationAction
    target_id: str
    context_key: str
    reason: str
    raw_hash: str

    def __post_init__(self) -> None:
        for name in (
            "request_id",
            "member_id",
            "target_id",
            "context_key",
            "reason",
            "raw_hash",
        ):
            require_non_empty(str(getattr(self, name)), name)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CollaborationAccessDecision:
    """Allowed or denied request with a policy receipt."""

    request_id: str
    member_id: str
    role: CollaborationRole | None
    action: CollaborationAction
    target_id: str
    context_key: str
    state: WorkspaceAlphaState
    allowed: bool
    reason: str
    policy_receipt: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CollaborationAccessReport:
    """Batch access evaluation and audit-friendly decision set."""

    workspace_id: str
    context_key: str
    state: WorkspaceAlphaState
    decisions: tuple[CollaborationAccessDecision, ...]
    issues: tuple[WorkspaceAlphaIssue, ...]
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class RoleBasedCollaborationEvaluator:
    """Evaluate workspace permissions with deny-by-default semantics."""

    _PERMISSIONS = {
        CollaborationRole.VIEWER: frozenset({CollaborationAction.VIEW}),
        CollaborationRole.CONTRIBUTOR: frozenset(
            {
                CollaborationAction.VIEW,
                CollaborationAction.COMMENT,
                CollaborationAction.EDIT,
                CollaborationAction.LAUNCH,
            }
        ),
        CollaborationRole.REVIEWER: frozenset(
            {CollaborationAction.VIEW, CollaborationAction.COMMENT, CollaborationAction.APPROVE}
        ),
        CollaborationRole.DATA_STEWARD: frozenset(
            {CollaborationAction.VIEW, CollaborationAction.COMMENT, CollaborationAction.SHARE}
        ),
        CollaborationRole.OWNER: frozenset(CollaborationAction),
    }

    def evaluate(
        self,
        members: Iterable[CollaborationMember | Mapping[str, Any]],
        requests: Iterable[CollaborationRequest | Mapping[str, Any]],
        *,
        workspace_id: str = "workspace-1",
        context_key: str,
    ) -> CollaborationAccessReport:
        require_non_empty(workspace_id, "workspace_id")
        require_non_empty(context_key, "context_key")
        issues: list[WorkspaceAlphaIssue] = []
        member_map: dict[str, CollaborationMember] = {}
        for row_number, value in enumerate(tuple(members), start=1):
            try:
                member = _coerce_member(value, context_key=context_key)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    WorkspaceAlphaIssue(
                        "invalid_collaboration_member",
                        str(exc),
                        content_hash(value),
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            if member.member_id in member_map:
                issues.append(
                    WorkspaceAlphaIssue(
                        "duplicate_member_id",
                        "collaboration member IDs must be unique",
                        member.raw_hash,
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            member_map[member.member_id] = member
        decisions: list[CollaborationAccessDecision] = []
        seen_requests: set[str] = set()
        for row_number, value in enumerate(tuple(requests), start=1):
            try:
                request = _coerce_request(value, context_key=context_key)
            except (TypeError, ValueError, ValidationError) as exc:
                issues.append(
                    WorkspaceAlphaIssue(
                        "invalid_collaboration_request",
                        str(exc),
                        content_hash(value),
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            if request.request_id in seen_requests:
                issues.append(
                    WorkspaceAlphaIssue(
                        "duplicate_request_id",
                        "collaboration request IDs must be unique",
                        request.raw_hash,
                        severity="error",
                        row_number=row_number,
                    )
                )
                continue
            seen_requests.add(request.request_id)
            member = member_map.get(request.member_id)
            if request.context_key != context_key:
                decisions.append(
                    self._decision(
                        request,
                        member,
                        WorkspaceAlphaState.OUT_OF_DOMAIN,
                        False,
                        "request context does not match workspace context",
                    )
                )
                continue
            if member is None:
                decisions.append(
                    self._decision(
                        request,
                        None,
                        WorkspaceAlphaState.DENIED,
                        False,
                        "member is not present in the workspace roster",
                    )
                )
                continue
            if member.context_key != context_key:
                decisions.append(
                    self._decision(
                        request,
                        member,
                        WorkspaceAlphaState.OUT_OF_DOMAIN,
                        False,
                        "member context is outside workspace context",
                    )
                )
                continue
            if not member.active:
                decisions.append(
                    self._decision(
                        request, member, WorkspaceAlphaState.DENIED, False, "member is inactive"
                    )
                )
                continue
            allowed = request.action in self._PERMISSIONS[member.role]
            decisions.append(
                self._decision(
                    request,
                    member,
                    WorkspaceAlphaState.ALLOWED if allowed else WorkspaceAlphaState.DENIED,
                    allowed,
                    "role grants the requested action"
                    if allowed
                    else "role does not grant the requested action",
                )
            )
        if not decisions:
            state = WorkspaceAlphaState.ABSTAINED
        elif any(item.state == WorkspaceAlphaState.OUT_OF_DOMAIN for item in decisions):
            state = WorkspaceAlphaState.OUT_OF_DOMAIN
        elif any(not item.allowed for item in decisions):
            state = WorkspaceAlphaState.DENIED
        elif any(issue.severity == "error" for issue in issues):
            state = WorkspaceAlphaState.PARTIAL
        else:
            state = WorkspaceAlphaState.ALLOWED
        return CollaborationAccessReport(
            workspace_id=workspace_id,
            context_key=context_key,
            state=state,
            decisions=tuple(decisions),
            issues=tuple(issues),
            warnings=(
                "Permissions are an application-level research policy and do not replace "
                "identity, data, or institutional access controls.",
                "Unknown members and actions are denied rather than inferred from display labels.",
            ),
            content_address=content_hash(
                {
                    "workspace_id": workspace_id,
                    "context_key": context_key,
                    "state": state,
                    "decisions": decisions,
                    "issues": issues,
                }
            ),
        )

    @staticmethod
    def _decision(
        request: CollaborationRequest,
        member: CollaborationMember | None,
        state: WorkspaceAlphaState,
        allowed: bool,
        reason: str,
    ) -> CollaborationAccessDecision:
        role = None if member is None else member.role
        policy_receipt = content_hash(
            {
                "member_id": request.member_id,
                "role": role,
                "action": request.action,
                "target_id": request.target_id,
                "state": state,
            },
            prefix="policy",
        )
        return CollaborationAccessDecision(
            request_id=request.request_id,
            member_id=request.member_id,
            role=role,
            action=request.action,
            target_id=request.target_id,
            context_key=request.context_key,
            state=state,
            allowed=allowed,
            reason=reason,
            policy_receipt=policy_receipt,
            content_address=content_hash(
                {
                    "request_id": request.request_id,
                    "policy_receipt": policy_receipt,
                    "reason": reason,
                }
            ),
        )


def _coerce_experiment(
    value: ValidationExperimentCard | Mapping[str, Any],
) -> ValidationExperimentCard:
    if isinstance(value, ValidationExperimentCard):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("experiment card must be a mapping")
    blockers = _strings(value.get("blockers", ()))
    return ValidationExperimentCard(
        experiment_id=str(value.get("experiment_id", value.get("id", ""))),
        target_id=str(value.get("target_id", value.get("target", ""))),
        title=str(value.get("title", value.get("label", ""))),
        assay_type=str(value.get("assay_type", value.get("assay", "unspecified"))),
        status=ExperimentStatus(str(value.get("status", ExperimentStatus.BACKLOG.value))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        priority=int(value.get("priority", 3)),
        owner=str(value.get("owner", "unassigned")),
        dependencies=_strings(value.get("dependencies", ())),
        blockers=blockers,
        source_ids=_strings(value.get("source_ids", value.get("source_id", ("workspace-input",)))),
        readout=str(value.get("readout", "declared readout")),
        due_label=(None if value.get("due_label") in (None, "") else str(value["due_label"])),
        notes=_strings(value.get("notes", ())),
        content_address=str(
            value.get("content_address", content_hash(dict(value), prefix="experiment"))
        ),
    )


def _coerce_launch_request(
    value: NotebookLaunchRequest | Mapping[str, Any],
) -> NotebookLaunchRequest:
    if isinstance(value, NotebookLaunchRequest):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("notebook launch request must be a mapping")
    return NotebookLaunchRequest(
        request_id=str(value.get("request_id", value.get("id", ""))),
        artifact_id=str(
            value.get("artifact_id", value.get("notebook_id", value.get("artifact", "")))
        ),
        runtime=NotebookRuntime(str(value.get("runtime", NotebookRuntime.PYTHON.value))),
        mode=LaunchMode(str(value.get("mode", LaunchMode.NOTEBOOK.value))),
        context_key=str(value.get("context_key", value.get("context", ""))),
        entrypoint=str(value.get("entrypoint", value.get("module", "notebook"))),
        parameters=dict(value.get("parameters", {})),
        resource_profile=str(value.get("resource_profile", "small")),
        allow_network=_as_bool(value.get("allow_network", False)),
        source_ids=_strings(value.get("source_ids", value.get("source_id", ("launch-input",)))),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
    )


def _coerce_snapshot(value: ShareableSignedSnapshot | Mapping[str, Any]) -> ShareableSignedSnapshot:
    if isinstance(value, ShareableSignedSnapshot):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("signed snapshot must be a mapping")
    return ShareableSignedSnapshot(
        snapshot_id=str(value.get("snapshot_id", "snapshot")),
        snapshot_type=str(value.get("snapshot_type", "workspace")),
        context_key=str(value.get("context_key", "")),
        payload=value.get("payload"),
        payload_hash=str(value.get("payload_hash", "")),
        key_id=str(value.get("key_id", "")),
        signature=str(value.get("signature", "")),
        algorithm=str(value.get("algorithm", "hmac-sha256")),
        issued_at=str(value.get("issued_at", "")),
        expires_at=(None if value.get("expires_at") in (None, "") else str(value["expires_at"])),
        audience=_strings(value.get("audience", ())),
        research_use_only=_as_bool(value.get("research_use_only", True)),
        limitations=_strings(value.get("limitations", ())),
        content_address=str(value.get("content_address", content_hash(dict(value)))),
    )


def _coerce_member(
    value: CollaborationMember | Mapping[str, Any], *, context_key: str
) -> CollaborationMember:
    if isinstance(value, CollaborationMember):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("collaboration member must be a mapping")
    return CollaborationMember(
        member_id=str(value.get("member_id", value.get("id", ""))),
        display_label=str(
            value.get("display_label", value.get("label", value.get("member_id", "")))
        ),
        role=CollaborationRole(str(value.get("role", CollaborationRole.VIEWER.value))),
        context_key=str(value.get("context_key", context_key)),
        active=_as_bool(value.get("active", True)),
        source_id=str(value.get("source_id", "collaboration-roster")),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
    )


def _coerce_request(
    value: CollaborationRequest | Mapping[str, Any], *, context_key: str
) -> CollaborationRequest:
    if isinstance(value, CollaborationRequest):
        return value
    if not isinstance(value, Mapping):
        raise ValidationError("collaboration request must be a mapping")
    return CollaborationRequest(
        request_id=str(value.get("request_id", value.get("id", ""))),
        member_id=str(value.get("member_id", value.get("member", ""))),
        action=CollaborationAction(str(value.get("action", CollaborationAction.VIEW.value))),
        target_id=str(value.get("target_id", value.get("target", "workspace"))),
        context_key=str(value.get("context_key", context_key)),
        reason=str(value.get("reason", "declared workspace access")),
        raw_hash=str(value.get("raw_hash", content_hash(dict(value)))),
    )


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,) if value.strip() else ()
    if value is None:
        return ()
    return tuple(dict.fromkeys(str(item) for item in value if str(item).strip()))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


__all__ = [
    "CollaborationAccessDecision",
    "CollaborationAccessReport",
    "CollaborationAction",
    "CollaborationMember",
    "CollaborationRequest",
    "CollaborationRole",
    "ExperimentStatus",
    "LaunchMode",
    "NotebookLaunchPlan",
    "NotebookLaunchRequest",
    "NotebookLaunchSpec",
    "NotebookRuntime",
    "NotebookSDKLauncher",
    "ShareableSignedSnapshot",
    "ShareableSnapshotPublisher",
    "SnapshotVerification",
    "ValidationBoardColumn",
    "ValidationExperimentBoard",
    "ValidationExperimentBoardBuilder",
    "ValidationExperimentCard",
    "WorkspaceAlphaIssue",
    "WorkspaceAlphaState",
    "RoleBasedCollaborationEvaluator",
]

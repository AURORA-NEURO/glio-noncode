"""Typed contracts for append-only release-window review decisions.

The review plane records an explicit decision against already verified
release-window evidence. It is intentionally not an identity or authorization
plane: entries contain no person, agent, credential, clock, path, or transport
fields. A promote decision is admissible only when the referenced window and
independent assurance are release-ready. Hold, block, and supersede decisions
remain valid review records but never become release receipts.
"""

# ruff: noqa: E501

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from .errors import ValidationError
from .serialization import content_hash

MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ENTRY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-entry"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_QUERY_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-query"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-runtime-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-runtime"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_STAGE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-runtime-stage"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-assurance-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-assurance"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_FINDING_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-assurance-finding"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_VERSION = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-diff-v1"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_BOUNDARY = "public_aggregate_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-diff"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_ACTION_PREFIX = "module-workbench-execution-packet-archive-store-replication-packet-diff-release-window-review-diff-action"
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DEFAULT_LIMIT = 50
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_LIMIT = 512
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ENTRIES = 256
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ACTIONS = 512
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_REQUIRED_ACTIONS = 32
MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_TEXT = 4096


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision(
    StrEnum
):
    """Decisions that can be recorded in the review chain."""

    PROMOTE = "promote"
    HOLD = "hold"
    BLOCK = "block"
    SUPERSEDE = "supersede"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState(
    StrEnum
):
    """Ledger states derived from the most recent decision."""

    UNREVIEWED = "unreviewed"
    PROMOTED = "promoted"
    HOLD = "hold"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind(
    StrEnum
):
    """Ordered stages of a review decision handoff."""

    LOAD = "load"
    VERIFY_WINDOW = "verify_window"
    VERIFY_ASSURANCE = "verify_assurance"
    VERIFY_LEDGER = "verify_ledger"
    RESOLVE_HEAD = "resolve_head"
    EVALUATE_HANDOFF = "evaluate_handoff"
    COMPLETE = "complete"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState(
    StrEnum
):
    """Fail-closed runtime stage states."""

    COMPLETED = "completed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceState(
    StrEnum
):
    """Independent assurance outcomes for a review ledger."""

    ACCEPTED = "accepted"
    HOLD = "hold"
    BLOCKED = "blocked"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity(
    StrEnum
):
    """Severity values for assurance findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind(
    StrEnum
):
    """Actions emitted when two review-ledger revisions are compared."""

    ADDED = "added"
    REMOVED = "removed"
    UNCHANGED = "unchanged"
    CHANGED = "changed"


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffState(
    StrEnum
):
    """Diff dispositions, including the append-only proof state."""

    EXACT = "exact"
    APPEND_ONLY = "append_only"
    DIVERGENT = "divergent"


def _text(
    value: Any,
    field: str,
    maximum: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_TEXT,
) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _optional_text(
    value: Any,
    field: str,
    maximum: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_TEXT,
) -> str | None:
    if value is None:
        return None
    return _text(value, field, maximum)


def _address(value: Any, field: str) -> str:
    normalized = _text(value, field, 512)
    if ":" not in normalized or normalized.startswith(":") or normalized.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return normalized


def _optional_address(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _address(value, field)


def _count(value: Any, field: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field} must be a non-negative integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    return value


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _public_boundary(value: Any) -> bool:
    """Reject identity, secret, language, and private transport keys."""

    forbidden = {
        "agent",
        "agent_id",
        "agent_name",
        "assistant",
        "assistant_id",
        "assistant_name",
        "author",
        "author_id",
        "author_name",
        "codex",
        "contact",
        "contact_name",
        "credential",
        "email",
        "generated_by",
        "hostname",
        "individual_id",
        "language",
        "model",
        "model_id",
        "model_name",
        "openai",
        "patient_id",
        "phone",
        "private",
        "programming_language",
        "secret",
        "token",
        "user",
        "user_id",
        "username",
    }
    if isinstance(value, Mapping):
        return all(
            str(key).casefold() not in forbidden and _public_boundary(item)
            for key, item in value.items()
        )
    if isinstance(value, (tuple, list)):
        return all(_public_boundary(item) for item in value)
    return True


def _text_tuple(
    value: Any,
    field: str,
    maximum: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_REQUIRED_ACTIONS,
) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValidationError(f"{field} must be an array")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    result = tuple(
        _text(
            item,
            f"{field}[]",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_TEXT,
        )
        for item in value
    )
    if len(set(result)) != len(result):
        raise ValidationError(f"{field} must not contain duplicates")
    return result


def _address_tuple(
    value: Any,
    field: str,
    maximum: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ENTRIES,
) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValidationError(f"{field} must be an array")
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    result = tuple(_address(item, f"{field}[]") for item in value)
    if len(set(result)) != len(result):
        raise ValidationError(f"{field} must not contain duplicates")
    return result


def _validate_enum(value: Any, enum_type: type[StrEnum], field: str) -> str:
    normalized = value.value if isinstance(value, enum_type) else value
    if not isinstance(normalized, str) or normalized not in {item.value for item in enum_type}:
        raise ValidationError(f"{field} is invalid")
    return normalized


_DECISION_STATE = {
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.PROMOTE.value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState.PROMOTED.value,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.HOLD.value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState.HOLD.value,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.BLOCK.value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState.BLOCKED.value,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.SUPERSEDE.value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState.SUPERSEDED.value,
}


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry:
    """One immutable decision in a release-window review chain."""

    def __init__(
        self,
        ordinal: int,
        entry_id: str,
        window_address: str,
        assurance_address: str,
        sensitivity_address: str | None,
        decision: str,
        state: str,
        release_ready: bool,
        accepted: bool,
        rationale: str,
        required_actions: tuple[str, ...],
        supersedes_entry_address: str | None,
        previous_entry_address: str | None,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.entry_id = entry_id
        self.window_address = window_address
        self.assurance_address = assurance_address
        self.sensitivity_address = sensitivity_address
        self.decision = decision
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.rationale = rationale
        self.required_actions = tuple(required_actions)
        self.supersedes_entry_address = supersedes_entry_address
        self.previous_entry_address = previous_entry_address
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "review entry ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ENTRIES
            - 1,
        )
        _text(self.entry_id, "review entry ID", 256)
        _address(self.window_address, "review entry window address")
        _address(self.assurance_address, "review entry assurance address")
        _optional_address(self.sensitivity_address, "review entry sensitivity address")
        decision = _validate_enum(
            self.decision,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision,
            "review entry decision",
        )
        state = _validate_enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState,
            "review entry state",
        )
        if _DECISION_STATE[decision] != state:
            raise ValidationError("review entry state does not follow decision")
        _bool(self.release_ready, "review entry release-ready flag")
        _bool(self.accepted, "review entry accepted flag")
        _text(self.rationale, "review entry rationale")
        self.required_actions = _text_tuple(self.required_actions, "review entry required actions")
        if (
            decision
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.PROMOTE.value
        ):
            if not self.release_ready or self.required_actions:
                raise ValidationError("promote entries require readiness and no open actions")
        else:
            if self.release_ready:
                raise ValidationError("non-promote entries cannot be release-ready")
            if not self.required_actions:
                raise ValidationError("non-promote entries require at least one explicit action")
        _optional_address(self.supersedes_entry_address, "review superseded entry address")
        if (
            decision
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.SUPERSEDE.value
            and self.supersedes_entry_address is None
        ):
            raise ValidationError("supersede entries require a superseded entry address")
        if (
            decision
            != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.SUPERSEDE.value
            and self.supersedes_entry_address is not None
        ):
            raise ValidationError("only supersede entries may reference a superseded entry")
        _optional_address(self.previous_entry_address, "review previous entry address")
        if self.ordinal == 0 and self.previous_entry_address is not None:
            raise ValidationError("the first review entry cannot have a previous entry")
        if self.ordinal > 0 and self.previous_entry_address is None:
            raise ValidationError("non-first review entries require a previous entry")
        _address(self.content_address, "review entry content address")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("review entry crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "entry_id": self.entry_id,
            "window_address": self.window_address,
            "assurance_address": self.assurance_address,
            "sensitivity_address": self.sensitivity_address,
            "decision": self.decision,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "rationale": self.rationale,
            "required_actions": list(self.required_actions),
            "supersedes_entry_address": self.supersedes_entry_address,
            "previous_entry_address": self.previous_entry_address,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_entry(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry,
) -> str:
    """Address an entry without including its address field."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ENTRY_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview:
    """Immutable append-only review ledger for one release-window evidence set."""

    def __init__(
        self,
        ledger_id: str,
        version: str,
        boundary: str,
        window_address: str,
        assurance_address: str,
        sensitivity_address: str | None,
        entries: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry,
            ...,
        ],
        entry_count: int,
        head_address: str | None,
        state: str,
        release_ready: bool,
        accepted: bool,
        append_only: bool,
        content_address: str,
    ) -> None:
        self.ledger_id = ledger_id
        self.version = version
        self.boundary = boundary
        self.window_address = window_address
        self.assurance_address = assurance_address
        self.sensitivity_address = sensitivity_address
        self.entries = tuple(entries)
        self.entry_count = entry_count
        self.head_address = head_address
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.append_only = append_only
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.ledger_id, "review ledger ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_VERSION
        ):
            raise ValidationError("review ledger version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_BOUNDARY
        ):
            raise ValidationError("review ledger boundary is invalid")
        _address(self.window_address, "review ledger window address")
        _address(self.assurance_address, "review ledger assurance address")
        _optional_address(self.sensitivity_address, "review ledger sensitivity address")
        _count(
            self.entry_count,
            "review ledger entry count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ENTRIES,
        )
        if self.entry_count != len(self.entries):
            raise ValidationError("review ledger entry count does not conserve")
        if tuple(item.ordinal for item in self.entries) != tuple(range(self.entry_count)):
            raise ValidationError("review ledger entry ordinals are not contiguous")
        if len({item.entry_id for item in self.entries}) != self.entry_count:
            raise ValidationError("review ledger entry IDs must be unique")
        for ordinal, entry in enumerate(self.entries):
            if not isinstance(
                entry,
                ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry,
            ):
                raise ValidationError("review ledger entries must be typed")
            if (
                entry.window_address != self.window_address
                or entry.assurance_address != self.assurance_address
            ):
                raise ValidationError("review ledger entry evidence links differ")
            if entry.sensitivity_address != self.sensitivity_address:
                raise ValidationError("review ledger entry sensitivity link differs")
            expected_previous = self.entries[ordinal - 1].content_address if ordinal else None
            if entry.previous_entry_address != expected_previous:
                raise ValidationError("review ledger chain is not contiguous")
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_entry(
                    entry
                )
                != entry.content_address
            ):
                raise ValidationError("review ledger entry address mismatch")
        expected_head = self.entries[-1].content_address if self.entries else None
        if self.head_address != expected_head:
            raise ValidationError("review ledger head does not conserve")
        state = _validate_enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState,
            "review ledger state",
        )
        expected_state = (
            self.entries[-1].state
            if self.entries
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState.UNREVIEWED.value
        )
        if state != expected_state:
            raise ValidationError("review ledger state does not follow head")
        _bool(self.release_ready, "review ledger release-ready flag")
        _bool(self.accepted, "review ledger accepted flag")
        _bool(self.append_only, "review ledger append-only flag")
        if not self.append_only:
            raise ValidationError("review ledger must be append-only")
        expected_ready = bool(
            self.entries
            and self.entries[-1].decision
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.PROMOTE.value
            and self.entries[-1].release_ready
        )
        if self.release_ready != expected_ready:
            raise ValidationError("review ledger release readiness does not follow head")
        expected_accepted = bool(self.entries) and all(item.accepted for item in self.entries)
        if self.accepted != expected_accepted:
            raise ValidationError("review ledger acceptance does not conserve entries")
        _optional_address(self.head_address, "review ledger head address")
        _address(self.content_address, "review ledger content address")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("review ledger crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "ledger_id": self.ledger_id,
            "version": self.version,
            "boundary": self.boundary,
            "window_address": self.window_address,
            "assurance_address": self.assurance_address,
            "sensitivity_address": self.sensitivity_address,
            "entry_count": self.entry_count,
            "head_address": self.head_address,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "append_only": self.append_only,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_entries: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_entries:
            body["entries"] = [item.to_dict() for item in self.entries]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
) -> str:
    """Address the complete review ledger."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStage:
    """One addressed stage in a review runtime."""

    def __init__(
        self,
        ordinal: int,
        stage_id: str,
        kind: str,
        state: str,
        input_address: str | None,
        output_address: str | None,
        accepted: bool,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.stage_id = stage_id
        self.kind = kind
        self.state = state
        self.input_address = input_address
        self.output_address = output_address
        self.accepted = accepted
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(self.ordinal, "review runtime stage ordinal", 32)
        _text(self.stage_id, "review runtime stage ID", 256)
        _validate_enum(
            self.kind,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageKind,
            "review runtime stage kind",
        )
        stage_state = _validate_enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState,
            "review runtime stage state",
        )
        _optional_address(self.input_address, "review runtime stage input address")
        _optional_address(self.output_address, "review runtime stage output address")
        _bool(self.accepted, "review runtime stage accepted flag")
        _text(self.detail, "review runtime stage detail")
        if (
            stage_state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.COMPLETED.value
            and not self.accepted
        ):
            raise ValidationError("completed review runtime stages must be accepted")
        if (
            stage_state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.BLOCKED.value
            and self.accepted
        ):
            raise ValidationError("blocked review runtime stages cannot be accepted")
        _address(self.content_address, "review runtime stage content address")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("review runtime stage crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "stage_id": self.stage_id,
            "kind": self.kind,
            "state": self.state,
            "input_address": self.input_address,
            "output_address": self.output_address,
            "accepted": self.accepted,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_stage(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStage,
) -> str:
    """Address a runtime stage without its address field."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_STAGE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime:
    """Fail-closed runtime projection for a review ledger."""

    def __init__(
        self,
        runtime_id: str,
        version: str,
        boundary: str,
        ledger_address: str,
        window_address: str,
        assurance_address: str,
        stages: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStage,
            ...,
        ],
        stage_count: int,
        completed_count: int,
        blocked_count: int,
        skipped_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.runtime_id = runtime_id
        self.version = version
        self.boundary = boundary
        self.ledger_address = ledger_address
        self.window_address = window_address
        self.assurance_address = assurance_address
        self.stages = tuple(stages)
        self.stage_count = stage_count
        self.completed_count = completed_count
        self.blocked_count = blocked_count
        self.skipped_count = skipped_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.runtime_id, "review runtime ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_VERSION
        ):
            raise ValidationError("review runtime version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_BOUNDARY
        ):
            raise ValidationError("review runtime boundary is invalid")
        _address(self.ledger_address, "review runtime ledger address")
        _address(self.window_address, "review runtime window address")
        _address(self.assurance_address, "review runtime assurance address")
        _count(self.stage_count, "review runtime stage count", 32)
        if self.stage_count != len(self.stages) or not self.stages:
            raise ValidationError("review runtime stage count does not conserve")
        if tuple(item.ordinal for item in self.stages) != tuple(range(self.stage_count)):
            raise ValidationError("review runtime stage ordinals are not contiguous")
        for stage in self.stages:
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime_stage(
                    stage
                )
                != stage.content_address
            ):
                raise ValidationError("review runtime stage address mismatch")
        _count(self.completed_count, "review runtime completed count", self.stage_count)
        _count(self.blocked_count, "review runtime blocked count", self.stage_count)
        _count(self.skipped_count, "review runtime skipped count", self.stage_count)
        if self.completed_count != sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.COMPLETED.value
            for item in self.stages
        ):
            raise ValidationError("review runtime completed count does not conserve")
        if self.blocked_count != sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.BLOCKED.value
            for item in self.stages
        ):
            raise ValidationError("review runtime blocked count does not conserve")
        if self.skipped_count != sum(
            item.state
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntimeStageState.SKIPPED.value
            for item in self.stages
        ):
            raise ValidationError("review runtime skipped count does not conserve")
        if self.completed_count + self.blocked_count + self.skipped_count != self.stage_count:
            raise ValidationError("review runtime stage counts do not conserve")
        state = _text(self.state, "review runtime state", 64)
        if state not in {"completed", "blocked"}:
            raise ValidationError("review runtime state is invalid")
        _bool(self.release_ready, "review runtime release-ready flag")
        _bool(self.accepted, "review runtime accepted flag")
        if self.accepted != (self.blocked_count == 0 and self.completed_count == self.stage_count):
            raise ValidationError("review runtime acceptance does not follow stages")
        if self.release_ready and not self.accepted:
            raise ValidationError("blocked review runtime cannot be release-ready")
        _address(self.content_address, "review runtime content address")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("review runtime crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "version": self.version,
            "boundary": self.boundary,
            "ledger_address": self.ledger_address,
            "window_address": self.window_address,
            "assurance_address": self.assurance_address,
            "stage_count": self.stage_count,
            "completed_count": self.completed_count,
            "blocked_count": self.blocked_count,
            "skipped_count": self.skipped_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_stages: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_stages:
            body["stages"] = [item.to_dict() for item in self.stages]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_runtime(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewRuntime,
) -> str:
    """Address the complete review runtime."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_RUNTIME_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceFinding:
    """One independent review-ledger assurance finding."""

    def __init__(
        self,
        ordinal: int,
        finding_id: str,
        kind: str,
        severity: str,
        passed: bool,
        observed: Any,
        expected: Any,
        detail: str,
        remediation: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.finding_id = finding_id
        self.kind = kind
        self.severity = severity
        self.passed = passed
        self.observed = observed
        self.expected = expected
        self.detail = detail
        self.remediation = remediation
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "review assurance finding ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ACTIONS
            - 1,
        )
        _text(self.finding_id, "review assurance finding ID", 256)
        _text(self.kind, "review assurance finding kind", 128)
        _validate_enum(
            self.severity,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity,
            "review assurance severity",
        )
        _bool(self.passed, "review assurance passed flag")
        _text(self.detail, "review assurance detail")
        _text(self.remediation, "review assurance remediation")
        _address(self.content_address, "review assurance finding address")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("review assurance finding crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "finding_id": self.finding_id,
            "kind": self.kind,
            "severity": self.severity,
            "passed": self.passed,
            "observed": self.observed,
            "expected": self.expected,
            "detail": self.detail,
            "remediation": self.remediation,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_finding(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceFinding,
) -> str:
    """Address an assurance finding without its address field."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_FINDING_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance:
    """Independent assurance aggregate for a review ledger."""

    def __init__(
        self,
        assurance_id: str,
        version: str,
        boundary: str,
        ledger_address: str,
        window_address: str,
        head_address: str | None,
        findings: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceFinding,
            ...,
        ],
        finding_count: int,
        passed_count: int,
        warning_count: int,
        blocker_count: int,
        state: str,
        release_ready: bool,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.assurance_id = assurance_id
        self.version = version
        self.boundary = boundary
        self.ledger_address = ledger_address
        self.window_address = window_address
        self.head_address = head_address
        self.findings = tuple(findings)
        self.finding_count = finding_count
        self.passed_count = passed_count
        self.warning_count = warning_count
        self.blocker_count = blocker_count
        self.state = state
        self.release_ready = release_ready
        self.accepted = accepted
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.assurance_id, "review assurance ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_VERSION
        ):
            raise ValidationError("review assurance version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_BOUNDARY
        ):
            raise ValidationError("review assurance boundary is invalid")
        _address(self.ledger_address, "review assurance ledger address")
        _address(self.window_address, "review assurance window address")
        _optional_address(self.head_address, "review assurance head address")
        _count(
            self.finding_count,
            "review assurance finding count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ACTIONS,
        )
        if self.finding_count != len(self.findings) or not self.findings:
            raise ValidationError("review assurance finding count does not conserve")
        if tuple(item.ordinal for item in self.findings) != tuple(range(self.finding_count)):
            raise ValidationError("review assurance finding ordinals are not contiguous")
        for finding in self.findings:
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance_finding(
                    finding
                )
                != finding.content_address
            ):
                raise ValidationError("review assurance finding address mismatch")
        expected_passed = sum(item.passed for item in self.findings)
        expected_warning = sum(
            not item.passed
            and item.severity
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.WARNING.value
            for item in self.findings
        )
        expected_blocker = sum(
            not item.passed
            and item.severity
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceSeverity.BLOCKER.value
            for item in self.findings
        )
        if (self.passed_count, self.warning_count, self.blocker_count) != (
            expected_passed,
            expected_warning,
            expected_blocker,
        ):
            raise ValidationError("review assurance finding counts do not conserve")
        _validate_enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssuranceState,
            "review assurance state",
        )
        _bool(self.release_ready, "review assurance release-ready flag")
        _bool(self.accepted, "review assurance accepted flag")
        if self.accepted != (self.blocker_count == 0):
            raise ValidationError("review assurance acceptance does not follow blockers")
        if self.release_ready != (self.accepted and self.warning_count == 0):
            raise ValidationError("review assurance readiness does not follow findings")
        _address(self.content_address, "review assurance content address")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("review assurance crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "assurance_id": self.assurance_id,
            "version": self.version,
            "boundary": self.boundary,
            "ledger_address": self.ledger_address,
            "window_address": self.window_address,
            "head_address": self.head_address,
            "finding_count": self.finding_count,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "blocker_count": self.blocker_count,
            "state": self.state,
            "release_ready": self.release_ready,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_findings: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_findings:
            body["findings"] = [item.to_dict() for item in self.findings]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_assurance(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewAssurance,
) -> str:
    """Address the complete review assurance aggregate."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ASSURANCE_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffAction:
    """One row in a review-ledger revision diff."""

    def __init__(
        self,
        ordinal: int,
        entry_id: str,
        action: str,
        left_address: str | None,
        right_address: str | None,
        detail: str,
        content_address: str,
    ) -> None:
        self.ordinal = ordinal
        self.entry_id = entry_id
        self.action = action
        self.left_address = left_address
        self.right_address = right_address
        self.detail = detail
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _count(
            self.ordinal,
            "review diff action ordinal",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ACTIONS
            - 1,
        )
        _text(self.entry_id, "review diff entry ID", 256)
        action = _validate_enum(
            self.action,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind,
            "review diff action",
        )
        _optional_address(self.left_address, "review diff left address")
        _optional_address(self.right_address, "review diff right address")
        _text(self.detail, "review diff action detail")
        if (
            action
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.ADDED.value
            and (self.left_address is not None or self.right_address is None)
        ):
            raise ValidationError("added diff actions require only a right address")
        if (
            action
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.REMOVED.value
            and (self.left_address is None or self.right_address is not None)
        ):
            raise ValidationError("removed diff actions require only a left address")
        if action in {
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.UNCHANGED.value,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.CHANGED.value,
        } and (self.left_address is None or self.right_address is None):
            raise ValidationError("matched diff actions require both addresses")
        _address(self.content_address, "review diff action address")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("review diff action crosses the public boundary")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "entry_id": self.entry_id,
            "action": self.action,
            "left_address": self.left_address,
            "right_address": self.right_address,
            "detail": self.detail,
            "content_address": self.content_address,
        }


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_action(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffAction,
) -> str:
    """Address one review-ledger diff action."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_ACTION_PREFIX,
    )


class ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff:
    """Revision comparison with an explicit append-only proof."""

    def __init__(
        self,
        diff_id: str,
        version: str,
        boundary: str,
        left_ledger_address: str,
        right_ledger_address: str,
        left_head_address: str | None,
        right_head_address: str | None,
        actions: tuple[
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffAction,
            ...,
        ],
        action_count: int,
        added_count: int,
        removed_count: int,
        unchanged_count: int,
        changed_count: int,
        state: str,
        append_only: bool,
        accepted: bool,
        content_address: str,
    ) -> None:
        self.diff_id = diff_id
        self.version = version
        self.boundary = boundary
        self.left_ledger_address = left_ledger_address
        self.right_ledger_address = right_ledger_address
        self.left_head_address = left_head_address
        self.right_head_address = right_head_address
        self.actions = tuple(actions)
        self.action_count = action_count
        self.added_count = added_count
        self.removed_count = removed_count
        self.unchanged_count = unchanged_count
        self.changed_count = changed_count
        self.state = state
        self.append_only = append_only
        self.accepted = accepted
        self.content_address = content_address
        self._validate()

    def _validate(self) -> None:
        _text(self.diff_id, "review diff ID", 256)
        if (
            self.version
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_VERSION
        ):
            raise ValidationError("review diff version is invalid")
        if (
            self.boundary
            != MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_BOUNDARY
        ):
            raise ValidationError("review diff boundary is invalid")
        _address(self.left_ledger_address, "review diff left ledger address")
        _address(self.right_ledger_address, "review diff right ledger address")
        _optional_address(self.left_head_address, "review diff left head address")
        _optional_address(self.right_head_address, "review diff right head address")
        _count(
            self.action_count,
            "review diff action count",
            MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ACTIONS,
        )
        if self.action_count != len(self.actions):
            raise ValidationError("review diff action count does not conserve")
        if tuple(item.ordinal for item in self.actions) != tuple(range(self.action_count)):
            raise ValidationError("review diff action ordinals are not contiguous")
        for action in self.actions:
            if (
                address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff_action(
                    action
                )
                != action.content_address
            ):
                raise ValidationError("review diff action address mismatch")
        expected = {
            "added_count": sum(
                item.action
                == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.ADDED.value
                for item in self.actions
            ),
            "removed_count": sum(
                item.action
                == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.REMOVED.value
                for item in self.actions
            ),
            "unchanged_count": sum(
                item.action
                == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.UNCHANGED.value
                for item in self.actions
            ),
            "changed_count": sum(
                item.action
                == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffActionKind.CHANGED.value
                for item in self.actions
            ),
        }
        if any(getattr(self, field) != value for field, value in expected.items()):
            raise ValidationError("review diff action counts do not conserve")
        state = _validate_enum(
            self.state,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffState,
            "review diff state",
        )
        expected_append_only = self.removed_count == 0 and self.changed_count == 0
        if self.append_only != expected_append_only:
            raise ValidationError("review diff append-only state does not conserve")
        expected_state = (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffState.EXACT.value
            if self.added_count == 0 and expected_append_only
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffState.APPEND_ONLY.value
            if expected_append_only
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiffState.DIVERGENT.value
        )
        if state != expected_state:
            raise ValidationError("review diff state does not follow actions")
        _bool(self.accepted, "review diff accepted flag")
        if self.accepted != (self.changed_count == 0 and self.removed_count == 0):
            raise ValidationError("review diff acceptance does not follow changes")
        _address(self.content_address, "review diff content address")
        if not _public_boundary(self.to_dict()):
            raise ValidationError("review diff crosses the public boundary")

    def summary(self) -> dict[str, Any]:
        return {
            "diff_id": self.diff_id,
            "version": self.version,
            "boundary": self.boundary,
            "left_ledger_address": self.left_ledger_address,
            "right_ledger_address": self.right_ledger_address,
            "left_head_address": self.left_head_address,
            "right_head_address": self.right_head_address,
            "action_count": self.action_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "unchanged_count": self.unchanged_count,
            "changed_count": self.changed_count,
            "state": self.state,
            "append_only": self.append_only,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def to_dict(self, *, include_actions: bool = True) -> dict[str, Any]:
        body = self.summary()
        if include_actions:
            body["actions"] = [item.to_dict() for item in self.actions]
        return body


def address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_diff(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDiff,
) -> str:
    """Address a complete review-ledger diff."""

    return content_hash(
        value.to_dict() | {"content_address": None},
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_DIFF_PREFIX,
    )


__all__ = [
    name
    for name in globals()
    if name.startswith(
        "MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW"
    )
    or name.startswith(
        "ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview"
    )
    or name.startswith(
        "address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review"
    )
]

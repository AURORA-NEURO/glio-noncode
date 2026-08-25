"""Replay-gated historical workspace reconstruction and semantic transitions.

The current run-workspace projection is useful for navigation, while dossier
history is useful for review-state auditing.  This module joins those two
planes without exposing raw dossier snapshots: every accepted historical
snapshot is rebuilt through :class:`CaseWorkspaceBuilder`, public-projected,
and compared by stable workspace record identity.  Added, removed, and
field-level changes remain visible with bounded payloads and content
addresses.

Historical workspace output is descriptive only.  A changed record is not a
scientific conclusion, and a released review snapshot does not authorize
clinical use.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .errors import StoreError, ValidationError
from .models import CaseManifest, Dossier
from .module_fabric_support import contains_private_key
from .run_catalog import inspect_run
from .run_comparison import RunHistory, RunSnapshot, build_run_history
from .run_workspace import _has_forbidden_key, _public_workspace
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash
from .workspace import CaseWorkspaceBuilder, ResearchWorkspace

WORKSPACE_HISTORY_VERSION = "workspace-history-v1"
WORKSPACE_HISTORY_MAX_CHANGES = 5_000


def _review_state(dossier: Dossier) -> str | None:
    return dossier.review.state.value if dossier.review is not None else None


def _counts(workspace: ResearchWorkspace) -> tuple[dict[str, int], dict[str, int]]:
    return (
        dict(sorted(Counter(item.record_type.value for item in workspace.records).items())),
        dict(sorted(Counter(item.state.value for item in workspace.records).items())),
    )


def _record_address(record: Mapping[str, Any] | None) -> str | None:
    if record is None:
        return None
    return content_hash(record, prefix="workspace-history-record")


def _record_map(workspace: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    values = workspace.get("records", ())
    if not isinstance(values, (list, tuple)):
        raise ValidationError("workspace records must be an array")
    result: dict[str, dict[str, Any]] = {}
    for raw in values:
        if not isinstance(raw, Mapping):
            raise ValidationError("workspace record must be an object")
        record = dict(raw)
        record_id = str(record.get("record_id", ""))
        if not record_id:
            raise ValidationError("workspace history record requires record_id")
        if record_id in result:
            raise ValidationError(f"workspace history contains duplicate record: {record_id}")
        result[record_id] = record
    return result


@dataclass(frozen=True, slots=True)
class WorkspaceRecordChange:
    """One public workspace record addition, removal, or field change."""

    change_type: str
    record_id: str
    record_type: str
    changed_fields: tuple[str, ...]
    before: Mapping[str, Any] | None
    after: Mapping[str, Any] | None
    before_address: str | None
    after_address: str | None
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_type": self.change_type,
            "record_id": self.record_id,
            "record_type": self.record_type,
            "changed_fields": list(self.changed_fields),
            "before": dict(self.before) if self.before is not None else None,
            "after": dict(self.after) if self.after is not None else None,
            "before_address": self.before_address,
            "after_address": self.after_address,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceHistorySnapshot:
    """One verified dossier snapshot rebuilt as a public workspace."""

    index: int
    dossier_address: str
    is_current: bool
    status: str
    review_state: str | None
    workspace_id: str
    workspace_state: str
    record_count: int
    record_type_counts: Mapping[str, int]
    state_counts: Mapping[str, int]
    workspace: Mapping[str, Any] | None
    warnings: tuple[str, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "dossier_address": self.dossier_address,
            "is_current": self.is_current,
            "status": self.status,
            "review_state": self.review_state,
            "workspace_id": self.workspace_id,
            "workspace_state": self.workspace_state,
            "record_count": self.record_count,
            "record_type_counts": dict(self.record_type_counts),
            "state_counts": dict(self.state_counts),
            "workspace": self.workspace,
            "warnings": list(self.warnings),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceTransition:
    """Bounded semantic change between two adjacent workspace snapshots."""

    source_snapshot_index: int
    target_snapshot_index: int
    source_workspace_address: str | None
    target_workspace_address: str | None
    source_status: str
    target_status: str
    source_review_state: str | None
    target_review_state: str | None
    metadata_changed: bool
    source_record_count: int
    target_record_count: int
    added_count: int
    removed_count: int
    changed_count: int
    unchanged_count: int
    truncated: bool
    changes: tuple[WorkspaceRecordChange, ...]
    warnings: tuple[str, ...]
    accepted: bool
    content_address: str

    @property
    def change_count(self) -> int:
        return self.added_count + self.removed_count + self.changed_count

    @property
    def changed(self) -> bool:
        return self.metadata_changed or self.change_count > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_snapshot_index": self.source_snapshot_index,
            "target_snapshot_index": self.target_snapshot_index,
            "source_workspace_address": self.source_workspace_address,
            "target_workspace_address": self.target_workspace_address,
            "source_status": self.source_status,
            "target_status": self.target_status,
            "source_review_state": self.source_review_state,
            "target_review_state": self.target_review_state,
            "metadata_changed": self.metadata_changed,
            "source_record_count": self.source_record_count,
            "target_record_count": self.target_record_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "changed_count": self.changed_count,
            "unchanged_count": self.unchanged_count,
            "change_count": self.change_count,
            "changed": self.changed,
            "truncated": self.truncated,
            "changes": [item.to_dict() for item in self.changes],
            "warnings": list(self.warnings),
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


@dataclass(frozen=True, slots=True)
class WorkspaceHistory:
    """Complete replay-gated workspace timeline for one persisted run."""

    run_id: str
    case_id: str
    current_snapshot_index: int
    snapshots: tuple[WorkspaceHistorySnapshot, ...]
    transitions: tuple[WorkspaceTransition, ...]
    replay_accepted: bool
    accepted: bool
    warnings: tuple[str, ...]
    content_address: str

    @property
    def snapshot_count(self) -> int:
        return len(self.snapshots)

    @property
    def transition_count(self) -> int:
        return len(self.transitions)

    @property
    def total_change_count(self) -> int:
        return sum(item.change_count + int(item.metadata_changed) for item in self.transitions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workspace_history_version": WORKSPACE_HISTORY_VERSION,
            "run_id": self.run_id,
            "case_id": self.case_id,
            "current_snapshot_index": self.current_snapshot_index,
            "snapshot_count": self.snapshot_count,
            "transition_count": self.transition_count,
            "total_change_count": self.total_change_count,
            "snapshots": [item.to_dict() for item in self.snapshots],
            "transitions": [item.to_dict() for item in self.transitions],
            "replay_accepted": self.replay_accepted,
            "accepted": self.accepted,
            "warnings": list(self.warnings),
            "content_address": self.content_address,
        }


def _make_change(
    change_type: str,
    record_id: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> WorkspaceRecordChange:
    before_fields = set(before or {})
    after_fields = set(after or {})
    changed_fields = tuple(
        sorted(
            field
            for field in before_fields | after_fields
            if (before or {}).get(field) != (after or {}).get(field)
        )
    )
    record_type = str((after or before or {}).get("record_type", "unknown"))
    body = {
        "change_type": change_type,
        "record_id": record_id,
        "record_type": record_type,
        "changed_fields": changed_fields,
        "before": before,
        "after": after,
        "before_address": _record_address(before),
        "after_address": _record_address(after),
    }
    return WorkspaceRecordChange(
        **body,
        content_address=content_hash(body, prefix="workspace-history-change"),
    )


def _transition(
    source: WorkspaceHistorySnapshot,
    target: WorkspaceHistorySnapshot,
    *,
    change_limit: int,
) -> WorkspaceTransition:
    warnings: list[str] = []
    if source.workspace is None or target.workspace is None:
        warnings.append("workspace records withheld because a snapshot failed integrity")
        body = {
            "source_snapshot_index": source.index,
            "target_snapshot_index": target.index,
            "source_workspace_address": source.workspace.get("content_address") if source.workspace else None,
            "target_workspace_address": target.workspace.get("content_address") if target.workspace else None,
            "source_status": source.status,
            "target_status": target.status,
            "source_review_state": source.review_state,
            "target_review_state": target.review_state,
            "metadata_changed": (
                source.status != target.status or source.review_state != target.review_state
            ),
            "source_record_count": source.record_count,
            "target_record_count": target.record_count,
            "added_count": 0,
            "removed_count": 0,
            "changed_count": 0,
            "unchanged_count": 0,
            "truncated": False,
            "changes": (),
            "warnings": tuple(warnings),
            "accepted": False,
        }
        return WorkspaceTransition(
            **body,
            content_address=content_hash(body, prefix="workspace-transition"),
        )

    source_records = _record_map(source.workspace)
    target_records = _record_map(target.workspace)
    changes: list[WorkspaceRecordChange] = []
    added = removed = changed = unchanged = 0
    for record_id in sorted(set(source_records) | set(target_records)):
        before = source_records.get(record_id)
        after = target_records.get(record_id)
        if before is None:
            added += 1
            change = _make_change("added", record_id, None, after)
        elif after is None:
            removed += 1
            change = _make_change("removed", record_id, before, None)
        elif canonical_json(before) != canonical_json(after):
            changed += 1
            change = _make_change("changed", record_id, before, after)
        else:
            unchanged += 1
            continue
        if len(changes) < change_limit:
            changes.append(change)
    change_count = added + removed + changed
    truncated = len(changes) < change_count
    if truncated:
        warnings.append(f"transition changes truncated at {change_limit} records")
    body = {
        "source_snapshot_index": source.index,
        "target_snapshot_index": target.index,
        "source_workspace_address": source.workspace.get("content_address"),
        "target_workspace_address": target.workspace.get("content_address"),
        "source_status": source.status,
        "target_status": target.status,
        "source_review_state": source.review_state,
        "target_review_state": target.review_state,
        "metadata_changed": (
            source.status != target.status or source.review_state != target.review_state
        ),
        "source_record_count": len(source_records),
        "target_record_count": len(target_records),
        "added_count": added,
        "removed_count": removed,
        "changed_count": changed,
        "unchanged_count": unchanged,
        "truncated": truncated,
        "changes": tuple(changes),
        "warnings": tuple(warnings),
        "accepted": source.accepted and target.accepted,
    }
    return WorkspaceTransition(
        **body,
        content_address=content_hash(body, prefix="workspace-transition"),
    )


def _blocked_snapshot(snapshot: RunSnapshot, warning: str) -> WorkspaceHistorySnapshot:
    body = {
        "index": snapshot.index,
        "dossier_address": snapshot.dossier_address,
        "is_current": snapshot.is_current,
        "status": snapshot.status,
        "review_state": snapshot.review_state,
        "workspace_id": "",
        "workspace_state": "blocked",
        "record_count": 0,
        "record_type_counts": {},
        "state_counts": {},
        "workspace": None,
        "warnings": tuple(dict.fromkeys((*snapshot.warnings, warning))),
        "accepted": False,
    }
    return WorkspaceHistorySnapshot(
        **body,
        content_address=content_hash(body, prefix="workspace-history-snapshot"),
    )


def _snapshot_with_manifest(
    snapshot: RunSnapshot,
    dossier: Dossier,
    manifest: CaseManifest,
) -> WorkspaceHistorySnapshot:
    workspace = CaseWorkspaceBuilder().build(manifest, dossier=dossier)
    record_type_counts, state_counts = _counts(workspace)
    public_workspace = _public_workspace(workspace)
    body = {
        "index": snapshot.index,
        "dossier_address": snapshot.dossier_address,
        "is_current": snapshot.is_current,
        "status": dossier.status.value,
        "review_state": _review_state(dossier),
        "workspace_id": workspace.workspace_id,
        "workspace_state": workspace.state.value,
        "record_count": len(workspace.records),
        "record_type_counts": record_type_counts,
        "state_counts": state_counts,
        "workspace": public_workspace,
        "warnings": tuple(dict.fromkeys((*snapshot.warnings, *workspace.warnings))),
        "accepted": snapshot.accepted,
    }
    accepted = snapshot.accepted and not _has_forbidden_key(body) and not contains_private_key(body)
    warnings = tuple(body["warnings"])
    if not accepted:
        body["workspace"] = None
        body["record_count"] = 0
        body["record_type_counts"] = {}
        body["state_counts"] = {}
        warnings = tuple(
            dict.fromkeys((*warnings, "historical workspace failed public-boundary checks"))
        )
        body["warnings"] = warnings
    body["accepted"] = accepted
    return WorkspaceHistorySnapshot(
        **body,
        content_address=content_hash(body, prefix="workspace-history-snapshot"),
    )


def _load_manifest(runtime: CaseRuntime, run_id: str) -> CaseManifest:
    inspection = inspect_run(runtime, run_id)
    input_address = str(inspection.summary.input_address)
    raw = runtime.store.store.get(input_address)
    if not isinstance(raw, Mapping):
        raise ValidationError("persisted run input must be an object")
    return CaseManifest.from_dict(raw)


def _load_dossier(runtime: CaseRuntime, snapshot: RunSnapshot) -> Dossier:
    raw = runtime.store.store.get(snapshot.dossier_address)
    if not isinstance(raw, Mapping):
        raise ValidationError("historical dossier snapshot must be an object")
    dossier = Dossier.from_dict(raw)
    if dossier.content_address != snapshot.dossier_address:
        raise ValidationError("historical dossier address changed during workspace reconstruction")
    return dossier


def _history_body(
    history: RunHistory,
    snapshots: tuple[WorkspaceHistorySnapshot, ...],
    transitions: tuple[WorkspaceTransition, ...],
    *,
    warnings: tuple[str, ...],
    accepted: bool,
) -> dict[str, Any]:
    return {
        "workspace_history_version": WORKSPACE_HISTORY_VERSION,
        "run_id": history.run_id,
        "case_id": history.case_id,
        "current_snapshot_index": history.current_snapshot_index,
        "snapshots": snapshots,
        "transitions": transitions,
        "replay_accepted": history.replay_accepted,
        "accepted": accepted,
        "warnings": warnings,
    }


def build_persisted_workspace_history(
    runtime: CaseRuntime,
    run_id: str,
    *,
    change_limit: int = WORKSPACE_HISTORY_MAX_CHANGES,
) -> WorkspaceHistory:
    """Rebuild every verified dossier snapshot as a historical workspace."""

    if change_limit < 1 or change_limit > WORKSPACE_HISTORY_MAX_CHANGES:
        raise ValidationError(
            f"change_limit must be between 1 and {WORKSPACE_HISTORY_MAX_CHANGES}"
        )
    history = build_run_history(runtime, run_id)
    warnings = list(history.warnings)
    snapshots: list[WorkspaceHistorySnapshot] = []
    manifest: CaseManifest | None = None
    if history.accepted:
        try:
            manifest = _load_manifest(runtime, run_id)
        except (StoreError, KeyError, TypeError, ValueError, ValidationError) as exc:
            warnings.append(f"workspace manifest reconstruction failed: {exc}")
        if manifest is not None:
            for snapshot in history.snapshots:
                try:
                    dossier = _load_dossier(runtime, snapshot)
                    projected = _snapshot_with_manifest(snapshot, dossier, manifest)
                except (StoreError, KeyError, TypeError, ValueError, ValidationError) as exc:
                    warnings.append(f"snapshot {snapshot.index} workspace reconstruction failed: {exc}")
                    projected = _blocked_snapshot(snapshot, "workspace reconstruction failed")
                snapshots.append(projected)
    if not snapshots:
        snapshots.extend(
            _blocked_snapshot(item, "run history failed integrity; workspace records withheld")
            for item in history.snapshots
        )
    snapshot_values = tuple(snapshots)
    transitions = tuple(
        _transition(snapshot_values[index], snapshot_values[index + 1], change_limit=change_limit)
        for index in range(max(0, len(snapshot_values) - 1))
    )
    accepted = (
        history.accepted
        and all(item.accepted for item in snapshot_values)
        and all(item.accepted for item in transitions)
        and not _has_forbidden_key(
            {
                "snapshots": snapshot_values,
                "transitions": transitions,
            }
        )
        and not contains_private_key(
            {
                "snapshots": snapshot_values,
                "transitions": transitions,
            }
        )
    )
    if not accepted and history.accepted:
        warnings.append("historical workspace closure is blocked by snapshot or transition checks")
    final_warnings = tuple(dict.fromkeys(warnings))
    body = _history_body(
        history,
        snapshot_values,
        transitions,
        warnings=final_warnings,
        accepted=accepted,
    )
    return WorkspaceHistory(
        run_id=history.run_id,
        case_id=history.case_id,
        current_snapshot_index=history.current_snapshot_index,
        snapshots=snapshot_values,
        transitions=transitions,
        replay_accepted=history.replay_accepted,
        accepted=accepted,
        warnings=final_warnings,
        content_address=content_hash(body, prefix="workspace-history"),
    )


def _select_snapshot(history: WorkspaceHistory, index: int) -> WorkspaceHistorySnapshot:
    if index < 0 or index >= len(history.snapshots):
        raise ValidationError(f"snapshot index must be between 0 and {len(history.snapshots) - 1}")
    snapshot = history.snapshots[index]
    if not snapshot.accepted or snapshot.workspace is None:
        raise ValidationError(f"workspace snapshot {index} is not accepted")
    return snapshot


def compare_persisted_workspace_snapshots(
    runtime: CaseRuntime,
    run_id: str,
    source_snapshot: int,
    target_snapshot: int,
    *,
    change_limit: int = WORKSPACE_HISTORY_MAX_CHANGES,
) -> WorkspaceTransition:
    """Return one selected workspace transition from a verified history."""

    history = build_persisted_workspace_history(
        runtime,
        run_id,
        change_limit=change_limit,
    )
    if not history.accepted:
        raise ValidationError("workspace history is not accepted")
    source = _select_snapshot(history, source_snapshot)
    target = _select_snapshot(history, target_snapshot)
    return _transition(source, target, change_limit=change_limit)


__all__ = [
    "WORKSPACE_HISTORY_MAX_CHANGES",
    "WORKSPACE_HISTORY_VERSION",
    "WorkspaceHistory",
    "WorkspaceHistorySnapshot",
    "WorkspaceRecordChange",
    "WorkspaceTransition",
    "build_persisted_workspace_history",
    "compare_persisted_workspace_snapshots",
]

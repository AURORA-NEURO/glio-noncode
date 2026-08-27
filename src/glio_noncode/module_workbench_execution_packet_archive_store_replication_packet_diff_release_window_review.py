"""Build an append-only review ledger for release-window evidence.

This module turns verified evidence into an explicit review record. It does not
assign a reviewer, infer authorization, mutate an archive store, or promote a
window on the basis of sensitivity analysis. A promote decision is accepted
only when both the release window and its independent assurance are already
release-ready; every other decision carries a bounded rationale and explicit
follow-up actions.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_from_directories,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance import (
    build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_contracts import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_BOUNDARY,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ENTRY_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ENTRIES,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_REQUIRED_ACTIONS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_TEXT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_entry,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity import (
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity,
)
from .serialization import canonical_json


def _text(
    value: Any,
    field: str,
    maximum: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_TEXT,
) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{field} must be a bounded non-empty string")
    return value


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _text_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise ValidationError(f"{field} must be an array")
    if (
        len(value)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_REQUIRED_ACTIONS
    ):
        raise ValidationError(f"{field} exceeds the published limit")
    result = tuple(_text(item, f"{field}[]") for item in value)
    if len(set(result)) != len(result):
        raise ValidationError(f"{field} must not contain duplicates")
    return result


def _decision(value: Any) -> str:
    normalized = (
        value.value
        if isinstance(
            value,
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision,
        )
        else value
    )
    if normalized not in {
        item.value
        for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision
    }:
        raise ValidationError("review decision is invalid")
    return normalized


def _review_entry(
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    assurance: Any,
    *,
    ordinal: int,
    entry_id: str,
    decision: str,
    rationale: str,
    required_actions: Sequence[str],
    previous_entry_address: str | None,
    supersedes_entry_address: str | None,
    sensitivity: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity
    | None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry:
    """Create one decision after verifying all supplied evidence references."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
        window
    )
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
        assurance
    )
    if assurance.window_address != window.content_address:
        raise ValidationError("review assurance does not reference the review window")
    if sensitivity is not None:
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            sensitivity
        )
        if not any(item.window_address == window.content_address for item in sensitivity.scenarios):
            raise ValidationError("review sensitivity does not contain the review window")
    entry_id = _text(entry_id, "review entry ID", 256)
    decision = _decision(decision)
    rationale = _text(rationale, "review rationale")
    actions = _text_tuple(required_actions, "review required actions")
    window_ready = bool(window.release_ready)
    assurance_ready = bool(assurance.release_ready)
    if (
        decision
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.PROMOTE.value
    ):
        if not window_ready or not assurance_ready:
            raise ValidationError("promote decision requires release-ready window and assurance")
        if actions:
            raise ValidationError("promote decision cannot retain required actions")
    elif not actions:
        raise ValidationError("non-promote decision requires at least one required action")
    release_ready = (
        decision
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.PROMOTE.value
    )
    body = {
        "ordinal": ordinal,
        "entry_id": entry_id,
        "window_address": window.content_address,
        "assurance_address": assurance.content_address,
        "sensitivity_address": None if sensitivity is None else sensitivity.content_address,
        "decision": decision,
        "state": {
            "promote": ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState.PROMOTED.value,
            "hold": ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState.HOLD.value,
            "block": ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState.BLOCKED.value,
            "supersede": ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState.SUPERSEDED.value,
        }[decision],
        "release_ready": release_ready,
        "accepted": True,
        "rationale": rationale,
        "required_actions": actions,
        "supersedes_entry_address": supersedes_entry_address,
        "previous_entry_address": previous_entry_address,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_ENTRY_PREFIX
        + ":pending-entry",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_entry(
            provisional
        ),
    )


def _ledger(
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    assurance: Any,
    entries: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry, ...
    ],
    *,
    ledger_id: str,
    sensitivity: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity
    | None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview:
    """Assemble a ledger and derive its head state from the entry chain."""

    body = {
        "ledger_id": _text(ledger_id, "review ledger ID", 256),
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_BOUNDARY,
        "window_address": window.content_address,
        "assurance_address": assurance.content_address,
        "sensitivity_address": None if sensitivity is None else sensitivity.content_address,
        "entries": entries,
        "entry_count": len(entries),
        "head_address": entries[-1].content_address if entries else None,
        "state": entries[-1].state
        if entries
        else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState.UNREVIEWED.value,
        "release_ready": bool(entries and entries[-1].release_ready),
        "accepted": bool(entries) and all(item.accepted for item in entries),
        "append_only": True,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview(
        **body,
        content_address=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_PREFIX
        + ":pending-ledger",
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
            provisional
        ),
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_entry(
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    assurance: Any,
    *,
    entry_id: str,
    decision: str
    | ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision,
    rationale: str,
    required_actions: Sequence[str] = (),
    sensitivity: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity
    | None = None,
    ordinal: int = 0,
    previous_entry_address: str | None = None,
    supersedes_entry_address: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry:
    """Build one independently addressed review decision."""

    if (
        ordinal < 0
        or ordinal
        >= MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ENTRIES
    ):
        raise ValidationError("review entry ordinal is outside the bound")
    if (
        _decision(decision)
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.SUPERSEDE.value
        and supersedes_entry_address is None
    ):
        raise ValidationError("supersede decisions require a superseded entry address")
    if (
        _decision(decision)
        != ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.SUPERSEDE.value
        and supersedes_entry_address is not None
    ):
        raise ValidationError("only supersede decisions may reference a prior entry")
    if previous_entry_address is not None:
        _address(previous_entry_address, "previous review entry address")
    return _review_entry(
        window,
        assurance,
        ordinal=ordinal,
        entry_id=entry_id,
        decision=decision,
        rationale=rationale,
        required_actions=required_actions,
        previous_entry_address=previous_entry_address,
        supersedes_entry_address=supersedes_entry_address,
        sensitivity=sensitivity,
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    assurance: Any,
    *,
    decisions: Sequence[Mapping[str, Any]] = (),
    sensitivity: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity
    | None = None,
    ledger_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview:
    """Build a complete append-only ledger from explicit decision mappings."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
        window
    )
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
        assurance
    )
    if (
        len(decisions)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ENTRIES
    ):
        raise ValidationError("review decision count exceeds the published limit")
    entries: list[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewEntry
    ] = []
    seen: set[str] = set()
    for ordinal, raw in enumerate(decisions):
        if not isinstance(raw, Mapping):
            raise ValidationError("review decisions must be objects")
        entry_id = _text(raw.get("entry_id"), "review decision entry ID", 256)
        if entry_id in seen:
            raise ValidationError("review decision entry IDs must be unique")
        seen.add(entry_id)
        decision = _decision(raw.get("decision"))
        supersedes = raw.get("supersedes_entry_address")
        if (
            supersedes is None
            and decision
            == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.SUPERSEDE.value
            and entries
        ):
            supersedes = entries[-1].content_address
        entry = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_entry(
            window,
            assurance,
            entry_id=entry_id,
            decision=decision,
            rationale=_text(raw.get("rationale"), "review decision rationale"),
            required_actions=raw.get("required_actions", ()),
            sensitivity=sensitivity,
            ordinal=ordinal,
            previous_entry_address=entries[-1].content_address if entries else None,
            supersedes_entry_address=supersedes,
        )
        entries.append(entry)
    return _ledger(window, assurance, tuple(entries), ledger_id=ledger_id, sensitivity=sensitivity)


def append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_decision(
    ledger: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow,
    assurance: Any,
    *,
    entry_id: str,
    decision: str
    | ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision,
    rationale: str,
    required_actions: Sequence[str] = (),
    sensitivity: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity
    | None = None,
    supersedes_entry_address: str | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview:
    """Append exactly one decision after proving the current ledger head."""

    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
        ledger, window=window, assurance=assurance, sensitivity=sensitivity
    )
    if (
        ledger.entry_count
        >= MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ENTRIES
    ):
        raise ValidationError("review ledger is at its entry limit")
    decision = _decision(decision)
    if (
        decision
        == ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision.SUPERSEDE.value
        and supersedes_entry_address is None
    ):
        supersedes_entry_address = ledger.head_address
    entry = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_entry(
        window,
        assurance,
        entry_id=entry_id,
        decision=decision,
        rationale=rationale,
        required_actions=required_actions,
        sensitivity=sensitivity,
        ordinal=ledger.entry_count,
        previous_entry_address=ledger.head_address,
        supersedes_entry_address=supersedes_entry_address,
    )
    return _ledger(
        window,
        assurance,
        ledger.entries + (entry,),
        ledger_id=ledger.ledger_id,
        sensitivity=sensitivity,
    )


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_from_directories(
    pairs: Sequence[tuple[str, str | Path, str | Path]],
    *,
    decisions: Sequence[Mapping[str, Any]] = (),
    policy: Any | None = None,
    batch_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-batch",
    window_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window",
    ledger_id: str = "glio-noncode-module-workbench-execution-archive-store-replication-packet-diff-release-window-review",
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview:
    """Build a review ledger directly from persisted packet directories."""

    window = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_from_directories(
        pairs, policy=policy, batch_id=batch_id, window_id=window_id
    )
    from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime import (
        run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_from_directories,
    )

    runtime = run_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_runtime_from_directories(
        pairs, policy=policy, batch_id=batch_id, window_id=window_id
    )
    assurance = build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
        window, runtime
    )
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
        window, assurance, decisions=decisions, ledger_id=ledger_id
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
    *,
    window: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindow
    | None = None,
    assurance: Any | None = None,
    sensitivity: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowSensitivity
    | None = None,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview:
    """Verify chain continuity, addresses, and optional evidence linkage."""

    if not isinstance(
        value, ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview
    ):
        raise ValidationError("review verification requires a typed ledger")
    if window is not None:
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window(
            window
        )
        if value.window_address != window.content_address:
            raise ValidationError("review ledger window link differs")
    if assurance is not None:
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_assurance(
            assurance
        )
        if value.assurance_address != assurance.content_address:
            raise ValidationError("review ledger assurance link differs")
    if sensitivity is not None:
        verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_sensitivity(
            sensitivity
        )
        if value.sensitivity_address != sensitivity.content_address:
            raise ValidationError("review ledger sensitivity link differs")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
            value
        )
        != value.content_address
    ):
        raise ValidationError("review ledger address mismatch")
    return value


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "entry_id",
        "window_address",
        "assurance_address",
        "sensitivity_address",
        "decision",
        "state",
        "release_ready",
        "accepted",
        "rationale",
        "required_actions",
        "supersedes_entry_address",
        "previous_entry_address",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for item in value.entries:
        row = item.to_dict()
        row["required_actions"] = " | ".join(item.required_actions)
        writer.writerow(row)
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReview,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review(
        value
    )
    lines = [
        "# Archive Store Replication Packet Diff Release Window Review",
        "",
        f"- state: `{value.state}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- append-only: `{str(value.append_only).lower()}`",
        f"- entries: `{value.entry_count}`",
        f"- head: `{value.head_address}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Entry | Decision | State | Ready | Actions | Rationale |",
        "|---:|---|---|---|---|---:|---|",
    ]
    for item in value.entries:
        lines.append(
            f"| {item.ordinal} | {item.entry_id} | {item.decision} | {item.state} | "
            f"{str(item.release_ready).lower()} | {len(item.required_actions)} | {item.rationale} |"
        )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_schema() -> (
    dict[str, Any]
):
    """Describe the review ledger and its fail-closed decision rules."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_BOUNDARY,
        "decisions": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewDecision
        ],
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewState
        ],
        "promote_requires": [
            "window_release_ready",
            "assurance_release_ready",
            "zero_required_actions",
        ],
        "non_promote_requires": ["rationale", "required_actions"],
        "append_only": True,
        "automatic_approval": False,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
        "limits": {
            "max_entries": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_ENTRIES,
            "max_required_actions": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_MAX_REQUIRED_ACTIONS,
        },
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_capabilities() -> (
    dict[str, Any]
):
    """Declare review-ledger operations."""

    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_VERSION,
        "operations": [
            "build",
            "build_from_directories",
            "append",
            "verify",
            "json",
            "csv",
            "markdown",
        ],
        "append_only": True,
        "automatic_approval": False,
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
        "fail_closed": True,
    }


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
    or name.startswith(
        "append_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review"
    )
    or name.startswith(
        "build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review"
    )
    or name.startswith(
        "module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review"
    )
    or name.startswith(
        "render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review"
    )
    or name.startswith(
        "verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review"
    )
]

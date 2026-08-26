"""Read-only maintenance planning over the local storage audit.

An audit explains what is wrong.  A maintenance plan explains what an operator
could review next.  This module deliberately stops at that boundary: no plan
method deletes an object, rewrites an index, restores a reference, or runs a
repair.  Each proposed action points back to the audit address and is marked
review-only so an external approval system cannot mistake diagnostics for an
execution command.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from io import StringIO
from typing import Any

from .errors import ValidationError
from .release_assurance_support import text_matches
from .runtime import CaseRuntime
from .serialization import canonical_json, content_hash
from .storage_audit import (
    StorageAuditReport,
    build_storage_audit,
)
from .storage_maintenance_contracts import (
    STORAGE_MAINTENANCE_ACTION_KINDS,
    STORAGE_MAINTENANCE_BOUNDARY,
    STORAGE_MAINTENANCE_DEFAULT_LIMIT,
    STORAGE_MAINTENANCE_MAX_ACTIONS,
    STORAGE_MAINTENANCE_MAX_LIMIT,
    STORAGE_MAINTENANCE_SCHEMA_VERSION,
    STORAGE_MAINTENANCE_SEVERITIES,
    STORAGE_MAINTENANCE_VERSION,
    StorageMaintenanceAction,
    StorageMaintenanceActionKind,
    StorageMaintenanceDiff,
    StorageMaintenancePlan,
    StorageMaintenancePolicy,
    StorageMaintenanceQueryResult,
    StorageMaintenanceSeverity,
    StorageMaintenanceState,
)


def _text(value: Any, field: str, *, maximum: int = 500) -> str:
    if value is None:
        raise ValidationError(f"{field} must not be empty")
    result = str(value).strip()
    if not result:
        raise ValidationError(f"{field} must not be empty")
    if len(result) > maximum:
        raise ValidationError(f"{field} exceeds the maximum length")
    return result


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


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValidationError(f"{field} must be boolean")
    return value


def _as_report(value: StorageAuditReport | CaseRuntime) -> StorageAuditReport:
    if isinstance(value, StorageAuditReport):
        return value
    if isinstance(value, CaseRuntime):
        return build_storage_audit(value)
    raise ValidationError("storage maintenance requires a storage audit or case runtime")


def build_storage_maintenance_policy(
    *,
    plan_id: str,
    max_actions: int = 256,
    include_orphans: bool = True,
    include_unexpected: bool = True,
    include_missing: bool = True,
    include_invalid: bool = True,
    include_failed_indexes: bool = True,
    require_manual_approval: bool = True,
) -> StorageMaintenancePolicy:
    """Build bounded policy controls for a review-only maintenance plan."""

    return StorageMaintenancePolicy(
        plan_id=_text(plan_id, "plan_id", maximum=180),
        max_actions=_int(
            max_actions,
            "max_actions",
            minimum=1,
            maximum=STORAGE_MAINTENANCE_MAX_ACTIONS,
        ),
        include_orphans=_bool(include_orphans, "include_orphans"),
        include_unexpected=_bool(include_unexpected, "include_unexpected"),
        include_missing=_bool(include_missing, "include_missing"),
        include_invalid=_bool(include_invalid, "include_invalid"),
        include_failed_indexes=_bool(include_failed_indexes, "include_failed_indexes"),
        require_manual_approval=_bool(require_manual_approval, "require_manual_approval"),
    )


def _severity_for(kind: StorageMaintenanceActionKind) -> StorageMaintenanceSeverity:
    if kind in {
        StorageMaintenanceActionKind.RESTORE_MISSING_OBJECT,
        StorageMaintenanceActionKind.REPAIR_INVALID_OBJECT,
        StorageMaintenanceActionKind.REPLAY_RUN,
        StorageMaintenanceActionKind.REOPEN_BATCH,
    }:
        return StorageMaintenanceSeverity.HIGH
    if kind in {
        StorageMaintenanceActionKind.QUARANTINE_ORPHAN,
        StorageMaintenanceActionKind.QUARANTINE_UNEXPECTED,
    }:
        return StorageMaintenanceSeverity.MODERATE
    return StorageMaintenanceSeverity.NONE


def _target_path(address: str | None, path: str | None) -> str | None:
    if path:
        return str(path).replace("\\", "/")
    if address and address.startswith("sha256:"):
        return f"objects/{address.split(':', 1)[1]}.json"
    return None


def _action(
    *,
    index: int,
    kind: StorageMaintenanceActionKind,
    target_path: str | None,
    target_address: str | None,
    reason: str,
    estimated_bytes: int = 0,
    approval_required: bool = True,
) -> StorageMaintenanceAction:
    body = {
        "action_id": f"storage-maintenance-action-{index:04d}",
        "kind": kind,
        "severity": _severity_for(kind),
        "target_path": _target_path(target_address, target_path),
        "target_address": target_address,
        "reason": _text(reason, "reason", maximum=500),
        "reversible": kind
        in {
            StorageMaintenanceActionKind.QUARANTINE_ORPHAN,
            StorageMaintenanceActionKind.QUARANTINE_UNEXPECTED,
        },
        "approval_required": approval_required,
        "review_only": True,
        "estimated_bytes": _int(estimated_bytes, "estimated_bytes", minimum=0),
        "accepted": True,
    }
    return StorageMaintenanceAction(
        **body,
        content_address=content_hash(body, prefix="storage-maintenance-action"),
    )


def _object_sizes(report: StorageAuditReport) -> dict[str, int]:
    return {item.address: item.byte_count for item in report.objects}


def _append_orphan_actions(
    actions: list[StorageMaintenanceAction],
    report: StorageAuditReport,
    *,
    approval_required: bool,
) -> None:
    sizes = _object_sizes(report)
    for address in report.orphan_addresses:
        actions.append(
            _action(
                index=len(actions) + 1,
                kind=StorageMaintenanceActionKind.QUARANTINE_ORPHAN,
                target_path=None,
                target_address=address,
                reason=(
                    "object is valid but unreachable from run and batch roots; "
                    "quarantine only after review"
                ),
                estimated_bytes=sizes.get(address, 0),
                approval_required=approval_required,
            )
        )


def _append_unexpected_actions(
    actions: list[StorageMaintenanceAction],
    report: StorageAuditReport,
    *,
    approval_required: bool,
) -> None:
    for path in report.unexpected_entries:
        actions.append(
            _action(
                index=len(actions) + 1,
                kind=StorageMaintenanceActionKind.QUARANTINE_UNEXPECTED,
                target_path=path,
                target_address=None,
                reason=(
                    "filesystem entry is outside the recognized storage layout; "
                    "inspect before quarantine"
                ),
                approval_required=approval_required,
            )
        )


def _append_missing_actions(
    actions: list[StorageMaintenanceAction],
    report: StorageAuditReport,
    *,
    approval_required: bool,
) -> None:
    for address in report.missing_addresses:
        actions.append(
            _action(
                index=len(actions) + 1,
                kind=StorageMaintenanceActionKind.RESTORE_MISSING_OBJECT,
                target_path=None,
                target_address=address,
                reason=(
                    "referenced object is missing; recover from a trusted backup "
                    "or block the dependent run"
                ),
                approval_required=approval_required,
            )
        )


def _append_invalid_actions(
    actions: list[StorageMaintenanceAction],
    report: StorageAuditReport,
    *,
    approval_required: bool,
) -> None:
    for item in report.objects:
        if item.accepted:
            continue
        actions.append(
            _action(
                index=len(actions) + 1,
                kind=StorageMaintenanceActionKind.REPAIR_INVALID_OBJECT,
                target_path=f"objects/{item.filename}",
                target_address=item.address,
                reason=(
                    "object bytes, JSON, or content address failed audit; "
                    "preserve the original before repair"
                ),
                estimated_bytes=item.byte_count,
                approval_required=approval_required,
            )
        )


def _append_index_actions(
    actions: list[StorageMaintenanceAction],
    report: StorageAuditReport,
    *,
    approval_required: bool,
) -> None:
    for item in report.runs:
        if item.accepted:
            continue
        actions.append(
            _action(
                index=len(actions) + 1,
                kind=StorageMaintenanceActionKind.REPLAY_RUN,
                target_path=f"runs/{item.filename}",
                target_address=None,
                reason=(
                    "run index or replay integrity failed; reopen and compare "
                    "history before any rewrite"
                ),
                approval_required=approval_required,
            )
        )
    for item in report.batches:
        if item.accepted:
            continue
        actions.append(
            _action(
                index=len(actions) + 1,
                kind=StorageMaintenanceActionKind.REOPEN_BATCH,
                target_path=f"batches/{item.filename}",
                target_address=item.result_address,
                reason=(
                    "batch index or result reopen failed; inspect the complete "
                    "batch before any rewrite"
                ),
                approval_required=approval_required,
            )
        )


def _state_for(
    report: StorageAuditReport, actions: tuple[StorageMaintenanceAction, ...]
) -> StorageMaintenanceState:
    if (
        report.accepted
        and len(actions) == 1
        and actions[0].kind is StorageMaintenanceActionKind.NO_ACTION
    ):
        return StorageMaintenanceState.CLEAN
    if report.missing_addresses:
        return StorageMaintenanceState.BLOCKED
    if any(
        item.kind
        in {
            StorageMaintenanceActionKind.RESTORE_MISSING_OBJECT,
            StorageMaintenanceActionKind.REPAIR_INVALID_OBJECT,
            StorageMaintenanceActionKind.REPLAY_RUN,
            StorageMaintenanceActionKind.REOPEN_BATCH,
        }
        for item in actions
    ):
        return StorageMaintenanceState.BLOCKED
    return StorageMaintenanceState.REVIEW


def build_storage_maintenance_plan(
    source: StorageAuditReport | CaseRuntime,
    *,
    policy: StorageMaintenancePolicy | Mapping[str, Any] | None = None,
    plan_id: str | None = None,
) -> StorageMaintenancePlan:
    """Create a deterministic, bounded, non-executing plan from an audit."""

    report = _as_report(source)
    selected_policy = (
        policy
        if isinstance(policy, StorageMaintenancePolicy)
        else StorageMaintenancePolicy.from_mapping(policy)
        if policy is not None
        else build_storage_maintenance_policy(plan_id=plan_id or "glio-noncode-storage-maintenance")
    )
    if plan_id is not None and selected_policy.plan_id != plan_id:
        raise ValidationError("maintenance plan ID does not match its policy")
    actions: list[StorageMaintenanceAction] = []
    approval_required = selected_policy.require_manual_approval
    if selected_policy.include_missing:
        _append_missing_actions(actions, report, approval_required=approval_required)
    if selected_policy.include_invalid:
        _append_invalid_actions(actions, report, approval_required=approval_required)
    if selected_policy.include_failed_indexes:
        _append_index_actions(actions, report, approval_required=approval_required)
    if selected_policy.include_orphans:
        _append_orphan_actions(actions, report, approval_required=approval_required)
    if selected_policy.include_unexpected:
        _append_unexpected_actions(actions, report, approval_required=approval_required)
    if not actions:
        actions.append(
            _action(
                index=1,
                kind=StorageMaintenanceActionKind.NO_ACTION,
                target_path=None,
                target_address=None,
                reason="storage audit is accepted and no maintenance action is proposed",
                approval_required=False,
            )
        )
    overflow = len(actions) > selected_policy.max_actions
    actions = actions[: selected_policy.max_actions]
    ordered = tuple(sorted(actions, key=lambda item: item.action_id))
    state = _state_for(report, ordered)
    if overflow:
        state = StorageMaintenanceState.BLOCKED
    body = {
        "plan_id": selected_policy.plan_id,
        "root": str(report.root),
        "audit_address": report.content_address,
        "policy": selected_policy.to_dict(),
        "actions": tuple(item.to_dict() for item in ordered),
        "state": state,
        "object_count": report.object_count,
        "orphan_count": report.orphan_object_count,
        "missing_count": report.missing_reference_count,
        "invalid_count": sum(not item.accepted for item in report.objects),
        "unexpected_count": len(report.unexpected_entries),
        "run_count": report.run_count,
        "batch_count": report.batch_count,
        "audit_accepted": report.accepted,
        "safe_to_apply": False,
        "accepted": not overflow,
    }
    address_body = {"storage_maintenance_version": STORAGE_MAINTENANCE_VERSION} | body
    return StorageMaintenancePlan(
        **(body | {"policy": selected_policy, "actions": ordered}),
        content_address=content_hash(address_body, prefix="storage-maintenance-plan"),
    )


def _as_plan(
    value: StorageMaintenancePlan | Mapping[str, Any],
) -> StorageMaintenancePlan:
    if isinstance(value, StorageMaintenancePlan):
        return value
    return StorageMaintenancePlan.from_mapping(value)


def query_storage_maintenance(
    plan: StorageMaintenancePlan | Mapping[str, Any],
    *,
    kind: str | None = None,
    severity: str | None = None,
    reversible_only: bool = False,
    text: str | None = None,
    offset: int = 0,
    limit: int = STORAGE_MAINTENANCE_DEFAULT_LIMIT,
) -> StorageMaintenanceQueryResult:
    """Return a bounded action page without changing the plan."""

    selected = _as_plan(plan)
    offset = _int(offset, "offset", minimum=0)
    limit = _int(limit, "limit", minimum=1, maximum=STORAGE_MAINTENANCE_MAX_LIMIT)
    kind_filter = None if kind is None else _text(kind, "kind", maximum=80).lower()
    severity_filter = None if severity is None else _text(severity, "severity", maximum=40).lower()
    text_filter = None if text is None else _text(text, "text", maximum=240).lower()
    if kind_filter is not None and kind_filter not in STORAGE_MAINTENANCE_ACTION_KINDS:
        raise ValidationError(f"unsupported maintenance action kind: {kind_filter}")
    if severity_filter is not None and severity_filter not in STORAGE_MAINTENANCE_SEVERITIES:
        raise ValidationError(f"unsupported maintenance severity: {severity_filter}")
    items = selected.actions
    if kind_filter is not None:
        items = tuple(item for item in items if item.kind.value == kind_filter)
    if severity_filter is not None:
        items = tuple(item for item in items if item.severity.value == severity_filter)
    if reversible_only:
        items = tuple(item for item in items if item.reversible)
    if text_filter:
        items = tuple(item for item in items if text_matches(item.to_dict(), text_filter))
    total = len(items)
    page = items[offset : offset + limit]
    filters = {
        "kind": kind,
        "severity": severity,
        "reversible_only": reversible_only,
        "text": text,
    }
    body = {
        "plan_id": selected.plan_id,
        "resource": "actions",
        "filters": filters,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": tuple(item.to_dict() for item in page),
        "accepted": selected.accepted,
    }
    return StorageMaintenanceQueryResult(
        plan_id=selected.plan_id,
        resource="actions",
        filters=filters,
        total=total,
        offset=offset,
        limit=limit,
        items=tuple(item.to_dict() for item in page),
        accepted=selected.accepted,
        content_address=content_hash(body, prefix="storage-maintenance-query"),
    )


def diff_storage_maintenance(
    baseline: StorageMaintenancePlan | Mapping[str, Any],
    candidate: StorageMaintenancePlan | Mapping[str, Any],
) -> StorageMaintenanceDiff:
    """Compare action closure and routing state between two plans."""

    left = _as_plan(baseline)
    right = _as_plan(candidate)
    left_actions = {item.action_id: item for item in left.actions}
    right_actions = {item.action_id: item for item in right.actions}
    added = tuple(sorted(set(right_actions) - set(left_actions)))
    removed = tuple(sorted(set(left_actions) - set(right_actions)))
    changed = tuple(
        sorted(
            action_id
            for action_id in set(left_actions) & set(right_actions)
            if left_actions[action_id].content_address != right_actions[action_id].content_address
        )
    )
    body = {
        "baseline_plan_id": left.plan_id,
        "candidate_plan_id": right.plan_id,
        "baseline_address": left.content_address,
        "candidate_address": right.content_address,
        "added_action_ids": added,
        "removed_action_ids": removed,
        "changed_action_ids": changed,
        "state_changed": left.state != right.state,
        "audit_changed": left.audit_address != right.audit_address,
        "accepted": left.accepted and right.accepted,
    }
    address_body = {"storage_maintenance_diff_version": "storage-maintenance-diff-v1"} | body
    return StorageMaintenanceDiff(
        **body,
        content_address=content_hash(address_body, prefix="storage-maintenance-diff"),
    )


def storage_maintenance_json(plan: StorageMaintenancePlan | Mapping[str, Any]) -> str:
    """Serialize a strict plan as canonical JSON."""

    return canonical_json(_as_plan(plan).to_dict())


def storage_maintenance_csv(plan: StorageMaintenancePlan | Mapping[str, Any]) -> str:
    """Serialize the action ledger as deterministic CSV."""

    selected = _as_plan(plan)
    output = StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        (
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
        )
    )
    for item in selected.actions:
        writer.writerow(
            (
                item.action_id,
                item.kind.value,
                item.severity.value,
                item.target_path or "",
                item.target_address or "",
                item.reason,
                str(item.reversible).lower(),
                str(item.approval_required).lower(),
                str(item.review_only).lower(),
                item.estimated_bytes,
                str(item.accepted).lower(),
                item.content_address,
            )
        )
    return output.getvalue()


def storage_maintenance_markdown(plan: StorageMaintenancePlan | Mapping[str, Any]) -> str:
    """Serialize the plan as a public operator review table."""

    selected = _as_plan(plan)
    lines = [
        "# Storage maintenance plan",
        "",
        f"- Plan: `{selected.plan_id}`",
        f"- Audit: `{selected.audit_address}`",
        f"- State: `{selected.state.value}`",
        f"- Accepted: `{str(selected.accepted).lower()}`",
        f"- Actions: {selected.action_count}",
        f"- Review only: `{str(not selected.safe_to_apply).lower()}`",
        "",
        "| Action | Kind | Severity | Target | Reversible | Approval | Reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| `{item.action_id}` | `{item.kind.value}` | `{item.severity.value}` | "
        f"`{item.target_path or item.target_address or '-'}` | "
        f"`{str(item.reversible).lower()}` | `{str(item.approval_required).lower()}` | "
        f"{item.reason} |"
        for item in selected.actions
    )
    return "\n".join(lines) + "\n"


def storage_maintenance_capabilities() -> dict[str, Any]:
    """Describe the review-only maintenance feature set."""

    return {
        "version": STORAGE_MAINTENANCE_VERSION,
        "schema_version": STORAGE_MAINTENANCE_SCHEMA_VERSION,
        "boundary": STORAGE_MAINTENANCE_BOUNDARY,
        "review_only": True,
        "automatic_mutation": False,
        "automatic_deletion": False,
        "manual_approval": True,
        "bounded_actions": True,
        "bounded_query": True,
        "structural_diff": True,
        "json_export": True,
        "csv_export": True,
        "markdown_export": True,
        "public_boundary": True,
        "timestamp_free": True,
        "action_kinds": STORAGE_MAINTENANCE_ACTION_KINDS,
        "severities": STORAGE_MAINTENANCE_SEVERITIES,
        "max_actions": STORAGE_MAINTENANCE_MAX_ACTIONS,
    }


def storage_maintenance_schema() -> dict[str, Any]:
    """Return the public maintenance-plan schema declaration."""

    return {
        "version": STORAGE_MAINTENANCE_SCHEMA_VERSION,
        "type": "object",
        "boundary": STORAGE_MAINTENANCE_BOUNDARY,
        "required": (
            "storage_maintenance_version",
            "plan_id",
            "root",
            "audit_address",
            "policy",
            "actions",
            "state",
            "audit_accepted",
            "safe_to_apply",
            "accepted",
            "content_address",
        ),
        "states": tuple(item.value for item in StorageMaintenanceState),
        "action_kinds": tuple(item.value for item in StorageMaintenanceActionKind),
        "severities": tuple(item.value for item in StorageMaintenanceSeverity),
        "max_actions": STORAGE_MAINTENANCE_MAX_ACTIONS,
        "review_only": True,
    }


__all__ = [
    name
    for name in globals()
    if name.startswith("build_storage_maintenance")
    or name.startswith("query_storage_maintenance")
    or name.startswith("diff_storage_maintenance")
    or name.startswith("storage_maintenance_")
    or name.startswith("StorageMaintenance")
]

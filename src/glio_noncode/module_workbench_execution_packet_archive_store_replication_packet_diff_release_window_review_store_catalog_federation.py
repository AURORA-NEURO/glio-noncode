"""Federate catalog members into an explicit release collection.

Federation is a read-only reconciliation boundary.  It selects a bounded set
of catalog entries, counts ready/held/blocked members, checks evidence-window
coherence and ledger uniqueness under explicit policy, and emits a deterministic
collection receipt.  It never rewrites a member store or changes a review
decision.
"""

# ruff: noqa: E501

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog import (
    load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog,
)
from .module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_contracts import (
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_FEDERATION_PREFIX,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
    MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationCheck,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMember,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMemberDisposition,
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationState,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_check,
    address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_member,
)
from .serialization import canonical_json, content_hash


def _text(value: Any, field: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    value = value.strip()
    if len(value) > maximum:
        raise ValidationError(f"{field} exceeds the published limit")
    return value


def _address(value: Any, field: str) -> str:
    value = _text(value, field, 512)
    if ":" not in value or value.endswith(":"):
        raise ValidationError(f"{field} must be a content address")
    return value


def _optional_address(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _address(value, field)


def _bounded(value: Any, field: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value > maximum:
        raise ValidationError(f"{field} is outside the published limit")
    return value


def _member(
    ordinal: int, entry: Any
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMember:
    if entry.store_state == "ready":
        disposition = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMemberDisposition.INCLUDED.value
        detail = "ready member included in the release collection"
    elif entry.store_state == "held":
        disposition = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMemberDisposition.HELD.value
        detail = "held member retained for review but not release closure"
    else:
        disposition = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMemberDisposition.EXCLUDED.value
        detail = "blocked or empty member excluded from release closure"
    body = {
        "ordinal": ordinal,
        "store_id": entry.store_id,
        "store_address": entry.store_address,
        "window_address": entry.window_address,
        "ledger_address": entry.ledger_address,
        "head_address": entry.head_address,
        "store_state": entry.store_state,
        "disposition": disposition,
        "accepted": entry.accepted,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMember(
        **body, content_address="pending:member"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMember(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_member(
            provisional
        ),
    )


def _check(
    ordinal: int, *, kind: str, passed: bool, expected: Any, observed: Any, detail: str
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationCheck:
    body = {
        "ordinal": ordinal,
        "kind": kind,
        "passed": passed,
        "expected": expected,
        "observed": observed,
        "detail": detail,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationCheck(
        **body, content_address="pending:check"
    )
    return ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationCheck(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_check(
            provisional
        ),
    )


def _checks(
    catalog: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    members: tuple[
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationMember,
        ...,
    ],
    *,
    selected_window_address: str | None,
    require_same_window: bool,
    require_unique_ledger: bool,
    minimum_members: int,
    minimum_ready: int,
    unknown_store_ids: tuple[str, ...],
) -> tuple[
    ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationCheck,
    ...,
]:
    windows = tuple(sorted({item.window_address for item in members}))
    ledgers = tuple(sorted({item.ledger_address for item in members}))
    ready_count = sum(item.store_state == "ready" for item in members)
    blocked_count = sum(item.store_state not in {"ready", "held"} for item in members)
    checks = (
        _check(
            0,
            kind="catalog-accepted",
            passed=catalog.accepted,
            expected=True,
            observed=catalog.accepted,
            detail="source catalog is accepted before federation",
        ),
        _check(
            1,
            kind="minimum-members",
            passed=len(members) >= minimum_members,
            expected=minimum_members,
            observed=len(members),
            detail="selected collection meets the member threshold",
        ),
        _check(
            2,
            kind="minimum-ready",
            passed=ready_count >= minimum_ready,
            expected=minimum_ready,
            observed=ready_count,
            detail="selected collection meets the ready threshold",
        ),
        _check(
            3,
            kind="selected-window",
            passed=selected_window_address is None
            or all(item.window_address == selected_window_address for item in members),
            expected=selected_window_address or "any",
            observed=windows,
            detail="selected members match the requested evidence window",
        ),
        _check(
            4,
            kind="same-window",
            passed=not require_same_window or len(windows) <= 1,
            expected=True if require_same_window else "not-required",
            observed=len(windows),
            detail="evidence-window coherence follows the explicit policy",
        ),
        _check(
            5,
            kind="unique-ledger",
            passed=not require_unique_ledger or len(ledgers) == len(members),
            expected=True if require_unique_ledger else "not-required",
            observed={"distinct": len(ledgers), "members": len(members)},
            detail="ledger uniqueness follows the explicit policy",
        ),
        _check(
            6,
            kind="no-blocked-members",
            passed=blocked_count == 0,
            expected=0,
            observed=blocked_count,
            detail="blocked members cannot enter release closure",
        ),
        _check(
            7,
            kind="known-store-selection",
            passed=not unknown_store_ids,
            expected=(),
            observed=unknown_store_ids,
            detail="requested store IDs all exist in the catalog",
        ),
        _check(
            8,
            kind="public-boundary",
            passed=True,
            expected=True,
            observed=True,
            detail="federation output carries no identity or private metadata",
        ),
    )
    if (
        len(checks)
        > MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS
    ):
        raise ValidationError("federation checks exceed the published limit")
    return checks


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
    catalog: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    *,
    federation_id: str = "glio-noncode-review-store-catalog-federation",
    selected_window_address: str | None = None,
    store_ids: Sequence[str] | None = None,
    require_same_window: bool = True,
    require_unique_ledger: bool = True,
    minimum_members: int = 1,
    minimum_ready: int = 1,
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation:
    """Select and reconcile a bounded release collection from a catalog."""

    if not isinstance(
        catalog,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalog,
    ):
        raise ValidationError("federation requires a typed catalog")
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
        catalog
    )
    federation_id = _text(federation_id, "federation ID", 256)
    selected_window_address = _optional_address(selected_window_address, "selected window address")
    if not isinstance(require_same_window, bool) or not isinstance(require_unique_ledger, bool):
        raise ValidationError("federation policy flags must be boolean")
    minimum_members = _bounded(
        minimum_members,
        "minimum federation members",
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
    )
    minimum_ready = _bounded(
        minimum_ready,
        "minimum federation ready members",
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
    )
    if minimum_members == 0:
        raise ValidationError("minimum federation members must be positive")
    if minimum_ready > minimum_members:
        raise ValidationError("minimum ready members cannot exceed minimum members")
    requested = (
        None
        if store_ids is None
        else tuple(sorted({_text(item, "federation store ID", 256) for item in store_ids}))
    )
    available = {item.store_id: item for item in catalog.entries}
    unknown = tuple(item for item in (requested or ()) if item not in available)
    selected = tuple(
        item
        for item in catalog.entries
        if (requested is None or item.store_id in requested)
        and (selected_window_address is None or item.window_address == selected_window_address)
    )
    members = tuple(_member(ordinal, entry) for ordinal, entry in enumerate(selected))
    checks = _checks(
        catalog,
        members,
        selected_window_address=selected_window_address,
        require_same_window=require_same_window,
        require_unique_ledger=require_unique_ledger,
        minimum_members=minimum_members,
        minimum_ready=minimum_ready,
        unknown_store_ids=unknown,
    )
    ready_count = sum(item.store_state == "ready" for item in members)
    held_count = sum(item.store_state == "held" for item in members)
    blocked_count = sum(item.store_state not in {"ready", "held"} for item in members)
    distinct_windows = len({item.window_address for item in members})
    distinct_ledgers = len({item.ledger_address for item in members})
    checks_pass = all(item.passed for item in checks)
    structural_checks_pass = all(item.passed for item in checks if item.kind != "minimum-ready")
    if not members:
        state = (
            ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationState.BLOCKED.value
            if unknown
            else ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationState.EMPTY.value
        )
    elif blocked_count or not structural_checks_pass:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationState.BLOCKED.value
    elif distinct_windows > 1:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationState.MIXED.value
    elif held_count or ready_count < minimum_ready:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationState.HELD.value
    else:
        state = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationState.READY.value
    accepted = bool(members) and structural_checks_pass
    body = {
        "federation_id": federation_id,
        "catalog_id": catalog.catalog_id,
        "catalog_address": catalog.content_address,
        "selected_window_address": selected_window_address,
        "require_same_window": require_same_window,
        "require_unique_ledger": require_unique_ledger,
        "minimum_members": minimum_members,
        "minimum_ready": minimum_ready,
        "member_count": len(members),
        "ready_count": ready_count,
        "held_count": held_count,
        "blocked_count": blocked_count,
        "distinct_window_count": distinct_windows,
        "distinct_ledger_count": distinct_ledgers,
        "state": state,
        "release_ready": accepted
        and state == "ready"
        and checks_pass
        and ready_count >= minimum_ready
        and len(members) >= minimum_members,
        "accepted": accepted,
        "members": members,
        "checks": checks,
    }
    provisional = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation(
        **body, content_address="pending:federation"
    )
    value = ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation(
        **body,
        content_address=address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            provisional
        ),
    )
    return value


def build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_from_directory(
    directory: str | Path, **kwargs: Any
) -> ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation:
    return build_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
        load_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog(
            directory
        ),
        **kwargs,
    )


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
) -> bool:
    if not isinstance(
        value,
        ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
    ):
        raise ValidationError("federation verification requires a typed federation")
    if (
        address_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
            value
        )
        != value.content_address
    ):
        raise ValidationError("federation content address mismatch")
    return True


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_json(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
        value
    )
    return canonical_json(value.to_dict()) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_csv(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
        value
    )
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "store_id",
        "window_address",
        "ledger_address",
        "store_state",
        "disposition",
        "accepted",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for member in value.members:
        writer.writerow({field: member.to_dict().get(field) for field in fields})
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_markdown(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
) -> str:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
        value
    )
    lines = [
        "# Review-Store Federation",
        "",
        f"- state: `{value.state}`",
        f"- release-ready: `{str(value.release_ready).lower()}`",
        f"- accepted: `{str(value.accepted).lower()}`",
        f"- members: `{value.member_count}`",
        f"- ready: `{value.ready_count}`",
        f"- held: `{value.held_count}`",
        f"- blocked: `{value.blocked_count}`",
        f"- windows: `{value.distinct_window_count}`",
        f"- ledgers: `{value.distinct_ledger_count}`",
        f"- address: `{value.content_address}`",
        "",
        "| # | Store | State | Disposition | Accepted |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {member.ordinal} | `{member.store_id}` | `{member.store_state}` | `{member.disposition}` | `{str(member.accepted).lower()}` |"
        for member in value.members
    )
    lines.extend(("", "## Checks", "", "| # | Check | Passed | Detail |", "|---:|---|---|---|"))
    lines.extend(
        f"| {check.ordinal} | `{check.kind}` | `{str(check.passed).lower()}` | {check.detail} |"
        for check in value.checks
    )
    return "\n".join(lines) + "\n"


def query_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
    value: ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederation,
    *,
    resource: str = "members",
    store_id: str | None = None,
    disposition: str | None = None,
    passed: bool | None = None,
    text: str | None = None,
    offset: int = 0,
    limit: int = MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
) -> dict[str, Any]:
    verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation(
        value
    )
    if resource not in {"summary", "members", "checks"}:
        raise ValidationError("federation resource is invalid")
    offset = _bounded(offset, "federation query offset", 1000000)
    limit = _bounded(
        limit,
        "federation query limit",
        MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
    )
    if limit == 0:
        raise ValidationError("federation query limit must be positive")
    if text is not None:
        text = _text(text, "federation query text", 4096).casefold()
    if resource == "summary":
        rows = [value.summary()]
    elif resource == "members":
        rows = [item.to_dict() for item in value.members]
        if store_id is not None:
            rows = [row for row in rows if row["store_id"] == store_id]
        if disposition is not None:
            rows = [row for row in rows if row["disposition"] == disposition]
    else:
        rows = [item.to_dict() for item in value.checks]
        if passed is not None:
            rows = [row for row in rows if row["passed"] == passed]
    if text is not None:
        rows = [
            row for row in rows if text in " ".join(str(item) for item in row.values()).casefold()
        ]
    page = rows[offset : offset + limit]
    payload = {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "boundary": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_FEDERATION_PREFIX
        + "-query",
        "federation_id": value.federation_id,
        "federation_address": value.content_address,
        "resource": resource,
        "offset": offset,
        "limit": limit,
        "total": len(rows),
        "returned": len(page),
        "accepted": True,
        "rows": page,
    }
    payload["query_address"] = content_hash(
        payload,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_FEDERATION_PREFIX
        + "-query",
    )
    return payload


def verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query(
    payload: Mapping[str, Any],
) -> bool:
    if (
        not isinstance(payload, Mapping)
        or not payload.get("accepted")
        or not isinstance(payload.get("query_address"), str)
    ):
        return False
    body = dict(payload)
    address = body.pop("query_address")
    return address == content_hash(
        body,
        prefix=MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_FEDERATION_PREFIX
        + "-query",
    )


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query_json(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query(
        payload
    ):
        raise ValidationError("federation query receipt is invalid")
    return canonical_json(dict(payload)) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query_csv(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query(
        payload
    ):
        raise ValidationError("federation query receipt is invalid")
    output = io.StringIO(newline="")
    fields = (
        "ordinal",
        "store_id",
        "kind",
        "window_address",
        "ledger_address",
        "store_state",
        "disposition",
        "passed",
        "accepted",
        "detail",
        "content_address",
    )
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in payload.get("rows", ()):
        writer.writerow({field: row.get(field) for field in fields})
    return output.getvalue()


def render_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query_markdown(
    payload: Mapping[str, Any],
) -> str:
    if not verify_module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query(
        payload
    ):
        raise ValidationError("federation query receipt is invalid")
    lines = [
        "# Review-Store Federation Query",
        "",
        f"- resource: `{payload.get('resource')}`",
        f"- returned: `{payload.get('returned')}` of `{payload.get('total')}`",
        f"- query address: `{payload.get('query_address')}`",
        "",
        "| # | Store | Kind | State | Accepted |",
        "|---:|---|---|---|---|",
    ]
    lines.extend(
        f"| {row.get('ordinal', '')} | `{row.get('store_id', '')}` | `{row.get('kind', '')}` | `{row.get('store_state', row.get('disposition', ''))}` | `{str(row.get('accepted', row.get('passed', ''))).lower()}` |"
        for row in payload.get("rows", ())
    )
    return "\n".join(lines) + "\n"


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "states": [
            item.value
            for item in ModuleWorkbenchExecutionPacketArchiveStoreReplicationPacketDiffReleaseWindowReviewStoreCatalogFederationState
        ],
        "resources": ["summary", "members", "checks"],
        "policies": [
            "selected_window_address",
            "store_ids",
            "require_same_window",
            "require_unique_ledger",
            "minimum_members",
            "minimum_ready",
        ],
        "limits": {
            "members": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_ENTRIES,
            "checks": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_MAX_CHECKS,
            "limit": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_DEFAULT_LIMIT,
        },
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "operations": [
            "select",
            "federate",
            "verify",
            "query",
            "json",
            "csv",
            "markdown",
            "schema",
            "capabilities",
        ],
        "guarantees": [
            "explicit selection policy",
            "window coherence checks",
            "ledger uniqueness checks",
            "ready/held/blocked conservation",
            "bounded members",
            "deterministic addressed output",
            "identity-free output",
        ],
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query_schema() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "resources": ["summary", "members", "checks"],
        "filters": ["store_id", "disposition", "passed", "text", "offset", "limit"],
        "identity_free": True,
        "path_free": True,
        "timestamp_free": True,
    }


def module_workbench_execution_packet_archive_store_replication_packet_diff_release_window_review_store_catalog_federation_query_capabilities() -> (
    dict[str, Any]
):
    return {
        "version": MODULE_WORKBENCH_EXECUTION_PACKET_ARCHIVE_STORE_REPLICATION_PACKET_DIFF_RELEASE_WINDOW_REVIEW_STORE_CATALOG_VERSION,
        "operations": ["query", "filter", "paginate", "verify", "json", "csv", "markdown"],
        "guarantees": [
            "bounded results",
            "stable member/check ordering",
            "addressed query receipt",
            "identity-free output",
        ],
    }

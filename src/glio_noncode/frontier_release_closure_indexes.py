"""Address-only indexes for the cross-domain release closure."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .frontier_release_closure_bundle import FrontierReleaseSnapshot
from .frontier_release_closure_contracts import (
    FrontierReleaseClosureCheck,
    FrontierReleaseIndexAudit,
    FrontierReleaseIndexEntry,
    FrontierReleaseIndexes,
    frontier_release_closure_check,
)
from .frontier_release_closure_support import all_rows
from .serialization import content_hash


def _entry(
    index_name: str,
    key: str,
    resource: str,
    reference: str,
    domain_id: str,
    address: str,
) -> FrontierReleaseIndexEntry:
    body = {
        "index_name": index_name,
        "key": key,
        "resource": resource,
        "reference": reference,
        "domain_id": domain_id,
        "source_address": address,
    }
    return FrontierReleaseIndexEntry(
        **body,
        content_address=content_hash(body, prefix="frontier-release-index-entry"),
    )


def _entries(
    index_name: str,
    resource: str,
    rows: Iterable[dict[str, Any]],
    key_name: str,
    reference_name: str,
    domain_name: str = "domain_id",
    address_name: str = "content_address",
) -> tuple[FrontierReleaseIndexEntry, ...]:
    entries = [
        _entry(
            index_name,
            str(row.get(key_name, "")),
            resource,
            str(row.get(reference_name, row.get(key_name, ""))),
            str(row.get(domain_name, "")),
            str(row.get(address_name, "")),
        )
        for row in rows
    ]
    return tuple(sorted(entries, key=lambda item: (item.key, item.reference)))


def build_frontier_release_indexes(
    snapshot: FrontierReleaseSnapshot,
) -> FrontierReleaseIndexes:
    rows = all_rows(snapshot)
    by_domain_id = _entries("by_domain_id", "domains", rows["domains"], "domain_id", "bundle_id")
    by_artifact_ref = _entries(
        "by_artifact_ref", "artifacts", rows["artifacts"], "artifact_ref", "artifact_ref"
    )
    by_gate_id = _entries("by_gate_id", "gates", rows["gates"], "gate_id", "gate_id")
    by_dependency_id = _entries(
        "by_dependency_id",
        "dependencies",
        rows["dependencies"],
        "dependency_id",
        "dependency_id",
    )
    by_bundle_id = _entries("by_bundle_id", "domains", rows["domains"], "bundle_id", "domain_id")
    state_rows = tuple(
        {
            **row,
            "state": "accepted" if row.get("accepted") else "blocked",
            "content_address": row.get("content_address", ""),
        }
        for row in rows["domains"]
    ) + tuple(
        {
            **row,
            "state": "passed" if row.get("passed") else "failed",
            "content_address": row.get("content_address", ""),
        }
        for row in rows["gates"]
    )
    by_state = _entries(
        "by_state", "state", state_rows, "state", "domain_id", address_name="content_address"
    )
    address_rows = tuple(
        row for values in rows.values() for row in values if row.get("content_address")
    )
    by_content_address = _entries(
        "by_content_address",
        "all",
        address_rows,
        "content_address",
        "content_address",
    )
    body = {
        "by_domain_id": by_domain_id,
        "by_artifact_ref": by_artifact_ref,
        "by_gate_id": by_gate_id,
        "by_dependency_id": by_dependency_id,
        "by_bundle_id": by_bundle_id,
        "by_state": by_state,
        "by_content_address": by_content_address,
        "accepted": True,
    }
    return FrontierReleaseIndexes(
        **body,
        content_address=content_hash(body, prefix="frontier-release-indexes"),
    )


def _index_values(indexes: FrontierReleaseIndexes) -> tuple[tuple[str, tuple[Any, ...]], ...]:
    return tuple(
        (name, getattr(indexes, name))
        for name in (
            "by_domain_id",
            "by_artifact_ref",
            "by_gate_id",
            "by_dependency_id",
            "by_bundle_id",
            "by_state",
            "by_content_address",
        )
    )


def audit_frontier_release_indexes(
    snapshot: FrontierReleaseSnapshot,
    indexes: FrontierReleaseIndexes,
) -> FrontierReleaseIndexAudit:
    rows = all_rows(snapshot)
    expected = {
        "by_domain_id": len(rows["domains"]),
        "by_artifact_ref": len(rows["artifacts"]),
        "by_gate_id": len(rows["gates"]),
        "by_dependency_id": len(rows["dependencies"]),
        "by_bundle_id": len(rows["domains"]),
        "by_state": len(rows["domains"]) + len(rows["gates"]),
        "by_content_address": sum(
            bool(row.get("content_address")) for values in rows.values() for row in values
        ),
    }
    checks: list[FrontierReleaseClosureCheck] = [
        frontier_release_closure_check(
            "indexes-address",
            "public",
            indexes.content_address.startswith("frontier-release-indexes:"),
            indexes.content_address,
            "frontier-release-indexes:*",
            "index package is addressed",
        )
    ]
    for name, values in _index_values(indexes):
        checks.append(
            frontier_release_closure_check(
                f"index-{name}-count",
                "public",
                len(values) == expected[name],
                len(values),
                expected[name],
                f"{name} conserves its source rows",
            )
        )
        checks.append(
            frontier_release_closure_check(
                f"index-{name}-addresses",
                "public",
                all(item.source_address for item in values),
                sum(bool(item.source_address) for item in values),
                len(values),
                f"{name} retains source addresses",
            )
        )
        checks.append(
            frontier_release_closure_check(
                f"index-{name}-identities",
                "public",
                all(item.key for item in values),
                sum(bool(item.key) for item in values),
                len(values),
                f"{name} retains lookup identities",
            )
        )
    accepted = all(item.passed for item in checks)
    body = {
        "bundle_id": snapshot.bundle_id,
        "checks": tuple(checks),
        "accepted": accepted,
    }
    return FrontierReleaseIndexAudit(
        **body,
        content_address=content_hash(body, prefix="frontier-release-index-audit"),
    )


def lookup_frontier_release_index(
    indexes: FrontierReleaseIndexes,
    index_name: str,
    key: str,
) -> tuple[FrontierReleaseIndexEntry, ...]:
    values = getattr(indexes, index_name, None)
    if values is None:
        raise ValueError(f"unknown frontier release index: {index_name}")
    return tuple(item for item in values if item.key == key)


__all__ = [
    "audit_frontier_release_indexes",
    "build_frontier_release_indexes",
    "lookup_frontier_release_index",
]

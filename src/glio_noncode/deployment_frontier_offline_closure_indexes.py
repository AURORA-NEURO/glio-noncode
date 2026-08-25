"""Ten address-only lookup indexes for D16 closure review."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .deployment_frontier_offline_closure_contracts import (
    DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
    DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
    DeploymentFrontierClosureCheck,
    DeploymentFrontierClosureIndexAudit,
    DeploymentFrontierClosureIndexEntry,
    DeploymentFrontierClosureIndexes,
    DeploymentFrontierClosurePlane,
    deployment_frontier_closure_check,
)
from .deployment_frontier_offline_closure_support import all_rows
from .deployment_frontier_offline_contracts import DeploymentFrontierOfflineBundle
from .serialization import content_hash

_ARTIFACT_IDS = {
    "artifacts": "artifacts",
    "records": "fixture",
    "executions": "evaluation",
    "checks": "evaluation",
    "sources": "fixture",
    "validation": "validation",
    "evidence": "evaluation",
    "edges": "lineage",
    "views": "view",
    "queue": "queue",
    "diagnostics": "diagnostics",
    "stages": "runtime",
    "stage_index": "stage-index",
    "operations": "operation-index",
    "controls": "fixture",
    "failures": "failure_injection",
}


def _entry(
    key: str,
    resource: str,
    target_id: str,
    ordinal: int,
    address: str,
) -> DeploymentFrontierClosureIndexEntry:
    return DeploymentFrontierClosureIndexEntry(
        key=str(key),
        resource=resource,
        target_id=str(target_id),
        artifact_id=_ARTIFACT_IDS.get(resource, resource),
        ordinal=ordinal,
        address=str(address),
    )


def _entries(
    resource: str,
    rows: Iterable[Mapping[str, Any]],
    key_field: str,
    target_field: str | None = None,
) -> tuple[DeploymentFrontierClosureIndexEntry, ...]:
    result: list[DeploymentFrontierClosureIndexEntry] = []
    for ordinal, row in enumerate(rows, 1):
        key = row.get(key_field)
        if key in (None, ""):
            continue
        result.append(
            _entry(
                str(key),
                resource,
                str(row.get(target_field or key_field, key)),
                ordinal,
                str(row.get("content_address", "")),
            )
        )
    return tuple(
        sorted(result, key=lambda item: (item.key, item.resource, item.target_id, item.ordinal))
    )


def _list_entries(
    resource: str,
    rows: Iterable[Mapping[str, Any]],
    list_field: str,
    target_field: str,
) -> tuple[DeploymentFrontierClosureIndexEntry, ...]:
    result: list[DeploymentFrontierClosureIndexEntry] = []
    for ordinal, row in enumerate(rows, 1):
        target = str(row.get(target_field, ordinal))
        values = row.get(list_field, ())
        if not isinstance(values, (list, tuple, set)):
            continue
        for value in values:
            result.append(
                _entry(str(value), resource, target, ordinal, str(row.get("content_address", "")))
            )
    return tuple(
        sorted(result, key=lambda item: (item.key, item.resource, item.target_id, item.ordinal))
    )


def _dedupe(
    entries: Iterable[DeploymentFrontierClosureIndexEntry],
) -> tuple[DeploymentFrontierClosureIndexEntry, ...]:
    seen: set[tuple[str, str, str, str]] = set()
    result = []
    for entry in entries:
        identity = (entry.key, entry.resource, entry.target_id, entry.address)
        if identity not in seen:
            seen.add(identity)
            result.append(entry)
    return tuple(
        sorted(result, key=lambda item: (item.key, item.resource, item.target_id, item.ordinal))
    )


def build_deployment_frontier_closure_indexes(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierClosureIndexes:
    rows = all_rows(bundle)
    indexes = {
        "by_artifact_id": _entries("artifacts", rows["artifacts"], "artifact_id"),
        "by_record_id": _dedupe(
            _entries("records", rows["records"], "record_id")
            + _entries("executions", rows["executions"], "record_id")
            + _entries("views", rows["views"], "record_id")
            + _entries("evidence", rows["evidence"], "record_id")
            + _entries("queue", rows["queue"], "record_id")
        ),
        "by_operation": _dedupe(
            _entries("operations", rows["operations"], "operation")
            + _entries("records", rows["records"], "operation")
            + _entries("executions", rows["executions"], "operation")
        ),
        "by_check_id": _entries("checks", rows["checks"], "check_id"),
        "by_source_id": _dedupe(_entries("sources", rows["sources"], "source_id")),
        "by_stage_id": _dedupe(
            _entries("stages", rows["stages"], "stage_id")
            + _entries("stage_index", rows["stage_index"], "stage_id")
        ),
        "by_edge_id": _entries("edges", rows["edges"], "edge_id"),
        "by_queue_priority": _entries("queue", rows["queue"], "priority", "record_id"),
        "by_issue_code": _dedupe(
            _list_entries("executions", rows["executions"], "issue_codes", "record_id")
            + _list_entries("queue", rows["queue"], "issue_codes", "record_id")
            + _entries("diagnostics", rows["diagnostics"], "code", "finding_id")
        ),
        "by_state": _dedupe(
            _entries("records", rows["records"], "expected_state", "record_id")
            + _entries("views", rows["views"], "state", "record_id")
        ),
    }
    resource_counts = {name: len(value) for name, value in indexes.items()}
    accepted = (
        len(indexes["by_artifact_id"]) == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT
        and len({item.key for item in indexes["by_record_id"]}) == 16
        and len(indexes["by_check_id"]) == DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT
        and len({item.key for item in indexes["by_source_id"]})
        == DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT
        and len({item.key for item in indexes["by_stage_id"]})
        == DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT
        and len(indexes["by_edge_id"]) == DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT
        and all(item.address for values in indexes.values() for item in values)
    )
    body = {
        "bundle_id": bundle.bundle_id,
        **indexes,
        "resource_counts": resource_counts,
        "accepted": accepted,
    }
    return DeploymentFrontierClosureIndexes(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-closure-indexes"),
    )


def audit_deployment_frontier_closure_indexes(
    bundle: DeploymentFrontierOfflineBundle,
    indexes: DeploymentFrontierClosureIndexes,
) -> DeploymentFrontierClosureIndexAudit:
    checks: tuple[DeploymentFrontierClosureCheck, ...] = (
        deployment_frontier_closure_check(
            "indexes-accepted",
            DeploymentFrontierClosurePlane.INDEX,
            indexes.accepted,
            indexes.accepted,
            True,
            "closure indexes are accepted",
        ),
        deployment_frontier_closure_check(
            "indexes-artifacts",
            DeploymentFrontierClosurePlane.INDEX,
            len(indexes.by_artifact_id) == DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            len(indexes.by_artifact_id),
            DEPLOYMENT_FRONTIER_CLOSURE_ARTIFACT_COUNT,
            "all artifacts are indexed",
        ),
        deployment_frontier_closure_check(
            "indexes-records",
            DeploymentFrontierClosurePlane.INDEX,
            len({item.key for item in indexes.by_record_id}) == 16,
            len({item.key for item in indexes.by_record_id}),
            16,
            "all records are indexed",
        ),
        deployment_frontier_closure_check(
            "indexes-checks",
            DeploymentFrontierClosurePlane.INDEX,
            len(indexes.by_check_id) == DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            len(indexes.by_check_id),
            DEPLOYMENT_FRONTIER_CLOSURE_EVALUATION_CHECK_COUNT,
            "all evaluation checks are indexed",
        ),
        deployment_frontier_closure_check(
            "indexes-sources",
            DeploymentFrontierClosurePlane.INDEX,
            len({item.key for item in indexes.by_source_id})
            == DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            len({item.key for item in indexes.by_source_id}),
            DEPLOYMENT_FRONTIER_CLOSURE_SOURCE_COUNT,
            "all sources are indexed",
        ),
        deployment_frontier_closure_check(
            "indexes-stages",
            DeploymentFrontierClosurePlane.INDEX,
            len({item.key for item in indexes.by_stage_id})
            == DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            len({item.key for item in indexes.by_stage_id}),
            DEPLOYMENT_FRONTIER_CLOSURE_RUNTIME_STAGE_COUNT,
            "all runtime stages are indexed",
        ),
        deployment_frontier_closure_check(
            "indexes-edges",
            DeploymentFrontierClosurePlane.INDEX,
            len(indexes.by_edge_id) == DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            len(indexes.by_edge_id),
            DEPLOYMENT_FRONTIER_CLOSURE_LINEAGE_EDGE_COUNT,
            "all lineage edges are indexed",
        ),
        deployment_frontier_closure_check(
            "indexes-operations",
            DeploymentFrontierClosurePlane.INDEX,
            len({item.key for item in indexes.by_operation}) == 4,
            len({item.key for item in indexes.by_operation}),
            4,
            "all operations are indexed",
        ),
        deployment_frontier_closure_check(
            "indexes-priority",
            DeploymentFrontierClosurePlane.INDEX,
            bool(indexes.by_queue_priority),
            len(indexes.by_queue_priority),
            ">0",
            "queue priorities are indexed",
        ),
        deployment_frontier_closure_check(
            "indexes-issues",
            DeploymentFrontierClosurePlane.INDEX,
            len({item.key for item in indexes.by_issue_code}) == 13,
            len({item.key for item in indexes.by_issue_code}),
            13,
            "all issue categories are indexed",
        ),
        deployment_frontier_closure_check(
            "indexes-states",
            DeploymentFrontierClosurePlane.INDEX,
            len({item.key for item in indexes.by_state}) == 4,
            len({item.key for item in indexes.by_state}),
            4,
            "all state categories are indexed",
        ),
        deployment_frontier_closure_check(
            "indexes-addressed",
            DeploymentFrontierClosurePlane.INDEX,
            all(
                item.get("address")
                for values in indexes.to_dict().values()
                if isinstance(values, list)
                for item in values
            ),
            True,
            True,
            "every index entry is addressed",
        ),
        deployment_frontier_closure_check(
            "indexes-root",
            DeploymentFrontierClosurePlane.INDEX,
            bool(bundle.content_address),
            bool(bundle.content_address),
            True,
            "indexes retain root identity",
        ),
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "checks": checks,
        "accepted": all(item.passed for item in checks),
    }
    return DeploymentFrontierClosureIndexAudit(
        **body, content_address=content_hash(body, prefix="deployment-frontier-closure-index-audit")
    )


def lookup_deployment_frontier_closure_index(
    indexes: DeploymentFrontierClosureIndexes,
    index_name: str,
    key: str,
) -> tuple[DeploymentFrontierClosureIndexEntry, ...]:
    normalized = index_name.casefold().replace("-", "_")
    aliases = {
        "artifact_id": "by_artifact_id",
        "record_id": "by_record_id",
        "operation": "by_operation",
        "check_id": "by_check_id",
        "source_id": "by_source_id",
        "stage_id": "by_stage_id",
        "edge_id": "by_edge_id",
        "queue_priority": "by_queue_priority",
        "issue_code": "by_issue_code",
        "state": "by_state",
    }
    field = aliases.get(
        normalized, normalized if normalized.startswith("by_") else f"by_{normalized}"
    )
    values = getattr(indexes, field, ())
    return tuple(item for item in values if item.key == str(key))


__all__ = [
    "audit_deployment_frontier_closure_indexes",
    "build_deployment_frontier_closure_indexes",
    "lookup_deployment_frontier_closure_index",
]

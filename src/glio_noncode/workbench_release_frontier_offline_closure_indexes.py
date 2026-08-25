"""Address-only D15 closure indexes over the complete workbench handoff."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .serialization import content_hash
from .workbench_release_frontier_offline_closure_contracts import (
    WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT,
    WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT,
    WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT,
    WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT,
    WorkbenchReleaseClosureCheck,
    WorkbenchReleaseClosureIndexAudit,
    WorkbenchReleaseClosureIndexEntry,
    WorkbenchReleaseClosureIndexes,
    WorkbenchReleaseClosurePlane,
    workbench_release_closure_check,
)
from .workbench_release_frontier_offline_closure_support import all_rows, count_map
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle


def _entry(
    key: Any,
    resource: str,
    target_id: Any,
    artifact_id: str,
    ordinal: int,
    address: Any,
) -> WorkbenchReleaseClosureIndexEntry:
    return WorkbenchReleaseClosureIndexEntry(
        key=str(key),
        resource=resource,
        target_id=str(target_id),
        artifact_id=artifact_id,
        ordinal=int(ordinal),
        address=str(address or ""),
    )


def _entries(
    rows: Iterable[Mapping[str, Any]], key: str, resource: str, artifact_id: str
) -> tuple[WorkbenchReleaseClosureIndexEntry, ...]:
    entries = []
    for ordinal, row in enumerate(rows, start=1):
        value = row.get(key)
        if value in (None, ""):
            continue
        values = value if isinstance(value, (list, tuple, set)) else (value,)
        target = (
            row.get("record_id")
            or row.get("stage_id")
            or row.get("edge_id")
            or row.get("diagnostic_id")
            or row.get("capability")
            or value
        )
        for item in values:
            entries.append(
                _entry(item, resource, target, artifact_id, ordinal, row.get("content_address"))
            )
    return tuple(
        sorted(entries, key=lambda item: (item.key, item.resource, item.target_id, item.ordinal))
    )


def _dedupe(
    entries: tuple[WorkbenchReleaseClosureIndexEntry, ...],
) -> tuple[WorkbenchReleaseClosureIndexEntry, ...]:
    seen: set[tuple[str, str, str, str]] = set()
    result = []
    for item in entries:
        identity = (item.key, item.resource, item.target_id, item.artifact_id)
        if identity not in seen:
            seen.add(identity)
            result.append(item)
    return tuple(result)


def build_workbench_release_closure_indexes(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseClosureIndexes:
    rows = all_rows(bundle)
    by_artifact_id = _entries(rows["artifacts"], "artifact_id", "artifact", "manifest")
    by_record_id = _dedupe(
        _entries(rows["records"], "record_id", "record", "fixture")
        + _entries(rows["executions"], "record_id", "execution", "evaluation")
        + _entries(rows["views"], "record_id", "view", "view")
    )
    by_operation = _dedupe(
        _entries(rows["records"], "operation", "record", "fixture")
        + _entries(rows["operations"], "operation", "operation", "operation-index")
        + _entries(rows["controls"], "operation", "control", "controls")
    )
    by_check_id = _entries(rows["checks"], "check_id", "check", "evaluation")
    by_source_id = _entries(rows["sources"], "source_id", "source", "fixture")
    by_stage_id = _dedupe(
        _entries(rows["stages"], "stage_id", "stage", "runtime")
        + _entries(rows["stage_index"], "stage_id", "stage_index", "stage-index")
    )
    by_edge_id = _entries(rows["edges"], "edge_id", "edge", "lineage")
    by_queue_priority = _entries(rows["queue"], "priority", "queue", "review-queue")
    by_capability = _dedupe(
        _entries(rows["records"], "capability", "record", "fixture")
        + _entries(rows["executions"], "capability", "execution", "evaluation")
        + _entries(rows["views"], "capability", "view", "view")
    )
    by_diagnostic_severity = _entries(rows["diagnostics"], "severity", "diagnostic", "diagnostics")
    counts = count_map(bundle)
    counts["index_entries"] = sum(
        len(value)
        for value in (
            by_artifact_id,
            by_record_id,
            by_operation,
            by_check_id,
            by_source_id,
            by_stage_id,
            by_edge_id,
            by_queue_priority,
            by_capability,
            by_diagnostic_severity,
        )
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "by_artifact_id": by_artifact_id,
        "by_record_id": by_record_id,
        "by_operation": by_operation,
        "by_check_id": by_check_id,
        "by_source_id": by_source_id,
        "by_stage_id": by_stage_id,
        "by_edge_id": by_edge_id,
        "by_queue_priority": by_queue_priority,
        "by_capability": by_capability,
        "by_diagnostic_severity": by_diagnostic_severity,
        "resource_counts": counts,
        "accepted": bundle.ready
        and len(by_artifact_id) == WORKBENCH_RELEASE_CLOSURE_ARTIFACT_COUNT
        and len(by_check_id) == WORKBENCH_RELEASE_CLOSURE_EVALUATION_CHECK_COUNT
        and len({item.key for item in by_source_id}) == WORKBENCH_RELEASE_CLOSURE_SOURCE_COUNT
        and len({item.key for item in by_stage_id}) == WORKBENCH_RELEASE_CLOSURE_RUNTIME_STAGE_COUNT
        and len(by_edge_id) == WORKBENCH_RELEASE_CLOSURE_LINEAGE_EDGE_COUNT,
    }
    return WorkbenchReleaseClosureIndexes(
        **{
            key: body[key]
            for key in (
                "bundle_id",
                "by_artifact_id",
                "by_record_id",
                "by_operation",
                "by_check_id",
                "by_source_id",
                "by_stage_id",
                "by_edge_id",
                "by_queue_priority",
                "by_capability",
                "by_diagnostic_severity",
                "resource_counts",
                "accepted",
            )
        },
        content_address=content_hash(body, prefix="workbench-release-closure-indexes"),
    )


def audit_workbench_release_closure_indexes(
    bundle: WorkbenchReleaseOfflineBundle,
    indexes: WorkbenchReleaseClosureIndexes | None = None,
) -> WorkbenchReleaseClosureIndexAudit:
    value = indexes or build_workbench_release_closure_indexes(bundle)
    collections = {
        "artifact": value.by_artifact_id,
        "record": value.by_record_id,
        "operation": value.by_operation,
        "check": value.by_check_id,
        "source": value.by_source_id,
        "stage": value.by_stage_id,
        "edge": value.by_edge_id,
        "queue": value.by_queue_priority,
        "capability": value.by_capability,
        "diagnostic": value.by_diagnostic_severity,
    }
    checks: list[WorkbenchReleaseClosureCheck] = []
    for name, entries in collections.items():
        checks.extend(
            (
                workbench_release_closure_check(
                    f"index-{name}-nonempty",
                    WorkbenchReleaseClosurePlane.INDEX,
                    bool(entries),
                    len(entries),
                    ">0",
                    f"{name} index is populated",
                ),
                workbench_release_closure_check(
                    f"index-{name}-addressed",
                    WorkbenchReleaseClosurePlane.INDEX,
                    all(item.address for item in entries),
                    sum(bool(item.address) for item in entries),
                    len(entries),
                    f"{name} entries are addressed",
                ),
                workbench_release_closure_check(
                    f"index-{name}-ordinals",
                    WorkbenchReleaseClosurePlane.INDEX,
                    all(item.ordinal > 0 for item in entries),
                    sum(item.ordinal > 0 for item in entries),
                    len(entries),
                    f"{name} entries have positive ordinals",
                ),
                workbench_release_closure_check(
                    f"index-{name}-targets",
                    WorkbenchReleaseClosurePlane.INDEX,
                    all(item.target_id for item in entries),
                    sum(bool(item.target_id) for item in entries),
                    len(entries),
                    f"{name} entries have targets",
                ),
            )
        )
    checks.extend(
        (
            workbench_release_closure_check(
                "index-artifact-count",
                WorkbenchReleaseClosurePlane.INDEX,
                len(value.by_artifact_id) == 56,
                len(value.by_artifact_id),
                56,
                "all artifacts are indexed",
            ),
            workbench_release_closure_check(
                "index-check-count",
                WorkbenchReleaseClosurePlane.INDEX,
                len(value.by_check_id) == 80,
                len(value.by_check_id),
                80,
                "all evaluation checks are indexed",
            ),
            workbench_release_closure_check(
                "index-source-count",
                WorkbenchReleaseClosurePlane.INDEX,
                len({item.key for item in value.by_source_id}) == 5,
                len({item.key for item in value.by_source_id}),
                5,
                "all sources are indexed",
            ),
            workbench_release_closure_check(
                "index-stage-count",
                WorkbenchReleaseClosurePlane.INDEX,
                len({item.key for item in value.by_stage_id}) == 49,
                len({item.key for item in value.by_stage_id}),
                49,
                "all runtime stages are indexed",
            ),
            workbench_release_closure_check(
                "index-edge-count",
                WorkbenchReleaseClosurePlane.INDEX,
                len(value.by_edge_id) == 52,
                len(value.by_edge_id),
                52,
                "all lineage edges are indexed",
            ),
            workbench_release_closure_check(
                "index-accepted",
                WorkbenchReleaseClosurePlane.INDEX,
                value.accepted,
                value.accepted,
                True,
                "closure indexes are accepted",
            ),
        )
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": bundle.bundle_id, "checks": tuple(checks), "accepted": accepted}
    return WorkbenchReleaseClosureIndexAudit(
        bundle_id=bundle.bundle_id,
        checks=tuple(checks),
        accepted=accepted,
        content_address=content_hash(body, prefix="workbench-release-closure-index-audit"),
    )


def lookup_workbench_release_closure_index(
    indexes: WorkbenchReleaseClosureIndexes, index_name: str, key: str
) -> tuple[WorkbenchReleaseClosureIndexEntry, ...]:
    mapping = {
        "artifact_id": indexes.by_artifact_id,
        "record_id": indexes.by_record_id,
        "operation": indexes.by_operation,
        "check_id": indexes.by_check_id,
        "source_id": indexes.by_source_id,
        "stage_id": indexes.by_stage_id,
        "edge_id": indexes.by_edge_id,
        "priority": indexes.by_queue_priority,
        "capability": indexes.by_capability,
        "severity": indexes.by_diagnostic_severity,
    }
    try:
        entries = mapping[index_name.casefold()]
    except KeyError as exc:
        raise ValueError(f"unknown D15 closure index: {index_name}") from exc
    return tuple(item for item in entries if item.key == key)


__all__ = [
    "audit_workbench_release_closure_indexes",
    "build_workbench_release_closure_indexes",
    "lookup_workbench_release_closure_index",
]

"""Address-only D14 closure indexes across every public projection."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .evidence_lifecycle_frontier_offline_closure_contracts import (
    EvidenceLifecycleClosureCheck,
    EvidenceLifecycleClosureIndexAudit,
    EvidenceLifecycleClosureIndexEntry,
    EvidenceLifecycleClosureIndexes,
    EvidenceLifecycleClosurePlane,
    evidence_lifecycle_closure_check,
)
from .evidence_lifecycle_frontier_offline_closure_support import all_rows, count_map
from .evidence_lifecycle_frontier_offline_contracts import EvidenceLifecycleOfflineBundle
from .serialization import content_hash


def _entry(
    key: Any, resource: str, target_id: Any, artifact_id: str, ordinal: int, address: Any
) -> EvidenceLifecycleClosureIndexEntry:
    return EvidenceLifecycleClosureIndexEntry(
        key=str(key),
        resource=resource,
        target_id=str(target_id),
        artifact_id=artifact_id,
        ordinal=int(ordinal),
        address=str(address or ""),
    )


def _entries(
    rows: Iterable[Mapping[str, Any]], key: str, resource: str, artifact_id: str
) -> tuple[EvidenceLifecycleClosureIndexEntry, ...]:
    entries: list[EvidenceLifecycleClosureIndexEntry] = []
    for ordinal, row in enumerate(rows, start=1):
        value = row.get(key)
        if value is None or value == "":
            continue
        values = value if isinstance(value, (list, tuple)) else (value,)
        target = row.get(
            "record_id",
            row.get(
                "stage_id", row.get("event_id", row.get("edge_id", row.get("scenario_id", value)))
            ),
        )
        for item in values:
            entries.append(
                _entry(item, resource, target, artifact_id, ordinal, row.get("content_address"))
            )
    return tuple(
        sorted(entries, key=lambda item: (item.key, item.resource, item.target_id, item.ordinal))
    )


def _dedupe(
    entries: tuple[EvidenceLifecycleClosureIndexEntry, ...],
) -> tuple[EvidenceLifecycleClosureIndexEntry, ...]:
    seen: set[tuple[str, str, str, str]] = set()
    result: list[EvidenceLifecycleClosureIndexEntry] = []
    for entry in entries:
        identity = (entry.key, entry.resource, entry.target_id, entry.artifact_id)
        if identity not in seen:
            seen.add(identity)
            result.append(entry)
    return tuple(result)


def build_evidence_lifecycle_closure_indexes(
    bundle: EvidenceLifecycleOfflineBundle,
) -> EvidenceLifecycleClosureIndexes:
    rows = all_rows(bundle)
    by_artifact_id = _entries(rows["artifacts"], "artifact_id", "artifact", "manifest")
    by_record_id = _dedupe(
        _entries(rows["records"], "record_id", "record", "fixture")
        + _entries(rows["executions"], "record_id", "execution", "evaluation")
    )
    by_operation = _dedupe(
        _entries(rows["records"], "operation", "record", "fixture")
        + _entries(rows["operations"], "operation", "operation", "fixture")
    )
    by_check_id = _entries(rows["checks"], "check_id", "check", "evaluation")
    by_source_id = _entries(rows["sources"], "source_id", "source", "fixture")
    by_event_type = _entries(rows["events"], "event_type", "event", "observability")
    by_stage_id = _entries(rows["stages"], "stage_id", "stage", "runtime")
    by_edge_id = _entries(rows["edges"], "edge_id", "edge", "lineage")
    by_queue_disposition = _entries(rows["queue"], "disposition", "queue", "review-queue")
    by_scenario_id = _entries(rows["scenarios"], "scenario_id", "scenario", "scenario-matrix")
    counts = count_map(bundle)
    counts["index_entries"] = sum(
        len(item)
        for item in (
            by_artifact_id,
            by_record_id,
            by_operation,
            by_check_id,
            by_source_id,
            by_event_type,
            by_stage_id,
            by_edge_id,
            by_queue_disposition,
            by_scenario_id,
        )
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "by_artifact_id": by_artifact_id,
        "by_record_id": by_record_id,
        "by_operation": by_operation,
        "by_check_id": by_check_id,
        "by_source_id": by_source_id,
        "by_event_type": by_event_type,
        "by_stage_id": by_stage_id,
        "by_edge_id": by_edge_id,
        "by_queue_disposition": by_queue_disposition,
        "by_scenario_id": by_scenario_id,
        "resource_counts": counts,
        "accepted": bundle.ready
        and len(by_artifact_id) == 21
        and len(by_check_id) == 120
        and len(by_stage_id) == 10,
    }
    return EvidenceLifecycleClosureIndexes(
        bundle_id=bundle.bundle_id,
        by_artifact_id=by_artifact_id,
        by_record_id=by_record_id,
        by_operation=by_operation,
        by_check_id=by_check_id,
        by_source_id=by_source_id,
        by_event_type=by_event_type,
        by_stage_id=by_stage_id,
        by_edge_id=by_edge_id,
        by_queue_disposition=by_queue_disposition,
        by_scenario_id=by_scenario_id,
        resource_counts=counts,
        accepted=bool(body["accepted"]),
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-indexes"),
    )


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> EvidenceLifecycleClosureCheck:
    return evidence_lifecycle_closure_check(
        check_id, EvidenceLifecycleClosurePlane.INDEX, passed, observed, required, detail
    )


def audit_evidence_lifecycle_closure_indexes(
    bundle: EvidenceLifecycleOfflineBundle,
    indexes: EvidenceLifecycleClosureIndexes | None = None,
) -> EvidenceLifecycleClosureIndexAudit:
    value = indexes or build_evidence_lifecycle_closure_indexes(bundle)
    collections = {
        "artifact": value.by_artifact_id,
        "record": value.by_record_id,
        "operation": value.by_operation,
        "check": value.by_check_id,
        "source": value.by_source_id,
        "event": value.by_event_type,
        "stage": value.by_stage_id,
        "edge": value.by_edge_id,
        "queue": value.by_queue_disposition,
        "scenario": value.by_scenario_id,
    }
    checks: list[EvidenceLifecycleClosureCheck] = []
    for name, entries in collections.items():
        checks.extend(
            (
                _check(
                    f"index-{name}-nonempty",
                    bool(entries),
                    len(entries),
                    ">0",
                    f"{name} index is populated",
                ),
                _check(
                    f"index-{name}-addressed",
                    all(item.address for item in entries),
                    sum(bool(item.address) for item in entries),
                    len(entries),
                    f"{name} entries carry addresses",
                ),
                _check(
                    f"index-{name}-ordinals",
                    all(item.ordinal > 0 for item in entries),
                    sum(item.ordinal > 0 for item in entries),
                    len(entries),
                    f"{name} entries carry positive ordinals",
                ),
                _check(
                    f"index-{name}-targets",
                    all(item.target_id for item in entries),
                    sum(bool(item.target_id) for item in entries),
                    len(entries),
                    f"{name} entries carry targets",
                ),
            )
        )
    checks.extend(
        (
            _check(
                "index-artifact-count",
                len(value.by_artifact_id) == 21,
                len(value.by_artifact_id),
                21,
                "all artifacts are indexed",
            ),
            _check(
                "index-record-count",
                len({item.key for item in value.by_record_id}) == 16,
                len({item.key for item in value.by_record_id}),
                16,
                "all records are indexed",
            ),
            _check(
                "index-check-count",
                len(value.by_check_id) == 120,
                len(value.by_check_id),
                120,
                "all evaluation checks are indexed",
            ),
            _check(
                "index-source-count",
                len(value.by_source_id) == 5,
                len(value.by_source_id),
                5,
                "all sources are indexed",
            ),
            _check(
                "index-stage-count",
                len(value.by_stage_id) == 10,
                len(value.by_stage_id),
                10,
                "all stages are indexed",
            ),
            _check(
                "index-edge-count",
                len(value.by_edge_id) == 36,
                len(value.by_edge_id),
                36,
                "all lineage edges are indexed",
            ),
            _check(
                "index-accepted",
                value.accepted,
                value.accepted,
                True,
                "closure indexes are accepted",
            ),
        )
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": bundle.bundle_id, "checks": tuple(checks), "accepted": accepted}
    return EvidenceLifecycleClosureIndexAudit(
        bundle_id=bundle.bundle_id,
        checks=tuple(checks),
        accepted=accepted,
        content_address=content_hash(body, prefix="evidence-lifecycle-closure-index-audit"),
    )


def lookup_evidence_lifecycle_closure_index(
    indexes: EvidenceLifecycleClosureIndexes, index_name: str, key: str
) -> tuple[EvidenceLifecycleClosureIndexEntry, ...]:
    mapping = {
        "artifact_id": indexes.by_artifact_id,
        "record_id": indexes.by_record_id,
        "operation": indexes.by_operation,
        "check_id": indexes.by_check_id,
        "source_id": indexes.by_source_id,
        "event_type": indexes.by_event_type,
        "stage_id": indexes.by_stage_id,
        "edge_id": indexes.by_edge_id,
        "queue_disposition": indexes.by_queue_disposition,
        "scenario_id": indexes.by_scenario_id,
    }
    try:
        entries = mapping[index_name.casefold()]
    except KeyError as exc:
        raise ValueError(f"unknown D14 closure index: {index_name}") from exc
    return tuple(item for item in entries if item.key == key)


__all__ = [
    "audit_evidence_lifecycle_closure_indexes",
    "build_evidence_lifecycle_closure_indexes",
    "lookup_evidence_lifecycle_closure_index",
]

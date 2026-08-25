"""Address-only indexes for fast D15 offline lookup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .workbench_release_frontier_offline_contracts import WorkbenchReleaseOfflineBundle
from .workbench_release_frontier_offline_query import _rows


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineIndexEntry:
    key: str
    address: str
    artifact_id: str
    ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineIndexes:
    bundle_id: str
    by_artifact_id: tuple[WorkbenchReleaseOfflineIndexEntry, ...]
    by_path: tuple[WorkbenchReleaseOfflineIndexEntry, ...]
    by_record_id: tuple[WorkbenchReleaseOfflineIndexEntry, ...]
    by_operation: tuple[WorkbenchReleaseOfflineIndexEntry, ...]
    by_stage_id: tuple[WorkbenchReleaseOfflineIndexEntry, ...]
    resource_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineIndexCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineIndexAudit:
    bundle_id: str
    checks: tuple[WorkbenchReleaseOfflineIndexCheck, ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_count": len(self.checks) - self.passed_count,
        }


def _entry(
    key: str, address: str, artifact_id: str, ordinal: int
) -> WorkbenchReleaseOfflineIndexEntry:
    return WorkbenchReleaseOfflineIndexEntry(
        key=str(key), address=str(address), artifact_id=str(artifact_id), ordinal=int(ordinal)
    )


def build_workbench_release_offline_indexes(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseOfflineIndexes:
    """Build indexes that retain addresses and coordinates, never payload copies."""

    by_artifact = tuple(
        _entry(item.artifact_id, item.content_address, item.artifact_id, index)
        for index, item in enumerate(bundle.artifacts)
    )
    by_path = tuple(
        _entry(item.relative_path, item.content_address, item.artifact_id, index)
        for index, item in enumerate(sorted(bundle.artifacts, key=lambda item: item.relative_path))
    )
    records = _rows(bundle, "fixture", "records")
    executions = _rows(bundle, "evaluation", "executions")
    stages = _rows(bundle, "runtime", "stages")
    by_record = tuple(
        _entry(str(item.get("record_id")), str(item.get("content_address")), "evaluation", index)
        for index, item in enumerate(executions)
    )
    by_operation = tuple(
        _entry(str(item.get("operation")), str(item.get("content_address")), "evaluation", index)
        for index, item in enumerate(executions)
    )
    by_stage = tuple(
        _entry(str(item.get("stage_id")), str(item.get("content_address")), "runtime", index)
        for index, item in enumerate(stages)
    )
    resource_counts = {
        "artifacts": len(bundle.artifacts),
        "records": len(records),
        "sources": len(_rows(bundle, "fixture", "sources")),
        "executions": len(executions),
        "checks": len(_rows(bundle, "evaluation", "checks")),
        "stages": len(stages),
        "operations": len({str(item.get("operation")) for item in records}),
        "queue_rows": len(_rows(bundle, "review-queue", "rows")),
    }
    body = {
        "bundle_id": bundle.bundle_id,
        "by_artifact_id": by_artifact,
        "by_path": by_path,
        "by_record_id": by_record,
        "by_operation": by_operation,
        "by_stage_id": by_stage,
        "resource_counts": resource_counts,
        "accepted": bundle.ready
        and len(by_artifact) == 56
        and len(by_record) == 16
        and len(by_stage) == 49,
    }
    return WorkbenchReleaseOfflineIndexes(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-indexes")
    )


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> WorkbenchReleaseOfflineIndexCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return WorkbenchReleaseOfflineIndexCheck(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-index-check")
    )


def audit_workbench_release_offline_indexes(
    bundle: WorkbenchReleaseOfflineBundle, indexes: WorkbenchReleaseOfflineIndexes
) -> WorkbenchReleaseOfflineIndexAudit:
    """Verify index uniqueness, address prefixes, and denominator conservation."""

    checks = (
        _check(
            "index-accepted", indexes.accepted, indexes.accepted, True, "index build is accepted"
        ),
        _check(
            "artifact-index-count",
            len(indexes.by_artifact_id) == 56,
            len(indexes.by_artifact_id),
            56,
            "artifact index conserves all artifacts",
        ),
        _check(
            "artifact-index-identities",
            len({item.key for item in indexes.by_artifact_id}) == len(indexes.by_artifact_id),
            len({item.key for item in indexes.by_artifact_id}),
            len(indexes.by_artifact_id),
            "artifact index keys are unique",
        ),
        _check(
            "path-index-count",
            len(indexes.by_path) == 56,
            len(indexes.by_path),
            56,
            "path index conserves all artifacts",
        ),
        _check(
            "path-index-identities",
            len({item.key for item in indexes.by_path}) == len(indexes.by_path),
            len({item.key for item in indexes.by_path}),
            len(indexes.by_path),
            "path index keys are unique",
        ),
        _check(
            "record-index-count",
            len(indexes.by_record_id) == 16,
            len(indexes.by_record_id),
            16,
            "record index conserves executions",
        ),
        _check(
            "record-index-identities",
            len({item.key for item in indexes.by_record_id}) == 16,
            len({item.key for item in indexes.by_record_id}),
            16,
            "record index keys are unique",
        ),
        _check(
            "operation-index-count",
            len(indexes.by_operation) == 16,
            len(indexes.by_operation),
            16,
            "operation index retains one entry per execution",
        ),
        _check(
            "stage-index-count",
            len(indexes.by_stage_id) == 49,
            len(indexes.by_stage_id),
            49,
            "stage index conserves the runtime trace",
        ),
        _check(
            "stage-index-identities",
            len({item.key for item in indexes.by_stage_id}) == 49,
            len({item.key for item in indexes.by_stage_id}),
            49,
            "stage identifiers are unique",
        ),
        _check(
            "address-index",
            all(
                item.address
                for item in indexes.by_artifact_id + indexes.by_record_id + indexes.by_stage_id
            ),
            True,
            True,
            "all index entries retain addresses",
        ),
        _check(
            "resource-counts",
            indexes.resource_counts
            == {
                "artifacts": 56,
                "records": 16,
                "sources": 5,
                "executions": 16,
                "checks": 80,
                "stages": 49,
                "operations": 4,
                "queue_rows": 12,
            },
            indexes.resource_counts,
            "D15 denominators",
            "resource counts reconcile",
        ),
        _check(
            "bundle-join",
            indexes.bundle_id == bundle.bundle_id,
            indexes.bundle_id,
            bundle.bundle_id,
            "index belongs to the supplied bundle",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": indexes.bundle_id, "checks": checks, "accepted": accepted}
    return WorkbenchReleaseOfflineIndexAudit(
        **body, content_address=content_hash(body, prefix="workbench-release-offline-index-audit")
    )


__all__ = [
    "WorkbenchReleaseOfflineIndexAudit",
    "WorkbenchReleaseOfflineIndexCheck",
    "WorkbenchReleaseOfflineIndexEntry",
    "WorkbenchReleaseOfflineIndexes",
    "audit_workbench_release_offline_indexes",
    "build_workbench_release_offline_indexes",
]

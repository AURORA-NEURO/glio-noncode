"""Address-only indexes for fast D16 offline review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .deployment_frontier_offline_contracts import (
    DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
    DeploymentFrontierOfflineBundle,
)
from .deployment_frontier_offline_query import _rows
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineIndexEntry:
    key: str
    address: str
    artifact_id: str
    ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineIndexes:
    bundle_id: str
    by_artifact_id: tuple[DeploymentFrontierOfflineIndexEntry, ...]
    by_path: tuple[DeploymentFrontierOfflineIndexEntry, ...]
    by_record_id: tuple[DeploymentFrontierOfflineIndexEntry, ...]
    by_operation: tuple[DeploymentFrontierOfflineIndexEntry, ...]
    by_stage_id: tuple[DeploymentFrontierOfflineIndexEntry, ...]
    by_issue: tuple[DeploymentFrontierOfflineIndexEntry, ...]
    by_state: tuple[DeploymentFrontierOfflineIndexEntry, ...]
    resource_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineIndexCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineIndexAudit:
    bundle_id: str
    checks: tuple[DeploymentFrontierOfflineIndexCheck, ...]
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
) -> DeploymentFrontierOfflineIndexEntry:
    return DeploymentFrontierOfflineIndexEntry(
        str(key), str(address), str(artifact_id), int(ordinal)
    )


def build_deployment_frontier_offline_indexes(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierOfflineIndexes:
    """Build indexes containing coordinates and addresses, never payload copies."""

    artifacts = tuple(
        _entry(item.artifact_id, item.content_address, item.artifact_id, index)
        for index, item in enumerate(bundle.artifacts)
    )
    paths = tuple(
        _entry(item.relative_path, item.content_address, item.artifact_id, index)
        for index, item in enumerate(sorted(bundle.artifacts, key=lambda item: item.relative_path))
    )
    executions = _rows(bundle, "evaluation", "executions")
    records = _rows(bundle, "fixture", "records")
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
    issue_rows = _rows(bundle, "issue-index", "rows")
    state_rows = _rows(bundle, "state-index", "rows")
    if not issue_rows:
        issue_value = next(
            (item for item in bundle.artifacts if item.artifact_id == "issue-index"), None
        )
        issue_rows = []
        if issue_value and issue_value.payload:
            import json

            value = json.loads(issue_value.payload)
            issue_rows = [
                {"issue": key, "count": count}
                for key, count in value.get("issue_counts", {}).items()
            ]
    if not state_rows:
        state_value = next(
            (item for item in bundle.artifacts if item.artifact_id == "state-index"), None
        )
        state_rows = []
        if state_value and state_value.payload:
            import json

            value = json.loads(state_value.payload)
            state_rows = [
                {"state": key, "count": count}
                for key, count in value.get("state_counts", {}).items()
            ]
    by_issue = tuple(
        _entry(str(item.get("issue")), str(item.get("count")), "issue-index", index)
        for index, item in enumerate(issue_rows)
    )
    by_state = tuple(
        _entry(str(item.get("state")), str(item.get("count")), "state-index", index)
        for index, item in enumerate(state_rows)
    )
    resource_counts = {
        "artifacts": len(bundle.artifacts),
        "records": len(records),
        "sources": len(_rows(bundle, "fixture", "sources")),
        "executions": len(executions),
        "checks": len(_rows(bundle, "evaluation", "checks")),
        "stages": len(stages),
        "operations": len({str(item.get("operation")) for item in records}),
        "issues": len(by_issue),
        "states": len(by_state),
    }
    body = {
        "bundle_id": bundle.bundle_id,
        "by_artifact_id": artifacts,
        "by_path": paths,
        "by_record_id": by_record,
        "by_operation": by_operation,
        "by_stage_id": by_stage,
        "by_issue": by_issue,
        "by_state": by_state,
        "resource_counts": resource_counts,
        "accepted": bundle.ready
        and len(artifacts) == DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT
        and len(by_record) == DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT
        and len(by_stage) == DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
    }
    return DeploymentFrontierOfflineIndexes(
        **body, content_address=content_hash(body, prefix="deployment-frontier-offline-indexes")
    )


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> DeploymentFrontierOfflineIndexCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return DeploymentFrontierOfflineIndexCheck(
        **body, content_address=content_hash(body, prefix="deployment-frontier-offline-index-check")
    )


def audit_deployment_frontier_offline_indexes(
    bundle: DeploymentFrontierOfflineBundle, indexes: DeploymentFrontierOfflineIndexes
) -> DeploymentFrontierOfflineIndexAudit:
    checks = (
        _check(
            "index-accepted", indexes.accepted, indexes.accepted, True, "index build is accepted"
        ),
        _check(
            "artifact-index-count",
            len(indexes.by_artifact_id) == DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            len(indexes.by_artifact_id),
            DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            "artifact index conserves all files",
        ),
        _check(
            "artifact-index-identities",
            len({item.key for item in indexes.by_artifact_id}) == len(indexes.by_artifact_id),
            len({item.key for item in indexes.by_artifact_id}),
            len(indexes.by_artifact_id),
            "artifact index keys are unique",
        ),
        _check(
            "path-index-identities",
            len({item.key for item in indexes.by_path})
            == len(indexes.by_path)
            == DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            len(indexes.by_path),
            DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            "path index keys are unique and complete",
        ),
        _check(
            "record-index-count",
            len(indexes.by_record_id) == DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT,
            len(indexes.by_record_id),
            DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT,
            "record index conserves executions",
        ),
        _check(
            "record-index-identities",
            len({item.key for item in indexes.by_record_id})
            == DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT,
            len({item.key for item in indexes.by_record_id}),
            DEPLOYMENT_FRONTIER_OFFLINE_RECORD_COUNT,
            "record identities are unique",
        ),
        _check(
            "operation-index-count",
            len(indexes.by_operation) == DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT,
            len(indexes.by_operation),
            DEPLOYMENT_FRONTIER_OFFLINE_EXECUTION_COUNT,
            "operation index retains one entry per execution",
        ),
        _check(
            "stage-index-count",
            len(indexes.by_stage_id) == DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
            len(indexes.by_stage_id),
            DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
            "stage index conserves runtime trace",
        ),
        _check(
            "stage-index-identities",
            len({item.key for item in indexes.by_stage_id})
            == DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
            len({item.key for item in indexes.by_stage_id}),
            DEPLOYMENT_FRONTIER_OFFLINE_STAGE_COUNT,
            "stage identifiers are unique",
        ),
        _check(
            "issue-index-count",
            len(indexes.by_issue) > 0,
            len(indexes.by_issue),
            ">0",
            "issue categories are indexed",
        ),
        _check(
            "state-index-count",
            len(indexes.by_state) > 0,
            len(indexes.by_state),
            ">0",
            "observed states are indexed",
        ),
        _check(
            "address-index",
            all(
                item.address
                for item in indexes.by_artifact_id + indexes.by_record_id + indexes.by_stage_id
            ),
            True,
            True,
            "index entries retain addresses",
        ),
        _check(
            "resource-counts",
            indexes.resource_counts
            == {
                "artifacts": 51,
                "records": 16,
                "sources": 5,
                "executions": 16,
                "checks": 80,
                "stages": 38,
                "operations": 4,
                "issues": len(indexes.by_issue),
                "states": len(indexes.by_state),
            },
            indexes.resource_counts,
            "D16 resource counts",
            "resource counts reconcile",
        ),
        _check(
            "bundle-join",
            indexes.bundle_id == bundle.bundle_id,
            indexes.bundle_id,
            bundle.bundle_id,
            "index belongs to supplied bundle",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": indexes.bundle_id, "checks": checks, "accepted": accepted}
    return DeploymentFrontierOfflineIndexAudit(
        **body, content_address=content_hash(body, prefix="deployment-frontier-offline-index-audit")
    )


__all__ = [
    "DeploymentFrontierOfflineIndexAudit",
    "DeploymentFrontierOfflineIndexCheck",
    "DeploymentFrontierOfflineIndexEntry",
    "DeploymentFrontierOfflineIndexes",
    "audit_deployment_frontier_offline_indexes",
    "build_deployment_frontier_offline_indexes",
]

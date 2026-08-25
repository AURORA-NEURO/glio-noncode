"""Address-only indexes for portable architecture-program queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .program_runtime_offline_contracts import (
    PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
    PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
    PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
    ProgramRuntimeOfflineBundle,
)
from .program_runtime_offline_query import _rows
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineIndexEntry:
    key: str
    address: str
    resource: str
    ordinal: int

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineIndexes:
    bundle_id: str
    by_artifact_id: tuple[ProgramRuntimeOfflineIndexEntry, ...]
    by_path: tuple[ProgramRuntimeOfflineIndexEntry, ...]
    by_domain_id: tuple[ProgramRuntimeOfflineIndexEntry, ...]
    by_check_id: tuple[ProgramRuntimeOfflineIndexEntry, ...]
    by_stage_id: tuple[ProgramRuntimeOfflineIndexEntry, ...]
    by_state: tuple[ProgramRuntimeOfflineIndexEntry, ...]
    resource_counts: dict[str, int]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ProgramRuntimeOfflineIndexAudit:
    bundle_id: str
    checks: tuple[dict[str, Any], ...]
    accepted: bool
    content_address: str

    @property
    def passed_count(self) -> int:
        return sum(item["passed"] for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "passed_count": self.passed_count,
            "failed_count": len(self.checks) - self.passed_count,
        }


def _entry(key: Any, address: Any, resource: str, ordinal: int) -> ProgramRuntimeOfflineIndexEntry:
    return ProgramRuntimeOfflineIndexEntry(
        key=str(key),
        address=str(address),
        resource=resource,
        ordinal=ordinal,
    )


def build_program_runtime_offline_indexes(
    bundle: ProgramRuntimeOfflineBundle,
) -> ProgramRuntimeOfflineIndexes:
    """Build deterministic indexes without copying opaque payloads."""

    artifact_entries = tuple(
        _entry(item.artifact_id, item.content_address, "artifacts", index)
        for index, item in enumerate(sorted(bundle.artifacts, key=lambda item: item.artifact_id))
    )
    path_entries = tuple(
        _entry(item.relative_path, item.content_address, "artifacts", index)
        for index, item in enumerate(sorted(bundle.artifacts, key=lambda item: item.relative_path))
    )
    domains = _rows(bundle, "domains")
    domain_entries = tuple(
        _entry(item.get("domain_id"), item.get("content_address"), "domains", index)
        for index, item in enumerate(sorted(domains, key=lambda item: str(item.get("domain_id"))))
    )
    checks = _rows(bundle, "checks")
    check_entries = tuple(
        _entry(item.get("check_id"), item.get("content_address", ""), "checks", index)
        for index, item in enumerate(sorted(checks, key=lambda item: str(item.get("check_id"))))
    )
    stages = _rows(bundle, "stages")
    stage_entries = tuple(
        _entry(item.get("stage_id"), item.get("content_address"), "stages", index)
        for index, item in enumerate(sorted(stages, key=lambda item: int(item.get("ordinal", 0))))
    )
    state_counts: dict[str, int] = {}
    for item in domains:
        state = str(item.get("runtime_state", "unknown"))
        state_counts[state] = state_counts.get(state, 0) + 1
    state_entries = tuple(
        _entry(state, count, "states", index)
        for index, (state, count) in enumerate(sorted(state_counts.items()))
    )
    resource_counts = {
        "artifacts": len(bundle.artifacts),
        "domains": len(domains),
        "checks": len(checks),
        "stages": len(stages),
        "quality_checks": len(_rows(bundle, "quality")),
        "release_checks": len(_rows(bundle, "release_checks")),
        "specifications": len(_rows(bundle, "specifications")),
        "capabilities": len(_rows(bundle, "capabilities")),
        "states": len(state_entries),
    }
    accepted = (
        len(artifact_entries) == PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT
        and len(domain_entries) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT
        and len(stage_entries) == PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT
        and all(item.address for item in artifact_entries + domain_entries + stage_entries)
    )
    body = {
        "bundle_id": bundle.bundle_id,
        "by_artifact_id": artifact_entries,
        "by_path": path_entries,
        "by_domain_id": domain_entries,
        "by_check_id": check_entries,
        "by_stage_id": stage_entries,
        "by_state": state_entries,
        "resource_counts": resource_counts,
        "accepted": accepted,
    }
    return ProgramRuntimeOfflineIndexes(
        **body,
        content_address=content_hash(body, prefix="program-runtime-offline-indexes"),
    )


def _audit_check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> dict[str, Any]:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return body | {
        "content_address": content_hash(body, prefix="program-runtime-offline-index-check")
    }


def audit_program_runtime_offline_indexes(
    bundle: ProgramRuntimeOfflineBundle,
    indexes: ProgramRuntimeOfflineIndexes,
) -> ProgramRuntimeOfflineIndexAudit:
    """Check that indexes conserve every queryable resource."""

    checks = (
        _audit_check(
            "index-accepted", indexes.accepted, indexes.accepted, True, "index build is accepted"
        ),
        _audit_check(
            "artifact-count",
            len(indexes.by_artifact_id) == PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
            len(indexes.by_artifact_id),
            PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
            "artifact index conserves files",
        ),
        _audit_check(
            "path-count",
            len(indexes.by_path) == PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
            len(indexes.by_path),
            PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
            "path index conserves files",
        ),
        _audit_check(
            "artifact-unique",
            len({item.key for item in indexes.by_artifact_id}) == len(indexes.by_artifact_id),
            len({item.key for item in indexes.by_artifact_id}),
            len(indexes.by_artifact_id),
            "artifact keys are unique",
        ),
        _audit_check(
            "path-unique",
            len({item.key for item in indexes.by_path}) == len(indexes.by_path),
            len({item.key for item in indexes.by_path}),
            len(indexes.by_path),
            "path keys are unique",
        ),
        _audit_check(
            "domain-count",
            len(indexes.by_domain_id) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(indexes.by_domain_id),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "domain index conserves receipts",
        ),
        _audit_check(
            "domain-unique",
            len({item.key for item in indexes.by_domain_id}) == len(indexes.by_domain_id),
            len({item.key for item in indexes.by_domain_id}),
            len(indexes.by_domain_id),
            "domain keys are unique",
        ),
        _audit_check(
            "check-index",
            len(indexes.by_check_id) > 0,
            len(indexes.by_check_id),
            ">0",
            "check index is populated",
        ),
        _audit_check(
            "stage-count",
            len(indexes.by_stage_id) == PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            len(indexes.by_stage_id),
            PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            "stage index conserves runtime stages",
        ),
        _audit_check(
            "stage-order",
            [item.ordinal for item in indexes.by_stage_id]
            == list(range(PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT)),
            [item.ordinal for item in indexes.by_stage_id],
            list(range(PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT)),
            "stage index remains ordered",
        ),
        _audit_check(
            "state-index",
            len(indexes.by_state) > 0,
            len(indexes.by_state),
            ">0",
            "state index is populated",
        ),
        _audit_check(
            "address-presence",
            all(
                item.address
                for group in (
                    indexes.by_artifact_id,
                    indexes.by_path,
                    indexes.by_domain_id,
                    indexes.by_check_id,
                    indexes.by_stage_id,
                )
                for item in group
            ),
            True,
            True,
            "all address indexes retain addresses",
        ),
        _audit_check(
            "resource-counts",
            indexes.resource_counts["artifacts"] == bundle.artifact_count
            and indexes.resource_counts["domains"] == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            indexes.resource_counts,
            "artifact and domain denominators",
            "resource counters join the bundle",
        ),
    )
    accepted = all(item["passed"] for item in checks)
    body = {"bundle_id": bundle.bundle_id, "checks": checks, "accepted": accepted}
    return ProgramRuntimeOfflineIndexAudit(
        bundle_id=bundle.bundle_id,
        checks=checks,
        accepted=accepted,
        content_address=content_hash(body, prefix="program-runtime-offline-index-audit"),
    )


__all__ = [
    "ProgramRuntimeOfflineIndexAudit",
    "ProgramRuntimeOfflineIndexEntry",
    "ProgramRuntimeOfflineIndexes",
    "audit_program_runtime_offline_indexes",
    "build_program_runtime_offline_indexes",
]

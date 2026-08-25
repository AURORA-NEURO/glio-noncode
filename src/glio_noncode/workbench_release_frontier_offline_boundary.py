"""Public-boundary and offline-filesystem audits for D15 bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable
from .workbench_release_frontier_offline_contracts import (
    WORKBENCH_RELEASE_OFFLINE_MANIFEST,
    WorkbenchReleaseOfflineBundle,
)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineBoundaryCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class WorkbenchReleaseOfflineBoundaryAudit:
    bundle_id: str
    checks: tuple[WorkbenchReleaseOfflineBoundaryCheck, ...]
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


def _check(
    check_id: str, passed: bool, observed: Any, required: Any, detail: str
) -> WorkbenchReleaseOfflineBoundaryCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return WorkbenchReleaseOfflineBoundaryCheck(
        **body,
        content_address=content_hash(body, prefix="workbench-release-offline-boundary-check"),
    )


def _keys(value: Any) -> tuple[str, ...]:
    if isinstance(value, dict):
        found: set[str] = set()
        for key, item in value.items():
            found.add(str(key))
            found.update(_keys(item))
        return tuple(sorted(found))
    if isinstance(value, (list, tuple)):
        found: set[str] = set()
        for item in value:
            found.update(_keys(item))
        return tuple(sorted(found))
    return ()


def workbench_release_offline_key_inventory(
    bundle: WorkbenchReleaseOfflineBundle,
) -> dict[str, Any]:
    """Return a deterministic key inventory for all JSON payloads."""

    found: set[str] = set()
    for artifact in bundle.artifacts:
        if artifact.payload is None or artifact.media_type != "application/json":
            continue
        try:
            found.update(_keys(json.loads(artifact.payload)))
        except json.JSONDecodeError:
            continue
    forbidden = tuple(
        sorted(
            key
            for key in found
            if _has_forbidden_key({key: True}) or contains_private_key({key: True})
        )
    )
    body = {
        "key_count": len(found),
        "keys": tuple(sorted(found)),
        "forbidden_keys": forbidden,
        "accepted": not forbidden,
    }
    return body | {
        "content_address": content_hash(body, prefix="workbench-release-offline-key-inventory")
    }


def audit_workbench_release_offline_boundary(
    bundle: WorkbenchReleaseOfflineBundle,
) -> WorkbenchReleaseOfflineBoundaryAudit:
    inventory = workbench_release_offline_key_inventory(bundle)
    checks = (
        _check(
            "manifest-public",
            not _has_forbidden_key(bundle.manifest_dict())
            and not contains_private_key(bundle.manifest_dict()),
            True,
            True,
            "root manifest has no private or attribution keys",
        ),
        _check(
            "payloads-public",
            inventory["accepted"],
            inventory["forbidden_keys"],
            (),
            "all JSON payload keys stay within the public boundary",
        ),
        _check(
            "artifact-count",
            bundle.artifact_count == 56,
            bundle.artifact_count,
            56,
            "all expected D15 artifacts are present",
        ),
        _check(
            "relative-paths",
            all(
                not PurePosixPath(item.relative_path).is_absolute()
                and ".." not in PurePosixPath(item.relative_path).parts
                for item in bundle.artifacts
            ),
            True,
            True,
            "artifact paths cannot escape the bundle root",
        ),
        _check(
            "unique-paths",
            len({item.relative_path for item in bundle.artifacts}) == bundle.artifact_count,
            bundle.artifact_count,
            bundle.artifact_count,
            "artifact paths are unique",
        ),
        _check(
            "unique-identities",
            len({item.artifact_id for item in bundle.artifacts}) == bundle.artifact_count,
            bundle.artifact_count,
            bundle.artifact_count,
            "artifact identities are unique",
        ),
        _check(
            "exact-addresses",
            all(
                item.content_address.startswith("workbench-release-bundle-artifact:")
                for item in bundle.artifacts
            ),
            True,
            True,
            "all artifacts use exact-byte addresses",
        ),
        _check(
            "key-inventory",
            inventory["accepted"],
            inventory["forbidden_keys"],
            (),
            "key inventory contains no forbidden key",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": bundle.bundle_id, "checks": checks, "accepted": accepted}
    return WorkbenchReleaseOfflineBoundaryAudit(
        **body,
        content_address=content_hash(body, prefix="workbench-release-offline-boundary-audit"),
    )


def audit_workbench_release_offline_directory(
    destination: str | Path,
) -> WorkbenchReleaseOfflineBoundaryAudit:
    """Audit filesystem shape without following symlinked payload targets."""

    from .workbench_release_frontier_offline_query import load_workbench_release_offline_bundle

    root = Path(destination)
    bundle = load_workbench_release_offline_bundle(root, include_payloads=True)
    expected = {
        WORKBENCH_RELEASE_OFFLINE_MANIFEST,
        *(item.relative_path for item in bundle.artifacts),
    }
    actual: set[str] = set()
    symlinks: list[str] = []
    hidden: list[str] = []
    if root.exists():
        for path in root.rglob("*"):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                symlinks.append(relative)
                continue
            if path.is_file():
                actual.add(relative)
            if any(part.startswith(".") for part in PurePosixPath(relative).parts):
                hidden.append(relative)
    checks = (
        _check(
            "directory-exists",
            root.is_dir(),
            str(root),
            "directory",
            "bundle destination is a directory",
        ),
        _check(
            "manifest-present",
            (root / WORKBENCH_RELEASE_OFFLINE_MANIFEST).is_file(),
            True,
            True,
            "root manifest is present",
        ),
        _check(
            "expected-files",
            actual == expected,
            sorted(actual - expected),
            sorted(expected - actual),
            "filesystem files equal manifest inventory",
        ),
        _check(
            "no-symlinks",
            not symlinks,
            symlinks,
            [],
            "offline handoff does not depend on symlink targets",
        ),
        _check(
            "no-hidden-files", not hidden, hidden, [], "offline handoff has no hidden payload files"
        ),
    )
    base = audit_workbench_release_offline_boundary(bundle)
    checks = tuple(base.checks) + checks
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": bundle.bundle_id, "checks": checks, "accepted": accepted}
    return WorkbenchReleaseOfflineBoundaryAudit(
        **body,
        content_address=content_hash(body, prefix="workbench-release-offline-directory-audit"),
    )


__all__ = [
    "WorkbenchReleaseOfflineBoundaryAudit",
    "WorkbenchReleaseOfflineBoundaryCheck",
    "audit_workbench_release_offline_boundary",
    "audit_workbench_release_offline_directory",
    "workbench_release_offline_key_inventory",
]

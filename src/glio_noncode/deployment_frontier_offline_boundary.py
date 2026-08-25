"""Public-boundary and filesystem-shape audits for D16 handoffs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .deployment_frontier_offline_bundle import load_deployment_frontier_offline_bundle
from .deployment_frontier_offline_contracts import (
    DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
    DEPLOYMENT_FRONTIER_OFFLINE_MANIFEST,
    DeploymentFrontierOfflineBundle,
)
from .module_fabric_support import contains_private_key
from .run_workspace import _has_forbidden_key
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineBoundaryCheck:
    check_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class DeploymentFrontierOfflineBoundaryAudit:
    bundle_id: str
    checks: tuple[DeploymentFrontierOfflineBoundaryCheck, ...]
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
) -> DeploymentFrontierOfflineBoundaryCheck:
    body = {
        "check_id": check_id,
        "passed": bool(passed),
        "observed": observed,
        "required": required,
        "detail": detail,
    }
    return DeploymentFrontierOfflineBoundaryCheck(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-boundary-check"),
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


def deployment_frontier_offline_key_inventory(
    bundle: DeploymentFrontierOfflineBundle,
) -> dict[str, Any]:
    """Inventory every JSON key and report prohibited fields explicitly."""

    found: set[str] = set()
    parse_failures: list[str] = []
    for artifact in bundle.artifacts:
        if artifact.payload is None or artifact.media_type != "application/json":
            continue
        try:
            found.update(_keys(json.loads(artifact.payload)))
        except json.JSONDecodeError:
            parse_failures.append(artifact.artifact_id)
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
        "parse_failures": tuple(sorted(parse_failures)),
        "accepted": not forbidden and not parse_failures,
    }
    return body | {
        "content_address": content_hash(body, prefix="deployment-frontier-offline-key-inventory")
    }


def audit_deployment_frontier_offline_boundary(
    bundle: DeploymentFrontierOfflineBundle,
) -> DeploymentFrontierOfflineBoundaryAudit:
    inventory = deployment_frontier_offline_key_inventory(bundle)
    paths = tuple(item.relative_path for item in bundle.artifacts)
    checks = (
        _check(
            "manifest-public",
            not _has_forbidden_key(bundle.manifest_dict())
            and not contains_private_key(bundle.manifest_dict()),
            True,
            True,
            "root manifest has no prohibited keys",
        ),
        _check(
            "payloads-public",
            inventory["accepted"],
            {
                "forbidden_keys": inventory["forbidden_keys"],
                "parse_failures": inventory["parse_failures"],
            },
            {"forbidden_keys": (), "parse_failures": ()},
            "all JSON payloads stay inside the public boundary",
        ),
        _check(
            "artifact-count",
            bundle.artifact_count == DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            bundle.artifact_count,
            DEPLOYMENT_FRONTIER_OFFLINE_ARTIFACT_COUNT,
            "D16 artifact denominator is complete",
        ),
        _check(
            "relative-paths",
            all(
                not PurePosixPath(path).is_absolute() and ".." not in PurePosixPath(path).parts
                for path in paths
            ),
            paths,
            "relative traversal-free paths",
            "artifact paths cannot escape the root",
        ),
        _check(
            "unique-paths",
            len(paths) == len(set(paths)),
            len(paths),
            len(set(paths)),
            "artifact paths are unique",
        ),
        _check(
            "unique-identities",
            len({item.artifact_id for item in bundle.artifacts}) == bundle.artifact_count,
            bundle.artifact_count,
            len({item.artifact_id for item in bundle.artifacts}),
            "artifact identities are unique",
        ),
        _check(
            "exact-addresses",
            all(
                item.content_address.startswith("deployment-frontier-offline-artifact:")
                for item in bundle.artifacts
            ),
            True,
            True,
            "all artifacts use exact-byte addresses",
        ),
        _check(
            "no-payload-attribution",
            not any(
                _has_forbidden_key(item.to_dict()) or contains_private_key(item.to_dict())
                for item in bundle.artifacts
            ),
            True,
            True,
            "artifact metadata and payload containers carry no attribution fields",
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": bundle.bundle_id, "checks": checks, "accepted": accepted}
    return DeploymentFrontierOfflineBoundaryAudit(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-boundary-audit"),
    )


def audit_deployment_frontier_offline_directory(
    destination: str | Path,
) -> DeploymentFrontierOfflineBoundaryAudit:
    """Audit directory closure without following symlinked payload targets."""

    root = Path(destination)
    bundle = load_deployment_frontier_offline_bundle(root, include_payloads=True)
    expected = {
        DEPLOYMENT_FRONTIER_OFFLINE_MANIFEST,
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
    base = audit_deployment_frontier_offline_boundary(bundle)
    checks = base.checks + (
        _check(
            "directory-exists",
            root.is_dir(),
            str(root),
            "directory",
            "bundle destination is a directory",
        ),
        _check(
            "manifest-present",
            (root / DEPLOYMENT_FRONTIER_OFFLINE_MANIFEST).is_file(),
            True,
            True,
            "root manifest is present",
        ),
        _check(
            "expected-files",
            actual == expected,
            sorted(actual),
            sorted(expected),
            "filesystem files equal manifest inventory",
        ),
        _check(
            "no-symlinks", not symlinks, symlinks, (), "offline handoff has no symlink dependency"
        ),
        _check(
            "no-hidden-files", not hidden, hidden, (), "offline handoff has no hidden payload files"
        ),
    )
    accepted = all(item.passed for item in checks)
    body = {"bundle_id": bundle.bundle_id, "checks": checks, "accepted": accepted}
    return DeploymentFrontierOfflineBoundaryAudit(
        **body,
        content_address=content_hash(body, prefix="deployment-frontier-offline-directory-audit"),
    )


__all__ = [
    "DeploymentFrontierOfflineBoundaryAudit",
    "DeploymentFrontierOfflineBoundaryCheck",
    "audit_deployment_frontier_offline_boundary",
    "audit_deployment_frontier_offline_directory",
    "deployment_frontier_offline_key_inventory",
]

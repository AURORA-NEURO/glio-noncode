"""Offline integrity and public-boundary audits for program handoffs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .module_fabric_support import contains_private_key
from .program_runtime_offline_bundle import (
    PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE,
    load_program_runtime_offline_bundle,
)
from .program_runtime_offline_contracts import (
    PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
    PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX,
    PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
    PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
    PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT,
    PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
    ProgramRuntimeOfflineAudit,
    ProgramRuntimeOfflineBundle,
    ProgramRuntimeOfflineCheckPlane,
    ProgramRuntimeOfflineVerification,
    program_runtime_offline_check,
)
from .program_runtime_offline_query import _payload, _rows
from .serialization import content_hash, hash_bytes


def _check(check_id: str, passed: bool, observed: Any, required: Any, detail: str):
    return program_runtime_offline_check(
        check_id,
        ProgramRuntimeOfflineCheckPlane.ARTIFACT,
        passed,
        observed,
        required,
        detail,
    )


def _json_artifacts_are_public(bundle: ProgramRuntimeOfflineBundle) -> bool:
    for artifact in bundle.artifacts:
        if artifact.media_type != PROGRAM_RUNTIME_OFFLINE_JSON_MEDIA_TYPE:
            continue
        try:
            value = json.loads(artifact.payload or "{}")
        except json.JSONDecodeError:
            return False
        if contains_private_key(value):
            return False
    return True


def audit_program_runtime_offline_bundle(bundle: ProgramRuntimeOfflineBundle):
    """Audit an already-loaded bundle without rebuilding its source runtime."""

    artifact_ids = tuple(item.artifact_id for item in bundle.artifacts)
    paths = tuple(item.relative_path for item in bundle.artifacts)
    artifact_checks = (
        _check("bundle-ready", bundle.ready, bundle.state.value, "ready", "bundle is ready"),
        _check(
            "bundle-addressed",
            bundle.content_address.startswith("program-runtime-offline-bundle:"),
            bundle.content_address,
            "program-runtime-offline-bundle:<digest>",
            "bundle root is addressed",
        ),
        _check(
            "artifact-count",
            bundle.artifact_count == PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
            bundle.artifact_count,
            PROGRAM_RUNTIME_OFFLINE_ARTIFACT_COUNT,
            "artifact count is conserved",
        ),
        _check(
            "artifact-identities",
            len(artifact_ids) == len(set(artifact_ids)),
            len(set(artifact_ids)),
            len(artifact_ids),
            "artifact ids are unique",
        ),
        _check(
            "path-identities",
            len(paths) == len(set(paths)),
            len(set(paths)),
            len(paths),
            "artifact paths are unique",
        ),
        _check(
            "artifact-address-prefix",
            all(
                item.content_address.startswith(f"{PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX}:")
                for item in bundle.artifacts
            ),
            True,
            True,
            "all artifact addresses use the transport prefix",
        ),
        _check(
            "artifact-byte-counts",
            all(
                item.payload is not None and item.byte_count == len(item.payload.encode("utf-8"))
                for item in bundle.artifacts
            ),
            True,
            True,
            "byte counts equal the in-memory payload bytes",
        ),
        _check(
            "artifact-line-counts",
            all(
                item.payload is not None and item.line_count == len(item.payload.splitlines())
                for item in bundle.artifacts
            ),
            True,
            True,
            "line counts equal the in-memory payload lines",
        ),
        _check(
            "artifact-content-addresses",
            all(
                item.payload is not None
                and item.content_address
                == hash_bytes(
                    item.payload.encode("utf-8"), prefix=PROGRAM_RUNTIME_OFFLINE_ARTIFACT_PREFIX
                )
                for item in bundle.artifacts
            ),
            True,
            True,
            "artifact addresses cover exact payload bytes",
        ),
        _check(
            "checks-closed",
            bundle.failed_check_count == 0,
            bundle.failed_check_count,
            0,
            "manifest checks contain no failed build checks",
        ),
        _check(
            "public-json",
            _json_artifacts_are_public(bundle),
            True,
            True,
            "JSON payloads contain no prohibited private keys",
        ),
        _check(
            "domain-denominator",
            len(_rows(bundle, "domains")) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(_rows(bundle, "domains")),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "domain operations are conserved",
        ),
        _check(
            "program-check-denominator",
            len(_rows(bundle, "checks")) == PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            len(_rows(bundle, "checks")),
            PROGRAM_RUNTIME_OFFLINE_PROGRAM_CHECK_COUNT,
            "program checks are conserved",
        ),
        _check(
            "quality-check-denominator",
            len(_rows(bundle, "quality")) == PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT,
            len(_rows(bundle, "quality")),
            PROGRAM_RUNTIME_OFFLINE_QUALITY_CHECK_COUNT,
            "quality checks are conserved",
        ),
        _check(
            "stage-denominator",
            len(_rows(bundle, "stages")) == PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            len(_rows(bundle, "stages")),
            PROGRAM_RUNTIME_OFFLINE_RUNTIME_STAGE_COUNT,
            "runtime stages are conserved",
        ),
        _check(
            "specification-denominator",
            len(_rows(bundle, "specifications")) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(_rows(bundle, "specifications")),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "specification catalog is conserved",
        ),
        _check(
            "capability-denominator",
            len(_rows(bundle, "capabilities")) == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len(_rows(bundle, "capabilities")),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "capability matrix is conserved",
        ),
        _check(
            "stage-order",
            [item.get("ordinal") for item in _rows(bundle, "stages")] == list(range(1, 13)),
            [item.get("ordinal") for item in _rows(bundle, "stages")],
            list(range(1, 13)),
            "stage ordinals are contiguous",
        ),
        _check(
            "runtime-address-join",
            (_payload(bundle, "runtime") or {}).get("content_address") == bundle.runtime_address,
            (_payload(bundle, "runtime") or {}).get("content_address"),
            bundle.runtime_address,
            "runtime artifact joins the manifest root",
        ),
        _check(
            "release-checks",
            len(_rows(bundle, "release_checks")) == 18
            and all(
                str(item.get("passed")).casefold() == "true"
                for item in _rows(bundle, "release_checks")
            ),
            len(_rows(bundle, "release_checks")),
            18,
            "source release checks are closed",
        ),
        _check(
            "operation-identities",
            len({str(item.get("domain_id")) for item in _rows(bundle, "operations")})
            == PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            len({str(item.get("domain_id")) for item in _rows(bundle, "operations")}),
            PROGRAM_RUNTIME_OFFLINE_DOMAIN_COUNT,
            "domain operation identities are unique",
        ),
    )
    accepted = all(item.passed for item in artifact_checks)
    body = {
        "bundle_id": bundle.bundle_id,
        "checks": artifact_checks,
        "accepted": accepted,
    }
    return ProgramRuntimeOfflineAudit(
        bundle_id=bundle.bundle_id,
        checks=artifact_checks,
        accepted=accepted,
        content_address=content_hash(body, prefix="program-runtime-offline-audit"),
    )


def verify_program_runtime_offline_bundle(
    destination: str | Path,
) -> ProgramRuntimeOfflineVerification:
    """Verify a materialized directory, including manifest and exact bytes."""

    root = Path(destination)
    bundle = load_program_runtime_offline_bundle(root, include_payloads=True)
    checks = list(audit_program_runtime_offline_bundle(bundle).checks)
    manifest_path = root / "bundle.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_body = dict(raw)
    supplied_address = str(manifest_body.pop("content_address", ""))
    checks.append(
        _check(
            "manifest-address",
            supplied_address
            == content_hash(manifest_body, prefix="program-runtime-offline-bundle"),
            supplied_address,
            "content hash of manifest fields",
            "manifest address covers the complete manifest",
        )
    )
    expected_paths = {"bundle.json", *(item.relative_path for item in bundle.artifacts)}
    actual_paths = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
    checks.append(
        _check(
            "directory-closure",
            actual_paths == expected_paths,
            sorted(actual_paths - expected_paths),
            sorted(expected_paths),
            "directory contains exactly the manifest and declared artifacts",
        )
    )
    accepted = all(item.passed for item in checks)
    body = {
        "bundle_id": bundle.bundle_id,
        "accepted": accepted,
        "checks": checks,
    }
    return ProgramRuntimeOfflineVerification(
        bundle_id=bundle.bundle_id,
        accepted=accepted,
        checks=tuple(checks),
        content_address=content_hash(body, prefix="program-runtime-offline-verification"),
    )


def audit_program_runtime_offline_directory(destination: str | Path):
    """Alias with an explicit directory-oriented name for operators."""

    return verify_program_runtime_offline_bundle(destination)


__all__ = [
    "audit_program_runtime_offline_bundle",
    "audit_program_runtime_offline_directory",
    "verify_program_runtime_offline_bundle",
]

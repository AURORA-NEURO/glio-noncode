"""Release manifest construction and verification for the frontier package."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .reference_release_frontier_runtime import ReferenceReleaseRuntimeReport
from .serialization import content_hash, jsonable, require_non_empty


class ReferenceReleaseManifestState(StrEnum):
    """Release state vocabulary."""

    READY = "ready"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ReferenceReleaseManifestCheck:
    """One manifest readiness check."""

    check_id: str
    passed: bool
    detail: str
    observed: Any
    expected: Any
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceReleaseManifest:
    """Signed-by-address release metadata with no external mutation."""

    release_id: str
    fixture_id: str
    fixture_version: str
    context_key: str
    state: ReferenceReleaseManifestState
    runtime_address: str
    replay_address: str
    quality_address: str
    selected_record_ids: tuple[str, ...]
    checks: tuple[ReferenceReleaseManifestCheck, ...]
    output_format: str
    content_address: str

    @property
    def ready(self) -> bool:
        return self.state is ReferenceReleaseManifestState.READY

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(item.check_id for item in self.checks if not item.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "ready": self.ready,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _check(
    index: int, passed: bool, detail: str, observed: Any, expected: Any
) -> ReferenceReleaseManifestCheck:
    body = {
        "check_id": f"release-manifest-{index:03d}",
        "passed": passed,
        "detail": detail,
        "observed": observed,
        "expected": expected,
    }
    return ReferenceReleaseManifestCheck(
        **body, content_address=content_hash(body, prefix="manifest-check")
    )


def build_reference_release_manifest(
    runtime: ReferenceReleaseRuntimeReport,
    *,
    release_id: str = "reference-release-frontier-manifest",
) -> ReferenceReleaseManifest:
    """Build a ready manifest only when every required runtime report passes."""

    require_non_empty(release_id, "release_id")
    selected = tuple(
        item.record_id
        for item in runtime.evaluation.executions
        if item.state in {"accepted", "published"}
    )
    checks = (
        _check(1, runtime.accepted, "runtime accepted", runtime.accepted, True),
        _check(
            2, runtime.quality.accepted, "quality gate accepted", runtime.quality.accepted, True
        ),
        _check(3, runtime.replay.accepted, "replay accepted", runtime.replay.accepted, True),
        _check(
            4,
            len(runtime.evaluation.executions) == 16,
            "execution closure",
            len(runtime.evaluation.executions),
            16,
        ),
        _check(5, len(selected) == 5, "accepted projection count", len(selected), 5),
        _check(
            6,
            runtime.data_audit.evidence_boundary == "public_aggregate_non_patient",
            "aggregate boundary",
            runtime.data_audit.evidence_boundary,
            "public_aggregate_non_patient",
        ),
        _check(
            7,
            all(
                item.content_address.startswith("sha256:") for item in runtime.evaluation.executions
            ),
            "execution addresses",
            True,
            True,
        ),
        _check(8, len(runtime.stages) == 9, "runtime stage count", len(runtime.stages), 9),
        _check(
            9,
            tuple(item.sequence for item in runtime.stages) == tuple(range(1, 10)),
            "stage sequence",
            tuple(item.sequence for item in runtime.stages),
            tuple(range(1, 10)),
        ),
        _check(
            10,
            all(
                item.content_address.startswith("release-runtime-stage:") for item in runtime.stages
            ),
            "stage addresses",
            True,
            True,
        ),
        _check(
            11,
            runtime.data_audit.context_key
            == runtime.lineage.nodes[0].attributes.get("context_key"),
            "context linkage",
            runtime.data_audit.context_key,
            runtime.lineage.nodes[0].attributes.get("context_key"),
        ),
        _check(
            12, runtime.metrics.sanitized, "metric sanitization", runtime.metrics.sanitized, True
        ),
    )
    state = (
        ReferenceReleaseManifestState.READY
        if all(item.passed for item in checks)
        else ReferenceReleaseManifestState.REVIEW
    )
    body = {
        "release_id": release_id,
        "fixture_id": runtime.fixture_id,
        "fixture_version": "2026.08.d04-c13-c16.v1",
        "context_key": runtime.data_audit.context_key,
        "state": state,
        "runtime_address": runtime.content_address,
        "replay_address": runtime.replay.content_address,
        "quality_address": runtime.quality.content_address,
        "selected_record_ids": selected,
        "checks": checks,
        "output_format": "json-v1",
    }
    return ReferenceReleaseManifest(
        **body, content_address=content_hash(body, prefix="release-manifest")
    )


def verify_reference_release_manifest(manifest: ReferenceReleaseManifest) -> tuple[str, ...]:
    """Return manifest integrity and readiness failures."""

    failures = list(manifest.failed_check_ids)
    if not manifest.content_address.startswith("release-manifest:"):
        failures.append("manifest-address")
    if len(manifest.selected_record_ids) != len(set(manifest.selected_record_ids)):
        failures.append("selected-record-duplicates")
    if manifest.ready and failures:
        failures.append("ready-with-failures")
    return tuple(dict.fromkeys(failures))


__all__ = [
    "ReferenceReleaseManifest",
    "ReferenceReleaseManifestCheck",
    "ReferenceReleaseManifestState",
    "build_reference_release_manifest",
    "verify_reference_release_manifest",
]

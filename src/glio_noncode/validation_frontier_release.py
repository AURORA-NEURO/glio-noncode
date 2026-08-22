"""Release manifest for Domain 13 planning evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .serialization import content_hash, jsonable
from .validation_frontier_bundle import ValidationFrontierReleaseBundle
from .validation_frontier_quality_gate import ValidationFrontierQualityGate
from .validation_frontier_replay import ValidationFrontierReplayReceipt


class ValidationFrontierReleaseState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    READY = "ready"
    BLOCKED = "blocked"
    PUBLISHED = "published"


@dataclass(frozen=True, slots=True)
class ValidationFrontierReleaseCheck:
    check_id: str
    passed: bool
    evidence_address: str
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationFrontierReleaseManifest:
    release_id: str
    version: str
    state: ValidationFrontierReleaseState
    bundle_address: str
    quality_gate_address: str
    replay_address: str
    checks: tuple[ValidationFrontierReleaseCheck, ...]
    allowed_uses: tuple[str, ...]
    excluded_uses: tuple[str, ...]
    content_address: str

    @property
    def accepted(self) -> bool:
        return self.state in {ValidationFrontierReleaseState.READY, ValidationFrontierReleaseState.PUBLISHED} and all(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"accepted": self.accepted}


def build_validation_frontier_release_manifest(bundle: ValidationFrontierReleaseBundle, gate: ValidationFrontierQualityGate, replay: ValidationFrontierReplayReceipt, *, release_id: str = "validation-frontier-release", version: str = "2026.08.d13.v1") -> ValidationFrontierReleaseManifest:
    raw = (("bundle", bool(bundle.content_address), bundle.content_address, "bundle is addressed"), ("quality-gate", gate.accepted, gate.content_address, "quality gate passes"), ("replay", replay.accepted, replay.content_address, "replay passes"), ("bundle-publishable", bundle.publishable, bundle.content_address, "positive planning paths are publishable"))
    checks = tuple(ValidationFrontierReleaseCheck(item[0], item[1], item[2], item[3], content_hash(item)) for item in raw)
    state = ValidationFrontierReleaseState.READY if all(item.passed for item in checks) else ValidationFrontierReleaseState.REVIEW
    body = {"release_id": release_id, "version": version, "state": state, "bundle_address": bundle.content_address, "quality_gate_address": gate.content_address, "replay_address": replay.content_address, "checks": checks, "allowed_uses": ("assay planning review", "method development", "reproducibility testing", "research triage"), "excluded_uses": ("patient care", "diagnosis", "prognosis", "treatment selection", "individual risk", "clinical validation claims")}
    return ValidationFrontierReleaseManifest(**body, content_address=content_hash(body))


__all__ = ["ValidationFrontierReleaseCheck", "ValidationFrontierReleaseManifest", "ValidationFrontierReleaseState", "build_validation_frontier_release_manifest"]

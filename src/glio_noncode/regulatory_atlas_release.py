"""Publication manifest and verification for Domain 05 C01–C04."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .regulatory_atlas_bundle import RegulatoryAtlasBundle, RegulatoryAtlasBundleBuilder
from .regulatory_atlas_fixture_eval import RegulatoryAtlasEvaluationReport
from .regulatory_atlas_public_data import RegulatoryAtlasFixture
from .regulatory_atlas_quality_gate import RegulatoryAtlasQualityGateReport
from .regulatory_atlas_replay import RegulatoryAtlasReplayReport
from .serialization import content_hash, jsonable, require_non_empty


class RegulatoryAtlasReleaseState(StrEnum):
    """Publication decision derived from independent checks."""

    PUBLISHED = "published"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasReleaseCheck:
    """One release check and short reason."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class RegulatoryAtlasReleaseManifest:
    """Reproducible publication decision for C01–C04."""

    release_id: str
    fixture_id: str
    fixture_version: str
    context_key: str
    state: RegulatoryAtlasReleaseState
    checks: tuple[RegulatoryAtlasReleaseCheck, ...]
    evaluation_address: str
    quality_address: str
    replay_address: str
    bundle_address: str
    content_address: str

    @property
    def publishable(self) -> bool:
        return self.state is RegulatoryAtlasReleaseState.PUBLISHED and all(
            check.passed for check in self.checks
        )

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        return tuple(check.check_id for check in self.checks if not check.passed)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {
            "publishable": self.publishable,
            "failed_check_ids": list(self.failed_check_ids),
        }


def _address(body: Any) -> str:
    return content_hash(body)


def _check(check_id: str, passed: bool, detail: str) -> RegulatoryAtlasReleaseCheck:
    body = {"check_id": check_id, "passed": passed, "detail": detail}
    return RegulatoryAtlasReleaseCheck(check_id, passed, detail, _address(body))


def build_regulatory_atlas_release_manifest(
    evaluation: RegulatoryAtlasEvaluationReport,
    quality: RegulatoryAtlasQualityGateReport,
    bundle: RegulatoryAtlasBundle,
    replay: RegulatoryAtlasReplayReport,
    *,
    fixture: RegulatoryAtlasFixture,
    release_id: str = "regulatory-atlas-c01-c04",
) -> RegulatoryAtlasReleaseManifest:
    """Build a release decision stricter than an adapter pass."""

    checks: list[RegulatoryAtlasReleaseCheck] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        checks.append(_check(check_id, passed, detail))

    add("release-id", bool(release_id.strip()), "release identity is declared")
    add(
        "fixture-id",
        evaluation.fixture_id
        == quality.fixture_id
        == replay.expectation.fixture_id
        == bundle.fixture_id
        == fixture.fixture_id,
        "all artifacts share fixture identity",
    )
    add(
        "fixture-version",
        evaluation.fixture_version
        == quality.fixture_version
        == replay.expectation.fixture_version
        == bundle.fixture_version
        == fixture.fixture_version,
        "all artifacts share fixture version",
    )
    add(
        "context",
        evaluation.context_key == bundle.context_key == fixture.context_key,
        "all artifacts share context",
    )
    add("evaluation", evaluation.accepted, "execution evaluation is accepted")
    add("quality", quality.accepted, "integrated quality gate is accepted")
    add("replay", replay.accepted, "replay floor is accepted")
    add("bundle", not RegulatoryAtlasBundleBuilder().verify(bundle), "bundle verification is empty")
    add(
        "positive-count",
        evaluation.positive_count == 4 and len(bundle.entries) == 4,
        "four supported positive receipts are publishable",
    )
    add(
        "control-exclusion",
        all(entry.role == "positive" for entry in bundle.entries),
        "review controls are excluded from accepted-only bundle",
    )
    add(
        "address-chain",
        replay.current_evaluation_address == evaluation.content_address
        and quality.evaluation.content_address == evaluation.content_address,
        "evaluation address chain is closed",
    )
    add(
        "no-input-copy",
        all(
            not {"payload", "input_text", "records", "restrictions"} & set(entry.to_dict())
            for entry in bundle.entries
        ),
        "release bundle contains no input collections",
    )
    state = (
        RegulatoryAtlasReleaseState.PUBLISHED
        if all(check.passed for check in checks)
        else (
            RegulatoryAtlasReleaseState.REVIEW
            if evaluation.accepted and quality.accepted
            else RegulatoryAtlasReleaseState.BLOCKED
        )
    )
    body = {
        "release_id": release_id,
        "fixture_id": fixture.fixture_id,
        "fixture_version": fixture.fixture_version,
        "context_key": fixture.context_key,
        "state": state,
        "checks": checks,
        "evaluation_address": evaluation.content_address,
        "quality_address": quality.content_address,
        "replay_address": replay.content_address,
        "bundle_address": bundle.content_address,
    }
    return RegulatoryAtlasReleaseManifest(**body, content_address=_address(body))


def verify_regulatory_atlas_release_manifest(
    manifest: RegulatoryAtlasReleaseManifest,
) -> tuple[str, ...]:
    """Verify manifest address, check addresses, and publication state."""

    failures: list[str] = []
    expected = {
        key: value
        for key, value in manifest.to_dict().items()
        if key not in {"publishable", "failed_check_ids", "content_address"}
    }
    if manifest.content_address != _address(expected):
        failures.append("manifest-address")
    for check in manifest.checks:
        body = {key: value for key, value in check.to_dict().items() if key != "content_address"}
        if check.content_address != _address(body):
            failures.append(f"check-address:{check.check_id}")
    if not manifest.checks:
        failures.append("missing-checks")
    if manifest.state is RegulatoryAtlasReleaseState.PUBLISHED and any(
        not check.passed for check in manifest.checks
    ):
        failures.append("published-with-failures")
    return tuple(failures)


def write_regulatory_atlas_release_manifest(
    manifest: RegulatoryAtlasReleaseManifest, path: str | Path
) -> None:
    """Write a verified JSON release manifest."""

    failures = verify_regulatory_atlas_release_manifest(manifest)
    if failures:
        raise ValidationError(
            f"cannot write invalid regulatory atlas release: {', '.join(failures)}"
        )
    output = Path(path)
    require_non_empty(str(output), "regulatory atlas release output path")
    output.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


__all__ = [
    "RegulatoryAtlasReleaseCheck",
    "RegulatoryAtlasReleaseManifest",
    "RegulatoryAtlasReleaseState",
    "build_regulatory_atlas_release_manifest",
    "verify_regulatory_atlas_release_manifest",
    "write_regulatory_atlas_release_manifest",
]

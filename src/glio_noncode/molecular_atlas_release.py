"""Publication manifest and verification for Domain 05 C05–C08."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .molecular_atlas_bundle import MolecularAtlasBundle, MolecularAtlasBundleBuilder
from .molecular_atlas_fixture_eval import MolecularAtlasEvaluationReport
from .molecular_atlas_public_data import MolecularAtlasFixture
from .molecular_atlas_quality_gate import MolecularAtlasQualityGateReport
from .molecular_atlas_replay import MolecularAtlasReplayReport
from .serialization import content_hash, jsonable, require_non_empty


class MolecularAtlasReleaseState(StrEnum):
    """Publication decision derived from independent checks."""

    PUBLISHED = "published"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class MolecularAtlasReleaseCheck:
    """One release check and short reason."""

    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class MolecularAtlasReleaseManifest:
    """Reproducible publication decision for C05–C08."""

    release_id: str
    fixture_id: str
    fixture_version: str
    context_key: str
    state: MolecularAtlasReleaseState
    checks: tuple[MolecularAtlasReleaseCheck, ...]
    evaluation_address: str
    quality_address: str
    replay_address: str
    bundle_address: str
    content_address: str

    @property
    def publishable(self) -> bool:
        return self.state is MolecularAtlasReleaseState.PUBLISHED and all(
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


def _check(check_id: str, passed: bool, detail: str) -> MolecularAtlasReleaseCheck:
    body = {"check_id": check_id, "passed": passed, "detail": detail}
    return MolecularAtlasReleaseCheck(check_id, passed, detail, _address(body))


def build_molecular_atlas_release_manifest(
    evaluation: MolecularAtlasEvaluationReport,
    quality: MolecularAtlasQualityGateReport,
    bundle: MolecularAtlasBundle,
    replay: MolecularAtlasReplayReport,
    *,
    fixture: MolecularAtlasFixture,
    release_id: str = "molecular-atlas-c05-c08",
) -> MolecularAtlasReleaseManifest:
    """Build a release decision stricter than an adapter pass."""

    checks: list[MolecularAtlasReleaseCheck] = []

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
    add("bundle", not MolecularAtlasBundleBuilder().verify(bundle), "bundle verification is empty")
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
        MolecularAtlasReleaseState.PUBLISHED
        if all(check.passed for check in checks)
        else (
            MolecularAtlasReleaseState.REVIEW
            if evaluation.accepted and quality.accepted
            else MolecularAtlasReleaseState.BLOCKED
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
    return MolecularAtlasReleaseManifest(**body, content_address=_address(body))


def verify_molecular_atlas_release_manifest(
    manifest: MolecularAtlasReleaseManifest,
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
    if manifest.state is MolecularAtlasReleaseState.PUBLISHED and any(
        not check.passed for check in manifest.checks
    ):
        failures.append("published-with-failures")
    return tuple(failures)


def write_molecular_atlas_release_manifest(
    manifest: MolecularAtlasReleaseManifest, path: str | Path
) -> None:
    """Write a verified JSON release manifest."""

    failures = verify_molecular_atlas_release_manifest(manifest)
    if failures:
        raise ValidationError(
            f"cannot write invalid molecular atlas release: {', '.join(failures)}"
        )
    output = Path(path)
    require_non_empty(str(output), "molecular atlas release output path")
    output.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


__all__ = [
    "MolecularAtlasReleaseCheck",
    "MolecularAtlasReleaseManifest",
    "MolecularAtlasReleaseState",
    "build_molecular_atlas_release_manifest",
    "verify_molecular_atlas_release_manifest",
    "write_molecular_atlas_release_manifest",
]

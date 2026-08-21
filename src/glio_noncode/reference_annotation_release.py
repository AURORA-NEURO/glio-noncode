"""Release manifest and publication decision for C05–C08 evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .reference_annotation_bundle import ReferenceAnnotationBundle, ReferenceAnnotationBundleBuilder
from .reference_annotation_contracts import (
    ReferenceAnnotationContractRegistry,
    default_reference_annotation_contracts,
)
from .reference_annotation_fixture_eval import ReferenceAnnotationEvaluationReport
from .reference_annotation_public_data import (
    ReferenceAnnotationFixture,
    default_reference_annotation_fixture,
)
from .reference_annotation_quality_gate import ReferenceAnnotationQualityGateReport
from .reference_annotation_replay import ReferenceAnnotationReplayReport
from .serialization import content_hash, jsonable


class ReferenceAnnotationReleaseState(StrEnum):
    PUBLISHED = "published"
    REVIEW = "review"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationReleaseCheck:
    check_id: str
    passed: bool
    detail: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ReferenceAnnotationReleaseManifest:
    release_id: str
    fixture_id: str
    fixture_version: str
    context_key: str
    state: ReferenceAnnotationReleaseState
    source_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]
    entry_count: int
    accepted_count: int
    review_count: int
    checks: tuple[ReferenceAnnotationReleaseCheck, ...]
    content_address: str

    @property
    def publishable(self) -> bool:
        return self.state is ReferenceAnnotationReleaseState.PUBLISHED and all(
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


def _check(check_id: str, passed: bool, detail: str) -> ReferenceAnnotationReleaseCheck:
    body = {"check_id": check_id, "passed": passed, "detail": detail}
    return ReferenceAnnotationReleaseCheck(check_id, passed, detail, _address(body))


def build_reference_annotation_release_manifest(
    report: ReferenceAnnotationEvaluationReport,
    quality: ReferenceAnnotationQualityGateReport,
    bundle: ReferenceAnnotationBundle,
    replay: ReferenceAnnotationReplayReport,
    *,
    fixture: ReferenceAnnotationFixture | None = None,
    contracts: ReferenceAnnotationContractRegistry | None = None,
    release_id: str = "reference-annotation-c05-c08",
) -> ReferenceAnnotationReleaseManifest:
    """Build a release decision that is stricter than a local evaluation pass."""

    selected = fixture or default_reference_annotation_fixture()
    registry = contracts or default_reference_annotation_contracts()
    builder = ReferenceAnnotationBundleBuilder()
    bundle_failures = builder.verify(bundle)
    checks = (
        _check(
            "fixture-id",
            report.fixture_id == selected.fixture_id == quality.fixture_id == bundle.fixture_id,
            "all release inputs share fixture identity",
        ),
        _check(
            "fixture-version",
            report.fixture_version
            == selected.fixture_version
            == quality.fixture_version
            == bundle.fixture_version,
            "all release inputs share fixture version",
        ),
        _check(
            "context-key",
            report.context_key == selected.context_key == quality.context_key == bundle.context_key,
            "all release inputs share context",
        ),
        _check("evaluation", report.accepted, "evaluation report is accepted"),
        _check("quality-gate", quality.accepted, "quality gate is accepted"),
        _check("replay", replay.accepted, "replay report is accepted"),
        _check("bundle", not bundle_failures, "bundle verification is accepted"),
        _check("bundle-published", bundle.published, "bundle is an accepted-only projection"),
        _check(
            "positive-count",
            bundle.accepted_count == 4,
            "four positive operation entries are present",
        ),
        _check(
            "review-count",
            bundle.review_count == 0,
            "publication bundle contains no review entries",
        ),
        _check(
            "contract-count",
            len(registry.contracts) == 4,
            "all four capability contracts are present",
        ),
        _check(
            "source-count",
            len(selected.sources) == 5,
            "all five public source receipts are present",
        ),
        _check(
            "capability-closure",
            {entry.capability_id for entry in bundle.entries}
            == {contract.capability_id for contract in registry.contracts},
            "bundle entries close over contracts",
        ),
        _check(
            "entry-floor",
            bundle.accepted_count >= len(registry.contracts),
            "one accepted entry exists per contract",
        ),
    )
    accepted = all(check.passed for check in checks)
    if accepted:
        state = ReferenceAnnotationReleaseState.PUBLISHED
    elif report.accepted and quality.accepted:
        state = ReferenceAnnotationReleaseState.REVIEW
    else:
        state = ReferenceAnnotationReleaseState.BLOCKED
    source_ids = tuple(source.source_id for source in selected.sources)
    capability_ids = tuple(contract.capability_id for contract in registry.contracts)
    body = {
        "release_id": release_id,
        "fixture_id": selected.fixture_id,
        "fixture_version": selected.fixture_version,
        "context_key": selected.context_key,
        "state": state,
        "source_ids": source_ids,
        "capability_ids": capability_ids,
        "entry_count": len(bundle.entries),
        "accepted_count": bundle.accepted_count,
        "review_count": bundle.review_count,
        "checks": checks,
    }
    return ReferenceAnnotationReleaseManifest(
        release_id,
        selected.fixture_id,
        selected.fixture_version,
        selected.context_key,
        state,
        source_ids,
        capability_ids,
        len(bundle.entries),
        bundle.accepted_count,
        bundle.review_count,
        checks,
        _address(body),
    )


def verify_reference_annotation_release_manifest(
    manifest: ReferenceAnnotationReleaseManifest,
) -> tuple[str, ...]:
    """Verify release identity, addresses, and publication state."""

    failures: list[str] = []
    if not manifest.source_ids or not manifest.capability_ids:
        failures.append("closure")
    if manifest.accepted_count < 0 or manifest.review_count < 0 or manifest.entry_count < 0:
        failures.append("counts")
    if manifest.accepted_count + manifest.review_count != manifest.entry_count:
        failures.append("count-reconciliation")
    if any(
        check.content_address
        != _address(
            {key: value for key, value in check.to_dict().items() if key != "content_address"}
        )
        for check in manifest.checks
    ):
        failures.append("check-address")
    body = {
        "release_id": manifest.release_id,
        "fixture_id": manifest.fixture_id,
        "fixture_version": manifest.fixture_version,
        "context_key": manifest.context_key,
        "state": manifest.state,
        "source_ids": manifest.source_ids,
        "capability_ids": manifest.capability_ids,
        "entry_count": manifest.entry_count,
        "accepted_count": manifest.accepted_count,
        "review_count": manifest.review_count,
        "checks": manifest.checks,
    }
    if manifest.content_address != _address(body):
        failures.append("manifest-address")
    if manifest.state is ReferenceAnnotationReleaseState.PUBLISHED and not manifest.publishable:
        failures.append("published-with-failure")
    return tuple(failures)


def write_reference_annotation_release_manifest(
    manifest: ReferenceAnnotationReleaseManifest, path: str | Path
) -> Path:
    """Write a stable JSON release manifest after local verification."""

    failures = verify_reference_annotation_release_manifest(manifest)
    if failures:
        raise ValidationError(
            f"cannot write invalid annotation release manifest: {', '.join(failures)}"
        )
    output = Path(path)
    import json

    output.write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output


__all__ = [
    "ReferenceAnnotationReleaseCheck",
    "ReferenceAnnotationReleaseManifest",
    "ReferenceAnnotationReleaseState",
    "build_reference_annotation_release_manifest",
    "verify_reference_annotation_release_manifest",
    "write_reference_annotation_release_manifest",
]

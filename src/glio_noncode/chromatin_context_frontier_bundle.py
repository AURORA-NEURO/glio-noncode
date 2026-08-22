"""Immutable bundle root for the C01-C04 release surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chromatin_context_frontier_fixture_eval import ChromatinContextFrontierEvaluation
from .chromatin_context_frontier_public_data import ChromatinContextFrontierFixture
from .chromatin_context_frontier_release import ChromatinContextFrontierReleaseManifest
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierBundleMember:
    member_id: str
    kind: str
    content_address: str
    required: bool
    detail: str
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.member_id or not self.kind or not self.content_address:
            raise ValidationError("bundle member is incomplete")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ChromatinContextFrontierBundle:
    bundle_id: str
    fixture_id: str
    release_id: str
    members: tuple[ChromatinContextFrontierBundleMember, ...]
    accepted: bool
    root_address: str = ""

    def __post_init__(self) -> None:
        if not self.bundle_id or not self.fixture_id or not self.release_id or not self.members:
            raise ValidationError("bundle is incomplete")
        if not self.root_address:
            object.__setattr__(self, "root_address", content_hash(self.member_addresses()))

    def member_addresses(self) -> dict[str, str]:
        return {item.member_id: item.content_address for item in self.members}

    def required_members(self) -> tuple[ChromatinContextFrontierBundleMember, ...]:
        return tuple(item for item in self.members if item.required)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"member_addresses": self.member_addresses()}


def build_chromatin_context_frontier_bundle(
    fixture: ChromatinContextFrontierFixture,
    evaluation: ChromatinContextFrontierEvaluation,
    release: ChromatinContextFrontierReleaseManifest,
) -> ChromatinContextFrontierBundle:
    members = (
        ChromatinContextFrontierBundleMember(
            "fixture", "public_fixture", fixture.content_address, True, "closed aggregate fixture"
        ),
        ChromatinContextFrontierBundleMember(
            "evaluation",
            "evaluation",
            evaluation.content_address,
            True,
            "positive and control execution",
        ),
        ChromatinContextFrontierBundleMember(
            "release",
            "release_manifest",
            release.content_address,
            True,
            "release and refusal manifest",
        ),
        ChromatinContextFrontierBundleMember(
            "source_receipts",
            "source_receipts",
            content_hash(tuple(item.content_address for item in fixture.sources)),
            True,
            "source receipt set",
        ),
        ChromatinContextFrontierBundleMember(
            "state_matrix",
            "state_matrix",
            content_hash(
                tuple((item.record_id, item.observed_state) for item in evaluation.records)
            ),
            True,
            "observed state matrix",
        ),
        ChromatinContextFrontierBundleMember(
            "issue_matrix",
            "issue_matrix",
            content_hash(
                tuple((item.record_id, item.observed_issue_codes) for item in evaluation.records)
            ),
            True,
            "observed issue matrix",
        ),
        ChromatinContextFrontierBundleMember(
            "limitations",
            "limitations",
            content_hash(release.limitations),
            False,
            "explicit evidence limits",
        ),
    )
    accepted = release.accepted and all(item.content_address for item in members if item.required)
    return ChromatinContextFrontierBundle(
        "glio-noncode-d07-c01-c04-bundle",
        fixture.fixture_id,
        release.release_id,
        members,
        accepted,
    )


__all__ = [
    "ChromatinContextFrontierBundle",
    "ChromatinContextFrontierBundleMember",
    "build_chromatin_context_frontier_bundle",
]

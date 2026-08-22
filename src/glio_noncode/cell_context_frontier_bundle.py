"""Content-addressed bundle root for Domain 08."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_frontier_fixture_eval import CellContextFrontierEvaluation
from .cell_context_frontier_public_data import CellContextFrontierFixture
from .cell_context_frontier_release import CellContextFrontierReleaseManifest
from .errors import ValidationError
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextFrontierBundleMember:
    member_id: str
    kind: str
    content_address: str
    required: bool
    detail: str
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.member_id or not self.kind or not self.content_address or not self.detail:
            raise ValidationError("cell bundle member is incomplete")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextFrontierBundle:
    bundle_id: str
    fixture_id: str
    release_id: str
    members: tuple[CellContextFrontierBundleMember, ...]
    accepted: bool
    root_address: str = ""

    def __post_init__(self) -> None:
        if not self.bundle_id or not self.fixture_id or not self.release_id or not self.members:
            raise ValidationError("cell bundle is incomplete")
        if not self.root_address:
            object.__setattr__(self, "root_address", content_hash(self.member_addresses()))

    def member_addresses(self) -> dict[str, str]:
        return {item.member_id: item.content_address for item in self.members}

    def required_members(self) -> tuple[CellContextFrontierBundleMember, ...]:
        return tuple(item for item in self.members if item.required)

    def member(self, member_id: str) -> CellContextFrontierBundleMember:
        for item in self.members:
            if item.member_id == member_id:
                return item
        raise KeyError(member_id)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self) | {"member_addresses": self.member_addresses()}


def build_cell_context_frontier_bundle(
    fixture: CellContextFrontierFixture,
    evaluation: CellContextFrontierEvaluation,
    release: CellContextFrontierReleaseManifest,
) -> CellContextFrontierBundle:
    members = (
        CellContextFrontierBundleMember(
            "fixture", "public_fixture", fixture.content_address, True, "closed aggregate fixture"
        ),
        CellContextFrontierBundleMember(
            "evaluation",
            "evaluation",
            evaluation.content_address,
            True,
            "context operation evaluation",
        ),
        CellContextFrontierBundleMember(
            "release",
            "release_manifest",
            release.content_address,
            True,
            "release and refusal manifest",
        ),
        CellContextFrontierBundleMember(
            "sources",
            "source_receipts",
            content_hash(tuple(item.content_address for item in fixture.sources)),
            True,
            "five public source receipts",
        ),
        CellContextFrontierBundleMember(
            "state_matrix",
            "state_matrix",
            content_hash(
                tuple((item.record_id, item.observed_state) for item in evaluation.records)
            ),
            True,
            "expected and observed context states",
        ),
        CellContextFrontierBundleMember(
            "issue_matrix",
            "issue_matrix",
            content_hash(
                tuple((item.record_id, item.observed_issue_codes) for item in evaluation.records)
            ),
            True,
            "parser issue floors",
        ),
        CellContextFrontierBundleMember(
            "limits",
            "limitations",
            content_hash(release.limitations),
            False,
            "explicit limits and open evidence work",
        ),
    )
    return CellContextFrontierBundle(
        "glio-noncode-d08-c01-c04-bundle",
        fixture.fixture_id,
        release.release_id,
        members,
        release.accepted and all(item.content_address for item in members if item.required),
    )


__all__ = [
    "CellContextFrontierBundle",
    "CellContextFrontierBundleMember",
    "build_cell_context_frontier_bundle",
]

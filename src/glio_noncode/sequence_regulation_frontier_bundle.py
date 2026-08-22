"""Portable bundle view for C09-C12 outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_regulation_frontier_fixture_eval import SequenceRegulationEvaluation
from .sequence_regulation_frontier_public_data import SequenceRegulationFixture
from .sequence_regulation_frontier_release import SequenceRegulationReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceRegulationBundle:
    bundle_id: str
    fixture_id: str
    release_id: str
    record_count: int
    result_addresses: tuple[str, ...]
    root_address: str
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_regulation_bundle(
    fixture: SequenceRegulationFixture,
    evaluation: SequenceRegulationEvaluation,
    release: SequenceRegulationReleaseManifest,
) -> SequenceRegulationBundle:
    if not evaluation.records:
        raise ValidationError("bundle requires evaluation records")
    addresses = tuple(item.adapter.content_address for item in evaluation.records)
    body = {
        "fixture_id": fixture.fixture_id,
        "release_id": release.release_id,
        "addresses": addresses,
    }
    return SequenceRegulationBundle(
        bundle_id="bundle:sequence-regulation-frontier",
        fixture_id=fixture.fixture_id,
        release_id=release.release_id,
        record_count=len(evaluation.records),
        result_addresses=addresses,
        root_address=content_hash(body),
        accepted=release.accepted and all(address.startswith("sha256:") for address in addresses),
    )


__all__ = ["SequenceRegulationBundle", "build_sequence_regulation_bundle"]

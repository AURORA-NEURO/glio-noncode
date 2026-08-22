"""Portable result bundle for methylation release consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .methylation_frontier_fixture_eval import MethylationFrontierEvaluation
from .methylation_frontier_public_data import MethylationFrontierFixture
from .methylation_frontier_release import MethylationFrontierReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class MethylationFrontierBundle:
    bundle_id: str
    fixture_id: str
    release_id: str
    record_count: int
    result_addresses: tuple[str, ...]
    root_address: str
    accepted: bool

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_methylation_frontier_bundle(
    fixture: MethylationFrontierFixture,
    evaluation: MethylationFrontierEvaluation,
    release: MethylationFrontierReleaseManifest,
) -> MethylationFrontierBundle:
    if not evaluation.records:
        raise ValidationError("bundle requires evaluation records")
    addresses = tuple(item.adapter.content_address for item in evaluation.records)
    body = {
        "fixture_id": fixture.fixture_id,
        "release_id": release.release_id,
        "addresses": addresses,
    }
    return MethylationFrontierBundle(
        bundle_id="bundle:methylation-frontier",
        fixture_id=fixture.fixture_id,
        release_id=release.release_id,
        record_count=len(evaluation.records),
        result_addresses=addresses,
        root_address=content_hash(body),
        accepted=release.accepted and all(address.startswith("sha256:") for address in addresses),
    )


__all__ = ["MethylationFrontierBundle", "build_methylation_frontier_bundle"]

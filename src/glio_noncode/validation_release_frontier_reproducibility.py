"""Reproducibility packet joining all required replay receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable
from .validation_release_frontier_contracts import ValidationReleaseEvaluation, ValidationReleaseFixture
from .validation_release_frontier_lineage import ValidationReleaseLineage
from .validation_release_frontier_replay import ValidationReleaseReplayReport


@dataclass(frozen=True, slots=True)
class ValidationReleaseReproducibilityPacket:
    fixture_address: str
    evaluation_address: str
    replay_address: str
    lineage_address: str
    deterministic: bool
    complete: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_validation_release_reproducibility_packet(fixture: ValidationReleaseFixture, evaluation: ValidationReleaseEvaluation, replay: ValidationReleaseReplayReport, lineage: ValidationReleaseLineage) -> ValidationReleaseReproducibilityPacket:
    body = {"fixture_address": fixture.content_address, "evaluation_address": evaluation.content_address, "replay_address": replay.content_address, "lineage_address": lineage.content_address, "deterministic": replay.deterministic, "complete": all(address.startswith("sha256:") for address in (fixture.content_address, evaluation.content_address, replay.content_address, lineage.content_address))}
    return ValidationReleaseReproducibilityPacket(**body, content_address=content_hash(body))


__all__ = ["ValidationReleaseReproducibilityPacket", "build_validation_release_reproducibility_packet"]

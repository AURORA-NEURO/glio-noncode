"""Release manifest for the sequence grammar beta evidence plane."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_quality_gate import SequenceGrammarQualityReport
from .sequence_grammar_frontier_runtime import SequenceGrammarRuntimeReport
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarReleaseManifest:
    release_id: str
    version: str
    accepted: bool
    evidence_boundary: str
    operation_ids: tuple[str, ...]
    fixture_id: str
    runtime_address: str
    quality_address: str
    limitations: tuple[str, ...]
    rollback_target: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.release_id.strip() or not self.version.strip() or not self.operation_ids:
            raise ValidationError("release manifest is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "release_id": self.release_id,
                        "version": self.version,
                        "accepted": self.accepted,
                        "evidence_boundary": self.evidence_boundary,
                        "operation_ids": self.operation_ids,
                        "fixture_id": self.fixture_id,
                        "runtime_address": self.runtime_address,
                        "quality_address": self.quality_address,
                        "limitations": self.limitations,
                        "rollback_target": self.rollback_target,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def build_sequence_grammar_release(
    quality: SequenceGrammarQualityReport, runtime: SequenceGrammarRuntimeReport
) -> SequenceGrammarReleaseManifest:
    return SequenceGrammarReleaseManifest(
        release_id="sequence-grammar-beta-release",
        version="2026.08.d06-c05-c08.beta.1",
        accepted=quality.accepted and runtime.accepted,
        evidence_boundary=runtime.reconciliation.fixture_id and "public_aggregate_non_patient",
        operation_ids=tuple(sorted(runtime.evaluation.operation_counts())),
        fixture_id=runtime.evaluation.fixture_id,
        runtime_address=runtime.content_address,
        quality_address=quality.content_address,
        limitations=(
            "research-only descriptive motif and grammar evidence",
            "no calibrated regulatory probability",
            "no clinical interpretation",
            "aggregate fixture mechanics only",
        ),
        rollback_target="sequence-grammar-beta-release.previous",
    )


__all__ = ["SequenceGrammarReleaseManifest", "build_sequence_grammar_release"]

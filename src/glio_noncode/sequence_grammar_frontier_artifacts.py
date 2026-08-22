"""Artifact inventory for sequence grammar releases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_bundle import SequenceGrammarBundle
from .sequence_grammar_frontier_quality_gate import SequenceGrammarQualityReport
from .sequence_grammar_frontier_release import SequenceGrammarReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarArtifact:
    artifact_id: str
    artifact_kind: str
    media_type: str
    content_address: str
    required: bool = True

    def __post_init__(self) -> None:
        if (
            not self.artifact_id.strip()
            or not self.artifact_kind.strip()
            or not self.content_address.startswith("sha256:")
        ):
            raise ValidationError("artifact is incomplete")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarArtifactInventory:
    accepted: bool
    artifacts: tuple[SequenceGrammarArtifact, ...]
    root_address: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.artifacts or not self.root_address.startswith("sha256:"):
            raise ValidationError("artifact inventory is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "accepted": self.accepted,
                        "artifacts": self.artifacts,
                        "root_address": self.root_address,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "artifact_count": len(self.artifacts),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "root_address": self.root_address,
            "content_address": self.content_address,
        }


def build_sequence_grammar_artifacts(
    quality: SequenceGrammarQualityReport,
    release: SequenceGrammarReleaseManifest,
    bundle: SequenceGrammarBundle,
) -> SequenceGrammarArtifactInventory:
    artifacts = (
        SequenceGrammarArtifact(
            "fixture",
            "public_fixture",
            "application/json",
            content_hash({"fixture_id": quality.fixture_id}),
        ),
        SequenceGrammarArtifact(
            "evaluation",
            "evaluation_report",
            "application/json",
            content_hash({"fixture_id": quality.fixture_id, "kind": "evaluation"}),
        ),
        SequenceGrammarArtifact(
            "quality", "quality_gate", "application/json", quality.content_address
        ),
        SequenceGrammarArtifact(
            "runtime", "runtime_report", "application/json", release.runtime_address
        ),
        SequenceGrammarArtifact(
            "schema",
            "schema_manifest",
            "application/json",
            content_hash({"kind": "schema", "fixture_id": quality.fixture_id}),
        ),
        SequenceGrammarArtifact(
            "lineage",
            "lineage_graph",
            "application/json",
            content_hash({"kind": "lineage", "fixture_id": quality.fixture_id}),
        ),
        SequenceGrammarArtifact(
            "policy",
            "policy_report",
            "application/json",
            content_hash({"kind": "policy", "fixture_id": quality.fixture_id}),
        ),
        SequenceGrammarArtifact(
            "bundle", "compact_bundle", "application/json", bundle.root_address
        ),
        SequenceGrammarArtifact(
            "release", "release_manifest", "application/json", release.content_address
        ),
    )
    accepted = (
        quality.accepted
        and release.accepted
        and bundle.accepted
        and all(artifact.content_address.startswith("sha256:") for artifact in artifacts)
    )
    return SequenceGrammarArtifactInventory(accepted, artifacts, release.content_address)


__all__ = [
    "SequenceGrammarArtifact",
    "SequenceGrammarArtifactInventory",
    "build_sequence_grammar_artifacts",
]

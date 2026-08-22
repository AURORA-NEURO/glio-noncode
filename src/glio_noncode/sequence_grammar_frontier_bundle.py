"""Compact evidence bundle for a sequence grammar release."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .sequence_grammar_frontier_fixture_eval import SequenceGrammarEvaluation
from .sequence_grammar_frontier_public_data import SequenceGrammarFixture
from .sequence_grammar_frontier_release import SequenceGrammarReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceGrammarBundleEntry:
    record_id: str
    operation: str
    role: str
    state: str
    issue_codes: tuple[str, ...]
    result_address: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.result_address.startswith("sha256:"):
            raise ValidationError("bundle entry is incomplete")
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "record_id": self.record_id,
                        "operation": self.operation,
                        "role": self.role,
                        "state": self.state,
                        "issue_codes": self.issue_codes,
                        "result_address": self.result_address,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceGrammarBundle:
    bundle_id: str
    fixture_id: str
    release_address: str
    accepted: bool
    entries: tuple[SequenceGrammarBundleEntry, ...]
    root_address: str = ""

    def __post_init__(self) -> None:
        if not self.bundle_id.strip() or not self.entries:
            raise ValidationError("bundle requires identity and entries")
        if not self.root_address:
            object.__setattr__(
                self,
                "root_address",
                content_hash(
                    {
                        "bundle_id": self.bundle_id,
                        "fixture_id": self.fixture_id,
                        "release_address": self.release_address,
                        "accepted": self.accepted,
                        "entries": self.entries,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "fixture_id": self.fixture_id,
            "release_address": self.release_address,
            "accepted": self.accepted,
            "entry_count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
            "root_address": self.root_address,
        }


def build_sequence_grammar_bundle(
    fixture: SequenceGrammarFixture,
    evaluation: SequenceGrammarEvaluation,
    release: SequenceGrammarReleaseManifest,
) -> SequenceGrammarBundle:
    entries = tuple(
        SequenceGrammarBundleEntry(
            execution.record_id,
            execution.operation.value,
            execution.role.value,
            execution.adapter_state.value,
            execution.issue_codes,
            execution.adapter_address,
        )
        for execution in evaluation.executions
    )
    return SequenceGrammarBundle(
        "sequence-grammar-beta-bundle",
        fixture.fixture_id,
        release.content_address,
        release.accepted and evaluation.accepted,
        entries,
    )


__all__ = ["SequenceGrammarBundle", "SequenceGrammarBundleEntry", "build_sequence_grammar_bundle"]

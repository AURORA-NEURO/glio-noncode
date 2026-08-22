"""Sanitized research bundle builder for sequence-effect outputs."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_fixture_eval import SequenceEffectEvaluation
from .sequence_effect_frontier_public_data import SequenceEffectFixture
from .sequence_effect_frontier_release import SequenceEffectReleaseManifest
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectBundleEntry:
    record_id: str
    operation: str
    state: str
    issue_codes: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectBundle:
    bundle_id: str
    boundary: str
    entries: tuple[SequenceEffectBundleEntry, ...]
    release_address: str
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash(
                    {
                        "bundle_id": self.bundle_id,
                        "boundary": self.boundary,
                        "entries": self.entries,
                        "release_address": self.release_address,
                        "accepted": self.accepted,
                    }
                ),
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "boundary": self.boundary,
            "entry_count": len(self.entries),
            "entries": [item.to_dict() for item in self.entries],
            "release_address": self.release_address,
            "accepted": self.accepted,
            "content_address": self.content_address,
        }

    def render_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=2) + "\n"

    def render_csv(self) -> str:
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("record_id", "operation", "state", "issue_codes", "content_address"))
        for entry in self.entries:
            writer.writerow(
                (
                    entry.record_id,
                    entry.operation,
                    entry.state,
                    "|".join(entry.issue_codes),
                    entry.content_address,
                )
            )
        return output.getvalue()


def build_sequence_effect_bundle(
    fixture: SequenceEffectFixture,
    evaluation: SequenceEffectEvaluation,
    release: SequenceEffectReleaseManifest,
    *,
    accepted_only: bool = False,
    bundle_id: str = "sequence-effect-bundle",
) -> SequenceEffectBundle:
    entries = tuple(
        SequenceEffectBundleEntry(
            item.record_id,
            item.operation.value,
            item.adapter_state.value,
            item.issue_codes,
            item.content_address,
        )
        for item in evaluation.executions
        if not accepted_only or item.accepted
    )
    return SequenceEffectBundle(
        bundle_id,
        fixture.evidence_boundary,
        entries,
        release.content_address,
        release.accepted and (not accepted_only or bool(entries)),
    )


__all__ = ["SequenceEffectBundle", "SequenceEffectBundleEntry", "build_sequence_effect_bundle"]

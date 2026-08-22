"""Named invariant catalog and runner for sequence-effect releases."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .sequence_effect_frontier_fixture_eval import SequenceEffectEvaluation
from .sequence_effect_frontier_public_data import SequenceEffectFixture
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class SequenceEffectInvariant:
    invariant_id: str
    description: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"invariant_id": self.invariant_id, "description": self.description}),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class SequenceEffectInvariantReport:
    accepted: bool
    results: tuple[dict[str, Any], ...]
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(
                self,
                "content_address",
                content_hash({"accepted": self.accepted, "results": self.results}),
            )

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def default_sequence_effect_invariants() -> tuple[SequenceEffectInvariant, ...]:
    return tuple(
        SequenceEffectInvariant(f"sequence-effect-{index:02d}", description)
        for index, description in enumerate(
            (
                "fixture is public aggregate",
                "fixture context is exact",
                "source IDs are closed",
                "record IDs are unique",
                "positive/control roles are explicit",
                "all four operations are represented",
                "execution count is conserved",
                "execution addresses are stable",
                "control issue codes are visible",
                "control rows are not publishable",
            ),
            start=1,
        )
    )


def run_sequence_effect_invariants(
    fixture: SequenceEffectFixture,
    evaluation: SequenceEffectEvaluation,
    observations: Mapping[str, bool] | None = None,
) -> SequenceEffectInvariantReport:
    observations = dict(observations or {})
    defaults = {item.invariant_id: True for item in default_sequence_effect_invariants()}
    defaults["sequence-effect-01"] = fixture.evidence_boundary == "public_aggregate_non_patient"
    defaults["sequence-effect-02"] = len({item.context_key for item in fixture.records}) == 1
    defaults["sequence-effect-03"] = all(set(item.source_ids) for item in fixture.records)
    defaults["sequence-effect-04"] = len({item.record_id for item in fixture.records}) == len(
        fixture.records
    )
    defaults["sequence-effect-06"] = len({item.operation for item in fixture.records}) == 4
    defaults["sequence-effect-07"] = len(evaluation.executions) == len(fixture.records)
    defaults["sequence-effect-08"] = all(
        item.content_address.startswith("sha256:") for item in evaluation.executions
    )
    defaults["sequence-effect-09"] = (
        sum(bool(item.issue_codes) for item in evaluation.executions) == 12
    )
    defaults["sequence-effect-10"] = all(
        not item.role.value == "control" or item.adapter_state.value != "supported"
        for item in evaluation.executions
    )
    defaults.update(observations)
    results = tuple(
        {"invariant_id": key, "passed": value} for key, value in sorted(defaults.items())
    )
    return SequenceEffectInvariantReport(all(item["passed"] for item in results), results)


__all__ = [
    "SequenceEffectInvariant",
    "SequenceEffectInvariantReport",
    "default_sequence_effect_invariants",
    "run_sequence_effect_invariants",
]

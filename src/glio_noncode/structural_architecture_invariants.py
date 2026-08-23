"""Executable conservation and publication invariants for D02."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .structural_architecture_contracts import StructuralArchitectureRuntime, addressed


@dataclass(frozen=True, slots=True)
class StructuralArchitectureInvariant:
    invariant_id: str
    passed: bool
    observed: Any
    required: Any
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "invariant_id": self.invariant_id,
            "passed": self.passed,
            "observed": self.observed,
            "required": self.required,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class StructuralArchitectureInvariantReport:
    fixture_id: str
    invariants: tuple[StructuralArchitectureInvariant, ...]
    accepted: bool
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "invariants": [item.to_dict() for item in self.invariants],
            "accepted": self.accepted,
            "content_address": self.content_address,
        }


def run_structural_architecture_invariants(
    runtime: StructuralArchitectureRuntime,
) -> StructuralArchitectureInvariantReport:
    checks = (
        _invariant(
            "case-conservation",
            len(runtime.evaluation.receipts),
            64,
            "case receipts conserve the declared fixture count",
        ),
        _invariant(
            "control-conservation",
            runtime.evaluation.control_count,
            48,
            "all controls remain visible",
        ),
        _invariant(
            "ledger-conservation",
            len(runtime.ledger.events),
            64,
            "lineage event count matches case count",
        ),
        _invariant(
            "stage-order",
            tuple(item.ordinal for item in runtime.stages),
            tuple(range(1, 21)),
            "runtime stages preserve order",
        ),
        _invariant("release-artifacts", len(runtime.artifacts), 6, "release inventory is complete"),
    )
    invariants = tuple(
        item
        if isinstance(item.passed, bool)
        else StructuralArchitectureInvariant(
            item.invariant_id,
            item.observed == item.required,
            item.observed,
            item.required,
            item.detail,
        )
        for item in checks
    )
    accepted = all(item.observed == item.required for item in invariants)
    body = {"fixture_id": runtime.fixture_id, "invariants": invariants, "accepted": accepted}
    return StructuralArchitectureInvariantReport(
        **body, content_address=addressed(body, "structural-invariants")
    )


def _invariant(
    invariant_id: str, observed: Any, required: Any, detail: str
) -> StructuralArchitectureInvariant:
    return StructuralArchitectureInvariant(
        invariant_id, observed == required, observed, required, detail
    )


__all__ = [
    "StructuralArchitectureInvariant",
    "StructuralArchitectureInvariantReport",
    "run_structural_architecture_invariants",
]

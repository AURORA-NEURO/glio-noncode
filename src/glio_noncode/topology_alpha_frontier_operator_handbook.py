"""Operator-facing procedures for alpha inspection and release review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierHandbookProcedure:
    procedure_id: str
    title: str
    purpose: str
    command: str
    expected: str
    if_failed: str
    evidence_to_retain: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class TopologyAlphaFrontierOperatorHandbook:
    name: str
    procedures: tuple[TopologyAlphaFrontierHandbookProcedure, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(self.to_dict(False)))

    def procedure(self, procedure_id: str) -> TopologyAlphaFrontierHandbookProcedure:
        for item in self.procedures:
            if item.procedure_id == procedure_id:
                return item
        raise KeyError(procedure_id)

    def to_dict(self, include_address: bool = True) -> dict[str, Any]:
        value = {"name": self.name, "procedures": [item.to_dict() for item in self.procedures], "accepted": self.accepted}
        if include_address:
            value["content_address"] = self.content_address
        return value


def default_topology_alpha_frontier_operator_handbook() -> TopologyAlphaFrontierOperatorHandbook:
    procedures = (
        TopologyAlphaFrontierHandbookProcedure("load", "Load aggregate fixture", "Confirm source boundary and balanced records.", "python -m glio_noncode topology-alpha-frontier-fixture", "16 records and 4 source receipts", "stop and inspect the fixture", ("fixture address", "source checksums")),
        TopologyAlphaFrontierHandbookProcedure("replay", "Replay all operations", "Run primitive adapters and compare state floors.", "python -m glio_noncode topology-alpha-frontier-evaluate", "16 state matches and 16 issue matches", "retain the failing record for review", ("evaluation address", "issue codes")),
        TopologyAlphaFrontierHandbookProcedure("inspect", "Inspect controls", "Filter by operation, state, role, or issue.", "glio-noncode topology-alpha-frontier-review", "12 open controls", "do not collapse review paths", ("review rows", "next actions")),
        TopologyAlphaFrontierHandbookProcedure("release", "Build release package", "Run all quality, policy, lineage, and artifact gates.", "glio-noncode topology-alpha-frontier-release", "publishable release manifest", "keep package in review", ("release address", "artifact inventory")),
        TopologyAlphaFrontierHandbookProcedure("verify", "Verify remote checks", "Confirm the required workflow completed for the pushed commit.", "gh run list --repo AURORA-NEURO/glio-noncode", "required checks complete", "inspect the failing workflow", ("workflow id", "commit id")),
    )
    return TopologyAlphaFrontierOperatorHandbook("topology-alpha-frontier-operations", procedures, len(procedures) == 5 and all(item.evidence_to_retain for item in procedures))


__all__ = ["TopologyAlphaFrontierHandbookProcedure", "TopologyAlphaFrontierOperatorHandbook", "default_topology_alpha_frontier_operator_handbook"]

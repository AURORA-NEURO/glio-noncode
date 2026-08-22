"""Detailed gate coverage for disease and molecular-state restrictions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .cell_context_beta_frontier_fixture_eval import CellContextBetaFrontierEvaluation
from .serialization import content_hash, jsonable


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierGateObservation:
    gate_id: str
    required_declaration: str
    supported_count: int
    refused_count: int
    refusal_record_ids: tuple[str, ...]
    detail: str
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class CellContextBetaFrontierGateDepthReport:
    gates: tuple[CellContextBetaFrontierGateObservation, ...]
    accepted: bool
    content_address: str = ""

    def __post_init__(self) -> None:
        if not self.content_address:
            object.__setattr__(self, "content_address", content_hash(jsonable(self)))

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


def audit_cell_context_beta_frontier_gates(
    evaluation: CellContextBetaFrontierEvaluation,
) -> CellContextBetaFrontierGateDepthReport:
    groups = {
        "disease-gate": "glioblastoma context",
        "idh-state-gate": "IDH-mutant declaration",
        "h3-state-gate": "H3K27-altered declaration",
        "lineage-context-gate": "adult or pediatric glioma context",
    }
    gates = []
    for gate_id, requirement in groups.items():
        if gate_id == "disease-gate":
            rows = tuple(
                item
                for item in evaluation.records
                if item.operation == "glioblastoma_malignant_state_prior"
            )
        elif gate_id == "idh-state-gate":
            rows = tuple(
                item
                for item in evaluation.records
                if item.operation == "idh_mutant_lineage_state_prior"
            )
        elif gate_id == "h3-state-gate":
            rows = tuple(
                item
                for item in evaluation.records
                if item.operation == "h3k27_altered_developmental_state_prior"
            )
        else:
            rows = tuple(
                item
                for item in evaluation.records
                if item.operation == "developmental_lineage_prior"
            )
        gates.append(
            CellContextBetaFrontierGateObservation(
                gate_id,
                requirement,
                sum(item.observed_state == "supported" for item in rows),
                sum(item.observed_state == "out_of_domain" for item in rows),
                tuple(item.record_id for item in rows if item.observed_state == "out_of_domain"),
                "supported and refused gate rows remain distinct",
            )
        )
    return CellContextBetaFrontierGateDepthReport(
        tuple(gates), all(item.supported_count >= 1 and item.refused_count >= 1 for item in gates)
    )


__all__ = [
    "CellContextBetaFrontierGateDepthReport",
    "CellContextBetaFrontierGateObservation",
    "audit_cell_context_beta_frontier_gates",
]

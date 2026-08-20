"""Factorized path scoring and sensitivity checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .models import HypothesisEdge
from .scoring import clamp, derived_path_score


@dataclass(frozen=True, slots=True)
class SensitivityResult:
    """How a path changes when one edge is challenged."""

    edge_id: str
    baseline_support: float
    challenged_support: float
    support_delta: float
    conclusion: str

    def to_dict(self) -> dict[str, object]:
        return {
            "edge_id": self.edge_id,
            "baseline_support": self.baseline_support,
            "challenged_support": self.challenged_support,
            "support_delta": self.support_delta,
            "conclusion": self.conclusion,
        }


@dataclass(frozen=True, slots=True)
class CausalPathSummary:
    """Factorized path summary with alternatives and fragility."""

    path_id: str
    edge_ids: tuple[str, ...]
    support: float
    uncertainty: float
    weakest_edge_id: str
    sensitivity: tuple[SensitivityResult, ...]
    alternatives: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "path_id": self.path_id,
            "edge_ids": list(self.edge_ids),
            "support": self.support,
            "uncertainty": self.uncertainty,
            "weakest_edge_id": self.weakest_edge_id,
            "sensitivity": [item.to_dict() for item in self.sensitivity],
            "alternatives": list(self.alternatives),
            "limitations": list(self.limitations),
        }


class CausalLattice:
    """Compute edge-specific support without collapsing the causal chain."""

    def summarize(
        self,
        path_id: str,
        edges: Iterable[HypothesisEdge],
        *,
        alternatives: Iterable[str] = (),
    ) -> CausalPathSummary:
        edge_list = tuple(edges)
        if not edge_list:
            raise ValueError("causal path requires edges")
        scores = tuple(edge.support for edge in edge_list)
        support = derived_path_score(scores)
        weakest = min(edge_list, key=lambda edge: (edge.support, edge.edge_id))
        sensitivity = tuple(self._challenge(path_id, edge_list, edge.edge_id) for edge in edge_list)
        return CausalPathSummary(
            path_id=path_id,
            edge_ids=tuple(edge.edge_id for edge in edge_list),
            support=round(support, 6),
            uncertainty=round(max(edge.uncertainty for edge in edge_list), 6),
            weakest_edge_id=weakest.edge_id,
            sensitivity=sensitivity,
            alternatives=tuple(alternatives),
            limitations=(
                "Path support is conditional on the supplied edge observations.",
                "Sensitivity does not identify a real-world intervention effect without an identification design.",
            ),
        )

    @staticmethod
    def _challenge(path_id: str, edges: tuple[HypothesisEdge, ...], challenged_id: str) -> SensitivityResult:
        baseline = derived_path_score(edge.support for edge in edges)
        challenged = derived_path_score(0.0 if edge.edge_id == challenged_id else edge.support for edge in edges)
        delta = round(baseline - challenged, 6)
        if delta >= 0.35:
            conclusion = "path is highly dependent on this edge"
        elif delta >= 0.15:
            conclusion = "path is moderately dependent on this edge"
        else:
            conclusion = "path remains supported by other edges"
        return SensitivityResult(challenged_id, round(baseline, 6), round(challenged, 6), delta, conclusion)


def compare_paths(paths: Iterable[CausalPathSummary]) -> tuple[CausalPathSummary, ...]:
    """Rank paths by support while retaining uncertainty and alternatives."""

    return tuple(sorted(paths, key=lambda path: (-path.support, path.uncertainty, path.path_id)))

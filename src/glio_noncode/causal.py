"""Factorized path scoring and sensitivity checks."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .errors import ValidationError
from .models import HypothesisEdge
from .scoring import derived_path_score


@dataclass(frozen=True, slots=True)
class SensitivityResult:
    """How a path changes when one edge is challenged."""

    edge_id: str
    baseline_support: float
    challenged_support: float
    support_delta: float
    aggregate_sensitivity: str
    challenged_bottleneck_support: float
    all_edges_have_nonzero_support_after_challenge: bool
    conclusion: str

    def to_dict(self) -> dict[str, object]:
        return {
            "edge_id": self.edge_id,
            "baseline_support": self.baseline_support,
            "challenged_support": self.challenged_support,
            "support_delta": self.support_delta,
            "aggregate_sensitivity": self.aggregate_sensitivity,
            "challenged_bottleneck_support": self.challenged_bottleneck_support,
            "all_edges_have_nonzero_support_after_challenge": (
                self.all_edges_have_nonzero_support_after_challenge
            ),
            "conclusion": self.conclusion,
        }


@dataclass(frozen=True, slots=True)
class CausalPathSummary:
    """Factorized path summary with alternatives and fragility."""

    path_id: str
    edge_ids: tuple[str, ...]
    support: float
    bottleneck_support: float
    all_edges_have_nonzero_support: bool
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
            "support_semantics": "heuristic aggregate proxy; not a calibrated probability",
            "bottleneck_support": self.bottleneck_support,
            "all_edges_have_nonzero_support": self.all_edges_have_nonzero_support,
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
        if not isinstance(path_id, str) or not path_id.strip():
            raise ValidationError("path_id must be a non-empty string")
        edge_list = tuple(edges)
        if not edge_list:
            raise ValueError("causal path requires edges")
        if any(not isinstance(edge, HypothesisEdge) for edge in edge_list):
            raise ValidationError("causal path edges must be HypothesisEdge objects")
        edge_ids = tuple(edge.edge_id for edge in edge_list)
        if len(edge_ids) != len(set(edge_ids)):
            raise ValidationError("causal path edge IDs must be unique")
        for previous, following in zip(edge_list, edge_list[1:], strict=False):
            if previous.target_id != following.source_id:
                raise ValidationError(
                    "causal path edges must be contiguous; "
                    f"{previous.edge_id} does not connect to {following.edge_id}"
                )
        scores = tuple(edge.support for edge in edge_list)
        support = derived_path_score(scores)
        bottleneck_support = min(scores)
        weakest = min(edge_list, key=lambda edge: (edge.support, edge.edge_id))
        sensitivity = tuple(self._challenge(edge_list, edge.edge_id) for edge in edge_list)
        return CausalPathSummary(
            path_id=path_id,
            edge_ids=edge_ids,
            support=round(support, 6),
            bottleneck_support=round(bottleneck_support, 6),
            all_edges_have_nonzero_support=all(score > 0.0 for score in scores),
            uncertainty=round(max(edge.uncertainty for edge in edge_list), 6),
            weakest_edge_id=weakest.edge_id,
            sensitivity=sensitivity,
            alternatives=tuple(alternatives),
            limitations=(
                "Path support is conditional on the supplied edge observations.",
                (
                    "Composite support is a heuristic proxy, not a calibrated probability; "
                    "the bottleneck is the minimum edge support."
                ),
                (
                    "Zeroing a required edge makes this serial path incomplete even if its "
                    "composite support proxy remains nonzero."
                ),
                (
                    "Sensitivity does not identify a real-world intervention effect without "
                    "an identification design."
                ),
            ),
        )

    @staticmethod
    def _challenge(edges: tuple[HypothesisEdge, ...], challenged_id: str) -> SensitivityResult:
        baseline = derived_path_score(edge.support for edge in edges)
        challenged_scores = tuple(
            0.0 if edge.edge_id == challenged_id else edge.support for edge in edges
        )
        challenged = derived_path_score(challenged_scores)
        challenged_bottleneck = min(challenged_scores)
        delta = round(baseline - challenged, 6)
        if delta >= 0.35:
            aggregate_sensitivity = "high"
        elif delta >= 0.15:
            aggregate_sensitivity = "moderate"
        else:
            aggregate_sensitivity = "low"
        return SensitivityResult(
            edge_id=challenged_id,
            baseline_support=round(baseline, 6),
            challenged_support=round(challenged, 6),
            support_delta=delta,
            aggregate_sensitivity=aggregate_sensitivity,
            challenged_bottleneck_support=round(challenged_bottleneck, 6),
            all_edges_have_nonzero_support_after_challenge=all(
                score > 0.0 for score in challenged_scores
            ),
            conclusion=(
                "Setting this required edge to zero leaves the serial path incomplete, "
                "even if the aggregate support proxy remains nonzero."
            ),
        )


def compare_paths(paths: Iterable[CausalPathSummary]) -> tuple[CausalPathSummary, ...]:
    """Rank paths by weakest-link support, then proxy, uncertainty, and identity."""

    return tuple(
        sorted(
            paths,
            key=lambda path: (
                -path.bottleneck_support,
                -path.support,
                path.uncertainty,
                path.path_id,
            ),
        )
    )

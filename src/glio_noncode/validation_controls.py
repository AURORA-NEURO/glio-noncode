"""Negative-control construction and validation-value prioritization."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .models import CandidateElement, EvidenceState, ExperimentOption
from .serialization import content_hash, jsonable
from .uncertainty import UncertaintyBand, UncertaintyReport


@dataclass(frozen=True, slots=True)
class NegativeControlCandidate:
    """One matched control candidate that is not a measured negative."""

    control_id: str
    element_id: str
    target_element_id: str
    context_key: str
    distance: float
    matching_dimensions: tuple[str, ...]
    expected_state: EvidenceState
    rationale: str
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "control_id",
            "element_id",
            "target_element_id",
            "context_key",
            "rationale",
        ):
            if not str(getattr(self, name)).strip():
                raise ValidationError(f"negative control {name} is required")
        if self.distance < 0.0:
            raise ValidationError("negative control distance must not be negative")
        if self.expected_state != EvidenceState.UNSUPPORTED:
            raise ValidationError("unmeasured controls must remain unsupported")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class NegativeControlSet:
    """A bounded, context-matched set of candidates for later measurement."""

    target_element_id: str
    controls: tuple[NegativeControlCandidate, ...]
    matching_dimensions: tuple[str, ...]
    warnings: tuple[str, ...]
    source_id: str
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class NegativeControlBuilder:
    """Select matched controls without turning similarity into evidence."""

    def build(
        self,
        target: CandidateElement,
        pool: Iterable[CandidateElement],
        *,
        limit: int = 5,
        source_id: str = "validation-control-builder",
    ) -> NegativeControlSet:
        if limit < 1 or limit > 100:
            raise ValidationError("negative control limit must be between 1 and 100")
        candidates = [
            element
            for element in pool
            if element.element_id != target.element_id
            and element.context.key == target.context.key
            and element.element_type == target.element_type
            and not set(element.target_genes) & set(target.target_genes)
            and not set(element.state_ids) & set(target.state_ids)
        ]
        candidates.sort(key=lambda element: (self._distance(target, element), element.element_id))
        selected = candidates[:limit]
        matching_dimensions = (
            "genome_build",
            "disease_class",
            "age_group",
            "cell_state",
            "territory",
            "treatment_phase",
            "element_type",
            "feature_distance",
            "disjoint_targets",
        )
        warnings: list[str] = []
        if len(selected) < limit:
            warnings.append(
                f"Only {len(selected)} matched control candidates were available "
                f"for a limit of {limit}."
            )
        if not selected:
            warnings.append(
                "No matched control candidates were available; no negative "
                "measurement was inferred."
            )
        controls = tuple(
            NegativeControlCandidate(
                control_id="control-"
                + content_hash({"target": target.element_id, "element": element.element_id}).split(
                    ":", 1
                )[1][:20],
                element_id=element.element_id,
                target_element_id=target.element_id,
                context_key=element.context.key,
                distance=round(self._distance(target, element), 6),
                matching_dimensions=matching_dimensions,
                expected_state=EvidenceState.UNSUPPORTED,
                rationale=(
                    "Context- and feature-matched control candidate selected for a future assay; "
                    "selection is not a measured negative."
                ),
                limitations=(
                    "Callable status, batch balance, and assay measurement must be "
                    "confirmed separately.",
                    "Control selection does not establish absence of regulatory or "
                    "disease activity.",
                ),
            )
            for element in selected
        )
        payload = {
            "target_element_id": target.element_id,
            "controls": controls,
            "matching_dimensions": matching_dimensions,
            "warnings": tuple(warnings),
            "source_id": source_id,
        }
        return NegativeControlSet(
            target_element_id=target.element_id,
            controls=controls,
            matching_dimensions=matching_dimensions,
            warnings=tuple(warnings),
            source_id=source_id,
            content_address=content_hash(payload),
        )

    @staticmethod
    def _distance(left: CandidateElement, right: CandidateElement) -> float:
        feature_names = sorted(set(left.features) | set(right.features))
        if not feature_names:
            return 1.0
        return sum(
            abs(float(left.features.get(name, 0.0)) - float(right.features.get(name, 0.0)))
            for name in feature_names
        ) / len(feature_names)


@dataclass(frozen=True, slots=True)
class ValidationPriority:
    """One ranked validation action with transparent scoring terms."""

    option_id: str
    priority: float
    expected_information_gain: float
    uncertainty_weight: float
    feasibility: float
    cost_penalty: float
    blockers: tuple[str, ...]
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


@dataclass(frozen=True, slots=True)
class ValidationPrioritySet:
    """Ordered validation actions and the uncertainty state used to rank them."""

    priorities: tuple[ValidationPriority, ...]
    uncertainty_band: UncertaintyBand
    budget_class: str
    warnings: tuple[str, ...]
    content_address: str

    def to_dict(self) -> dict[str, Any]:
        return jsonable(self)


class ValidationValuePlanner:
    """Rank validation options without pretending priority is causal evidence."""

    _cost_penalties = {
        "low": 0.05,
        "medium": 0.20,
        "high": 0.45,
        "very_high": 0.70,
    }

    def rank(
        self,
        options: Iterable[ExperimentOption],
        uncertainty: UncertaintyReport,
        *,
        budget_class: str = "medium",
    ) -> ValidationPrioritySet:
        if budget_class not in self._cost_penalties:
            raise ValidationError("budget_class must be one of low, medium, high, or very_high")
        penalty = self._cost_penalties[budget_class]
        warnings: list[str] = []
        if uncertainty.band == UncertaintyBand.ABSTAIN:
            warnings.append(
                "Uncertainty is abstained; priorities are provisional until missing "
                "domain inputs are resolved."
            )
        priorities: list[ValidationPriority] = []
        uncertainty_weight = round(max(0.1, uncertainty.overall), 6)
        for option in options:
            blockers: list[str] = []
            if uncertainty.band == UncertaintyBand.ABSTAIN:
                blockers.append(
                    "resolve abstained uncertainty before treating priority as actionable"
                )
            priority = round(
                option.expected_information_gain
                * option.feasibility
                * uncertainty_weight
                * max(0.0, 1.0 - penalty),
                6,
            )
            priorities.append(
                ValidationPriority(
                    option_id=option.option_id,
                    priority=priority,
                    expected_information_gain=option.expected_information_gain,
                    uncertainty_weight=uncertainty_weight,
                    feasibility=option.feasibility,
                    cost_penalty=penalty,
                    blockers=tuple(blockers),
                    rationale=(
                        "Priority combines declared information gain, feasibility, unresolved "
                        "uncertainty, and the selected budget penalty; it is not effect evidence."
                    ),
                )
            )
        priorities.sort(key=lambda item: (-item.priority, item.option_id))
        if not priorities:
            warnings.append("No validation options were supplied.")
        payload = {
            "priorities": priorities,
            "uncertainty_band": uncertainty.band,
            "budget_class": budget_class,
            "warnings": tuple(warnings),
        }
        return ValidationPrioritySet(
            priorities=tuple(priorities),
            uncertainty_band=uncertainty.band,
            budget_class=budget_class,
            warnings=tuple(warnings),
            content_address=content_hash(payload),
        )

"""Validation route selection based on missing evidence and information gain."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from .errors import ValidationError
from .models import AssayType, EdgeType, ExperimentOption, Hypothesis, HypothesisEdge
from .serialization import canonical_bytes

MAX_EXPERIMENT_HYPOTHESES = 10_000
MAX_EXPERIMENT_EDGES_PER_HYPOTHESIS = 1_024
MAX_EXPERIMENT_TOTAL_EDGES = 20_000
_ABSTENTION_PATH_IDENTITY = ("unresolved", "unresolved_gene", "unresolved_state")


def _bounded_positive_integer(value: object, field_name: str, ceiling: int) -> int:
    if type(value) is not int:
        raise ValidationError(f"{field_name} must be an integer")
    if value < 1:
        raise ValidationError(f"{field_name} must be positive")
    if value > ceiling:
        raise ValidationError(f"{field_name} must not exceed the safety ceiling of {ceiling}")
    return value


@dataclass(frozen=True, slots=True)
class ExperimentPlanningLimits:
    """Hard-ceiling, downward-configurable limits for validation planning."""

    max_hypotheses: int = MAX_EXPERIMENT_HYPOTHESES
    max_edges_per_hypothesis: int = MAX_EXPERIMENT_EDGES_PER_HYPOTHESIS
    max_total_edges: int = MAX_EXPERIMENT_TOTAL_EDGES

    def __post_init__(self) -> None:
        for field_name, ceiling in (
            ("max_hypotheses", MAX_EXPERIMENT_HYPOTHESES),
            ("max_edges_per_hypothesis", MAX_EXPERIMENT_EDGES_PER_HYPOTHESIS),
            ("max_total_edges", MAX_EXPERIMENT_TOTAL_EDGES),
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_positive_integer(getattr(self, field_name), field_name, ceiling),
            )


DEFAULT_EXPERIMENT_PLANNING_LIMITS = ExperimentPlanningLimits()


class ExperimentPlanner:
    """Generate bounded assay options rather than an unqualified assay menu."""

    def __init__(self, *, limits: ExperimentPlanningLimits | None = None) -> None:
        selected = DEFAULT_EXPERIMENT_PLANNING_LIMITS if limits is None else limits
        if not isinstance(selected, ExperimentPlanningLimits):
            raise ValidationError("limits must be ExperimentPlanningLimits")
        self.limits = selected

    def plan(self, hypothesis: Hypothesis) -> tuple[ExperimentOption, ...]:
        edges = self._validated_edges(hypothesis)
        if len(edges) > self.limits.max_total_edges:
            raise ValidationError(
                "experiment planning exceeds the configured maximum of "
                f"{self.limits.max_total_edges} total edges"
            )
        return self._plan(hypothesis, edges)

    def _plan(
        self,
        hypothesis: Hypothesis,
        edges: tuple[HypothesisEdge, ...],
    ) -> tuple[ExperimentOption, ...]:
        options: list[ExperimentOption] = []
        edges_by_type = {
            edge_type: tuple(edge.edge_id for edge in edges if edge.edge_type is edge_type)
            for edge_type in EdgeType
        }
        missing = bool(hypothesis.missing_evidence)
        variant_to_element = edges_by_type[EdgeType.VARIANT_TO_ELEMENT]
        if variant_to_element:
            options.append(
                ExperimentOption(
                    option_id=f"{hypothesis.hypothesis_id}:mpra",
                    assay=AssayType.MPRA,
                    tests_edges=variant_to_element,
                    expected_information_gain=0.78 if missing else 0.54,
                    feasibility=0.72,
                    cost_class="medium",
                    required_context=self._required_context(
                        hypothesis.context.cell_state, hypothesis.context.disease_class
                    ),
                    controls=(
                        "reference_allele",
                        "alternate_allele",
                        "neutral_sequence",
                        "positive_control",
                    ),
                    readouts=("allele_specific_reporter_activity", "replicate_consistency"),
                    limitations=("episomal context may not recapitulate endogenous chromatin",),
                )
            )
        element_to_gene = edges_by_type[EdgeType.ELEMENT_TO_GENE]
        if element_to_gene:
            options.append(
                ExperimentOption(
                    option_id=f"{hypothesis.hypothesis_id}:crispri",
                    assay=AssayType.CRISPR_INTERFERENCE,
                    tests_edges=element_to_gene,
                    expected_information_gain=0.86 if missing else 0.62,
                    feasibility=0.58,
                    cost_class="high",
                    required_context=self._required_context(
                        hypothesis.context.cell_state, hypothesis.context.territory
                    ),
                    controls=("non_targeting_guide", "promoter_control", "multiple_guides"),
                    readouts=(
                        "target_gene_expression",
                        "state_marker_expression",
                        "cell_state_abundance",
                    ),
                    limitations=(
                        "guide efficiency and local chromatin accessibility can confound "
                        "interpretation",
                    ),
                )
            )
        causal_path = edges_by_type[EdgeType.CAUSAL_PATH]
        is_abstention_path = (
            hypothesis.element_id,
            hypothesis.gene_id,
            hypothesis.state_id,
        ) == _ABSTENTION_PATH_IDENTITY
        if causal_path and not is_abstention_path and hypothesis.uncertainty >= 0.35:
            options.append(
                ExperimentOption(
                    option_id=f"{hypothesis.hypothesis_id}:contact",
                    assay=AssayType.CONTACT_ASSAY,
                    tests_edges=causal_path,
                    expected_information_gain=0.69,
                    feasibility=0.46,
                    cost_class="high",
                    required_context=self._required_context(
                        hypothesis.context.cell_state, hypothesis.context.territory
                    ),
                    controls=(
                        "matched_unaffected_locus",
                        "resolution_control",
                        "biological_replicates",
                    ),
                    readouts=("allele_or_haplotype_contact", "boundary_integrity", "loop_support"),
                    limitations=(
                        "contact evidence alone does not establish regulatory directionality",
                    ),
                )
            )
        if not options:
            options.append(
                ExperimentOption(
                    option_id=f"{hypothesis.hypothesis_id}:review",
                    assay=AssayType.RNA_MEASUREMENT,
                    tests_edges=tuple(edge.edge_id for edge in edges),
                    expected_information_gain=0.31,
                    feasibility=0.88,
                    cost_class="low",
                    required_context=self._required_context(hypothesis.context.cell_state),
                    controls=("matched_context", "technical_replicates"),
                    readouts=("target_gene_expression",),
                    limitations=("correlation is not a causal test",),
                )
            )
        return tuple(sorted(options, key=lambda option: (-option.priority, option.option_id)))

    def plan_many(self, hypotheses: Iterable[Hypothesis]) -> tuple[ExperimentOption, ...]:
        if isinstance(hypotheses, (str, bytes, bytearray, Mapping)):
            raise ValidationError("hypotheses must be an iterable of Hypothesis objects")
        try:
            iterator = iter(hypotheses)
        except TypeError as error:
            raise ValidationError("hypotheses must be iterable") from error

        options: list[ExperimentOption] = []
        seen: dict[str, Hypothesis] = {}
        seen_edges: dict[str, HypothesisEdge] = {}
        total_edges = 0
        for index, hypothesis in enumerate(iterator):
            if index >= self.limits.max_hypotheses:
                raise ValidationError(
                    "hypotheses exceeds the configured maximum of "
                    f"{self.limits.max_hypotheses} items"
                )
            if not isinstance(hypothesis, Hypothesis):
                raise ValidationError("hypotheses must contain only Hypothesis objects")
            edges = self._validated_edges(hypothesis)
            previous = seen.get(hypothesis.hypothesis_id)
            if previous is not None:
                if canonical_bytes(previous.to_dict()) != canonical_bytes(
                    hypothesis.to_dict()
                ):
                    raise ValidationError(
                        f"hypothesis_id collision has different content: {hypothesis.hypothesis_id}"
                    )
                raise ValidationError(f"duplicate hypothesis_id: {hypothesis.hypothesis_id}")
            seen[hypothesis.hypothesis_id] = hypothesis
            for edge in edges:
                previous_edge = seen_edges.get(edge.edge_id)
                if previous_edge is not None and canonical_bytes(
                    previous_edge.to_dict()
                ) != canonical_bytes(edge.to_dict()):
                    raise ValidationError(
                        f"edge_id collision has different content: {edge.edge_id}"
                    )
                seen_edges[edge.edge_id] = edge
            if len(edges) > self.limits.max_total_edges - total_edges:
                raise ValidationError(
                    "experiment planning exceeds the configured maximum of "
                    f"{self.limits.max_total_edges} total edges"
                )
            total_edges += len(edges)
            options.extend(self._plan(hypothesis, edges))
        return tuple(sorted(options, key=lambda option: (-option.priority, option.option_id)))

    def _validated_edges(self, hypothesis: Hypothesis) -> tuple[HypothesisEdge, ...]:
        if not isinstance(hypothesis, Hypothesis):
            raise ValidationError("hypothesis must be a Hypothesis")
        edges = hypothesis.edges
        if len(edges) > self.limits.max_edges_per_hypothesis:
            raise ValidationError(
                f"hypothesis {hypothesis.hypothesis_id} edges exceeds the configured maximum of "
                f"{self.limits.max_edges_per_hypothesis} items"
            )
        if any(not isinstance(edge, HypothesisEdge) for edge in edges):
            raise ValidationError("hypothesis edges must contain only HypothesisEdge objects")
        if any(not isinstance(edge.edge_type, EdgeType) for edge in edges):
            raise ValidationError("hypothesis edge_type must be an EdgeType")
        return tuple(sorted(edges, key=lambda edge: edge.edge_id))

    @staticmethod
    def _required_context(*values: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(values))

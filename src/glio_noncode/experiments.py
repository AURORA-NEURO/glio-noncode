"""Validation route selection based on missing evidence and information gain."""

from __future__ import annotations

from typing import Iterable

from .models import AssayType, ExperimentOption, Hypothesis


class ExperimentPlanner:
    """Generate bounded assay options rather than an unqualified assay menu."""

    def plan(self, hypothesis: Hypothesis) -> tuple[ExperimentOption, ...]:
        options: list[ExperimentOption] = []
        edges = tuple(edge.edge_id for edge in hypothesis.edges)
        missing = set(hypothesis.missing_evidence)
        if any("variant_to_element" in edge for edge in edges):
            options.append(
                ExperimentOption(
                    option_id=f"{hypothesis.hypothesis_id}:mpra",
                    assay=AssayType.MPRA,
                    tests_edges=tuple(edge for edge in edges if "variant_to_element" in edge),
                    expected_information_gain=0.78 if missing else 0.54,
                    feasibility=0.72,
                    cost_class="medium",
                    required_context=(hypothesis.context.cell_state, hypothesis.context.disease_class),
                    controls=("reference_allele", "alternate_allele", "neutral_sequence", "positive_control"),
                    readouts=("allele_specific_reporter_activity", "replicate_consistency"),
                    limitations=("episomal context may not recapitulate endogenous chromatin",),
                )
            )
        if any("element_to_gene" in edge for edge in edges):
            options.append(
                ExperimentOption(
                    option_id=f"{hypothesis.hypothesis_id}:crispri",
                    assay=AssayType.CRISPR_INTERFERENCE,
                    tests_edges=tuple(edge for edge in edges if "element_to_gene" in edge),
                    expected_information_gain=0.86 if missing else 0.62,
                    feasibility=0.58,
                    cost_class="high",
                    required_context=(hypothesis.context.cell_state, hypothesis.context.territory),
                    controls=("non_targeting_guide", "promoter_control", "multiple_guides"),
                    readouts=("target_gene_expression", "state_marker_expression", "cell_state_abundance"),
                    limitations=("guide efficiency and local chromatin accessibility can confound interpretation",),
                )
            )
        if any("causal_path" in edge for edge in edges) and hypothesis.uncertainty >= 0.35:
            options.append(
                ExperimentOption(
                    option_id=f"{hypothesis.hypothesis_id}:contact",
                    assay=AssayType.CONTACT_ASSAY,
                    tests_edges=tuple(edge for edge in edges if "causal_path" in edge),
                    expected_information_gain=0.69,
                    feasibility=0.46,
                    cost_class="high",
                    required_context=(hypothesis.context.cell_state, hypothesis.context.territory),
                    controls=("matched_unaffected_locus", "resolution_control", "biological_replicates"),
                    readouts=("allele_or_haplotype_contact", "boundary_integrity", "loop_support"),
                    limitations=("contact evidence alone does not establish regulatory directionality",),
                )
            )
        if not options:
            options.append(
                ExperimentOption(
                    option_id=f"{hypothesis.hypothesis_id}:review",
                    assay=AssayType.RNA_MEASUREMENT,
                    tests_edges=edges,
                    expected_information_gain=0.31,
                    feasibility=0.88,
                    cost_class="low",
                    required_context=(hypothesis.context.cell_state,),
                    controls=("matched_context", "technical_replicates"),
                    readouts=("target_gene_expression",),
                    limitations=("correlation is not a causal test",),
                )
            )
        return tuple(sorted(options, key=lambda option: (-option.priority, option.option_id)))

    def plan_many(self, hypotheses: Iterable[Hypothesis]) -> tuple[ExperimentOption, ...]:
        options: list[ExperimentOption] = []
        for hypothesis in hypotheses:
            options.extend(self.plan(hypothesis))
        return tuple(sorted(options, key=lambda option: (-option.priority, option.option_id)))

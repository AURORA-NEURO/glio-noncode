from __future__ import annotations

import json
import unittest

from glio_noncode.causal_beta import (
    CausalBetaState,
    CausalEvidenceDirection,
    CausalMediatorEvidenceParser,
    CounterfactualAlleleStateObservation,
    CounterfactualAlleleStateSimulator,
    ElementToGeneCausalMediator,
    GeneToStateCausalMediator,
    MediatorKind,
    SequenceToElementCausalMediator,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"
OTHER_CONTEXT = "GRCh38|glioma|adult|differentiated|core|unknown"


def evidence(
    evidence_id: str,
    source_id: str,
    *,
    kind: str = "sequence_to_element",
    source_node: str = "variant:v1",
    target_node: str = "element:enh-1",
    context_key: str = CONTEXT,
    support: float = 0.8,
    uncertainty: float = 0.1,
    direction: str = "supports",
    sensitivity: float | None = 0.7,
    negative_control: bool = False,
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "mediator_kind": kind,
        "source_node": source_node,
        "target_node": target_node,
        "context_key": context_key,
        "support": support,
        "uncertainty": uncertainty,
        "source_id": source_id,
        "source_version": "v1",
        "direction": direction,
        "sensitivity": sensitivity,
        "negative_control": negative_control,
    }


class CausalBetaTests(unittest.TestCase):
    def test_parser_retains_valid_evidence_and_quarantines_bad_rows(self) -> None:
        batch = CausalMediatorEvidenceParser().parse_text(
            json.dumps(
                {
                    "evidence": [
                        evidence("e-1", "atlas-a"),
                        {"evidence_id": "bad", "support": "not-a-number"},
                    ]
                }
            ),
            source_id="causal-atlas",
            source_version="2026.1",
        )
        self.assertEqual(len(batch.evidence), 1)
        self.assertEqual(batch.evidence[0].source_id, "causal-atlas")
        self.assertEqual(batch.evidence[0].source_version, "v1")
        self.assertEqual(batch.issues[0].code, "invalid_causal_evidence_row")
        self.assertTrue(batch.input_hash)
        self.assertTrue(batch.content_address)

    def test_sequence_to_element_requires_independent_sources_and_retains_sensitivity(self) -> None:
        result = SequenceToElementCausalMediator().evaluate(
            (evidence("e-1", "atlas-a"), evidence("e-2", "atlas-b", support=0.6, sensitivity=0.5)),
            source_node="variant:v1",
            target_node="element:enh-1",
            context_key=CONTEXT,
            model_id="seq-element-beta",
            model_version="1",
        )
        self.assertEqual(result.state, CausalBetaState.SUPPORTED)
        self.assertAlmostEqual(result.support, 0.7, places=6)
        self.assertAlmostEqual(result.sensitivity, 0.6, places=6)
        self.assertEqual(result.evidence_ids, ("e-1", "e-2"))
        self.assertEqual(set(result.source_ids), {"atlas-a", "atlas-b"})
        self.assertIn("not a causal probability", " ".join(result.warnings))

    def test_single_source_is_partial_and_context_mismatch_is_out_of_domain(self) -> None:
        partial = SequenceToElementCausalMediator().evaluate(
            (evidence("e-1", "atlas-a"),),
            source_node="variant:v1",
            target_node="element:enh-1",
            context_key=CONTEXT,
            model_id="seq-element-beta",
            model_version="1",
        )
        self.assertEqual(partial.state, CausalBetaState.PARTIAL)
        self.assertGreater(partial.uncertainty, 0.2)
        out_of_domain = SequenceToElementCausalMediator().evaluate(
            (evidence("e-other", "atlas-a", context_key=OTHER_CONTEXT),),
            source_node="variant:v1",
            target_node="element:enh-1",
            context_key=CONTEXT,
            model_id="seq-element-beta",
            model_version="1",
        )
        self.assertEqual(out_of_domain.state, CausalBetaState.OUT_OF_DOMAIN)
        self.assertIsNone(out_of_domain.support)

    def test_mediator_wrappers_keep_declared_mediator_kind(self) -> None:
        element_gene = ElementToGeneCausalMediator().evaluate(
            (
                evidence(
                    "eg-1",
                    "contact-atlas",
                    kind="element_to_gene",
                    source_node="element:enh-1",
                    target_node="gene:GENE1",
                ),
            ),
            source_node="element:enh-1",
            target_node="gene:GENE1",
            context_key=CONTEXT,
            model_id="element-gene-beta",
            model_version="1",
        )
        gene_state = GeneToStateCausalMediator().evaluate(
            (
                evidence(
                    "gs-1",
                    "state-atlas",
                    kind="gene_to_state",
                    source_node="gene:GENE1",
                    target_node="state:stem_like",
                ),
            ),
            source_node="gene:GENE1",
            target_node="state:stem_like",
            context_key=CONTEXT,
            model_id="gene-state-beta",
            model_version="1",
        )
        self.assertEqual(element_gene.mediator_kind, MediatorKind.ELEMENT_TO_GENE)
        self.assertEqual(gene_state.mediator_kind, MediatorKind.GENE_TO_STATE)
        self.assertEqual(element_gene.state, CausalBetaState.PARTIAL)

    def test_against_direction_makes_the_mediator_contradictory(self) -> None:
        result = SequenceToElementCausalMediator().evaluate(
            (
                evidence("support", "atlas-a"),
                evidence(
                    "against",
                    "atlas-b",
                    support=0.7,
                    direction=CausalEvidenceDirection.AGAINST.value,
                ),
            ),
            source_node="variant:v1",
            target_node="element:enh-1",
            context_key=CONTEXT,
            model_id="seq-element-beta",
            model_version="1",
        )
        self.assertEqual(result.state, CausalBetaState.CONTRADICTORY)
        self.assertIsNone(result.support)
        self.assertEqual(result.negative_evidence_ids, ("against",))

    def test_counterfactual_simulator_reports_reference_alternate_delta(self) -> None:
        observations = (
            CounterfactualAlleleStateObservation(
                "ref-1", "reference", "state:open", 0.2, 0.1, CONTEXT, "assay-a", "v1", "raw-ref"
            ),
            CounterfactualAlleleStateObservation(
                "alt-1", "alternate", "state:open", 0.8, 0.1, CONTEXT, "assay-a", "v1", "raw-alt"
            ),
        )
        result = CounterfactualAlleleStateSimulator().simulate(
            observations,
            state_id="state:open",
            context_key=CONTEXT,
            model_id="allele-state-beta",
            model_version="1",
        )
        self.assertEqual(result.state, CausalBetaState.SUPPORTED)
        self.assertAlmostEqual(result.reference_value, 0.2)
        self.assertAlmostEqual(result.alternate_value, 0.8)
        self.assertAlmostEqual(result.delta_alternate_minus_reference, 0.6)
        self.assertAlmostEqual(result.sensitivity, 0.6)
        self.assertIn("not proof of causality", " ".join(result.warnings))

    def test_counterfactual_simulator_handles_partial_and_ambiguous_replicates(self) -> None:
        partial = CounterfactualAlleleStateSimulator().simulate(
            (
                {
                    "observation_id": "ref-only",
                    "allele": "reference",
                    "state_id": "state:open",
                    "value": 0.2,
                    "uncertainty": 0.1,
                    "context_key": CONTEXT,
                    "source_id": "assay-a",
                    "source_version": "v1",
                },
            ),
            state_id="state:open",
            context_key=CONTEXT,
            model_id="allele-state-beta",
            model_version="1",
        )
        self.assertEqual(partial.state, CausalBetaState.PARTIAL)
        self.assertIsNone(partial.delta_alternate_minus_reference)
        ambiguous = CounterfactualAlleleStateSimulator().simulate(
            (
                {
                    "observation_id": "ref-a",
                    "allele": "reference",
                    "state_id": "state:open",
                    "value": 0.1,
                    "uncertainty": 0.1,
                    "context_key": CONTEXT,
                    "source_id": "assay-a",
                    "source_version": "v1",
                },
                {
                    "observation_id": "ref-b",
                    "allele": "reference",
                    "state_id": "state:open",
                    "value": 0.8,
                    "uncertainty": 0.1,
                    "context_key": CONTEXT,
                    "source_id": "assay-b",
                    "source_version": "v1",
                },
                {
                    "observation_id": "alt-a",
                    "allele": "alternate",
                    "state_id": "state:open",
                    "value": 0.9,
                    "uncertainty": 0.1,
                    "context_key": CONTEXT,
                    "source_id": "assay-a",
                    "source_version": "v1",
                },
            ),
            state_id="state:open",
            context_key=CONTEXT,
            model_id="allele-state-beta",
            model_version="1",
            ambiguity_tolerance=0.2,
        )
        self.assertEqual(ambiguous.state, CausalBetaState.AMBIGUOUS)
        self.assertAlmostEqual(ambiguous.delta_alternate_minus_reference, 0.45)


if __name__ == "__main__":
    unittest.main()

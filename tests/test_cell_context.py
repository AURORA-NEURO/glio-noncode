from __future__ import annotations

import unittest

from glio_noncode.cell_context import (
    AdultPediatricRouter,
    CellStateContextAssembler,
    ContextDimension,
    ContextObservationParser,
    ContextResolutionState,
    DiseaseOntologyContextualizer,
    MalignantMicroenvironmentTerritoryResolver,
    MolecularClassStateContextualizer,
)
from glio_noncode.models import ReferenceContext


class CellContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ReferenceContext(
            "GRCh38", "glioma", "adult", "stem_like", territory="core"
        )
        self.other_context = ReferenceContext(
            "GRCh38", "glioma", "pediatric", "stem_like", territory="core"
        )

    def _parse(self, text: str):
        return ContextObservationParser().parse_text(text, source_id="context-atlas")

    def test_parser_preserves_receipts_and_quarantines_invalid_rows(self) -> None:
        text = (
            "subject_id\tdimension\tcandidate_id\tcandidate_label\tcontext_key\tconfidence\n"
            f"case-1\tdisease_ontology\tMONDO:001\tglioma\t{self.context.key}\t0.9\n"
            f"case-1\tbad_dimension\tMONDO:002\tbad\t{self.context.key}\t0.8\n"
        )
        batch = self._parse(text)
        self.assertEqual(len(batch.observations), 1)
        self.assertEqual(batch.observations[0].dimension, ContextDimension.DISEASE_ONTOLOGY)
        self.assertEqual(batch.observations[0].subject_id, "case-1")
        self.assertEqual(batch.observations[0].confidence, 0.9)
        self.assertEqual(len(batch.issues), 1)
        self.assertTrue(batch.observations[0].raw_hash.startswith("sha256:"))
        self.assertTrue(batch.content_address.startswith("sha256:"))

    def test_disease_resolution_is_exact_context_and_subject_gated(self) -> None:
        text = (
            "subject_id\tdimension\tcandidate_id\tcandidate_label\tcontext_key\tconfidence\n"
            f"case-1\tdisease_ontology\tMONDO:001\tDiffuse glioma\t{self.context.key}\t0.9\n"
            f"case-2\tdisease_ontology\tMONDO:999\tOther glioma\t{self.context.key}\t0.9\n"
            f"case-1\tdisease_ontology\tMONDO:002\tPediatric glioma\t"
            f"{self.other_context.key}\t0.9\n"
        )
        result = DiseaseOntologyContextualizer().resolve(
            self.context, self._parse(text).observations, subject_id="case-1"
        )
        self.assertEqual(result.state, ContextResolutionState.SUPPORTED)
        self.assertEqual(result.selected_candidate_id, "MONDO:001")
        self.assertEqual(result.evidence_ids, ("context-atlas:2",))
        self.assertEqual(result.source_ids, ("context-atlas",))

        out_of_domain = DiseaseOntologyContextualizer().resolve(
            self.other_context,
            self._parse(text).observations,
            subject_id="case-2",
        )
        self.assertEqual(out_of_domain.state, ContextResolutionState.OUT_OF_DOMAIN)
        self.assertIsNone(out_of_domain.selected_candidate_id)

    def test_adult_pediatric_router_abstains_on_unknown_and_detects_conflict(self) -> None:
        unknown = ReferenceContext("GRCh38", "glioma", "unknown", "stem_like")
        unknown_result = AdultPediatricRouter().route(unknown, subject_id="case-1")
        self.assertEqual(unknown_result.state, ContextResolutionState.ABSTAINED)

        text = (
            "subject_id\tdimension\tcandidate_id\tcandidate_label\tcontext_key\n"
            f"case-1\tage_route\tpediatric\tpediatric\t{self.context.key}\n"
        )
        conflict = AdultPediatricRouter().route(
            self.context, self._parse(text).observations, subject_id="case-1"
        )
        self.assertEqual(conflict.state, ContextResolutionState.CONTRADICTORY)
        self.assertIsNone(conflict.selected_candidate_id)

    def test_molecular_resolution_keeps_class_and_state_separate(self) -> None:
        text = (
            "subject_id\tdimension\tcandidate_id\tcandidate_label\tcontext_key\tconfidence\n"
            f"case-1\tmolecular_class\tIDH_mutant\tIDH-mutant\t{self.context.key}\t0.8\n"
            f"case-1\tmolecular_state\tproneural\tproneural\t{self.context.key}\t0.7\n"
        )
        result = MolecularClassStateContextualizer().resolve(
            self.context, self._parse(text).observations, subject_id="case-1"
        )
        self.assertEqual(result.state, ContextResolutionState.SUPPORTED)
        self.assertEqual(result.molecular_class.selected_candidate_id, "IDH_mutant")
        self.assertEqual(result.molecular_state.selected_candidate_id, "proneural")
        self.assertGreater(result.uncertainty, 0.0)

        missing = MolecularClassStateContextualizer().resolve(
            self.context,
            self._parse(text.replace("molecular_state", "other_dimension")).observations,
            subject_id="case-1",
        )
        self.assertEqual(missing.state, ContextResolutionState.ABSTAINED)

    def test_territory_resolver_exposes_one_to_many_mapping(self) -> None:
        text = (
            "subject_id\tdimension\tcandidate_id\tcandidate_label\tcontext_key\n"
            f"case-1\tterritory\tmalignant_core\tmalignant core\t{self.context.key}\n"
            f"case-1\tterritory\timmune_edge\timmune edge\t{self.context.key}\n"
        )
        result = MalignantMicroenvironmentTerritoryResolver().resolve(
            self.context, self._parse(text).observations, subject_id="case-1"
        )
        self.assertEqual(result.state, ContextResolutionState.AMBIGUOUS)
        self.assertIsNone(result.selected_candidate_id)
        self.assertEqual(len(result.candidates), 2)

    def test_assembler_propagates_ambiguity_into_glioma_state_context(self) -> None:
        text = (
            "subject_id\tdimension\tcandidate_id\tcandidate_label\tcontext_key\n"
            f"case-1\tdisease_ontology\tMONDO:001\tglioma\t{self.context.key}\n"
            f"case-1\tterritory\tcore\tcore\t{self.context.key}\n"
            f"case-1\tterritory\timmune_edge\timmune edge\t{self.context.key}\n"
            f"case-1\tmolecular_class\tIDH_mutant\tIDH-mutant\t{self.context.key}\n"
            f"case-1\tmolecular_state\tproneural\tproneural\t{self.context.key}\n"
        )
        observations = self._parse(text).observations
        disease = DiseaseOntologyContextualizer().resolve(
            self.context, observations, subject_id="case-1"
        )
        age = AdultPediatricRouter().route(self.context, subject_id="case-1")
        molecular = MolecularClassStateContextualizer().resolve(
            self.context, observations, subject_id="case-1"
        )
        territory = MalignantMicroenvironmentTerritoryResolver().resolve(
            self.context, observations, subject_id="case-1"
        )
        self.assertEqual(territory.state, ContextResolutionState.AMBIGUOUS)
        assembled = CellStateContextAssembler().assemble(
            "case-1", self.context, disease, age, molecular, territory
        )
        self.assertEqual(assembled.state, ContextResolutionState.AMBIGUOUS)
        self.assertEqual(assembled.subject_id, "case-1")
        self.assertTrue(assembled.content_address.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()

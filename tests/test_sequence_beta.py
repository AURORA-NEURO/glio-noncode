from __future__ import annotations

import unittest

from glio_noncode.sequence_beta import (
    CooperativeTFGrammarModel,
    GrammarInteraction,
    MotifCreationScanner,
    MotifDefinition,
    MotifDisruptionScanner,
    MotifGrammarRule,
    MotifSpacingGrammarAnalyzer,
    SequenceBetaState,
)


class SequenceBetaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gata = MotifDefinition(
            motif_id="TF:GATA",
            name="GATA factor",
            consensus="GATA",
            source_id="motif-catalog",
            source_version="2026.1",
            strand_aware=False,
        )
        self.acgt = MotifDefinition(
            motif_id="TF:ACGT",
            name="ACGT factor",
            consensus="ACGT",
            source_id="motif-catalog",
            source_version="2026.1",
            strand_aware=False,
        )

    def test_disruption_and_creation_retain_reference_and_alternate_evidence(self) -> None:
        disrupted = MotifDisruptionScanner().scan(
            "TTTGATACCC",
            "TTTGGACCC",
            variant_id="var-1",
            motifs=(self.gata, self.acgt),
            window_start=101,
            context_key="GRCh38|glioma|adult|stem_like|unknown|unknown",
        )
        self.assertEqual(disrupted.state, SequenceBetaState.SUPPORTED)
        self.assertEqual(disrupted.context_key, "GRCh38|glioma|adult|stem_like|unknown|unknown")
        self.assertEqual(
            [(hit.motif_id, hit.start, hit.end) for hit in disrupted.disrupted_hits],
            [("TF:GATA", 104, 107)],
        )
        self.assertEqual(disrupted.created_hits, ())
        self.assertEqual(disrupted.retained_hit_count, 0)
        self.assertEqual(disrupted.source_versions, ("2026.1",))

        created = MotifCreationScanner().scan(
            "TTTGGACCC",
            "TTTGATACCC",
            variant_id="var-1",
            motifs=(self.gata,),
        )
        self.assertEqual(created.disrupted_hits, ())
        self.assertEqual(
            [(hit.motif_id, hit.start) for hit in created.created_hits], [("TF:GATA", 4)]
        )

    def test_iupac_and_reverse_strand_matching_are_declared(self) -> None:
        motif = MotifDefinition(
            motif_id="TF:RY",
            name="ambiguity motif",
            consensus="RY",
            source_id="motif-catalog",
            source_version="2026.1",
            threshold=1.0,
            strand_aware=True,
        )
        report = MotifDisruptionScanner().scan(
            "TTACGGTT",
            "TTACGGTT",
            variant_id="var-2",
            motifs=(motif,),
        )
        self.assertEqual(report.state, SequenceBetaState.SUPPORTED)
        self.assertTrue(any(hit.strand == "-" for hit in report.reference_hits))
        self.assertTrue(any(hit.strand == "+" for hit in report.reference_hits))

    def test_invalid_window_and_empty_motif_catalog_are_explicit(self) -> None:
        invalid = MotifDisruptionScanner().scan(
            "TTGZ",
            "TTGA",
            variant_id="var-invalid",
            motifs=(self.gata,),
        )
        self.assertEqual(invalid.state, SequenceBetaState.PARTIAL)
        self.assertEqual(invalid.issues[0].code, "invalid_sequence_alphabet")

        abstained = MotifDisruptionScanner().scan(
            "TTGA",
            "TTGA",
            variant_id="var-empty",
            motifs=(),
        )
        self.assertEqual(abstained.state, SequenceBetaState.ABSTAINED)
        self.assertEqual(abstained.reference_hits, ())

    def test_spacing_analyzer_retains_all_compatible_pairs_and_unmatched_rules(self) -> None:
        scan = MotifDisruptionScanner().scan(
            "GATATTTACGT",
            "GATATTTACGT",
            variant_id="var-3",
            motifs=(self.gata, self.acgt),
        )
        report = MotifSpacingGrammarAnalyzer().analyze(
            scan.reference_hits,
            (
                MotifGrammarRule(
                    rule_id="grammar-1",
                    motif_a="TF:GATA",
                    motif_b="TF:ACGT",
                    minimum_spacing=3,
                    maximum_spacing=3,
                    allowed_orientations=("same",),
                ),
            ),
            context_key="GRCh38|glioma|adult|stem_like|unknown|unknown",
        )
        self.assertEqual(report.state, SequenceBetaState.SUPPORTED)
        self.assertEqual(len(report.observations), 1)
        self.assertEqual(report.observations[0].spacing, 3)

        unmatched = MotifSpacingGrammarAnalyzer().analyze(
            scan.reference_hits,
            (
                MotifGrammarRule(
                    rule_id="grammar-missing",
                    motif_a="TF:GATA",
                    motif_b="TF:ACGT",
                    minimum_spacing=10,
                    maximum_spacing=20,
                ),
            ),
        )
        self.assertEqual(unmatched.state, SequenceBetaState.ABSTAINED)
        self.assertEqual(unmatched.unmatched_rule_ids, ("grammar-missing",))

    def test_cooperative_model_is_versioned_and_not_a_probability(self) -> None:
        scan = MotifDisruptionScanner().scan(
            "GATATTTACGT",
            "GATATTTACGT",
            variant_id="var-4",
            motifs=(self.gata, self.acgt),
        )
        model = CooperativeTFGrammarModel()
        result = model.score(
            scan.reference_hits,
            (
                GrammarInteraction(
                    interaction_id="co-op-1",
                    motif_a="TF:GATA",
                    motif_b="TF:ACGT",
                    weight=1.5,
                    maximum_spacing=3,
                    required=True,
                    source_version="2026.1",
                ),
            ),
            sequence_id="window-4",
            sequence="GATATTTACGT",
            model_id="declared-grammar",
            model_version="2026.1",
        )
        self.assertEqual(result.state, SequenceBetaState.SUPPORTED)
        self.assertEqual(result.score, 1.5)
        self.assertEqual(result.interaction_contributions, {"co-op-1": 1.5})
        self.assertIn("not a probability", " ".join(result.warnings))

        missing = model.score(
            scan.reference_hits[:1],
            (
                GrammarInteraction(
                    interaction_id="co-op-required",
                    motif_a="TF:GATA",
                    motif_b="TF:ACGT",
                    weight=2.0,
                    maximum_spacing=3,
                    required=True,
                ),
            ),
            sequence_id="window-4",
            sequence="GATATTTACGT",
            model_id="declared-grammar",
            model_version="2026.1",
        )
        self.assertEqual(missing.state, SequenceBetaState.ABSTAINED)
        self.assertEqual(missing.missing_required_interactions, ("co-op-required",))


if __name__ == "__main__":
    unittest.main()

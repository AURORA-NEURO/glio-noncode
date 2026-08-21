from __future__ import annotations

import unittest

from glio_noncode.variant_beta import (
    AnnotationEvidenceLine,
    AnnotationState,
    AnnotationStatement,
    BetaState,
    CategoricalCatalogParser,
    CatVRSNormalizer,
    MultiAllelicDecomposer,
    RepeatAwareNormalizer,
)


class VariantBetaTests(unittest.TestCase):
    def test_categorical_catalog_quarantines_bad_rows_and_matches_declared_ids(self) -> None:
        catalog = (
            "category_id\tlabel\tdefinition\tmembers\taliases\trules\n"
            "CAT-PROMOTER\tpromoter\tdeclared promoter\tvar-1,var-2\tregulatory_promoter\t"
            '{"membership":"declared"}\n'
            "CAT-BAD\t\t\t\t\t\n"
        )
        batch = CategoricalCatalogParser().parse_text(
            catalog,
            source_id="catalog",
            source_version="2026.1",
            input_format="tsv",
        )
        self.assertEqual(batch.state, BetaState.PARTIAL)
        self.assertEqual(len(batch.definitions), 1)
        self.assertEqual(batch.definitions[0].rules["membership"], "declared")

        matched = CatVRSNormalizer(batch.definitions).normalize({"id": "var-2"})
        self.assertEqual(matched.state, BetaState.SUPPORTED)
        self.assertEqual(matched.selected_category_id, "CAT-PROMOTER")
        self.assertIn("declared_member_variation_id", matched.candidates[0].match_basis)

        abstained = CatVRSNormalizer(batch.definitions).normalize({"label": "promoter-like"})
        self.assertEqual(abstained.state, BetaState.ABSTAINED)
        self.assertEqual(abstained.selected_category_id, None)

    def test_categorical_alias_collision_is_explicitly_ambiguous(self) -> None:
        source = [
            {
                "category_id": "CAT-1",
                "label": "one",
                "definition": "one",
                "aliases": ["shared"],
                "rules": {"declared": True},
                "source_id": "catalog",
                "source_version": "1",
            },
            {
                "category_id": "CAT-2",
                "label": "two",
                "definition": "two",
                "aliases": ["shared"],
                "rules": {"declared": True},
                "source_id": "catalog",
                "source_version": "1",
            },
        ]
        report = CatVRSNormalizer(
            CategoricalCatalogParser()
            .parse_json(__import__("json").dumps(source), source_id="catalog")
            .definitions
        ).normalize({"label": "shared"})
        self.assertEqual(report.state, BetaState.AMBIGUOUS)
        self.assertIsNone(report.selected_category_id)
        self.assertEqual(len(report.candidates), 2)

    def test_annotation_envelope_preserves_evidence_and_detects_conflict(self) -> None:
        evidence = (
            AnnotationEvidenceLine(
                evidence_id="e1",
                evidence_type="publication",
                source_id="pmid:1",
                source_version="2026",
                raw_hash="a" * 64,
                state=AnnotationState.SUPPORTED,
                summary="first source",
            ),
            AnnotationEvidenceLine(
                evidence_id="e2",
                evidence_type="assay",
                source_id="assay:1",
                source_version="run-1",
                raw_hash="b" * 64,
                state=AnnotationState.SUPPORTED,
                summary="second source",
            ),
        )
        statements = (
            AnnotationStatement(
                statement_id="s1",
                subject_id="vrs:1",
                predicate="regulatory_effect",
                object_value="activating",
                object_type="controlled_term",
                context_key="GRCh38|glioma|adult|unknown|unknown|unknown",
                state=AnnotationState.SUPPORTED,
                evidence_ids=("e1",),
                source_ids=(),
                method_id="method:a",
                summary="first interpretation",
            ),
            AnnotationStatement(
                statement_id="s2",
                subject_id="vrs:1",
                predicate="regulatory_effect",
                object_value="repressive",
                object_type="controlled_term",
                context_key="GRCh38|glioma|adult|unknown|unknown|unknown",
                state=AnnotationState.SUPPORTED,
                evidence_ids=("e2",),
                source_ids=(),
                method_id="method:b",
                summary="second interpretation",
            ),
        )
        from glio_noncode.variant_beta import VAAnnotationEnvelopeBuilder

        envelope = VAAnnotationEnvelopeBuilder().build(
            "annotation-1",
            {"id": "vrs:1", "type": "Allele"},
            statements,
            evidence,
            context_key="GRCh38|glioma|adult|unknown|unknown|unknown",
        )
        self.assertEqual(envelope.state, AnnotationState.CONTRADICTORY)
        self.assertEqual(len(envelope.evidence_lines), 2)
        self.assertEqual(envelope.va_spec_object["type"], "Statement")
        self.assertTrue(any("without averaging" in warning for warning in envelope.warnings))

    def test_annotation_subject_mismatch_is_out_of_domain(self) -> None:
        statement = AnnotationStatement(
            statement_id="s1",
            subject_id="vrs:other",
            predicate="effect",
            object_value="unknown",
            object_type="term",
            context_key="ctx",
            state=AnnotationState.PARTIAL,
            evidence_ids=(),
            source_ids=(),
            method_id="method",
            summary="not resolved",
        )
        from glio_noncode.variant_beta import VAAnnotationEnvelopeBuilder

        envelope = VAAnnotationEnvelopeBuilder().build(
            "annotation-2",
            {"id": "vrs:subject"},
            (statement,),
            context_key="ctx",
        )
        self.assertEqual(envelope.state, AnnotationState.OUT_OF_DOMAIN)

    def test_multiallelic_decomposition_preserves_parent_and_projects_genotype(self) -> None:
        result = MultiAllelicDecomposer().decompose(
            {
                "variant_id": "parent-1",
                "chrom": "7",
                "pos": 100,
                "ref": "A",
                "alt": "T,C",
                "genotype": "1/2",
                "origin": "somatic",
            },
            source_id="vcf",
            source_version="run-7",
        )
        self.assertEqual(result.state, BetaState.SUPPORTED)
        self.assertEqual(len(result.children), 2)
        self.assertEqual({child.allele_index for child in result.children}, {1, 2})
        self.assertTrue(
            all(child.parent_raw_hash == result.input_hash for child in result.children)
        )
        self.assertEqual(result.children[0].genotype_projection.target_copy_count, 1)
        self.assertEqual(result.children[0].genotype_projection.other_alt_indices, (2,))
        self.assertEqual(result.children[1].genotype_projection.other_alt_indices, (1,))

    def test_multiallelic_missing_genotype_is_partial_and_structural_alt_abstains(self) -> None:
        partial = MultiAllelicDecomposer().decompose(
            {"chrom": "7", "pos": 100, "ref": "A", "alt": "T,C", "genotype": "./1"}
        )
        self.assertEqual(partial.state, BetaState.PARTIAL)
        self.assertTrue(
            any(issue.code == "genotype_projection_abstained" for issue in partial.issues)
        )

        structural = MultiAllelicDecomposer().decompose(
            {"chrom": "7", "pos": 100, "ref": "A", "alt": "<DEL>"}
        )
        self.assertEqual(structural.state, BetaState.ABSTAINED)
        self.assertEqual(structural.children, ())

    def test_repeat_normalization_reports_equivalent_homopolymer_placements(self) -> None:
        result = RepeatAwareNormalizer().normalize(
            {"variant_id": "ins-1", "chrom": "1", "pos": 102, "ref": "A", "alt": "AA"},
            reference_sequence="AAAAAA",
            reference_start=100,
            max_shift_bp=50,
        )
        self.assertEqual(result.state.value, "ambiguous")
        self.assertGreater(len(result.placements), 1)
        self.assertIn(-2, {placement.shift_from_input for placement in result.placements})
        self.assertIsNone(result.selected_placement)

    def test_repeat_normalization_abstains_on_reference_mismatch(self) -> None:
        result = RepeatAwareNormalizer().normalize(
            {"variant_id": "snv-1", "chrom": "1", "pos": 102, "ref": "C", "alt": "T"},
            reference_sequence="AAAAAA",
            reference_start=100,
        )
        self.assertEqual(result.state.value, "abstained")
        self.assertEqual(result.issues[0].code, "reference_mismatch")

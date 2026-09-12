from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from glio_noncode.errors import ValidationError
from glio_noncode.expression_claims import RNA_CONSEQUENCE_CHANNEL
from glio_noncode.expression_evidence import (
    AllelicDirection,
    ExpressionDirection,
    RegulatoryDirection,
    RNAConsequenceEvidence,
    RNAEvidenceState,
)
from glio_noncode.hypotheses import BuiltHypotheses, HypothesisBuilder
from glio_noncode.models import EdgeType, EvidenceState, HypothesisEdge
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import canonical_bytes, content_hash
from glio_noncode.validation import ContractValidator

from .helpers import fixture_manifest


def consequence(
    *,
    prediction_id: str = "prediction:runtime:rna-a",
    feature_id: str | None = None,
    variant_id: str | None = None,
    context_key: str | None = None,
    state: RNAEvidenceState = RNAEvidenceState.SUPPORTED,
) -> RNAConsequenceEvidence:
    manifest = fixture_manifest()
    selected_feature = feature_id or manifest.candidate_elements[0].target_genes[0]
    selected_variant = variant_id or manifest.variants[0].variant_id
    selected_context = context_key or manifest.context.key
    expression_state = state
    expression_direction = ExpressionDirection.UP
    expression_z = 7.0
    allelic_state = state
    allelic_direction = AllelicDirection.ALT_ENRICHED
    allelic_ratio = 2.0
    allelic_q = 0.001
    if state is RNAEvidenceState.OUT_OF_DOMAIN:
        expression_direction = ExpressionDirection.UNKNOWN
        expression_z = None
        allelic_direction = AllelicDirection.UNKNOWN
        allelic_ratio = None
        allelic_q = None
    return RNAConsequenceEvidence(
        prediction_id=prediction_id,
        prediction_address=content_hash(
            {"prediction_id": prediction_id},
            prefix="regulatory-effect-prediction",
        ),
        variant_id=selected_variant,
        feature_id=selected_feature,
        context_key=selected_context,
        predicted_direction=RegulatoryDirection.GAIN,
        state=state,
        expression_state=expression_state,
        expression_direction=expression_direction,
        expression_robust_z=expression_z,
        expression_result_address=content_hash(
            {"prediction_id": prediction_id, "component": "expression"},
            prefix="expression-outlier",
        ),
        allelic_state=allelic_state,
        allelic_direction=allelic_direction,
        allelic_log2_ratio=allelic_ratio,
        allelic_q_value=allelic_q,
        allelic_result_address=content_hash(
            {"prediction_id": prediction_id, "component": "allelic"},
            prefix="allelic-imbalance",
        ),
        reason_codes=(f"runtime_fixture_{state.value}",),
    )


def edge_for(
    built: BuiltHypotheses,
    edge_type: EdgeType,
    *,
    target_id: str | None = None,
) -> HypothesisEdge:
    return next(
        edge
        for edge in built.hypotheses[0].edges
        if edge.edge_type is edge_type and (target_id is None or edge.target_id == target_id)
    )


class ExpressionHypothesisIntegrationTests(unittest.TestCase):
    def test_matched_claim_changes_only_exact_gene_edge_and_causal_path(self) -> None:
        manifest = fixture_manifest()
        gene_id = manifest.candidate_elements[0].target_genes[0]
        other_gene_id = manifest.candidate_elements[0].target_genes[1]
        baseline = HypothesisBuilder().build(manifest, "run-rna-integration")
        augmented = HypothesisBuilder().build(
            manifest,
            "run-rna-integration",
            rna_consequences=(consequence(),),
        )

        rna_claim = next(
            claim for claim in augmented.claims if claim.channel == RNA_CONSEQUENCE_CHANNEL
        )
        baseline_gene = edge_for(baseline, EdgeType.ELEMENT_TO_GENE, target_id=gene_id)
        augmented_gene = edge_for(augmented, EdgeType.ELEMENT_TO_GENE, target_id=gene_id)
        untouched_gene = edge_for(
            augmented,
            EdgeType.ELEMENT_TO_GENE,
            target_id=other_gene_id,
        )
        baseline_untouched_gene = edge_for(
            baseline,
            EdgeType.ELEMENT_TO_GENE,
            target_id=other_gene_id,
        )
        baseline_path = edge_for(baseline, EdgeType.CAUSAL_PATH)
        augmented_path = edge_for(augmented, EdgeType.CAUSAL_PATH)
        path_claim = next(
            claim for claim in augmented.claims if claim.edge_id == augmented_path.edge_id
        )

        self.assertEqual(rna_claim.edge_id, augmented_gene.edge_id)
        self.assertIn(rna_claim.evidence_id, augmented_gene.claim_ids)
        self.assertNotIn(rna_claim.evidence_id, untouched_gene.claim_ids)
        self.assertGreater(augmented_gene.support, baseline_gene.support)
        self.assertEqual(untouched_gene.support, baseline_untouched_gene.support)
        self.assertIn(rna_claim.evidence_id, path_claim.depends_on)
        self.assertGreater(augmented_path.support, baseline_path.support)
        self.assertEqual(augmented.hypotheses[0].support, augmented_path.support)

    def test_unmatched_evidence_is_reported_without_attaching_a_claim(self) -> None:
        manifest = fixture_manifest()
        baseline = HypothesisBuilder().build(manifest, "run-rna-mismatch")
        mismatched = HypothesisBuilder().build(
            manifest,
            "run-rna-mismatch",
            rna_consequences=(consequence(variant_id="variant:not-in-case"),),
        )

        self.assertFalse(
            any(claim.channel == RNA_CONSEQUENCE_CHANNEL for claim in mismatched.claims)
        )
        self.assertTrue(any("did not match" in warning for warning in mismatched.warnings))
        self.assertEqual(
            tuple(edge.support for edge in mismatched.hypotheses[0].edges),
            tuple(edge.support for edge in baseline.hypotheses[0].edges),
        )

    def test_out_of_domain_claim_is_missing_evidence_not_positive_support(self) -> None:
        manifest = fixture_manifest()
        gene_id = manifest.candidate_elements[0].target_genes[0]
        baseline = HypothesisBuilder().build(manifest, "run-rna-out-of-domain")
        guarded = HypothesisBuilder().build(
            manifest,
            "run-rna-out-of-domain",
            rna_consequences=(consequence(state=RNAEvidenceState.OUT_OF_DOMAIN),),
        )

        rna_claim = next(
            claim for claim in guarded.claims if claim.channel == RNA_CONSEQUENCE_CHANNEL
        )
        baseline_gene = edge_for(baseline, EdgeType.ELEMENT_TO_GENE, target_id=gene_id)
        guarded_gene = edge_for(guarded, EdgeType.ELEMENT_TO_GENE, target_id=gene_id)
        self.assertEqual(rna_claim.state, EvidenceState.OUT_OF_DOMAIN)
        self.assertIsNone(rna_claim.score)
        self.assertEqual(guarded_gene.support, baseline_gene.support)
        self.assertIn(rna_claim.evidence_id, guarded_gene.claim_ids)
        self.assertIn(rna_claim.evidence_id, guarded.hypotheses[0].missing_evidence)

    def test_invalid_consequence_blocks_runtime_without_persisting_a_run(self) -> None:
        manifest = fixture_manifest()
        invalid = replace(
            consequence(),
            expression_state=None,
            expression_direction=None,
            expression_robust_z=None,
            expression_result_address=None,
            allelic_state=None,
            allelic_direction=None,
            allelic_log2_ratio=None,
            allelic_q_value=None,
            allelic_result_address=None,
        )
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            run_id = runtime._run_id(manifest, (invalid,))
            with self.assertRaisesRegex(ValidationError, "no measured RNA component"):
                runtime.evaluate(manifest, rna_consequences=(invalid,))
            self.assertFalse((Path(directory) / "runs" / f"{run_id}.json").exists())

    def test_default_and_explicit_empty_evaluations_are_exactly_equal(self) -> None:
        manifest = fixture_manifest()
        fixed = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
        with (
            tempfile.TemporaryDirectory() as first_directory,
            tempfile.TemporaryDirectory() as second_directory,
            patch("glio_noncode.models.utc_now", return_value=fixed),
            patch("glio_noncode.events.utc_now", return_value=fixed),
            patch("glio_noncode.runtime.utc_now", return_value=fixed),
        ):
            implicit = CaseRuntime(first_directory).evaluate(manifest)
            explicit = CaseRuntime(second_directory).evaluate(
                manifest,
                rna_consequences=(),
            )
        self.assertEqual(implicit, explicit)


class ExpressionRuntimeIdentityTests(unittest.TestCase):
    def test_rna_inputs_are_order_independent_and_change_run_identity(self) -> None:
        manifest = fixture_manifest()
        first = consequence(prediction_id="prediction:runtime:first")
        second = consequence(
            prediction_id="prediction:runtime:second",
            feature_id=manifest.candidate_elements[0].target_genes[1],
        )
        legacy_payload = {
            "input": manifest.content_address,
            "requested_by": manifest.requested_by,
        }
        legacy_run_id = "run-" + content_hash(legacy_payload).split(":", 1)[1][:24]

        self.assertEqual(CaseRuntime._run_id(manifest), legacy_run_id)
        self.assertEqual(CaseRuntime._run_id(manifest, ()), legacy_run_id)
        self.assertNotEqual(
            CaseRuntime._run_id(manifest, (first,)),
            CaseRuntime._run_id(manifest, (second,)),
        )
        self.assertEqual(
            CaseRuntime._run_id(manifest, (first, second)),
            CaseRuntime._run_id(manifest, (second, first)),
        )

    def test_runtime_records_replayable_rna_batch_but_keeps_manifest_input(self) -> None:
        manifest = fixture_manifest()
        rna = consequence()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(manifest, rna_consequences=(rna,))
            run = runtime.get_run(dossier.run_id)
            event_record = runtime.store.store.get(run["event_address"])
            received = event_record["events"][0]["payload"]

            self.assertEqual(run["input_address"], manifest.content_address)
            self.assertEqual(received["rna_consequence_count"], 1)
            rna_batch = runtime.store.store.get(received["rna_input_address"])
            self.assertEqual(rna_batch["kind"], "rna_consequence_batch")
            self.assertEqual(rna_batch["consequences"], [rna.to_dict()])
            self.assertIn(received["rna_input_address"], dossier.source_bundle_addresses)
            rna_claim = next(
                claim for claim in dossier.evidence if claim.channel == RNA_CONSEQUENCE_CHANNEL
            )
            self.assertEqual(rna_claim.depends_on, (received["rna_input_address"],))
            self.assertEqual(
                rna_claim.payload["retained_owner_address"],
                received["rna_input_address"],
            )

    def test_rna_only_source_closure_budget_fails_before_publication(self) -> None:
        manifest = fixture_manifest()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, source_closure_max_bytes=1)
            with self.assertRaisesRegex(ValidationError, "aggregate canonical byte ceiling"):
                runtime.evaluate(manifest, rna_consequences=(consequence(),))
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_rna_byte_budget_stops_generator_progressively(self) -> None:
        manifest = fixture_manifest()
        consumed = 0

        def rows():
            nonlocal consumed
            for index in range(100):
                consumed += 1
                yield consequence(
                    prediction_id=f"prediction:runtime:progressive-{index:03d}",
                )

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory, rna_input_max_bytes=1)
            with self.assertRaisesRegex(
                ValidationError,
                "RNA input exceeds the configured persisted byte ceiling",
            ):
                runtime.evaluate(manifest, rna_consequences=rows())
            self.assertEqual(consumed, 1)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

    def test_rna_source_object_obeys_validator_byte_ceiling_on_write_and_reopen(self) -> None:
        manifest = fixture_manifest()
        rows = tuple(
            consequence(
                prediction_id=f"prediction:runtime:bounded-{index:03d}",
                feature_id=f"unmatched-feature-{index:03d}",
            )
            for index in range(100)
        )
        rna_record = {
            "schema_version": "1.0.0",
            "kind": "rna_consequence_batch",
            "consequences": [
                row.to_dict() for row in sorted(rows, key=lambda item: item.content_address)
            ],
        }
        object_ceiling = len(canonical_bytes(rna_record)) - 1
        self.assertGreater(object_ceiling, len(canonical_bytes(manifest.to_dict())))

        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            runtime.validator = ContractValidator(
                limits=replace(
                    runtime.validator.limits,
                    max_canonical_bytes=object_ceiling,
                )
            )
            with self.assertRaisesRegex(
                ValidationError,
                "RNA input exceeds the configured persisted byte ceiling",
            ):
                runtime.evaluate(manifest, rna_consequences=rows)
            self.assertEqual(tuple(runtime.store.store.objects.glob("*.json")), ())
            self.assertEqual(tuple(runtime.store.runs.glob("*.json")), ())

        with tempfile.TemporaryDirectory() as directory:
            writer = CaseRuntime(directory)
            dossier = writer.evaluate(manifest, rna_consequences=rows)
            run = writer.get_run(dossier.run_id)
            for field in ("input_address", "event_address", "dossier_address"):
                self.assertLessEqual(
                    len(canonical_bytes(writer.store.store.get(run[field]))),
                    object_ceiling,
                )
            reader = CaseRuntime(directory)
            reader.validator = ContractValidator(
                limits=replace(
                    reader.validator.limits,
                    max_canonical_bytes=object_ceiling,
                )
            )
            with self.assertRaisesRegex(
                ValidationError,
                "persisted RNA input object exceeds its configured byte ceiling",
            ):
                reader.load_run_snapshot(dossier.run_id)


if __name__ == "__main__":
    unittest.main()

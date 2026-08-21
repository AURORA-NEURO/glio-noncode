from __future__ import annotations

import unittest

from glio_noncode.frontier_data_alpha import (
    AnnotationDriftDetector,
    AssayLineageProtocolTracker,
    BiospecimenPreanalyticQualityAssessor,
    BreakpointUncertaintyPropagator,
    CompoundHaplotypeEvaluator,
    ConsentPolicyAttacher,
    DataCompletenessScorer,
    FrontierState,
    IdentityConflictAdjudicator,
    InputAnomalyQuarantine,
    IntakeBundleExporter,
    ReferenceReleaseGate,
    ReproducibleReferenceBundleBuilder,
    SourceProvenanceChecker,
    SpecimenContextEnvelopePublisher,
    StructuralVariantEvidenceExporter,
    TandemRepeatInterpreter,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierDataAlphaTests(unittest.TestCase):
    def test_consent_and_anomaly_paths_preserve_blocked_records(self) -> None:
        consent = ConsentPolicyAttacher().attach(
            [
                {"record_id": "v-1", "context_key": CONTEXT, "consent_status": "granted"},
                {"record_id": "v-2", "context_key": CONTEXT, "consent_status": "withdrawn"},
            ],
            context_key=CONTEXT,
            policy_id="policy-1",
            policy_version="2026-08",
            purpose="research",
            permitted_uses=("nonclinical", "reproducibility"),
            source_id="consent-registry",
        )
        self.assertEqual(consent.accepted_record_ids, ("v-1",))
        self.assertEqual(consent.blocked_record_ids, ("v-2",))
        anomalies = InputAnomalyQuarantine().inspect(
            [
                {
                    "record_id": "v-1",
                    "context_key": CONTEXT,
                    "chromosome": "chr7",
                    "position": 100,
                    "sequence": "ACGT",
                },
                {
                    "record_id": "v-1",
                    "context_key": CONTEXT,
                    "chromosome": "chr7",
                    "position": 100,
                    "sequence": "ACGX",
                },
            ],
            context_key=CONTEXT,
            source_id="intake",
        )
        self.assertEqual(anomalies.accepted_record_ids, ("v-1",))
        self.assertEqual(anomalies.quarantined_record_ids, ("v-1",))
        self.assertIn("duplicate_record_id", anomalies.observations[1].anomaly_codes)

    def test_completeness_and_content_addressed_bundle(self) -> None:
        report = DataCompletenessScorer().score(
            [
                {
                    "record_id": "r-1",
                    "context_key": CONTEXT,
                    "chromosome": "chr7",
                    "position": 100,
                    "sequence": "ACGT",
                },
                {"record_id": "r-2", "context_key": CONTEXT, "chromosome": "chr7"},
            ],
            context_key=CONTEXT,
            required_fields=("chromosome", "position", "sequence"),
            source_id="source-a",
        )
        self.assertEqual(report.accepted_record_ids, ("r-1",))
        self.assertIn("sequence", report.scores[1].missing_fields)
        bundle = IntakeBundleExporter().export(
            [
                {
                    "record_id": "r-1",
                    "context_key": CONTEXT,
                    "state": "accepted",
                    "source_id": "source-a",
                }
            ],
            bundle_id="bundle-1",
            context_key=CONTEXT,
        )
        self.assertEqual(bundle.record_count, 1)
        self.assertTrue(bundle.content_address.startswith("sha256:"))

    def test_structural_repeat_haplotype_and_breakpoint_receipts(self) -> None:
        repeats = TandemRepeatInterpreter().interpret(
            [
                {
                    "repeat_id": "rep-1",
                    "chromosome": "chr9",
                    "start": 10,
                    "end": 30,
                    "motif": "CAG",
                    "reference_units": 4,
                    "observed_units": 7,
                    "uncertainty_units": 1,
                }
            ],
            context_key=CONTEXT,
            source_id="repeat-caller",
        )
        self.assertEqual(repeats.expanded_ids, ("rep-1",))
        haplotypes = CompoundHaplotypeEvaluator().evaluate(
            [
                {
                    "haplotype_id": "hap-1",
                    "variant_ids": ["v1", "v2"],
                    "observed_variant_ids": ["v1"],
                    "phase_state": "unknown",
                }
            ],
            context_key=CONTEXT,
            minimum_completeness=0.5,
        )
        self.assertEqual(haplotypes.compatible_ids, ("hap-1",))
        breakpoints = BreakpointUncertaintyPropagator().propagate(
            [
                {
                    "breakpoint_id": "bp-1",
                    "chromosome": "chr12",
                    "left_min": 100,
                    "left_max": 105,
                    "right_min": 900,
                    "right_max": 910,
                    "confidence": 0.9,
                }
            ],
            context_key=CONTEXT,
            source_id="sv-caller",
        )
        self.assertEqual(breakpoints.intervals[0].propagated_uncertainty_bp, 15)
        evidence = StructuralVariantEvidenceExporter().export(
            [
                {
                    "variant_id": "sv-1",
                    "evidence_type": "split_read",
                    "source_id": "sv-caller",
                    "context_key": CONTEXT,
                }
            ],
            bundle_id="sv-bundle",
            context_key=CONTEXT,
        )
        self.assertEqual(evidence.state, FrontierState.PUBLISHED)

    def test_specimen_quality_lineage_identity_and_publisher(self) -> None:
        quality = BiospecimenPreanalyticQualityAssessor().assess(
            [
                {
                    "specimen_id": "sp-1",
                    "ischemia_minutes": 15,
                    "storage_temperature_c": -80,
                    "rna_integrity": 0.9,
                }
            ],
            context_key=CONTEXT,
            source_id="qc",
        )
        self.assertEqual(quality.pass_ids, ("sp-1",))
        lineage = AssayLineageProtocolTracker().track(
            [
                {
                    "node_id": "n-1",
                    "specimen_id": "sp-1",
                    "protocol_id": "p-1",
                    "assay": "ATAC-seq",
                    "operator_id": "operator-1",
                    "started_at": "2026-08-20T10:00:00Z",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(lineage.root_ids, ("n-1",))
        identity = IdentityConflictAdjudicator().adjudicate(
            [{"specimen_id": "sp-1", "observed_identities": ["case-1", "case-1", "case-2"]}],
            context_key=CONTEXT,
        )
        self.assertEqual(identity.review_ids, ("sp-1",))
        envelope = SpecimenContextEnvelopePublisher().publish(
            envelope_id="env-1",
            context_key=CONTEXT,
            specimen_ids=("sp-1",),
            lineage_address="sha256:lineage",
            quality_address=quality.content_address,
            identity_address=identity.content_address,
        )
        self.assertEqual(envelope.state, FrontierState.PUBLISHED)

    def test_reference_provenance_drift_bundle_and_release_gate(self) -> None:
        provenance = SourceProvenanceChecker().check(
            [
                {
                    "source_id": "ref-1",
                    "source_uri": "https://example.test/ref",
                    "declared_checksum": "sha256:a",
                    "observed_checksum": "sha256:a",
                    "license_id": "research",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(provenance.compatible_ids, ("ref-1",))
        drift = AnnotationDriftDetector().compare(
            [{"annotation_id": "a-1", "label": "enhancer", "retrieved_at": "old"}],
            [{"annotation_id": "a-1", "label": "promoter", "retrieved_at": "new"}],
            context_key=CONTEXT,
        )
        self.assertEqual(drift.drifted_ids, ("a-1",))
        bundle = ReproducibleReferenceBundleBuilder().build(
            [{"reference_id": "ref-1", "context_key": CONTEXT, "status": "available"}],
            bundle_id="ref-bundle",
            context_key=CONTEXT,
            schema_hash="sha256:schema",
        )
        decision = ReferenceReleaseGate().evaluate(
            release_id="release-1",
            context_key=CONTEXT,
            bundle_address=bundle.bundle_address,
            checks={
                "checksum": True,
                "schema": True,
                "license": True,
                "context": True,
                "source": True,
            },
        )
        self.assertEqual(decision.state, FrontierState.PUBLISHED)


if __name__ == "__main__":
    unittest.main()

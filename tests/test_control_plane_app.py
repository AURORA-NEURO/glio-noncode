from __future__ import annotations

import unittest
from dataclasses import replace
from tempfile import TemporaryDirectory

from glio_noncode.atlas import PublicAtlasRetriever
from glio_noncode.causal import CausalLattice
from glio_noncode.cohort import CohortObservation, RecurrenceModel
from glio_noncode.control_plane import (
    ClaimCeiling,
    InvocationRequest,
    InvocationState,
    MissionContext,
    ProvenanceContext,
)
from glio_noncode.control_plane_app import ControlPlaneApplication
from glio_noncode.data_sources import FetchReceipt, FetchStatus, ReferenceBundle, SequenceSlice
from glio_noncode.models import (
    EdgeType,
    EvidenceClaim,
    EvidenceState,
    EvidenceTier,
    HypothesisEdge,
    ReferenceContext,
    SupportLevel,
)
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import content_hash

from .helpers import fixture_manifest


def _request(
    tool_id: str,
    payload: dict[str, object],
    request_id: str,
    *,
    release: bool = False,
    allow_network: bool = False,
    allowed_source_ids: tuple[str, ...] = (),
) -> InvocationRequest:
    mission = MissionContext(
        mission_id="mission-app-test",
        project_id="project-app-test",
        intended_use="research-only control-plane integration",
        requested_question="Which bounded workflow should run?",
        claim_ceiling=(ClaimCeiling.RESEARCH_RELEASE if release else ClaimCeiling.HYPOTHESIS),
        allow_network=allow_network,
        allowed_source_ids=allowed_source_ids,
    )
    return InvocationRequest(
        request_id=request_id,
        mission=mission,
        agent_id=tool_id.split(".")[0],
        tool_id=tool_id,
        input_payload=payload,
        provenance=ProvenanceContext(("sha256:input",), reference_build="GRCh38"),
        idempotency_key=f"idem-{request_id}",
    )


def _receipt(source_id: str, suffix: str) -> FetchReceipt:
    return FetchReceipt(
        source_id=source_id,
        source_version="fixture-1",
        url=f"https://{source_id.lower()}.example/{suffix}",
        request_hash=f"sha256:req-{suffix}",
        response_hash=f"sha256:resp-{suffix}",
        status=FetchStatus.FETCHED,
        http_status=200,
        attempts=1,
        retrieved_at="2026-08-20T00:00:00+00:00",
        elapsed_seconds=0.01,
        cache_expires_at=None,
    )


class StubReferenceRetriever:
    def retrieve(self, variant, context, *, window_bp=None):
        sequence = SequenceSlice(
            assembly=context.genome_build,
            chromosome=variant.chromosome,
            start=variant.start,
            end=variant.start + 3,
            sequence="ACGT",
            source_id="SRC-UCSC-REST",
            receipt=_receipt("SRC-UCSC-REST", "sequence"),
        )
        return ReferenceBundle(
            variant_id=variant.variant_id,
            context_key=context.key,
            sequence=sequence,
            elements=(),
            raw_features=({"feature_type": "gene", "id": "ENSG000001"},),
            receipts=(sequence.receipt, _receipt("SRC-ENSEMBL-REST", "overlap")),
            warnings=(),
            content_address=content_hash({"variant_id": variant.variant_id}),
        )


class ControlPlaneApplicationTests(unittest.TestCase):
    def test_core_bindings_execute_real_intake_and_identity_handlers(self) -> None:
        app = ControlPlaneApplication()
        self.assertEqual(app.manifest()["binding_count"], 12)
        vcf = "\n".join(
            (
                "##fileformat=VCFv4.3",
                "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
                "7\t100\tv1\tA\tT\t.\tPASS\t.",
            )
        )
        intake = app.executor.execute(
            _request(
                "A07.publish",
                {"text": vcf, "source_id": "control-plane-vcf", "input_format": "vcf"},
                "intake-1",
            )
        )
        self.assertEqual(intake.state, InvocationState.COMPLETED)
        self.assertEqual(intake.response.state.value, "supported")
        identity = app.executor.execute(
            _request(
                "A08.publish",
                {"notation": "7:100:A>T", "variant_id": "v1"},
                "identity-1",
            )
        )
        self.assertEqual(identity.state, InvocationState.COMPLETED)
        self.assertEqual(identity.response.state.value, "supported")

    def test_power_drift_and_human_review_bindings_are_typed(self) -> None:
        app = ControlPlaneApplication()
        power = app.executor.execute(
            _request("A41.publish", {"effect_size": 0.2, "target_power": 0.8}, "power-1")
        )
        self.assertEqual(power.state, InvocationState.COMPLETED)
        drift = app.executor.execute(
            _request(
                "A47.publish",
                {
                    "baseline": {"unsupported_claim_fraction": 0.1},
                    "current": {"unsupported_claim_fraction": 0.8},
                },
                "drift-1",
            )
        )
        self.assertEqual(drift.state, InvocationState.COMPLETED)
        review = app.executor.execute(_request("A45.publish", {}, "review-1", release=True))
        self.assertEqual(review.state, InvocationState.ABSTAINED)
        self.assertEqual(review.response.reason_code, "human_adjudication_required")

    def test_atlas_binding_requires_network_boundary_and_returns_reference_envelope(self) -> None:
        blocked = ControlPlaneApplication().executor.execute(
            _request(
                "A15.publish",
                {
                    "notation": "7:100:A>T",
                    "context": {
                        "genome_build": "GRCh38",
                        "disease_class": "glioma",
                        "age_group": "adult",
                        "cell_state": "stem_like",
                    },
                },
                "atlas-blocked",
            )
        )
        self.assertEqual(blocked.state, InvocationState.ABSTAINED)
        self.assertEqual(blocked.response.reason_code, "network_not_enabled")

        app = ControlPlaneApplication(
            atlas_retriever=PublicAtlasRetriever(StubReferenceRetriever())
        )
        allowed = app.executor.execute(
            _request(
                "A15.publish",
                {
                    "notation": "7:100:A>T",
                    "context": {
                        "genome_build": "GRCh38",
                        "disease_class": "glioma",
                        "age_group": "adult",
                        "cell_state": "stem_like",
                    },
                    "query": {"window_bp": 25},
                },
                "atlas-allowed",
                allow_network=True,
                allowed_source_ids=("SRC-ENSEMBL-REST", "SRC-UCSC-REST"),
            )
        )
        self.assertEqual(allowed.state, InvocationState.COMPLETED)
        self.assertEqual(allowed.response.state, EvidenceState.SUPPORTED)
        self.assertIn("SRC-UCSC-REST", allowed.response.source_ids)

    def test_sequence_and_uncertainty_bindings_preserve_typed_boundaries(self) -> None:
        app = ControlPlaneApplication()
        sequence_payload = {
            "notation": "7:100:A>T",
            "sequence": {
                "assembly": "GRCh38",
                "chromosome": "chr7",
                "start": 100,
                "end": 103,
                "sequence": "ACGT",
                "source_id": "SRC-UCSC-REST",
                "receipt": _receipt("SRC-UCSC-REST", "sequence").to_dict(),
            },
            "motifs": [{"motif_id": "m1", "label": "AC motif", "pattern": "AC"}],
        }
        sequence = app.executor.execute(_request("A23.publish", sequence_payload, "sequence-1"))
        self.assertEqual(sequence.state, InvocationState.COMPLETED)
        self.assertEqual(sequence.response.state, EvidenceState.SUPPORTED)
        self.assertIn("disrupted", sequence.response.claim_summary)

        context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")
        claim = EvidenceClaim(
            evidence_id="claim-1",
            edge_id="edge-1",
            source_id="sequence-fixture",
            channel="motif_delta",
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.COMPUTED,
            score=None,
            confidence=0.8,
            context=context,
            summary="bounded sequence observation",
        )
        uncertainty = app.executor.execute(
            _request("A36.publish", {"claims": [claim.to_dict()]}, "uncertainty-1")
        )
        self.assertEqual(uncertainty.state, InvocationState.COMPLETED)
        self.assertEqual(uncertainty.response.state, EvidenceState.SUPPORTED)
        self.assertIn("uncertainty aggregation", uncertainty.response.claim_summary.lower())

    def test_cohort_and_causal_bindings_preserve_denominators_and_weakest_edges(self) -> None:
        app = ControlPlaneApplication()
        context = ReferenceContext("GRCh38", "diffuse_glioma", "adult", "stem_like")
        rows = [
            CohortObservation(
                observation_id=f"obs-{index}",
                subject_id=f"subject-{index}",
                locus_id="locus-a" if index < 2 else f"locus-{index}",
                mutated=index < 2,
                callable=True,
                mutability_score=0.4 + index * 0.01,
                chromatin_score=0.6,
                ancestry_group="group-a",
                disease_class="diffuse_glioma",
                context=context,
            )
            for index in range(6)
        ]
        recurrence = app.executor.execute(
            _request(
                "A32.publish",
                {
                    "locus_id": "locus-a",
                    "source_id": "fixture-cohort",
                    "observations": [
                        {
                            "observation_id": row.observation_id,
                            "subject_id": row.subject_id,
                            "locus_id": row.locus_id,
                            "mutated": row.mutated,
                            "callable": row.callable,
                            "mutability_score": row.mutability_score,
                            "chromatin_score": row.chromatin_score,
                            "ancestry_group": row.ancestry_group,
                            "disease_class": row.disease_class,
                            "context": row.context.to_dict(),
                        }
                        for row in rows
                    ],
                },
                "cohort-1",
            )
        )
        expected = RecurrenceModel().evaluate(rows, "locus-a")
        self.assertEqual(recurrence.state, InvocationState.COMPLETED)
        self.assertIn(str(expected.callable_count), recurrence.response.claim_summary)

        edges = (
            HypothesisEdge(
                "e1",
                EdgeType.VARIANT_TO_ELEMENT,
                "variant",
                "element",
                0.8,
                0.2,
                1.0,
                ("claim-1",),
                SupportLevel.HIGH,
            ),
            HypothesisEdge(
                "e2",
                EdgeType.ELEMENT_TO_GENE,
                "element",
                "gene",
                0.25,
                0.7,
                0.8,
                ("claim-2",),
                SupportLevel.LOW,
            ),
        )
        causal = app.executor.execute(
            _request(
                "A34.publish",
                {
                    "path_id": "path-1",
                    "edges": [edge.to_dict() for edge in edges],
                    "alternatives": ["alternative-gene"],
                },
                "causal-1",
            )
        )
        expected_path = CausalLattice().summarize(
            "path-1", edges, alternatives=("alternative-gene",)
        )
        self.assertEqual(causal.state, InvocationState.COMPLETED)
        self.assertIn(expected_path.weakest_edge_id, causal.response.claim_summary)

    def test_lifecycle_binding_returns_plan_without_adjudicating(self) -> None:
        with TemporaryDirectory() as directory:
            previous = CaseRuntime(directory).evaluate(fixture_manifest())
        changed = replace(
            previous,
            dossier_id=previous.dossier_id + "-next",
            evidence=(replace(previous.evidence[0], state=EvidenceState.CONTRADICTORY),)
            + previous.evidence[1:],
        )
        result = ControlPlaneApplication().executor.execute(
            _request(
                "A46.publish",
                {
                    "previous": previous.to_dict(),
                    "current": changed.to_dict(),
                    "source_version_before": "source-1",
                    "source_version_after": "source-2",
                    "reason": "public reference source release changed",
                },
                "reclass-1",
                release=True,
            )
        )
        self.assertEqual(result.state, InvocationState.COMPLETED)
        self.assertEqual(result.review_route.required, True)
        self.assertIn("reclassification", result.response.evidence_id)


if __name__ == "__main__":
    unittest.main()

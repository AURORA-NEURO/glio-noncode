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
    CandidateElement,
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
from glio_noncode.uncertainty import UncertaintyPropagator

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
        self.assertEqual(app.manifest()["binding_count"], 48)
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

    def test_data_plane_bindings_preserve_projection_structure_lineage_origin_and_qc(self) -> None:
        app = ControlPlaneApplication()
        context = {
            "genome_build": "GRCh38",
            "disease_class": "glioma",
            "age_group": "adult",
            "cell_state": "stem_like",
        }
        projection = app.executor.execute(
            _request(
                "A09.publish",
                {"notation": "7:100:A>T", "target_build": "GRCh38"},
                "projection-1",
            )
        )
        self.assertEqual(projection.state, InvocationState.COMPLETED)
        self.assertIn("identity", projection.response.claim_summary)

        pangenome = app.executor.execute(
            _request(
                "A11.publish",
                {
                    "notation": "7:100:A>T",
                    "target_builds": ["GRCh38", "GRCh37"],
                },
                "pangenome-1",
            )
        )
        self.assertEqual(pangenome.state, InvocationState.COMPLETED)
        self.assertIn("target assemblies", pangenome.response.claim_summary)

        structural = app.executor.execute(
            _request(
                "A10.publish",
                {
                    "context": context,
                    "source_id": "fixture-sv",
                    "records": [
                        {
                            "record_id": "sv1",
                            "chromosome": "7",
                            "position": 100,
                            "reference": "N",
                            "alternate": "<DEL>",
                            "info": {"END": "120"},
                        }
                    ],
                },
                "structural-1",
            )
        )
        self.assertEqual(structural.state, InvocationState.COMPLETED)
        self.assertIn("1 events", structural.response.claim_summary)

        lineage = app.executor.execute(
            _request(
                "A12.publish",
                {
                    "records": [
                        {
                            "sample_id": "normal-1",
                            "parent_sample_ids": [],
                            "relationship": "normal",
                            "timepoint": "baseline",
                        },
                        {
                            "sample_id": "tumor-1",
                            "parent_sample_ids": ["normal-1"],
                            "relationship": "tumor",
                            "timepoint": "baseline",
                        },
                    ]
                },
                "lineage-1",
            )
        )
        self.assertEqual(lineage.state, InvocationState.COMPLETED)
        self.assertIn("2 records", lineage.response.claim_summary)

        origin = app.executor.execute(
            _request(
                "A13.publish",
                {
                    "variant_id": "v1",
                    "observations": [
                        {
                            "observation_id": "obs-1",
                            "variant_id": "v1",
                            "sample_id": "tumor-1",
                            "relationship": "tumor",
                            "alternate_fraction": 0.42,
                            "present_in_normal": False,
                            "timepoint": "baseline",
                        }
                    ],
                },
                "origin-1",
            )
        )
        self.assertEqual(origin.state, InvocationState.COMPLETED)
        self.assertIn("somatic", origin.response.claim_summary)

        qc = app.executor.execute(
            _request(
                "A14.publish",
                {
                    "observations": [
                        {
                            "assay_id": "assay-1",
                            "sample_id": "tumor-1",
                            "assay_type": "atac",
                            "usable_reads": 200000,
                            "mapping_rate": 0.95,
                            "replicate_correlation": 0.90,
                            "contamination_rate": 0.01,
                            "controls_passed": True,
                        }
                    ]
                },
                "qc-1",
            )
        )
        self.assertEqual(qc.state, InvocationState.COMPLETED)
        self.assertIn("pass=1", qc.response.claim_summary)

        security = app.executor.execute(
            _request(
                "A48.publish",
                {
                    "project_id": "project-app-test",
                    "artifact_class": "research_dossier",
                    "target": "public_artifact",
                    "metadata": {"retained_field": "value"},
                },
                "security-1",
                release=True,
            )
        )
        self.assertEqual(security.state, InvocationState.COMPLETED)
        self.assertIn("allowed=false", security.response.claim_summary)
        self.assertTrue(security.review_route.required)

        atlas_channels = {
            "A16": "brain_context",
            "A17": "glioma_cell_state",
            "A18": "chromatin",
            "A19": "methylation",
            "A20": "contact",
            "A21": "literature",
            "A22": "functional",
        }
        for index, (agent_id, channel) in enumerate(atlas_channels.items()):
            atlas = app.executor.execute(
                _request(
                    f"{agent_id}.publish",
                    {
                        "variant_id": "v1",
                        "edge_id": f"edge-{agent_id}",
                        "context": context,
                        "observations": [
                            {
                                "observation_id": f"{agent_id}-obs",
                                "source_id": "SRC-ENCODE-REST",
                                "source_version": "encode-2026",
                                "context": context,
                                "channel": channel,
                                "state": "supported",
                                "tier": "reference",
                                "score": 0.75,
                                "confidence": 0.9,
                                "summary": f"bounded {channel} observation",
                                "payload": {"fixture": True},
                            }
                        ],
                    },
                    f"atlas-context-{index}",
                )
            )
            self.assertEqual(atlas.state, InvocationState.COMPLETED)
            self.assertIn("met the context threshold", atlas.response.claim_summary)

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

    def test_validation_evidence_and_report_bindings_execute_typed_work(self) -> None:
        with TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
        app = ControlPlaneApplication()
        uncertainty = UncertaintyPropagator().summarize(dossier.evidence)
        uncertainty_payload = uncertainty.to_dict()
        for component in uncertainty_payload["components"]:
            component["component_id"] = component.pop("name")

        route = app.executor.execute(
            _request(
                "A39.publish",
                {
                    "hypothesis": dossier.hypotheses[0].to_dict(),
                    "options": [option.to_dict() for option in dossier.experiments],
                    "uncertainty": uncertainty_payload,
                },
                "route-1",
            )
        )
        self.assertEqual(route.state, InvocationState.COMPLETED)
        self.assertIn("validation routes", route.response.claim_summary)

        sequence = "A" + ("C" * 19) + "AGG" + ("T" * 5)
        guide = app.executor.execute(
            _request(
                "A40.publish",
                {
                    "notation": "7:100:A>T",
                    "sequence": {
                        "assembly": "GRCh38",
                        "chromosome": "chr7",
                        "start": 100,
                        "end": 127,
                        "sequence": sequence,
                        "source_id": "SRC-UCSC-REST",
                        "receipt": _receipt("SRC-UCSC-REST", "guide-window").to_dict(),
                    },
                },
                "guide-1",
            )
        )
        self.assertEqual(guide.state, InvocationState.COMPLETED)
        self.assertIn("candidates", guide.response.claim_summary)

        claim = dossier.evidence[0]
        edge = dossier.hypotheses[0].edges[0]
        graph = app.executor.execute(
            _request(
                "A43.publish",
                {"claims": [claim.to_dict()], "edge": edge.to_dict()},
                "graph-1",
            )
        )
        self.assertEqual(graph.state, InvocationState.COMPLETED)
        self.assertIn(edge.edge_id, graph.response.evidence_id)

        report = app.executor.execute(
            _request(
                "A44.publish",
                {"dossier": dossier.to_dict(), "format": "json"},
                "report-1",
            )
        )
        self.assertEqual(report.state, InvocationState.COMPLETED)
        self.assertIn("report rendered", report.response.claim_summary)

        target = CandidateElement(
            "element-target",
            "chr7",
            100,
            120,
            "enhancer",
            dossier.hypotheses[0].context,
            "fixture-elements",
            target_genes=("GENE_TARGET",),
            features={"accessibility": 0.8, "conservation": 0.6},
        )
        control = CandidateElement(
            "element-control",
            "chr7",
            300,
            320,
            "enhancer",
            target.context,
            "fixture-elements",
            target_genes=("GENE_CONTROL",),
            features={"accessibility": 0.78, "conservation": 0.59},
        )
        controls = app.executor.execute(
            _request(
                "A37.publish",
                {
                    "context": target.context.to_dict(),
                    "target": target.to_dict(),
                    "pool": [control.to_dict()],
                },
                "controls-1",
            )
        )
        self.assertEqual(controls.state, InvocationState.COMPLETED)
        self.assertIn("unmeasured candidates", controls.response.claim_summary)

        benchmark = app.executor.execute(
            _request(
                "A38.publish",
                {
                    "benchmark_id": "fixture-benchmark",
                    "examples": [
                        {
                            "example_id": "example-1",
                            "manifest": fixture_manifest().to_dict(),
                            "expected_element_id": None,
                            "expected_gene_id": None,
                        }
                    ],
                },
                "benchmark-1",
            )
        )
        self.assertEqual(benchmark.state, InvocationState.COMPLETED)
        self.assertIn("evaluated 1 examples", benchmark.response.claim_summary)

        value = app.executor.execute(
            _request(
                "A42.publish",
                {
                    "options": [option.to_dict() for option in dossier.experiments],
                    "uncertainty": uncertainty_payload,
                },
                "value-1",
            )
        )
        self.assertEqual(value.state, InvocationState.COMPLETED)
        self.assertIn("Validation value ranked", value.response.claim_summary)

    def test_control_plane_orchestration_bindings_preserve_typed_decisions(self) -> None:
        app = ControlPlaneApplication()
        compile_result = app.executor.execute(
            _request(
                "A02.publish",
                {"requested_agent_ids": ["A35"]},
                "compile-1",
            )
        )
        self.assertEqual(compile_result.state, InvocationState.COMPLETED)
        self.assertIn("A35", compile_result.response.selected_agent_ids)

        policy_result = app.executor.execute(
            _request(
                "A03.publish",
                {
                    "target_agent_id": "A15",
                    "target_tool_id": "A15.inspect",
                    "invocation_payload": {"variant_id": "v1"},
                },
                "policy-1",
            )
        )
        self.assertEqual(policy_result.state, InvocationState.COMPLETED)
        self.assertFalse(policy_result.response.allowed)
        self.assertTrue(policy_result.response.violations)

        schedule_result = app.executor.execute(
            _request(
                "A04.publish",
                {"target_tool_id": "A23.publish"},
                "schedule-1",
            )
        )
        self.assertEqual(schedule_result.state, InvocationState.COMPLETED)
        self.assertTrue(schedule_result.response.admitted)

        envelope = {
            "evidence_id": "shared-evidence",
            "agent_id": "A23",
            "tool_id": "A23.publish",
            "state": "supported",
            "tier": "computed",
            "claim_summary": "fixture",
            "payload_hash": "sha256:one",
        }
        conflict = dict(envelope, payload_hash="sha256:two")
        arbitration_result = app.executor.execute(
            _request(
                "A05.publish",
                {"envelopes": [envelope, conflict]},
                "arbiter-1",
            )
        )
        self.assertEqual(arbitration_result.state, InvocationState.COMPLETED)
        self.assertEqual(arbitration_result.response.conflicts, ("shared-evidence",))
        self.assertEqual(len(arbitration_result.response.abstentions), 1)

        review_result = app.executor.execute(
            _request(
                "A06.publish",
                {
                    "target_agent_id": "A23",
                    "response": {
                        "kind": "abstention",
                        "reason_code": "missing_sequence",
                        "scope": "sequence",
                        "explanation": "No sequence receipt was supplied.",
                    },
                },
                "review-1",
                release=True,
            )
        )
        self.assertEqual(review_result.state, InvocationState.COMPLETED)
        self.assertTrue(review_result.response.required)
        self.assertTrue(review_result.response.blocked)

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

    def test_remaining_inference_bindings_execute_with_typed_boundaries(self) -> None:
        app = ControlPlaneApplication()
        observation = {
            "observation_id": "obs-1",
            "source_id": "fixture-source",
            "state": "supported",
            "score": 0.8,
            "confidence": 0.9,
            "context_score": 0.9,
            "payload": {"gene_id": "GENE1", "state_id": "stem_like"},
        }
        payloads = {
            "A24.publish": {
                "sequence_evidence": {
                    "variant_id": "v1",
                    "state": "supported",
                    "created_hits": [{"motif_id": "motif-1"}],
                },
                "candidate_element": {"element_id": "element-1"},
            },
            "A25.publish": {
                "sequence_evidence": {"variant_id": "v1"},
                "chromatin_evidence": {
                    "element_id": "element-1",
                    "observations": [
                        {
                            **observation,
                            "payload": {"delta": 0.2},
                        }
                    ],
                },
            },
            "A26.publish": {
                "contact_evidence": {
                    "target_id": "GENE1",
                    "observations": [
                        {
                            **observation,
                            "payload": {"contact_delta": -0.2},
                        }
                    ],
                },
                "candidate_element": {"element_id": "element-1"},
            },
            "A27.publish": {
                "canonical_variant": {"variant_id": "v1", "chromosome": "7", "start": 100},
                "candidate_element": {"element_id": "element-1", "link_score": 0.7},
            },
            "A28.publish": {
                "candidate_element": {"element_id": "element-1", "target_genes": ["GENE1"]},
                "contact_evidence": {"observations": [observation]},
            },
            "A29.publish": {
                "canonical_variant": {"variant_id": "v1", "reference": "A", "alternate": "T"},
                "functional_evidence": {
                    "observations": [
                        {**observation, "payload": {"allele": "ref", "value": 0.2}},
                        {
                            **observation,
                            "observation_id": "obs-2",
                            "payload": {"allele": "alt", "value": 0.6},
                        },
                    ]
                },
            },
            "A30.publish": {
                "link_evidence": {"observations": [observation]},
                "cell_state_annotation": {
                    "state_id": "stem_like",
                    "gene_id": "GENE1",
                    "element_id": "element-1",
                },
            },
            "A31.publish": {
                "origin_assessment": {"variant_id": "v1", "clonality": "clonal_candidate"},
                "functional_evidence": {
                    "observations": [
                        {**observation, "payload": {"timepoint": "T0", "value": 0.2}},
                        {
                            **observation,
                            "observation_id": "obs-2",
                            "payload": {"timepoint": "T1", "value": 0.5},
                        },
                    ]
                },
            },
            "A33.publish": {
                "origin_assessment": {"variant_id": "v1", "origin": "germline"},
                "cohort_record": {"inherited_context": True, "observations": [observation]},
            },
            "A35.publish": {
                "causal_lattice": {"hypothesis_id": "hyp-1", "declared_prior": 0.1, "support": 0.8},
                "evidence_envelope": {"evidence_id": "evidence-1"},
            },
        }
        for index, (tool_id, payload) in enumerate(payloads.items()):
            with self.subTest(tool_id=tool_id):
                result = app.executor.execute(_request(tool_id, payload, f"inference-{index}"))
                self.assertEqual(result.state, InvocationState.COMPLETED)
                self.assertIsNotNone(result.response)
        posterior = app.executor.execute(
            _request("A35.publish", payloads["A35.publish"], "inference-review")
        )
        self.assertTrue(posterior.review_route.required)


if __name__ == "__main__":
    unittest.main()

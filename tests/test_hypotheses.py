from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from glio_noncode.case_workflow import (
    MAX_CASE_RNA_CONSEQUENCES,
    MAX_CASE_RUNTIME_WORK_ITEMS,
    MAX_CASE_TARGETS_PER_ELEMENT,
)
from glio_noncode.errors import ValidationError
from glio_noncode.evidence import EvidenceGraph
from glio_noncode.expression_claims import RNA_CONSEQUENCE_CHANNEL
from glio_noncode.expression_evidence import (
    RegulatoryDirection,
    RNAConsequenceEvidence,
    RNAEvidenceState,
)
from glio_noncode.hypotheses import (
    MAX_HYPOTHESIS_RNA_CONSEQUENCES,
    MAX_HYPOTHESIS_TARGETS_PER_ELEMENT,
    MAX_HYPOTHESIS_WORK_ITEMS,
    HypothesisBuilder,
    HypothesisWorkLimits,
)
from glio_noncode.models import Dossier, EdgeType
from glio_noncode.replay import ReplayVerifier
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import content_hash

from .helpers import fixture_manifest


def manifest_with_elements(
    count: int,
    *,
    target_count: int = 1,
    state_count: int = 1,
):
    manifest = fixture_manifest()
    template = manifest.candidate_elements[0]
    elements = tuple(
        replace(
            template,
            element_id=f"bounded-element-{index}",
            source_id=f"bounded-source-{index}",
            start=template.start + index,
            end=template.end + index,
            target_genes=tuple(f"GENE-{index}-{gene}" for gene in range(target_count)),
            state_ids=tuple(f"STATE-{index}-{state}" for state in range(state_count)),
        )
        for index in range(count)
    )
    return replace(manifest, candidate_elements=elements)


def rna_row(index: int) -> RNAConsequenceEvidence:
    manifest = fixture_manifest()
    return RNAConsequenceEvidence(
        prediction_id=f"prediction-bounds-{index}",
        prediction_address=content_hash(
            {"prediction_id": f"prediction-bounds-{index}"},
            prefix="regulatory-effect-prediction",
        ),
        variant_id=manifest.variants[0].variant_id,
        feature_id=manifest.candidate_elements[0].target_genes[0],
        context_key=manifest.context.key,
        predicted_direction=RegulatoryDirection.UNKNOWN,
        state=RNAEvidenceState.ABSTAINED,
        expression_state=None,
        expression_direction=None,
        expression_robust_z=None,
        expression_result_address=None,
        allelic_state=None,
        allelic_direction=None,
        allelic_log2_ratio=None,
        allelic_q_value=None,
        allelic_result_address=None,
        reason_codes=("no_rna_result",),
    )


def manifest_without_elements(variant_count: int):
    manifest = fixture_manifest()
    template = manifest.variants[0]
    variants = tuple(
        replace(
            template,
            variant_id=f"bounded-variant-{index}",
            start=template.start + index,
            end=template.end + index,
        )
        for index in range(variant_count)
    )
    return replace(manifest, variants=variants, candidate_elements=())


def manifest_with_shared_element(variant_count: int):
    manifest = fixture_manifest()
    template = manifest.variants[0]
    variants = tuple(
        replace(
            template,
            variant_id=f"shared-element-variant-{index}",
            start=template.start + index,
            end=template.end + index,
        )
        for index in range(variant_count)
    )
    return replace(manifest, variants=variants)


def manifest_with_shared_gene_state(*, source_ids: tuple[str, str] = ("atlas-a", "atlas-b")):
    manifest = fixture_manifest()
    template = manifest.candidate_elements[0]
    elements = tuple(
        replace(
            template,
            element_id=f"shared-state-element-{index}",
            source_id=source_id,
            start=template.start + index,
            end=template.end + index,
            target_genes=("SHARED_GENE",),
            state_ids=("SHARED_STATE",),
            annotations=dict(template.annotations)
            | {"state_definition": f"source-specific-definition-{index}"},
        )
        for index, source_id in enumerate(source_ids)
    )
    return replace(manifest, candidate_elements=elements)


class HypothesisWorkLimitTests(unittest.TestCase):
    def test_case_facade_and_builder_share_one_hard_limit_contract(self) -> None:
        self.assertEqual(MAX_CASE_TARGETS_PER_ELEMENT, MAX_HYPOTHESIS_TARGETS_PER_ELEMENT)
        self.assertEqual(MAX_CASE_RUNTIME_WORK_ITEMS, MAX_HYPOTHESIS_WORK_ITEMS)
        self.assertEqual(MAX_CASE_RNA_CONSEQUENCES, MAX_HYPOTHESIS_RNA_CONSEQUENCES)

    def test_limit_configuration_requires_exact_positive_integers_below_hard_ceilings(
        self,
    ) -> None:
        ceilings = {
            "max_targets_per_element": MAX_HYPOTHESIS_TARGETS_PER_ELEMENT,
            "max_work_items": MAX_HYPOTHESIS_WORK_ITEMS,
            "max_rna_consequences": MAX_HYPOTHESIS_RNA_CONSEQUENCES,
        }
        for field_name, ceiling in ceilings.items():
            for malformed in (True, 1.0, "1"):
                with self.subTest(field_name=field_name, malformed=malformed):
                    with self.assertRaisesRegex(ValidationError, "must be an integer"):
                        HypothesisWorkLimits(**{field_name: malformed})
            with self.subTest(field_name=field_name, malformed=0):
                with self.assertRaisesRegex(ValidationError, "must be positive"):
                    HypothesisWorkLimits(**{field_name: 0})
            with self.subTest(field_name=field_name, malformed=ceiling + 1):
                with self.assertRaisesRegex(ValidationError, "safety ceiling"):
                    HypothesisWorkLimits(**{field_name: ceiling + 1})

        with self.assertRaisesRegex(ValidationError, "limits must be HypothesisWorkLimits"):
            HypothesisBuilder(limits={})  # type: ignore[arg-type]

    def test_target_and_state_limits_accept_below_and_at_boundary_then_reject_over(self) -> None:
        builder = HypothesisBuilder(
            limits=HypothesisWorkLimits(
                max_targets_per_element=3,
                max_work_items=100,
            )
        )
        for field_name in ("target_genes", "state_ids"):
            for size in (2, 3):
                with self.subTest(field_name=field_name, size=size):
                    manifest = manifest_with_elements(
                        1,
                        target_count=size if field_name == "target_genes" else 1,
                        state_count=size if field_name == "state_ids" else 1,
                    )
                    self.assertEqual(
                        len(builder.build(manifest, f"run-{field_name}-{size}").hypotheses),
                        size,
                    )

            over = manifest_with_elements(
                1,
                target_count=4 if field_name == "target_genes" else 1,
                state_count=4 if field_name == "state_ids" else 1,
            )
            with self.subTest(field_name=field_name, size=4):
                with self.assertRaisesRegex(ValidationError, field_name):
                    builder.build(over, f"run-{field_name}-over")

    def test_work_limit_accepts_below_and_at_boundary_then_rejects_before_scanning(self) -> None:
        builder = HypothesisBuilder(limits=HypothesisWorkLimits(max_work_items=10))

        below = builder.build(manifest_with_elements(1), "run-work-below")
        at = builder.build(manifest_with_elements(2), "run-work-at")
        self.assertEqual(len(below.hypotheses), 1)
        self.assertEqual(len(at.hypotheses), 2)

        with patch.object(
            builder,
            "_eligible_elements",
            side_effect=AssertionError("eligibility scan must not start"),
        ):
            with self.assertRaisesRegex(ValidationError, "maximum of 10 work items"):
                builder.build(manifest_with_elements(3), "run-work-over")

    def test_each_gene_state_route_is_a_separate_factorized_hypothesis(self) -> None:
        manifest = manifest_with_elements(1, target_count=2, state_count=2)
        built = HypothesisBuilder().build(manifest, "run-route-fanout")
        expected_routes = {
            (gene_id, state_id)
            for gene_id in manifest.candidate_elements[0].target_genes
            for state_id in manifest.candidate_elements[0].state_ids
        }

        self.assertEqual(
            {(hypothesis.gene_id, hypothesis.state_id) for hypothesis in built.hypotheses},
            expected_routes,
        )
        self.assertEqual(len({item.hypothesis_id for item in built.hypotheses}), 4)
        for hypothesis in built.hypotheses:
            with self.subTest(route=(hypothesis.gene_id, hypothesis.state_id)):
                self.assertEqual(len(hypothesis.edges), 4)
                by_type = {edge.edge_type: edge for edge in hypothesis.edges}
                self.assertEqual(set(by_type), set(EdgeType))
                self.assertEqual(
                    by_type[EdgeType.VARIANT_TO_ELEMENT].target_id,
                    hypothesis.element_id,
                )
                self.assertEqual(by_type[EdgeType.ELEMENT_TO_GENE].target_id, hypothesis.gene_id)
                self.assertEqual(by_type[EdgeType.GENE_TO_STATE].source_id, hypothesis.gene_id)
                self.assertEqual(by_type[EdgeType.GENE_TO_STATE].target_id, hypothesis.state_id)
                self.assertEqual(by_type[EdgeType.CAUSAL_PATH].target_id, hypothesis.state_id)

    def test_missing_gene_and_state_targets_remain_unresolved_without_prior_support(self) -> None:
        for target_count, state_count, unresolved_id in (
            (0, 1, "unresolved_gene"),
            (1, 0, "unresolved_state"),
        ):
            with self.subTest(unresolved_id=unresolved_id):
                manifest = manifest_with_elements(
                    1,
                    target_count=target_count,
                    state_count=state_count,
                )
                hypothesis = HypothesisBuilder().build(
                    manifest, f"run-{unresolved_id}"
                ).hypotheses[0]

                self.assertIn(unresolved_id, (hypothesis.gene_id, hypothesis.state_id))
                self.assertEqual(hypothesis.support, 0.0)
                self.assertTrue(hypothesis.missing_evidence)

    def test_abstention_path_counts_one_work_item_per_variant(self) -> None:
        builder = HypothesisBuilder(limits=HypothesisWorkLimits(max_work_items=2))

        self.assertEqual(
            len(builder.build(manifest_without_elements(1), "run-abstain-below").hypotheses),
            1,
        )
        self.assertEqual(
            len(builder.build(manifest_without_elements(2), "run-abstain-at").hypotheses),
            2,
        )
        with self.assertRaisesRegex(ValidationError, "maximum of 2 work items"):
            builder.build(manifest_without_elements(3), "run-abstain-over")

    def test_each_hypothesis_uses_edge_index_and_complete_graph_is_materialized_once(self) -> None:
        original = EvidenceGraph.all_claims
        with patch.object(EvidenceGraph, "all_claims", autospec=True, side_effect=original) as read:
            built = HypothesisBuilder().build(
                manifest_with_elements(3),
                "run-edge-indexed-claims",
            )

        self.assertEqual(len(built.hypotheses), 3)
        self.assertEqual(read.call_count, 1)

    def test_multiple_variants_reuse_shared_element_gene_and_gene_state_claims(self) -> None:
        manifest = manifest_with_shared_element(2)
        fixed = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
        with patch("glio_noncode.models.utc_now", return_value=fixed):
            first = HypothesisBuilder().build(manifest, "run-shared-element")
            second = HypothesisBuilder().build(manifest, "run-shared-element")

        self.assertEqual(first, second)
        self.assertEqual(len(first.hypotheses), 4)
        claim_ids = tuple(claim.evidence_id for claim in first.claims)
        self.assertEqual(len(claim_ids), len(set(claim_ids)))

        for edge_type in (EdgeType.ELEMENT_TO_GENE, EdgeType.GENE_TO_STATE):
            shared_edges = tuple(
                edge
                for hypothesis in first.hypotheses
                for edge in hypothesis.edges
                if edge.edge_type is edge_type
            )
            distinct_edge_ids = {edge.edge_id for edge in shared_edges}
            self.assertGreater(len(shared_edges), len(distinct_edge_ids))
            for edge_id in distinct_edge_ids:
                instances = tuple(edge for edge in shared_edges if edge.edge_id == edge_id)
                self.assertTrue(all(edge == instances[0] for edge in instances))
                self.assertTrue(
                    set(instances[0].claim_ids).issubset(claim_ids),
                )

    def test_shared_edges_persist_rehydrate_and_replay_through_case_runtime(self) -> None:
        manifest = manifest_with_shared_element(2)
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(manifest)
            run_record = runtime.get_run(dossier.run_id)
            event_record = runtime.store.store.get(run_record["event_address"])
            dossier_record = runtime.get_dossier(run_record["dossier_address"])

            restored = Dossier.from_dict(dossier_record)
            replay = ReplayVerifier().verify(run_record, event_record, dossier_record)

        self.assertEqual(restored, dossier)
        self.assertEqual(len(restored.hypotheses), 4)
        self.assertTrue(replay.event_chain_valid)
        self.assertTrue(replay.stored_dossier_matches_address)
        self.assertEqual(replay.warnings, ())

    def test_distinct_elements_contribute_to_one_complete_gene_state_edge_snapshot(self) -> None:
        manifest = manifest_with_shared_gene_state()
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(manifest)
            run_record = runtime.get_run(dossier.run_id)
            event_record = runtime.store.store.get(run_record["event_address"])
            dossier_record = runtime.get_dossier(run_record["dossier_address"])

            restored = Dossier.from_dict(dossier_record)
            replay = ReplayVerifier().verify(run_record, event_record, dossier_record)

        state_edges = tuple(
            edge
            for hypothesis in restored.hypotheses
            for edge in hypothesis.edges
            if edge.edge_type is EdgeType.GENE_TO_STATE
        )
        self.assertEqual(len(state_edges), 2)
        self.assertEqual(state_edges[0], state_edges[1])

        state_claims = tuple(
            claim for claim in restored.evidence if claim.edge_id == state_edges[0].edge_id
        )
        self.assertEqual(len(state_claims), 2)
        self.assertEqual(
            {claim.source_id for claim in state_claims},
            {"atlas-a:state", "atlas-b:state"},
        )
        self.assertEqual(
            {claim.payload["state_definition"] for claim in state_claims},
            {"source-specific-definition-0", "source-specific-definition-1"},
        )
        self.assertEqual(
            set(state_edges[0].claim_ids),
            {claim.evidence_id for claim in state_claims},
        )
        self.assertTrue(replay.event_chain_valid)
        self.assertTrue(replay.stored_dossier_matches_address)
        self.assertEqual(replay.warnings, ())

    def test_same_source_cannot_reuse_state_claim_id_for_conflicting_definition(self) -> None:
        manifest = manifest_with_shared_gene_state(source_ids=("same-atlas", "same-atlas"))

        with self.assertRaisesRegex(ValidationError, "different content"):
            HypothesisBuilder().build(manifest, "run-conflicting-state-definition")

    def test_shared_claim_reuse_rejects_same_id_with_different_content(self) -> None:
        built = HypothesisBuilder().build(fixture_manifest(), "run-claim-collision")
        original = built.claims[0]
        graph = EvidenceGraph()
        graph.append(original)

        reused = HypothesisBuilder._record_claim(  # noqa: SLF001 - collision contract
            graph,
            replace(original, created_at="2099-01-01T00:00:00+00:00"),
        )
        self.assertIs(reused, original)
        with self.assertRaisesRegex(ValidationError, "different content"):
            HypothesisBuilder._record_claim(  # noqa: SLF001 - collision contract
                graph,
                replace(original, summary="different scientific assertion"),
            )

        typed_graph = EvidenceGraph()
        boolean_payload = replace(original, payload={"collision_value": True})
        typed_graph.append(boolean_payload)
        with self.assertRaisesRegex(ValidationError, "different content"):
            HypothesisBuilder._record_claim(  # noqa: SLF001 - collision contract
                typed_graph,
                replace(boolean_payload, payload={"collision_value": 1}),
            )

    def test_rna_iterable_stops_after_one_sentinel_and_manifest_failure_consumes_none(self) -> None:
        builder = HypothesisBuilder(
            limits=HypothesisWorkLimits(
                max_work_items=10,
                max_rna_consequences=3,
            )
        )
        for size in (2, 3):
            with self.subTest(size=size):
                rows = builder.validate_inputs(
                    manifest_with_elements(1),
                    rna_consequences=(rna_row(index) for index in range(size)),
                )
                self.assertEqual(len(rows), size)

        consumed: list[int] = []

        def unbounded_rows():
            index = 0
            while True:
                consumed.append(index)
                yield object()
                index += 1

        with self.assertRaisesRegex(ValidationError, "maximum of 3 items"):
            builder.validate_inputs(
                manifest_with_elements(1),
                rna_consequences=unbounded_rows(),
            )
        self.assertEqual(consumed, [0, 1, 2, 3])

        class MustNotIterate:
            def __iter__(self):
                raise AssertionError("RNA input must not be consumed after manifest rejection")

        with self.assertRaisesRegex(ValidationError, "maximum of 10 work items"):
            builder.validate_inputs(
                manifest_with_elements(3),
                rna_consequences=MustNotIterate(),
            )

    def test_retained_rna_owner_reaches_claim_and_causal_path_identity(self) -> None:
        manifest = fixture_manifest()
        row = rna_row(0)
        owner = content_hash({"kind": "runtime-rna-consequence-batch"})
        owned = HypothesisBuilder().build(
            manifest,
            "run-retained-rna-owner",
            rna_consequences=(row,),
            retained_owner_address=owner,
        )
        standalone = HypothesisBuilder().build(
            manifest,
            "run-retained-rna-owner",
            rna_consequences=(row,),
        )
        owned_claim = next(
            claim for claim in owned.claims if claim.channel == RNA_CONSEQUENCE_CHANNEL
        )
        standalone_claim = next(
            claim for claim in standalone.claims if claim.channel == RNA_CONSEQUENCE_CHANNEL
        )

        self.assertEqual(owned_claim.depends_on, (owner,))
        self.assertEqual(owned_claim.payload["retained_owner_address"], owner)
        self.assertEqual(
            owned_claim.payload["source_addresses"],
            standalone_claim.payload["source_addresses"],
        )
        self.assertNotEqual(owned_claim.evidence_id, standalone_claim.evidence_id)
        causal_edge = next(
            edge
            for hypothesis in owned.hypotheses
            if hypothesis.gene_id == row.feature_id
            for edge in hypothesis.edges
            if edge.edge_type is EdgeType.CAUSAL_PATH
        )
        path_claim = next(
            claim for claim in owned.claims if claim.evidence_id in causal_edge.claim_ids
        )
        self.assertIn(owned_claim.evidence_id, path_claim.depends_on)

        with self.assertRaisesRegex(ValidationError, "canonical sha256"):
            HypothesisBuilder().build(
                manifest,
                "run-invalid-retained-rna-owner",
                rna_consequences=(row,),
                retained_owner_address="sha256:not-a-digest",
            )
        with self.assertRaisesRegex(ValidationError, "requires at least one RNA"):
            HypothesisBuilder().build(
                manifest,
                "run-unused-retained-rna-owner",
                retained_owner_address=owner,
            )

    def test_default_and_explicit_default_limits_preserve_complete_output(self) -> None:
        manifest = fixture_manifest()
        fixed = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
        with patch("glio_noncode.models.utc_now", return_value=fixed):
            implicit = HypothesisBuilder().build(manifest, "run-default-limit-identity")
            explicit = HypothesisBuilder(limits=HypothesisWorkLimits()).build(
                manifest,
                "run-default-limit-identity",
            )

        self.assertEqual(implicit, explicit)

    def test_runtime_rejects_over_budget_before_any_object_or_run_is_persisted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(
                directory,
                hypothesis_limits=HypothesisWorkLimits(max_work_items=10),
            )
            with self.assertRaisesRegex(ValidationError, "maximum of 10 work items"):
                runtime.evaluate(manifest_with_elements(3))

            self.assertEqual(list(Path(directory).rglob("*.json")), [])


if __name__ == "__main__":
    unittest.main()

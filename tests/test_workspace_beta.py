import unittest

from glio_noncode.causal_beta import CausalBetaState, CausalMediatorResult, MediatorKind
from glio_noncode.inference_extensions import DriverPosteriorResult, InferenceState
from glio_noncode.topology_beta import (
    LoopStripeObservation,
    PromoterCaptureContact,
    TopologyBetaKind,
)
from glio_noncode.workspace import (
    ResearchWorkspace,
    WorkspaceKind,
    WorkspaceRecord,
    WorkspaceRecordType,
    WorkspaceSection,
    WorkspaceState,
)
from glio_noncode.workspace_beta import (
    CausalChainExplorer,
    CausalChainState,
    EvidenceTableAndFilters,
    EvidenceTableFilter,
    PosteriorComponent,
    PosteriorDecompositionViewer,
    TopologyEdgeKind,
    TopologyViewer,
)


class WorkspaceBetaTests(unittest.TestCase):
    CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"

    def _loop(self, context: str = CONTEXT) -> LoopStripeObservation:
        return LoopStripeObservation(
            feature_id="loop-1",
            feature_kind=TopologyBetaKind.LOOP,
            chromosome_a="7",
            start_a=100,
            end_a=120,
            chromosome_b="7",
            start_b=1000,
            end_b=1020,
            signal=8.5,
            context_key=context,
            source_id="hic-1",
            source_version="v1",
            raw_hash="sha256:loop",
            resolution=10,
        )

    def _contact(self, context: str = CONTEXT) -> PromoterCaptureContact:
        return PromoterCaptureContact(
            contact_id="pc-1",
            promoter_id="gene-1",
            target_element_id="element-1",
            promoter_chromosome="7",
            promoter_start=1000,
            promoter_end=1020,
            target_chromosome="7",
            target_start=100,
            target_end=120,
            signal=5.0,
            context_key=context,
            source_id="capture-1",
            source_version="v2",
            raw_hash="sha256:contact",
        )

    def test_topology_viewer_keeps_exact_context_focus_and_receipts(self) -> None:
        viewport = TopologyViewer().build(
            context_key=self.CONTEXT,
            loops=(self._loop(), self._loop("other-context")),
            contacts=(self._contact(),),
            focus_chromosome="7",
            focus_start=90,
            focus_end=130,
        )
        self.assertEqual(viewport.state, WorkspaceState.PARTIAL)
        self.assertEqual(viewport.observed_edge_count, 2)
        self.assertEqual(
            {edge.kind for edge in viewport.edges},
            {TopologyEdgeKind.LOOP, TopologyEdgeKind.PROMOTER_CAPTURE},
        )
        self.assertTrue(any("context" in warning for warning in viewport.warnings))
        self.assertEqual(viewport.edges[0].context_key, self.CONTEXT)

    def _mediator(
        self,
        kind: MediatorKind,
        source: str,
        target: str,
        *,
        state: CausalBetaState = CausalBetaState.SUPPORTED,
        context: str = CONTEXT,
        index: str = "1",
    ) -> CausalMediatorResult:
        return CausalMediatorResult(
            mediator_kind=kind,
            source_node=source,
            target_node=target,
            context_key=context,
            model_id="model",
            model_version="v1",
            state=state,
            support=0.8 if state == CausalBetaState.SUPPORTED else None,
            uncertainty=0.1 if state == CausalBetaState.SUPPORTED else 1.0,
            sensitivity=0.7,
            evidence_ids=(f"evidence-{index}",),
            negative_evidence_ids=(),
            source_ids=(f"source-{index}",),
            source_versions=("v1",),
            reason="declared exact-context mediator",
            warnings=("research summary",),
            content_address=f"sha256:mediator-{index}",
        )

    def test_causal_chain_explorer_marks_complete_and_retains_alternatives(self) -> None:
        results = (
            self._mediator(MediatorKind.SEQUENCE_TO_ELEMENT, "variant-1", "element-1"),
            self._mediator(MediatorKind.ELEMENT_TO_GENE, "element-1", "gene-1", index="2"),
            self._mediator(MediatorKind.GENE_TO_STATE, "gene-1", "state-1", index="3"),
            self._mediator(
                MediatorKind.ELEMENT_TO_GENE,
                "element-1",
                "gene-2",
                index="4",
            ),
            self._mediator(
                MediatorKind.GENE_TO_STATE,
                "gene-1",
                "state-1",
                context="other-context",
                index="5",
            ),
        )
        view = CausalChainExplorer().explore(results, context_key=self.CONTEXT)
        self.assertEqual(view.state, CausalChainState.COMPLETE)
        self.assertTrue(view.complete)
        self.assertEqual(len(view.alternative_edge_ids), 2)
        self.assertEqual(len(view.missing_mediator_kinds), 0)
        self.assertTrue(any("withheld" in warning for warning in view.warnings))

    def test_causal_chain_explorer_preserves_contradiction_as_chain_state(self) -> None:
        view = CausalChainExplorer().explore(
            (
                self._mediator(
                    MediatorKind.SEQUENCE_TO_ELEMENT,
                    "variant-1",
                    "element-1",
                    state=CausalBetaState.CONTRADICTORY,
                ),
            ),
            context_key=self.CONTEXT,
        )
        self.assertEqual(view.state, CausalChainState.CONTRADICTORY)
        self.assertFalse(view.complete)

    def test_posterior_decomposition_reconciles_declared_support(self) -> None:
        posterior = DriverPosteriorResult(
            hypothesis_id="h-1",
            state=InferenceState.SUPPORTED,
            declared_prior=0.2,
            evidence_support=0.75,
            posterior_proxy=0.652174,
            calibration_status="unvalidated_research_proxy",
            uncertainty=0.3,
            observation_ids=("obs-1",),
            limitations=("research only",),
            content_address="sha256:posterior",
        )
        view = PosteriorDecompositionViewer().view(
            posterior,
            (
                PosteriorComponent(
                    "sequence",
                    "sequence support",
                    0.4,
                    self.CONTEXT,
                    source_ids=("seq",),
                ),
                PosteriorComponent(
                    "topology",
                    "topology support",
                    0.35,
                    self.CONTEXT,
                    source_ids=("topology",),
                ),
            ),
            context_key=self.CONTEXT,
        )
        self.assertEqual(view.state, WorkspaceState.SUPPORTED)
        self.assertTrue(view.is_reconciled)
        self.assertEqual(view.residual, 0.0)
        self.assertAlmostEqual(sum(view.normalized_shares.values()), 1.0)

    def test_posterior_decomposition_exposes_unreconciled_and_foreign_components(self) -> None:
        posterior = {
            "hypothesis_id": "h-2",
            "state": "supported",
            "declared_prior": 0.1,
            "evidence_support": 0.8,
            "posterior_proxy": 0.3,
        }
        view = PosteriorDecompositionViewer().view(
            posterior,
            (
                {"component_id": "foreign", "contribution": 0.8, "context_key": "other"},
                {"component_id": "local", "contribution": 0.2, "context_key": self.CONTEXT},
            ),
            context_key=self.CONTEXT,
        )
        self.assertEqual(view.state, WorkspaceState.PARTIAL)
        self.assertEqual(view.residual, 0.6)
        self.assertFalse(view.is_reconciled)

    def _workspace(self) -> ResearchWorkspace:
        records = (
            WorkspaceRecord(
                record_id="evidence-1",
                record_type=WorkspaceRecordType.EVIDENCE,
                label="sequence supports element",
                context_key=self.CONTEXT,
                state=WorkspaceState.SUPPORTED,
                source_ids=("source-a",),
                tags=("sequence", "tier-1"),
                fields={"channel": "sequence", "tier": "tier-1", "confidence": 0.9},
                searchable_text="sequence element",
            ),
            WorkspaceRecord(
                record_id="evidence-2",
                record_type=WorkspaceRecordType.EVIDENCE,
                label="topology unresolved",
                context_key=self.CONTEXT,
                state=WorkspaceState.PARTIAL,
                source_ids=("source-b",),
                tags=("topology", "tier-2"),
                fields={"channel": "topology", "tier": "tier-2", "confidence": 0.4},
                searchable_text="topology promoter",
            ),
            WorkspaceRecord(
                record_id="hypothesis-1",
                record_type=WorkspaceRecordType.HYPOTHESIS,
                label="not evidence",
                context_key=self.CONTEXT,
                state=WorkspaceState.PARTIAL,
            ),
        )
        section = WorkspaceSection(
            "evidence",
            "Evidence",
            (WorkspaceRecordType.EVIDENCE,),
            0,
            "Evidence",
            "Evidence records",
        )
        return ResearchWorkspace(
            workspace_id="workspace-1",
            kind=WorkspaceKind.CASE,
            context_key=self.CONTEXT,
            records=records,
            sections=(section,),
            state=WorkspaceState.PARTIAL,
            warnings=("source warning",),
            content_address="sha256:workspace",
        )

    def test_evidence_table_filters_facets_paginates_and_keeps_states(self) -> None:
        table = EvidenceTableAndFilters().build(
            self._workspace(),
            EvidenceTableFilter(
                context_key=self.CONTEXT,
                channels=("sequence",),
                min_confidence=0.8,
                limit=1,
            ),
        )
        self.assertEqual(table.state, WorkspaceState.SUPPORTED)
        self.assertEqual(table.total_matches, 1)
        self.assertEqual(table.rows[0].record_id, "evidence-1")
        self.assertEqual(table.facets["channel"], {"sequence": 1})
        self.assertTrue(any("filtering" in warning for warning in table.warnings))

    def test_evidence_table_context_mismatch_abstains_out_of_domain(self) -> None:
        table = EvidenceTableAndFilters().build(
            self._workspace(),
            EvidenceTableFilter(context_key="other-context"),
        )
        self.assertEqual(table.state, WorkspaceState.OUT_OF_DOMAIN)
        self.assertEqual(table.rows, ())


if __name__ == "__main__":
    unittest.main()

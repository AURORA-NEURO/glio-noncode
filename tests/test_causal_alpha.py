from __future__ import annotations

import unittest

from glio_noncode.causal_alpha import (
    ConfounderDisposition,
    ConfoundingChecklistAdjudicator,
    DependenceMethod,
    EvidenceDependenceCorrector,
    MediationSensitivityAnalyzer,
    NegativeEvidenceIntegrator,
)
from glio_noncode.causal_beta import CausalBetaState, MediatorKind
from glio_noncode.causal_reasoning import CausalState

CONTEXT = "GRCh38|glioma|adult|stem_like|core|unknown"
OTHER_CONTEXT = "GRCh38|glioma|adult|differentiated|core|unknown"


class CausalAlphaTests(unittest.TestCase):
    def _mediator_rows(self) -> list[dict[str, object]]:
        return [
            {
                "evidence_id": "seq-1",
                "mediator_kind": "sequence_to_element",
                "source_node": "variant:v1",
                "target_node": "element:enh-1",
                "context_key": CONTEXT,
                "support": 0.8,
                "uncertainty": 0.1,
                "source_id": "sequence-model",
                "source_version": "v1",
            },
            {
                "evidence_id": "seq-2",
                "mediator_kind": "sequence_to_element",
                "source_node": "variant:v1",
                "target_node": "element:enh-1",
                "context_key": CONTEXT,
                "support": 0.6,
                "uncertainty": 0.1,
                "source_id": "motif-atlas",
                "source_version": "v2",
            },
        ]

    def test_mediation_sensitivity_keeps_leave_one_source_out_influence(self) -> None:
        report = MediationSensitivityAnalyzer().analyze(
            self._mediator_rows(),
            mediator_kind=MediatorKind.SEQUENCE_TO_ELEMENT,
            source_node="variant:v1",
            target_node="element:enh-1",
            context_key=CONTEXT,
            model_id="seq-alpha",
            model_version="1",
            robustness_tolerance=0.3,
        )
        self.assertEqual(report.result.base_state, CausalBetaState.SUPPORTED)
        self.assertEqual(report.result.sensitivity_state, CausalBetaState.SUPPORTED)
        self.assertEqual(report.result.source_ids, ("motif-atlas", "sequence-model"))
        self.assertEqual(len(report.result.leave_one_out), 2)
        self.assertTrue(report.result.robust_to_source_omission)
        self.assertGreater(report.result.maximum_absolute_delta or 0.0, 0.0)

    def test_mediation_sensitivity_abstains_for_context_only_evidence(self) -> None:
        rows = self._mediator_rows()
        for row in rows:
            row["context_key"] = OTHER_CONTEXT
        report = MediationSensitivityAnalyzer().analyze(
            rows,
            mediator_kind=MediatorKind.SEQUENCE_TO_ELEMENT,
            source_node="variant:v1",
            target_node="element:enh-1",
            context_key=CONTEXT,
            model_id="seq-alpha",
            model_version="1",
        )
        self.assertEqual(report.result.base_state, CausalBetaState.OUT_OF_DOMAIN)
        self.assertIsNone(report.result.maximum_absolute_delta)

    def test_confounding_adjudicator_retains_missing_and_unresolved_items(self) -> None:
        report = ConfoundingChecklistAdjudicator().assess(
            [
                {
                    "observation_id": "batch-1",
                    "confounder_id": "batch",
                    "label": "processing batch",
                    "status": "addressed",
                    "addressed": True,
                    "severity": 0.7,
                    "adjustment_method": "fixed_effect",
                    "context_key": CONTEXT,
                    "source_id": "design-review",
                },
                {
                    "observation_id": "purity-1",
                    "confounder_id": "purity",
                    "label": "tumor purity",
                    "status": "unresolved",
                    "addressed": False,
                    "severity": 0.9,
                    "context_key": CONTEXT,
                    "source_id": "qc-review",
                },
            ],
            context_key=CONTEXT,
            required_confounder_ids=("batch", "purity", "sex"),
        )
        self.assertEqual(report.state, CausalState.PARTIAL)
        self.assertEqual(report.missing_confounder_ids, ("sex",))
        self.assertEqual(report.unresolved_confounder_ids, ("purity",))
        self.assertEqual(report.adjudications[0].disposition, ConfounderDisposition.ADDRESSED)
        self.assertEqual(report.adjudications[1].disposition, ConfounderDisposition.UNRESOLVED)
        self.assertEqual(report.adjudications[2].disposition, ConfounderDisposition.MISSING)

    def test_confounding_adjudicator_reports_supported_when_all_checks_are_addressed(self) -> None:
        report = ConfoundingChecklistAdjudicator().assess(
            [
                {
                    "observation_id": "batch-1",
                    "confounder_id": "batch",
                    "label": "batch",
                    "status": "addressed",
                    "severity": 0.4,
                    "context_key": CONTEXT,
                    "source_id": "review",
                },
                {
                    "observation_id": "purity-1",
                    "confounder_id": "purity",
                    "label": "purity",
                    "status": "not_applicable",
                    "severity": 0.2,
                    "context_key": CONTEXT,
                    "source_id": "review",
                },
            ],
            context_key=CONTEXT,
            required_confounder_ids=("batch", "purity"),
        )
        self.assertEqual(report.state, CausalState.SUPPORTED)

    def test_dependence_corrector_selects_one_path_per_group(self) -> None:
        report = EvidenceDependenceCorrector().correct(
            [
                {
                    "evidence_id": "e1",
                    "edge_id": "edge-1",
                    "method_family": "contact",
                    "dependence_group": "hic-replicates",
                    "support": 0.6,
                    "uncertainty": 0.2,
                    "context_key": CONTEXT,
                    "source_id": "hic",
                },
                {
                    "evidence_id": "e2",
                    "edge_id": "edge-1",
                    "method_family": "contact",
                    "dependence_group": "hic-replicates",
                    "support": 0.9,
                    "uncertainty": 0.1,
                    "context_key": CONTEXT,
                    "source_id": "hic",
                },
                {
                    "evidence_id": "e3",
                    "edge_id": "edge-1",
                    "method_family": "coaccessibility",
                    "dependence_group": "single_cell",
                    "support": 0.7,
                    "uncertainty": 0.1,
                    "context_key": CONTEXT,
                    "source_id": "sc-atlas",
                },
            ],
            context_key=CONTEXT,
            minimum_independent_groups=2,
        )
        result = report.results[0]
        self.assertEqual(report.state, CausalState.SUPPORTED)
        self.assertEqual(result.independent_group_count, 2)
        self.assertEqual(result.selected_evidence_ids, ("e2", "e3"))
        self.assertEqual(result.duplicate_evidence_ids, ("e1",))
        self.assertAlmostEqual(result.corrected_support or 0.0, 0.72)

    def test_dependence_corrector_can_group_by_method_family(self) -> None:
        report = EvidenceDependenceCorrector().correct(
            [
                {
                    "evidence_id": "e1",
                    "edge_id": "edge-1",
                    "method_family": "contact",
                    "dependence_group": "a",
                    "support": 0.8,
                    "uncertainty": 0.1,
                    "context_key": CONTEXT,
                    "source_id": "source-a",
                },
                {
                    "evidence_id": "e2",
                    "edge_id": "edge-1",
                    "method_family": "contact",
                    "dependence_group": "b",
                    "support": 0.7,
                    "uncertainty": 0.1,
                    "context_key": CONTEXT,
                    "source_id": "source-b",
                },
            ],
            context_key=CONTEXT,
            correction_method=DependenceMethod.METHOD_FAMILY,
            minimum_independent_groups=2,
        )
        self.assertEqual(report.state, CausalState.PARTIAL)
        self.assertEqual(report.results[0].independent_group_count, 1)

    def test_negative_integrator_surfaces_positive_negative_conflict(self) -> None:
        report = NegativeEvidenceIntegrator().integrate(
            [
                {
                    "evidence_id": "positive",
                    "edge_id": "edge-1",
                    "polarity": "positive",
                    "strength": 0.8,
                    "context_key": CONTEXT,
                    "source_id": "functional",
                },
                {
                    "evidence_id": "negative-control",
                    "edge_id": "edge-1",
                    "polarity": "negative_control",
                    "strength": 0.9,
                    "negative_control": True,
                    "context_key": CONTEXT,
                    "source_id": "control",
                },
            ],
            context_key=CONTEXT,
        )
        result = report.results[0]
        self.assertEqual(report.state, CausalState.CONTRADICTORY)
        self.assertEqual(result.negative_control_ids, ("negative-control",))
        self.assertIsNone(result.integrated_support_proxy)

    def test_negative_integrator_marks_negative_only_as_measured_negative(self) -> None:
        report = NegativeEvidenceIntegrator().integrate(
            [
                {
                    "evidence_id": "negative",
                    "edge_id": "edge-1",
                    "polarity": "negative",
                    "strength": 0.9,
                    "context_key": CONTEXT,
                    "source_id": "control",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, CausalState.MEASURED_NEGATIVE)
        self.assertEqual(report.results[0].negative_evidence_ids, ("negative",))

    def test_negative_integrator_context_gate_is_explicit(self) -> None:
        report = NegativeEvidenceIntegrator().integrate(
            [
                {
                    "evidence_id": "other",
                    "edge_id": "edge-1",
                    "polarity": "negative",
                    "strength": 0.9,
                    "context_key": OTHER_CONTEXT,
                    "source_id": "control",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, CausalState.OUT_OF_DOMAIN)
        self.assertEqual(report.results, ())


if __name__ == "__main__":
    unittest.main()

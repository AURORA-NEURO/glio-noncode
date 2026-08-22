from __future__ import annotations

import unittest

from glio_noncode.causal_alpha import (
    ConfoundingChecklistAdjudicator,
    EvidenceDependenceCorrector,
    MediationSensitivityAnalyzer,
    NegativeEvidenceIntegrator,
)
from glio_noncode.causal_alpha_frontier_adapters import build_causal_alpha_frontier_adapters
from glio_noncode.causal_alpha_frontier_contracts import build_causal_alpha_frontier_contracts
from glio_noncode.causal_alpha_frontier_fixture_eval import evaluate_causal_alpha_frontier_fixture_deep
from glio_noncode.causal_alpha_frontier_public_data import (
    CAUSAL_ALPHA_FRONTIER_CONTEXT_KEY,
    default_causal_alpha_frontier_fixture,
)
from glio_noncode.causal_beta import CausalBetaState, MediatorKind
from glio_noncode.causal_reasoning import CausalState
from glio_noncode.errors import ValidationError


class CausalAlphaFrontierContractTests(unittest.TestCase):
    def test_contract_registry_has_one_contract_per_capability(self) -> None:
        report = build_causal_alpha_frontier_contracts()
        self.assertTrue(report.accepted)
        self.assertEqual(tuple(item.capability_id for item in report.contracts), ("GNC-D11-C09", "GNC-D11-C10", "GNC-D11-C11", "GNC-D11-C12"))
        self.assertEqual(len({item.content_address for item in report.contracts}), 4)
        self.assertEqual(report.for_capability("GNC-D11-C09").operation.value, "mediation_sensitivity")
        self.assertEqual(report.for_operation("negative_evidence").capability_id, "GNC-D11-C12")

    def test_contracts_list_required_and_output_fields(self) -> None:
        report = build_causal_alpha_frontier_contracts()
        for contract in report.contracts:
            self.assertTrue(contract.required_fields)
            self.assertTrue(contract.output_fields)
            self.assertTrue(contract.issue_codes)
            self.assertTrue(contract.limitation)
            self.assertTrue(contract.content_address.startswith("sha256:"))
            self.assertEqual(contract.to_dict()["operation"], contract.operation)

    def test_adapter_registry_implementation_names_are_explicit(self) -> None:
        registry = build_causal_alpha_frontier_adapters()
        names = {item.operation.value: item.implementation for item in registry.adapters}
        self.assertIn("MediationSensitivityAnalyzer", names["mediation_sensitivity"])
        self.assertIn("ConfoundingChecklistAdjudicator", names["confounding_checklist"])
        self.assertIn("EvidenceDependenceCorrector", names["dependence_correction"])
        self.assertIn("NegativeEvidenceIntegrator", names["negative_evidence"])

    def test_mediation_adapter_preserves_leave_one_out_receipts(self) -> None:
        context = CAUSAL_ALPHA_FRONTIER_CONTEXT_KEY
        report = MediationSensitivityAnalyzer().analyze(
            [
                {"evidence_id": "a", "mediator_kind": "sequence_to_element", "source_node": "variant:v1", "target_node": "element:e1", "context_key": context, "support": 0.8, "uncertainty": 0.1, "source_id": "source-a", "source_version": "1"},
                {"evidence_id": "b", "mediator_kind": "sequence_to_element", "source_node": "variant:v1", "target_node": "element:e1", "context_key": context, "support": 0.7, "uncertainty": 0.1, "source_id": "source-b", "source_version": "1"},
            ],
            mediator_kind=MediatorKind.SEQUENCE_TO_ELEMENT,
            source_node="variant:v1",
            target_node="element:e1",
            context_key=context,
            model_id="test",
            model_version="1",
        )
        self.assertEqual(report.result.base_state, CausalBetaState.SUPPORTED)
        self.assertEqual(len(report.result.leave_one_out), 2)
        self.assertEqual(report.result.source_ids, ("source-a", "source-b"))
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in report.result.leave_one_out))

    def test_mediation_context_only_rows_are_out_of_domain(self) -> None:
        fixture = default_causal_alpha_frontier_fixture()
        result = evaluate_causal_alpha_frontier_fixture_deep(fixture).evaluation.for_operation("mediation_sensitivity")[-1]
        self.assertEqual(result.observed_state, CausalState.OUT_OF_DOMAIN)
        self.assertIn("context_mismatch", result.observed_issue_codes)

    def test_confounding_adjudicator_preserves_all_dispositions(self) -> None:
        context = CAUSAL_ALPHA_FRONTIER_CONTEXT_KEY
        report = ConfoundingChecklistAdjudicator().assess(
            [
                {"observation_id": "a", "confounder_id": "batch", "label": "batch", "status": "addressed", "addressed": True, "severity": 0.2, "context_key": context, "source_id": "source-a"},
                {"observation_id": "b", "confounder_id": "purity", "label": "purity", "status": "unresolved", "addressed": False, "severity": 0.9, "context_key": context, "source_id": "source-b"},
            ],
            context_key=context,
            required_confounder_ids=("batch", "purity", "sex"),
        )
        self.assertEqual(report.state, CausalState.PARTIAL)
        self.assertEqual(report.missing_confounder_ids, ("sex",))
        self.assertEqual(report.unresolved_confounder_ids, ("purity",))
        self.assertEqual(len(report.adjudications), 3)
        self.assertEqual({item.disposition.value for item in report.adjudications}, {"addressed", "unresolved", "missing"})

    def test_dependence_correction_retains_duplicates_and_groups(self) -> None:
        context = CAUSAL_ALPHA_FRONTIER_CONTEXT_KEY
        report = EvidenceDependenceCorrector().correct(
            [
                {"evidence_id": "a", "edge_id": "edge", "method_family": "contact", "dependence_group": "contact-replicates", "support": 0.6, "uncertainty": 0.2, "context_key": context, "source_id": "source-a"},
                {"evidence_id": "b", "edge_id": "edge", "method_family": "contact", "dependence_group": "contact-replicates", "support": 0.9, "uncertainty": 0.1, "context_key": context, "source_id": "source-b"},
                {"evidence_id": "c", "edge_id": "edge", "method_family": "expression", "dependence_group": "expression-replicates", "support": 0.8, "uncertainty": 0.1, "context_key": context, "source_id": "source-c"},
            ],
            context_key=context,
            minimum_independent_groups=2,
        )
        result = report.results[0]
        self.assertEqual(report.state, CausalState.SUPPORTED)
        self.assertEqual(result.independent_group_count, 2)
        self.assertEqual(result.selected_evidence_ids, ("b", "c"))
        self.assertEqual(result.duplicate_evidence_ids, ("a",))
        self.assertEqual(set(result.dependence_groups), {"contact-replicates", "expression-replicates"})

    def test_negative_integrator_keeps_positive_and_control_separate(self) -> None:
        context = CAUSAL_ALPHA_FRONTIER_CONTEXT_KEY
        report = NegativeEvidenceIntegrator().integrate(
            [
                {"evidence_id": "positive", "edge_id": "edge", "polarity": "positive", "strength": 0.8, "context_key": context, "source_id": "source-a"},
                {"evidence_id": "control", "edge_id": "edge", "polarity": "negative_control", "strength": 0.9, "negative_control": True, "context_key": context, "source_id": "source-b"},
            ],
            context_key=context,
        )
        result = report.results[0]
        self.assertEqual(report.state, CausalState.CONTRADICTORY)
        self.assertEqual(result.positive_evidence_ids, ("positive",))
        self.assertEqual(result.negative_control_ids, ("control",))
        self.assertIsNone(result.integrated_support_proxy)

    def test_negative_only_path_is_measured_negative(self) -> None:
        context = CAUSAL_ALPHA_FRONTIER_CONTEXT_KEY
        report = NegativeEvidenceIntegrator().integrate(
            [{"evidence_id": "negative", "edge_id": "edge", "polarity": "negative", "strength": 0.9, "context_key": context, "source_id": "source-a"}],
            context_key=context,
        )
        self.assertEqual(report.state, CausalState.MEASURED_NEGATIVE)
        self.assertEqual(report.results[0].negative_evidence_ids, ("negative",))
        self.assertEqual(report.results[0].negative_coverage, 0.0)

    def test_invalid_operation_parameters_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            MediationSensitivityAnalyzer().analyze([], mediator_kind=MediatorKind.SEQUENCE_TO_ELEMENT, source_node="a", target_node="b", context_key="x", model_id="m", model_version="1", minimum_sources=0)
        with self.assertRaises(ValidationError):
            EvidenceDependenceCorrector().correct([], context_key="x", minimum_independent_groups=0)
        with self.assertRaises(ValidationError):
            NegativeEvidenceIntegrator().integrate([], context_key="x", minimum_negative_controls=-1)

    def test_deep_evaluation_keeps_underlying_output_envelopes(self) -> None:
        evaluation = evaluate_causal_alpha_frontier_fixture_deep(default_causal_alpha_frontier_fixture())
        for result in evaluation.evaluation.results:
            self.assertTrue(result.output)
            self.assertTrue(result.content_address.startswith("sha256:"))
            self.assertEqual(result.expected_state, result.observed_state)
            self.assertEqual(result.accepted, result.state_match)


if __name__ == "__main__":
    unittest.main()

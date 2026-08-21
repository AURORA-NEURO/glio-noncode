from __future__ import annotations

import unittest

from glio_noncode.frontier_data_alpha import FrontierState
from glio_noncode.frontier_release_hardening import (
    DeploymentDependencyResolver,
    EvidenceGraphIntegrityAuditor,
    EvidenceLineageBuilder,
    FederatedPrivacyAccountant,
    HumanFactorsScenarioSimulator,
    OffTargetAlignmentAuditor,
    ReleaseHistoryLedger,
    ReportArtifactRenderer,
    SecurityPathScanner,
    ValidationExecutionReadinessChecker,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierReleaseHardeningTests(unittest.TestCase):
    def test_alignment_audit_retains_mismatch_positions_and_risk(self) -> None:
        report = OffTargetAlignmentAuditor().audit(
            [
                {
                    "candidate_id": "candidate-1",
                    "guide_sequence": "ACGTACGT",
                    "target_sequence": "ACGTTCGT",
                    "pam": "NGG",
                    "pam_match": True,
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(report.audits[0].mismatch_positions, (4,))
        self.assertGreaterEqual(report.audits[0].risk_score, 0.35)

    def test_validation_readiness_checks_context_controls_and_outputs(self) -> None:
        report = ValidationExecutionReadinessChecker().evaluate(
            {
                "context_key": CONTEXT,
                "experiments": [{"experiment_id": "exp-1", "context_key": CONTEXT}],
                "controls": [{"control_id": "ctrl-1"}],
                "outputs": ["readout"],
            },
            package_id="package-1",
            context_key=CONTEXT,
            required_controls=("ctrl-1",),
            required_outputs=("readout",),
        )
        self.assertEqual(report.state, FrontierState.ACCEPTED)
        self.assertEqual(report.failed_ids, ())

    def test_graph_audit_finds_dangling_nodes_and_cycles(self) -> None:
        dangling = EvidenceGraphIntegrityAuditor().audit(
            [{"node_id": "a", "context_key": CONTEXT}],
            [{"source_id": "a", "target_id": "missing"}],
            context_key=CONTEXT,
        )
        self.assertEqual(dangling.dangling_node_ids, ("missing",))
        cycle = EvidenceGraphIntegrityAuditor().audit(
            [{"node_id": "a", "context_key": CONTEXT}, {"node_id": "b", "context_key": CONTEXT}],
            [{"source_id": "a", "target_id": "b"}, {"source_id": "b", "target_id": "a"}],
            context_key=CONTEXT,
        )
        self.assertEqual(cycle.state, FrontierState.REVIEW)
        self.assertIn("a", cycle.cycle_node_ids)

    def test_lineage_and_artifact_rendering_are_addressed(self) -> None:
        lineage = EvidenceLineageBuilder().build(
            [{"item_id": "claim-1", "context_key": CONTEXT, "source_addresses": ["sha256:source"]}],
            context_key=CONTEXT,
        )
        self.assertEqual(lineage.root_ids, ("claim-1",))
        artifact = ReportArtifactRenderer().render(
            [{"record_id": "claim-1", "state": "review"}],
            artifact_id="report.csv",
            format="csv",
            columns=("record_id", "state"),
        )
        self.assertIn("record_id,state", artifact.content)
        self.assertTrue(artifact.content_address.startswith("sha256:"))

    def test_human_factors_simulator_requires_focus_and_recovers_errors(self) -> None:
        valid = HumanFactorsScenarioSimulator().simulate(
            [
                {"event_id": "e-1", "event_type": "focus", "target_id": "submit"},
                {"event_id": "e-2", "event_type": "error"},
                {"event_id": "e-3", "event_type": "recover"},
                {"event_id": "e-4", "event_type": "submit"},
            ],
            scenario_id="scenario-1",
        )
        self.assertTrue(valid.completed)
        self.assertEqual(valid.recovery_count, 1)
        invalid = HumanFactorsScenarioSimulator().simulate(
            [{"event_id": "e-1", "event_type": "submit"}],
            scenario_id="scenario-2",
        )
        self.assertFalse(invalid.completed)

    def test_security_scanner_never_returns_secret_values(self) -> None:
        report = SecurityPathScanner().scan(
            {"subject_id": "subject-1", "nested": {"api_token": "do-not-return"}}
        )
        self.assertEqual(report.sensitive_path_count, 1)
        self.assertEqual(report.secret_path_count, 1)
        self.assertNotIn("do-not-return", str(report.to_dict()))
        self.assertEqual(report.state, FrontierState.REVIEW)

    def test_dependency_resolution_and_cycle_diagnostics(self) -> None:
        resolved = DeploymentDependencyResolver().resolve(
            [{"service_id": "api", "depends_on": ["db"]}, {"service_id": "db", "depends_on": []}]
        )
        self.assertEqual(resolved.execution_order, ("db", "api"))
        cycle = DeploymentDependencyResolver().resolve(
            [{"service_id": "a", "depends_on": ["b"]}, {"service_id": "b", "depends_on": ["a"]}]
        )
        self.assertEqual(cycle.state, FrontierState.REVIEW)
        self.assertIn("a", cycle.cycle_ids)

    def test_privacy_accountant_composes_only_allowed_requests(self) -> None:
        report = FederatedPrivacyAccountant().account(
            [
                {"request_id": "r-1", "site_id": "site-a", "epsilon": 0.4, "delta": 0.01},
                {"request_id": "r-2", "site_id": "site-a", "epsilon": 0.8, "delta": 0.01},
            ],
            epsilon_budget=1.0,
            delta_budget=0.05,
            per_site_epsilon_budget=0.7,
        )
        self.assertEqual(report.allowed_ids, ("r-1",))
        self.assertEqual(report.denied_ids, ("r-2",))

    def test_release_history_preserves_predecessor_chain(self) -> None:
        ledger = ReleaseHistoryLedger()
        first = ledger.append(
            [], release_id="release-1", version="1.0", action="release", result="passed"
        )
        second = ledger.append(
            first.to_dict()["entries"],
            release_id="release-2",
            version="1.1",
            action="release",
            result="passed",
        )
        self.assertTrue(second.valid_chain)
        self.assertEqual(second.current_version, "1.1")


if __name__ == "__main__":
    unittest.main()

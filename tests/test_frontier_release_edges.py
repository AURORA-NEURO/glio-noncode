from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.frontier_data_alpha import FrontierState
from glio_noncode.frontier_end_to_end import (
    DeploymentGovernancePipeline,
    EvidenceLifecyclePipeline,
    ValidationFrontierPipeline,
    WorkbenchQualityPipeline,
)
from glio_noncode.frontier_release_alpha import (
    AccessibilityHumanFactorsLayer,
    DeprecationSupersessionManager,
    GlobalSearchCommandPalette,
    ReleaseRollbackController,
    SignedDossierPublisher,
    StructuredReviewForm,
)
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
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierReleaseEdgeTests(unittest.TestCase):
    def test_high_off_target_candidate_is_reviewed(self) -> None:
        report = OffTargetAlignmentAuditor().audit(
            [
                {
                    "candidate_id": "high",
                    "guide_sequence": "ACGTACGT",
                    "target_sequence": "ACGTACGT",
                    "pam": "NGG",
                    "pam_match": True,
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
            risk_threshold=0.2,
        )
        self.assertEqual(report.review_ids, ("high",))

    def test_context_mismatch_blocks_validation_pipeline(self) -> None:
        other = "GRCh38|glioma|adult|differentiated|core|untreated"
        report = ValidationFrontierPipeline().run(
            {
                "risk_records": [
                    {
                        "target_id": "guide-1",
                        "context_key": other,
                        "on_target_score": 0.9,
                        "off_targets": [],
                    }
                ],
                "package": {"experiments": [{"experiment_id": "exp-1"}]},
            },
            pipeline_id="bad-validation",
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("off_target_risk", report.blocked_stage_ids)

    def test_graph_cycle_propagates_to_evidence_pipeline(self) -> None:
        report = EvidenceLifecyclePipeline().run(
            {
                "nodes": [
                    {"node_id": "a", "context_key": CONTEXT},
                    {"node_id": "b", "context_key": CONTEXT},
                ],
                "edges": [
                    {"source_id": "a", "target_id": "b"},
                    {"source_id": "b", "target_id": "a"},
                ],
                "dossier": {"value": "held"},
                "key_id": "key",
            },
            pipeline_id="cyclic-evidence",
            context_key=CONTEXT,
            signing_secret="secret",
        )
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("graph_integrity", report.blocked_stage_ids)

    def test_supersession_cycle_is_not_active(self) -> None:
        report = DeprecationSupersessionManager().manage(
            [
                {
                    "record_id": "a",
                    "superseded_by": "b",
                    "status": "active",
                    "reason": "replace",
                    "context_key": CONTEXT,
                },
                {
                    "record_id": "b",
                    "superseded_by": "a",
                    "status": "active",
                    "reason": "replace",
                    "context_key": CONTEXT,
                },
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(report.active_ids, ())
        self.assertTrue(any(item.issues for item in report.decisions))

    def test_signed_dossier_rejects_wrong_secret_and_audience(self) -> None:
        publisher = SignedDossierPublisher()
        dossier = publisher.publish(
            {"claim": "claim-1"},
            dossier_id="dossier",
            context_key=CONTEXT,
            key_id="key",
            signing_secret="secret",
            audience=("reviewer",),
        )
        wrong_secret = publisher.verify(
            dossier.to_dict(), signing_secret="wrong", audience="reviewer"
        )
        wrong_audience = publisher.verify(
            dossier.to_dict(), signing_secret="secret", audience="administrator"
        )
        self.assertFalse(wrong_secret.valid_signature)
        self.assertFalse(wrong_audience.audience_allowed)

    def test_incomplete_review_form_and_accessibility_surface_need_review(self) -> None:
        form = StructuredReviewForm().evaluate(
            [{"field_id": "decision", "required": True, "choices": ["accept"]}],
            {},
            form_id="form",
            context_key=CONTEXT,
            reviewer_id="reviewer",
        )
        self.assertFalse(form.valid)
        accessibility = AccessibilityHumanFactorsLayer().evaluate(
            {"keyboard": True}, surface_id="surface"
        )
        self.assertEqual(accessibility.state, FrontierState.REVIEW)
        self.assertGreater(accessibility.fail_count, 0)

    def test_search_type_filter_can_exclude_records(self) -> None:
        report = GlobalSearchCommandPalette().search(
            [
                {"record_id": "claim-1", "record_type": "claim", "title": "EGFR"},
                {"record_id": "sample-1", "record_type": "sample", "title": "EGFR sample"},
            ],
            query="EGFR",
            record_type="claim",
        )
        self.assertEqual(tuple(item.record_id for item in report.results), ("claim-1",))

    def test_human_factors_recovery_without_error_is_invalid(self) -> None:
        report = HumanFactorsScenarioSimulator().simulate(
            [{"event_id": "recover", "event_type": "recover"}],
            scenario_id="bad-recovery",
        )
        self.assertFalse(report.completed)
        self.assertEqual(report.events[0].issue, "recovery_without_error")

    def test_security_scanner_finds_nested_sensitive_and_secret_paths(self) -> None:
        report = SecurityPathScanner().scan(
            {"outer": [{"patient_id": "p-1", "credentials": {"password": "hidden"}}]}
        )
        paths = {item.path for item in report.findings}
        self.assertIn("outer[0].patient_id", paths)
        self.assertIn("outer[0].credentials.password", paths)

    def test_dependency_missing_target_blocks_order(self) -> None:
        report = DeploymentDependencyResolver().resolve(
            [{"service_id": "api", "depends_on": ["missing"]}]
        )
        self.assertEqual(report.execution_order, ("api",))
        self.assertEqual(report.missing_dependencies, ("missing",))
        self.assertEqual(report.state, FrontierState.REVIEW)

    def test_privacy_budget_denial_does_not_consume_budget(self) -> None:
        report = FederatedPrivacyAccountant().account(
            [
                {"request_id": "too-large", "site_id": "site", "epsilon": 2.0, "delta": 0.2},
                {"request_id": "small", "site_id": "site", "epsilon": 0.5, "delta": 0.01},
            ],
            epsilon_budget=1.0,
            delta_budget=0.1,
        )
        self.assertEqual(report.allowed_ids, ("small",))
        self.assertEqual(report.total_epsilon, 0.5)

    def test_release_controller_denies_same_version(self) -> None:
        decision = ReleaseRollbackController().decide(
            release_id="release",
            current_version="1.0",
            requested_version="1.0",
            checks={"tests": True, "integrity": True, "compatibility": True, "policy": True},
        )
        self.assertEqual(decision.state.value, "denied")
        self.assertIn("version_already_current", decision.failed_checks)

    def test_workbench_pipeline_propagates_accessibility_failure(self) -> None:
        report = WorkbenchQualityPipeline().run(
            {
                "form_schema": [],
                "form_response": {},
                "report_sections": [],
                "records": [{"record_id": "r", "title": "query"}],
                "query": "query",
                "accessibility_surface": {"keyboard": True},
                "human_factors_events": [],
            },
            pipeline_id="workbench-edge",
            context_key=CONTEXT,
            reviewer_id="reviewer",
        )
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("accessibility", report.blocked_stage_ids)

    def test_deployment_pipeline_propagates_policy_and_release_failures(self) -> None:
        report = DeploymentGovernancePipeline().run(
            {
                "requests": [
                    {
                        "request_id": "request",
                        "subject_id": "subject",
                        "action": "write",
                        "roles": ["reader"],
                        "context_key": CONTEXT,
                    }
                ],
                "policies": {"read-only": {"actions": ["read"], "roles": ["reader"]}},
                "services": [],
                "privacy_requests": [],
                "epsilon_budget": 1.0,
                "delta_budget": 0.1,
                "deployment": {
                    "artifacts": [
                        {
                            "artifact_id": "api",
                            "version": "1",
                            "digest": "sha256:api",
                            "size_bytes": 1,
                            "required_runtime": "python",
                        }
                    ],
                    "services": [{"service_id": "api"}],
                    "environment_requirements": {},
                },
                "platform": "local",
                "runtime_version": "python",
                "tasks": [],
                "sites": [],
                "privacy_budget": 0,
                "current_version": "1",
                "requested_version": "1",
                "release_checks": {},
            },
            pipeline_id="deployment-edge",
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertIn("security_policy", report.blocked_stage_ids)

    def test_lineage_rejects_missing_source_receipts(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceLineageBuilder().build(
                [{"item_id": "claim-1", "context_key": CONTEXT, "source_addresses": []}],
                context_key=CONTEXT,
            )

    def test_markdown_artifact_contains_declared_columns_and_rows(self) -> None:
        artifact = ReportArtifactRenderer().render(
            [{"id": "claim-1", "state": "supported"}],
            artifact_id="report.md",
            format="markdown",
            columns=("id", "state"),
        )
        self.assertIn("| id | state |", artifact.content)
        self.assertIn("| claim-1 | supported |", artifact.content)

    def test_release_history_invalid_predecessor_is_reviewed(self) -> None:
        report = ReleaseHistoryLedger().append(
            [
                {
                    "sequence": 2,
                    "release_id": "old",
                    "version": "1.0",
                    "action": "release",
                    "result": "passed",
                    "predecessor_address": "sha256:wrong",
                    "entry_address": "sha256:old",
                }
            ],
            release_id="new",
            version="1.1",
            action="release",
            result="passed",
        )
        self.assertFalse(report.valid_chain)
        self.assertEqual(report.state, FrontierState.REVIEW)

    def test_context_mismatch_is_visible_in_graph_audit(self) -> None:
        other = "GRCh38|glioma|adult|differentiated|core|untreated"
        report = EvidenceGraphIntegrityAuditor().audit(
            [{"node_id": "claim-1", "context_key": other}],
            [],
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, FrontierState.REVIEW)
        self.assertTrue(any(issue.code == "graph_node_context_mismatch" for issue in report.issues))

    def test_empty_graph_is_valid_but_empty_lineage_is_not_silent(self) -> None:
        graph = EvidenceGraphIntegrityAuditor().audit([], [], context_key=CONTEXT)
        self.assertEqual(graph.state, FrontierState.ACCEPTED)
        self.assertEqual(graph.node_count, 0)
        self.assertEqual(graph.edge_count, 0)
        self.assertEqual(graph.issues, ())
        with self.assertRaises(ValidationError):
            EvidenceLineageBuilder().build(
                [{"item_id": "claim-1", "context_key": CONTEXT}],
                context_key=CONTEXT,
            )

    def test_markdown_artifact_has_deterministic_address_for_same_rows(self) -> None:
        renderer = ReportArtifactRenderer()
        first = renderer.render(
            [{"id": "claim-1", "state": "review"}],
            artifact_id="report.md",
            format="markdown",
            columns=("id", "state"),
        )
        second = renderer.render(
            [{"id": "claim-1", "state": "review"}],
            artifact_id="report.md",
            format="markdown",
            columns=("id", "state"),
        )
        self.assertEqual(first.content_address, second.content_address)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from glio_noncode.frontier_data_alpha import FrontierState
from glio_noncode.frontier_release_alpha import (
    AccessibilityHumanFactorsLayer,
    AuditReproducibilityBundleBuilder,
    DeprecationSupersessionManager,
    ExperimentPackageExporter,
    ExportReportBuilder,
    FederatedExecutionCoordinator,
    GlobalSearchCommandPalette,
    LocalDeploymentBundleBuilder,
    OffTargetRiskEstimator,
    PrivacySecurityPolicyEngine,
    ReclassificationEngine,
    ReleaseRollbackController,
    ResultIngestionClaimUpdater,
    SignedDossierPublisher,
    StructuredReviewForm,
    ValidationValueOfInformationOptimizer,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierReleaseAlphaTests(unittest.TestCase):
    def test_validation_risk_voi_package_and_claim_ingestion(self) -> None:
        risk = OffTargetRiskEstimator().estimate(
            [
                {
                    "target_id": "guide-1",
                    "context_key": CONTEXT,
                    "on_target_score": 0.9,
                    "off_targets": [{"score": 0.05, "weight": 1.0}],
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(risk.low_risk_ids, ("guide-1",))
        voi = ValidationValueOfInformationOptimizer().optimize(
            [
                {
                    "experiment_id": "exp-1",
                    "cost": 5,
                    "information_gain": 0.8,
                    "risk_reduction": 0.4,
                },
                {
                    "experiment_id": "exp-2",
                    "cost": 20,
                    "information_gain": 0.9,
                    "risk_reduction": 0.2,
                },
            ],
            plan_id="voi-1",
            context_key=CONTEXT,
            budget=10,
        )
        self.assertEqual(voi.selected_ids, ("exp-1",))
        package = ExperimentPackageExporter().export(
            {
                "experiments": [{"experiment_id": "exp-1"}],
                "controls": [{"control_id": "ctrl-1"}],
                "protocols": [{"protocol_id": "protocol-1"}],
            },
            package_id="package-1",
            context_key=CONTEXT,
        )
        self.assertEqual(package.state, FrontierState.PUBLISHED)
        updates = ResultIngestionClaimUpdater().update(
            [{"claim_id": "claim-1", "state": "hypothesis"}],
            [
                {
                    "claim_id": "claim-1",
                    "result_id": "result-1",
                    "claim_state": "supported",
                    "context_key": CONTEXT,
                    "evidence_address": "sha256:evidence",
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(updates.updated_ids, ("claim-1",))

    def test_lifecycle_reclassification_supersession_audit_and_signature(self) -> None:
        reclassification = ReclassificationEngine().reclassify(
            [
                {
                    "claim_id": "claim-1",
                    "classification": "suggestive",
                    "evidence_score": 0.9,
                    "reviewer_ids": ["r-1", "r-2"],
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(reclassification.accepted_ids, ("claim-1",))
        supersession = DeprecationSupersessionManager().manage(
            [
                {
                    "record_id": "claim-1",
                    "status": "active",
                    "reason": "current",
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
        )
        self.assertEqual(supersession.active_ids, ("claim-1",))
        audit = AuditReproducibilityBundleBuilder().build(
            {"evidence": [{"id": "e-1"}], "review": [{"id": "r-1"}], "release": [{"id": "rel-1"}]},
            bundle_id="audit-1",
            context_key=CONTEXT,
        )
        self.assertEqual(audit.state, FrontierState.PUBLISHED)
        publisher = SignedDossierPublisher()
        dossier = publisher.publish(
            {"claim_id": "claim-1", "context_key": CONTEXT},
            dossier_id="dossier-1",
            context_key=CONTEXT,
            key_id="key-1",
            signing_secret="secret",
            audience=("reviewer",),
        )
        verification = publisher.verify(
            dossier.to_dict(), signing_secret="secret", audience="reviewer"
        )
        self.assertTrue(verification.valid_signature)
        self.assertEqual(verification.state.value, "ready")

    def test_workbench_review_report_search_and_accessibility(self) -> None:
        form = StructuredReviewForm().evaluate(
            [
                {
                    "field_id": "decision",
                    "label": "Decision",
                    "required": True,
                    "choices": ["accept", "review"],
                }
            ],
            {"decision": "accept"},
            form_id="form-1",
            context_key=CONTEXT,
            reviewer_id="reviewer-1",
        )
        self.assertTrue(form.valid)
        report = ExportReportBuilder().build(
            [{"section_id": "summary", "title": "Summary", "content": {"claim": "claim-1"}}],
            report_id="report-1",
            context_key=CONTEXT,
            format="markdown",
        )
        self.assertEqual(report.state, FrontierState.PUBLISHED)
        search = GlobalSearchCommandPalette().search(
            [{"record_id": "claim-1", "record_type": "claim", "title": "EGFR enhancer"}],
            query="EGFR",
            commands=("open-claim", "publish-report"),
        )
        self.assertEqual(search.results[0].record_id, "claim-1")
        accessibility = AccessibilityHumanFactorsLayer().evaluate(
            {
                "keyboard": True,
                "label": True,
                "focus_order": True,
                "contrast": True,
                "motion": True,
                "reading_order": True,
            },
            surface_id="review-panel",
        )
        self.assertEqual(accessibility.score, 1.0)

    def test_platform_policy_deployment_federation_and_rollback(self) -> None:
        policy = PrivacySecurityPolicyEngine().evaluate(
            [
                {
                    "request_id": "req-1",
                    "subject_id": "reviewer-1",
                    "action": "read",
                    "roles": ["reviewer"],
                    "context_key": CONTEXT,
                }
            ],
            context_key=CONTEXT,
            policies={"research-read": {"actions": ["read"], "roles": ["reviewer"]}},
        )
        self.assertEqual(policy.allowed_ids, ("req-1",))
        deployment = LocalDeploymentBundleBuilder().build(
            {
                "artifacts": [
                    {
                        "artifact_id": "api",
                        "version": "1.0",
                        "digest": "sha256:api",
                        "size_bytes": 100,
                        "required_runtime": "python3.11",
                    }
                ],
                "services": [{"service_id": "api", "port": 8000}],
                "environment_requirements": {"DATA_ROOT": "local"},
            },
            bundle_id="deploy-1",
            platform="linux-x86_64",
            runtime_version="python3.11",
        )
        self.assertEqual(deployment.state.value, "ready")
        federated = FederatedExecutionCoordinator().coordinate(
            [{"task_id": "task-1", "privacy_cost": 2, "minimum_sample_count": 10}],
            [
                {
                    "site_id": "site-a",
                    "available": True,
                    "sample_count": 20,
                    "supported_contexts": [CONTEXT],
                }
            ],
            plan_id="fed-1",
            context_key=CONTEXT,
            privacy_budget=5,
        )
        self.assertEqual(federated.eligible_task_ids, ("task-1",))
        rollback = ReleaseRollbackController().decide(
            release_id="rel-1",
            current_version="1.0",
            requested_version="0.9",
            action="rollback",
            previous_version="0.9",
            checks={"tests": True, "integrity": True, "compatibility": True, "policy": True},
        )
        self.assertEqual(rollback.state.value, "rolled_back")


if __name__ == "__main__":
    unittest.main()

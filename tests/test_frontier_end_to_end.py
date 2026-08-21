from __future__ import annotations

import unittest

from glio_noncode.frontier_data_alpha import FrontierState
from glio_noncode.frontier_end_to_end import (
    DeploymentGovernancePipeline,
    EvidenceLifecyclePipeline,
    ValidationFrontierPipeline,
    WorkbenchQualityPipeline,
)

CONTEXT = "GRCh38|glioma|adult|stem_like|core|untreated"


class FrontierEndToEndTests(unittest.TestCase):
    def test_validation_pipeline_composes_all_declared_stages(self) -> None:
        report = ValidationFrontierPipeline().run(
            {
                "risk_records": [
                    {
                        "target_id": "guide-1",
                        "context_key": CONTEXT,
                        "on_target_score": 0.9,
                        "off_targets": [{"score": 0.05}],
                    }
                ],
                "voi_records": [
                    {
                        "experiment_id": "exp-1",
                        "cost": 2,
                        "information_gain": 0.8,
                        "risk_reduction": 0.3,
                    }
                ],
                "budget": 5,
                "package": {
                    "context_key": CONTEXT,
                    "experiments": [{"experiment_id": "exp-1"}],
                    "controls": [{"control_id": "ctrl-1"}],
                    "protocols": [{"protocol_id": "p-1"}],
                    "outputs": ["readout"],
                },
                "required_controls": ["ctrl-1"],
                "required_outputs": ["readout"],
                "claims": [{"claim_id": "claim-1", "state": "hypothesis"}],
                "results": [
                    {
                        "claim_id": "claim-1",
                        "result_id": "result-1",
                        "claim_state": "supported",
                        "context_key": CONTEXT,
                        "evidence_address": "sha256:evidence",
                    }
                ],
            },
            pipeline_id="validation-pipeline",
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, FrontierState.ACCEPTED)
        self.assertEqual(len(report.completed_stage_ids), 5)

    def test_evidence_pipeline_composes_integrity_lineage_audit_and_signing(self) -> None:
        report = EvidenceLifecyclePipeline().run(
            {
                "nodes": [{"node_id": "claim-1", "context_key": CONTEXT}],
                "edges": [],
                "lineage": [
                    {
                        "item_id": "claim-1",
                        "context_key": CONTEXT,
                        "source_addresses": ["sha256:source"],
                    }
                ],
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "evidence_score": 0.9,
                        "reviewer_ids": ["r-1", "r-2"],
                        "context_key": CONTEXT,
                    }
                ],
                "supersession": [
                    {
                        "record_id": "claim-1",
                        "status": "active",
                        "reason": "current",
                        "context_key": CONTEXT,
                    }
                ],
                "audit_sections": {
                    "evidence": [{"id": "claim-1"}],
                    "review": [{"id": "r-1"}],
                    "release": [{"id": "release-1"}],
                },
                "dossier": {"claim_id": "claim-1"},
                "key_id": "pipeline-key",
            },
            pipeline_id="evidence-pipeline",
            context_key=CONTEXT,
            signing_secret="secret",
        )
        self.assertEqual(report.state, FrontierState.ACCEPTED)
        self.assertIn("signed_dossier", report.completed_stage_ids)

    def test_workbench_pipeline_composes_review_report_search_and_human_factors(self) -> None:
        report = WorkbenchQualityPipeline().run(
            {
                "form_schema": [{"field_id": "decision", "required": True, "choices": ["accept"]}],
                "form_response": {"decision": "accept"},
                "report_sections": [
                    {"section_id": "summary", "title": "Summary", "content": {"claim": "claim-1"}}
                ],
                "records": [
                    {"record_id": "claim-1", "title": "EGFR enhancer", "record_type": "claim"}
                ],
                "query": "EGFR",
                "commands": ["open-claim"],
                "accessibility_surface": {
                    "keyboard": True,
                    "label": True,
                    "focus_order": True,
                    "contrast": True,
                    "motion": True,
                    "reading_order": True,
                },
                "human_factors_events": [
                    {"event_type": "focus", "target_id": "submit"},
                    {"event_type": "submit"},
                ],
            },
            pipeline_id="workbench-pipeline",
            context_key=CONTEXT,
            reviewer_id="reviewer-1",
        )
        self.assertEqual(report.state, FrontierState.ACCEPTED)

    def test_deployment_pipeline_composes_security_privacy_federation_and_release(self) -> None:
        report = DeploymentGovernancePipeline().run(
            {
                "requests": [
                    {
                        "request_id": "req-1",
                        "subject_id": "reviewer-1",
                        "action": "read",
                        "roles": ["reviewer"],
                        "context_key": CONTEXT,
                    }
                ],
                "policies": {"read": {"actions": ["read"], "roles": ["reviewer"]}},
                "services": [
                    {"service_id": "api", "depends_on": ["db"]},
                    {"service_id": "db", "depends_on": []},
                ],
                "privacy_requests": [
                    {"request_id": "privacy-1", "site_id": "site-a", "epsilon": 0.1, "delta": 0.01}
                ],
                "epsilon_budget": 1.0,
                "delta_budget": 0.1,
                "deployment": {
                    "artifacts": [
                        {
                            "artifact_id": "api",
                            "version": "1.0",
                            "digest": "sha256:api",
                            "size_bytes": 10,
                            "required_runtime": "python3.11",
                        }
                    ],
                    "services": [{"service_id": "api"}],
                    "environment_requirements": {"DATA_ROOT": "local"},
                },
                "platform": "local",
                "runtime_version": "python3.11",
                "tasks": [{"task_id": "task-1", "privacy_cost": 1, "minimum_sample_count": 1}],
                "sites": [
                    {
                        "site_id": "site-a",
                        "available": True,
                        "sample_count": 10,
                        "supported_contexts": [CONTEXT],
                    }
                ],
                "privacy_budget": 5,
                "current_version": "1.0",
                "requested_version": "1.1",
                "release_checks": {
                    "tests": True,
                    "integrity": True,
                    "compatibility": True,
                    "policy": True,
                },
            },
            pipeline_id="deployment-pipeline",
            context_key=CONTEXT,
        )
        self.assertEqual(report.state, FrontierState.ACCEPTED)
        self.assertEqual(len(report.completed_stage_ids), 6)


if __name__ == "__main__":
    unittest.main()

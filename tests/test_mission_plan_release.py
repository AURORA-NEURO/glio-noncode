from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from glio_noncode.mission_plan_release import (
    MISSION_PLAN_RELEASE_MANIFEST_FILE,
    MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS,
    MissionPlanReleaseCheck,
    build_mission_plan_release,
    load_mission_plan_release,
    mission_plan_release_capabilities,
    mission_plan_release_schema,
    verify_mission_plan_release,
    write_mission_plan_release,
)
from glio_noncode.mission_plan_release_diff import (
    diff_mission_plan_releases,
    mission_plan_release_diff_capabilities,
    mission_plan_release_diff_csv,
    mission_plan_release_diff_export_payloads,
    mission_plan_release_diff_json,
    mission_plan_release_diff_markdown,
    mission_plan_release_diff_schema,
)
from glio_noncode.mission_plan_release_query import (
    MissionPlanReleaseQuery,
    mission_plan_release_query_capabilities,
    mission_plan_release_query_csv,
    mission_plan_release_query_export_payloads,
    mission_plan_release_query_json,
    mission_plan_release_query_markdown,
    mission_plan_release_query_schema,
    query_mission_plan_release,
)
from glio_noncode.mission_plan_release_runtime import (
    mission_plan_release_runtime_capabilities,
    mission_plan_release_runtime_json,
    mission_plan_release_runtime_schema,
    run_mission_plan_release_runtime,
)
from glio_noncode.mission_plan_release_observability import (
    build_mission_plan_release_observability,
    mission_plan_release_observability_capabilities,
    mission_plan_release_observability_csv,
    mission_plan_release_observability_export_payloads,
    mission_plan_release_observability_json,
    mission_plan_release_observability_markdown,
    mission_plan_release_observability_schema,
)
from glio_noncode.mission_plan_release_lineage import (
    build_mission_plan_release_lineage,
    mission_plan_release_lineage_capabilities,
    mission_plan_release_lineage_edges_csv,
    mission_plan_release_lineage_export_payloads,
    mission_plan_release_lineage_json,
    mission_plan_release_lineage_markdown,
    mission_plan_release_lineage_nodes_csv,
    mission_plan_release_lineage_schema,
)
from glio_noncode.mission_plan_release_policy import (
    MissionPlanReleasePolicy,
    default_mission_plan_release_policy,
    evaluate_mission_plan_release_policy,
    mission_plan_release_policy_capabilities,
    mission_plan_release_policy_csv,
    mission_plan_release_policy_export_payloads,
    mission_plan_release_policy_json,
    mission_plan_release_policy_markdown,
    mission_plan_release_policy_schema,
)
from glio_noncode.mission_plan_release_catalog import (
    MISSION_PLAN_RELEASE_CATALOG_REQUIRED_ARTIFACTS,
    build_mission_plan_release_catalog,
    load_mission_plan_release_catalog,
    mission_plan_release_catalog_capabilities,
    mission_plan_release_catalog_csv,
    mission_plan_release_catalog_export_payloads,
    mission_plan_release_catalog_json,
    mission_plan_release_catalog_markdown,
    mission_plan_release_catalog_schema,
    verify_mission_plan_release_catalog,
    write_mission_plan_release_catalog,
)
from glio_noncode.mission_plan_release_catalog_query import (
    MissionPlanReleaseCatalogQuery,
    mission_plan_release_catalog_query_capabilities,
    mission_plan_release_catalog_query_csv,
    mission_plan_release_catalog_query_export_payloads,
    mission_plan_release_catalog_query_json,
    mission_plan_release_catalog_query_markdown,
    mission_plan_release_catalog_query_schema,
    query_mission_plan_release_catalog,
)
from glio_noncode.mission_plan_release_catalog_diff import (
    MissionPlanReleaseCatalogDiffStatus,
    diff_mission_plan_release_catalogs,
    mission_plan_release_catalog_diff_capabilities,
    mission_plan_release_catalog_diff_csv,
    mission_plan_release_catalog_diff_export_payloads,
    mission_plan_release_catalog_diff_json,
    mission_plan_release_catalog_diff_markdown,
    mission_plan_release_catalog_diff_schema,
)
from glio_noncode.mission_plan_release_catalog_audit import (
    build_mission_plan_release_catalog_audit,
    mission_plan_release_catalog_audit_capabilities,
    mission_plan_release_catalog_audit_csv,
    mission_plan_release_catalog_audit_export_payloads,
    mission_plan_release_catalog_audit_json,
    mission_plan_release_catalog_audit_markdown,
    mission_plan_release_catalog_audit_schema,
)
from glio_noncode.mission_plan_release_catalog_report import (
    MissionPlanReleaseCatalogReport,
    build_mission_plan_release_catalog_report,
    mission_plan_release_catalog_report_capabilities,
    mission_plan_release_catalog_report_csv,
    mission_plan_release_catalog_report_export_payloads,
    mission_plan_release_catalog_report_json,
    mission_plan_release_catalog_report_markdown,
    mission_plan_release_catalog_report_schema,
)
from glio_noncode.mission_plan_release_catalog_gate import (
    MissionPlanReleaseCatalogGate,
    MissionPlanReleaseCatalogGateCheck,
    MissionPlanReleaseCatalogGatePolicy,
    build_mission_plan_release_catalog_gate,
    mission_plan_release_catalog_gate_capabilities,
    mission_plan_release_catalog_gate_csv,
    mission_plan_release_catalog_gate_export_payloads,
    mission_plan_release_catalog_gate_json,
    mission_plan_release_catalog_gate_markdown,
    mission_plan_release_catalog_gate_schema,
)
from glio_noncode.mission_plan_release_catalog_gate_runtime import (
    MissionPlanReleaseCatalogGateRuntime,
    mission_plan_release_catalog_gate_runtime_capabilities,
    mission_plan_release_catalog_gate_runtime_csv,
    mission_plan_release_catalog_gate_runtime_export_payloads,
    mission_plan_release_catalog_gate_runtime_json,
    mission_plan_release_catalog_gate_runtime_markdown,
    mission_plan_release_catalog_gate_runtime_schema,
    run_mission_plan_release_catalog_gate_runtime,
)
from glio_noncode.mission_plan_release_catalog_gate_packet import (
    MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS,
    build_mission_plan_release_catalog_gate_packet,
    load_mission_plan_release_catalog_gate_packet,
    mission_plan_release_catalog_gate_packet_capabilities,
    mission_plan_release_catalog_gate_packet_schema,
    verify_mission_plan_release_catalog_gate_packet,
    write_mission_plan_release_catalog_gate_packet,
)
from glio_noncode.mission_plan_release_catalog_gate_query import (
    MissionPlanReleaseCatalogGateQuery,
    MissionPlanReleaseCatalogGateQueryResult,
    mission_plan_release_catalog_gate_query_capabilities,
    mission_plan_release_catalog_gate_query_csv,
    mission_plan_release_catalog_gate_query_export_payloads,
    mission_plan_release_catalog_gate_query_json,
    mission_plan_release_catalog_gate_query_markdown,
    mission_plan_release_catalog_gate_query_schema,
    query_mission_plan_release_catalog_gate,
)
from glio_noncode.mission_plan_release_catalog_gate_diff import (
    MissionPlanReleaseCatalogGateDiff,
    MissionPlanReleaseCatalogGateDiffStatus,
    diff_mission_plan_release_catalog_gates,
    mission_plan_release_catalog_gate_diff_capabilities,
    mission_plan_release_catalog_gate_diff_csv,
    mission_plan_release_catalog_gate_diff_export_payloads,
    mission_plan_release_catalog_gate_diff_json,
    mission_plan_release_catalog_gate_diff_markdown,
    mission_plan_release_catalog_gate_diff_schema,
)
from glio_noncode.mission_plan_release_catalog_gate_observability import (
    MissionPlanReleaseCatalogGateObservability,
    build_mission_plan_release_catalog_gate_observability,
    mission_plan_release_catalog_gate_observability_capabilities,
    mission_plan_release_catalog_gate_observability_csv,
    mission_plan_release_catalog_gate_observability_export_payloads,
    mission_plan_release_catalog_gate_observability_json,
    mission_plan_release_catalog_gate_observability_markdown,
    mission_plan_release_catalog_gate_observability_schema,
)
from glio_noncode.mission_plan_public_conformance import (
    conform_mission_plan_public,
    mission_plan_public_conformance_capabilities,
    mission_plan_public_conformance_csv,
    mission_plan_public_conformance_export_payloads,
    mission_plan_public_conformance_json,
    mission_plan_public_conformance_markdown,
    mission_plan_public_conformance_schema,
    mission_plan_public_replay_capabilities,
    mission_plan_public_replay_csv,
    mission_plan_public_replay_export_payloads,
    mission_plan_public_replay_json,
    mission_plan_public_replay_markdown,
    mission_plan_public_replay_schema,
    replay_mission_plan_public,
)
from glio_noncode.mission_runtime_public import build_public_mission_plan


class MissionPlanReleaseTests(unittest.TestCase):
    @staticmethod
    def _payload() -> dict[str, object]:
        return {
            "mission": {
                "mission_id": "release-mission",
                "project_id": "glio-noncode",
                "intended_use": "research hypothesis exploration",
                "requested_question": "Which bounded observations require review?",
                "allowed_data_scopes": ["synthetic", "public_reference"],
            },
            "requested_agent_ids": ["A02"],
            "workflow_id": "release-workflow",
        }

    @classmethod
    def _receipt(cls):
        return build_public_mission_plan(cls._payload())

    @classmethod
    def _changed_receipt(cls):
        return build_public_mission_plan(
            cls._payload()
            | {
                "workflow_steps": [
                    {
                        "step_id": "ingest",
                        "kind": "ingest",
                        "resource": {"cpu": 2, "memory_gb": 1, "storage_gb": 1, "max_seconds": 90},
                        "output_contract": "case_manifest",
                    },
                    {
                        "step_id": "review",
                        "kind": "review",
                        "depends_on": ["ingest"],
                        "optional": True,
                        "output_contract": "reviewable_dossier",
                    },
                ]
            }
        )

    @classmethod
    def _second_receipt(cls):
        return build_public_mission_plan(
            cls._payload()
            | {
                "mission": cls._payload()["mission"]
                | {"mission_id": "second-release-mission"},
                "workflow_id": "second-release-workflow",
            }
        )

    def test_build_is_deterministic_and_closed(self) -> None:
        first = build_mission_plan_release(self._receipt())
        second = build_mission_plan_release(self._receipt())
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertTrue(first.accepted)
        self.assertEqual(first.manifest["artifact_count"], 5)
        self.assertEqual(
            {item.filename for item in first.artifacts},
            set(MISSION_PLAN_RELEASE_REQUIRED_ARTIFACTS),
        )
        self.assertEqual(first.manifest["summary_address"].split(":", 1)[0], "mission-plan-release-summary")
        self.assertEqual(first.manifest["checks_address"].split(":", 1)[0], "mission-plan-release-checks")
        self.assertEqual(first.receipt.content_address, first.plan_address)

    def test_materialize_verify_and_hydrate_without_planner(self) -> None:
        bundle = build_mission_plan_release(self._receipt())
        with tempfile.TemporaryDirectory() as directory:
            root = write_mission_plan_release(bundle, directory)
            self.assertEqual(root, Path(directory))
            verification = verify_mission_plan_release(directory)
            self.assertTrue(verification.accepted, verification.to_dict())
            self.assertEqual(verification.artifact_count, 5)
            self.assertEqual(verification.verified_artifact_count, 5)
            self.assertTrue(verification.exact_bytes)
            self.assertTrue(verification.receipt_address_valid)
            self.assertTrue(verification.checks_valid)
            self.assertTrue(verification.summary_valid)
            offline = load_mission_plan_release(directory)
            self.assertEqual(offline.plan_address, bundle.plan_address)
            self.assertEqual(offline.receipt.to_dict(), bundle.receipt.to_dict())
            self.assertEqual(len(offline.checks), 5)
            self.assertEqual(
                json.loads((Path(directory) / MISSION_PLAN_RELEASE_MANIFEST_FILE).read_text()),
                bundle.manifest,
            )

    def test_verifier_fails_closed_for_tamper_missing_and_extra_files(self) -> None:
        bundle = build_mission_plan_release(self._receipt())
        with tempfile.TemporaryDirectory() as directory:
            write_mission_plan_release(bundle, directory)
            root = Path(directory)
            (root / "mission-plan.md").write_text(
                (root / "mission-plan.md").read_text(encoding="utf-8") + "tampered\n",
                encoding="utf-8",
            )
            verification = verify_mission_plan_release(root)
            self.assertFalse(verification.accepted)
            self.assertIn("mission-plan.md", verification.tampered_files)
            (root / "mission-plan.md").write_bytes(
                next(item.payload for item in bundle.artifacts if item.filename == "mission-plan.md")
            )
            (root / "unexpected.json").write_text("{}", encoding="utf-8")
            verification = verify_mission_plan_release(root)
            self.assertFalse(verification.accepted)
            self.assertIn("unexpected.json", verification.unexpected_files)
            (root / "release-checks.json").unlink()
            verification = verify_mission_plan_release(root)
            self.assertFalse(verification.accepted)
            self.assertIn("release-checks.json", verification.missing_files)

    def test_write_refuses_nonempty_destination_without_explicit_intent(self) -> None:
        bundle = build_mission_plan_release(self._receipt())
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "existing.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(ValueError):
                write_mission_plan_release(bundle, directory)
            self.assertEqual(Path(directory, "existing.txt").read_text(encoding="utf-8"), "keep")

    def test_query_filters_and_pagination_are_stable(self) -> None:
        bundle = build_mission_plan_release(self._receipt())
        with tempfile.TemporaryDirectory() as directory:
            write_mission_plan_release(bundle, directory)
            offline = load_mission_plan_release(directory)
            all_steps = query_mission_plan_release(offline, MissionPlanReleaseQuery(limit=20))
            self.assertEqual(all_steps.total_matches, 8)
            self.assertFalse(all_steps.has_more)
            self.assertEqual(all_steps.steps[0].step_id, "ingest")
            review = query_mission_plan_release(offline, {"kind": "review", "limit": 1})
            self.assertEqual(review.total_matches, 1)
            self.assertEqual(review.steps[0].step_id, "review")
            dependent = query_mission_plan_release(offline, {"depends_on": "review"})
            self.assertEqual([step.step_id for step in dependent.steps], ["export"])
            page = query_mission_plan_release(offline, {"offset": 2, "limit": 3})
            self.assertEqual([step.step_id for step in page.steps], ["context", "evidence", "integrate"])
            self.assertTrue(page.has_more)
            self.assertEqual(
                query_mission_plan_release(offline, {"offset": 2, "limit": 3}).to_dict(),
                page.to_dict(),
            )

    def test_query_exports_and_schema_are_deterministic(self) -> None:
        bundle = build_mission_plan_release(self._receipt())
        with tempfile.TemporaryDirectory() as directory:
            write_mission_plan_release(bundle, directory)
            result = query_mission_plan_release(directory, {"deterministic": True, "limit": 20})
            payloads = mission_plan_release_query_export_payloads(result)
            self.assertEqual(payloads["mission-plan-release-query.json"], mission_plan_release_query_json(result))
            self.assertEqual(payloads["mission-plan-release-query.md"], mission_plan_release_query_markdown(result))
            self.assertEqual(payloads["mission-plan-release-query.csv"], mission_plan_release_query_csv(result))
            self.assertIn("step_id", payloads["mission-plan-release-query.csv"])
            self.assertEqual(json.loads(payloads["mission-plan-release-query.json"]), result.to_dict())
            self.assertEqual(mission_plan_release_query_schema()["query_version"], result.query_version)
            self.assertTrue(mission_plan_release_query_capabilities()["verified_release_input"])

    def test_diff_exposes_structural_and_resource_changes_only(self) -> None:
        left = self._receipt()
        right = self._changed_receipt()
        diff = diff_mission_plan_releases(left, right)
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.workflow_changed)
        self.assertIn("ingest", diff.changed_step_ids)
        self.assertIn("context", diff.removed_step_ids)
        self.assertEqual(diff.resource_delta["total_cpu"], -7.0)
        self.assertNotIn("selected_agent_ids", diff.to_dict())
        self.assertEqual(json.loads(mission_plan_release_diff_json(diff)), diff.to_dict())
        self.assertIn("# Mission plan release diff", mission_plan_release_diff_markdown(diff))
        self.assertIn("step_id", mission_plan_release_diff_csv(diff))
        payloads = mission_plan_release_diff_export_payloads(diff)
        self.assertEqual(payloads["mission-plan-release-diff.json"], mission_plan_release_diff_json(diff))
        self.assertEqual(mission_plan_release_diff_schema()["diff_version"], diff.diff_version)
        self.assertTrue(mission_plan_release_diff_capabilities()["step_level_comparison"])

    def test_diff_accepts_verified_release_directories(self) -> None:
        left_bundle = build_mission_plan_release(self._receipt())
        right_bundle = build_mission_plan_release(self._changed_receipt())
        with tempfile.TemporaryDirectory() as directory:
            left_path = Path(directory) / "left"
            right_path = Path(directory) / "right"
            write_mission_plan_release(left_bundle, left_path)
            write_mission_plan_release(right_bundle, right_path)
            diff = diff_mission_plan_releases(left_path, right_path)
            self.assertEqual(diff.left_release_id, left_bundle.release_id)
            self.assertEqual(diff.right_release_id, right_bundle.release_id)
            self.assertTrue(diff.accepted)

    def test_runtime_records_replayable_stages_with_optional_materialization(self) -> None:
        receipt = self._receipt()
        in_memory = run_mission_plan_release_runtime(receipt)
        self.assertTrue(in_memory.accepted)
        self.assertFalse(in_memory.materialized)
        self.assertEqual([stage.ordinal for stage in in_memory.stages], [1, 2, 3, 4, 5, 6])
        self.assertEqual(in_memory.stages[2].state.value, "skipped")
        self.assertEqual(json.loads(mission_plan_release_runtime_json(in_memory)), in_memory.to_dict())
        with tempfile.TemporaryDirectory() as directory:
            runtime = run_mission_plan_release_runtime(receipt, destination=Path(directory) / "release")
            self.assertTrue(runtime.accepted)
            self.assertTrue(runtime.materialized)
            self.assertIsNotNone(runtime.verification_address)
            self.assertEqual(runtime.stages[2].state.value, "completed")
            self.assertEqual(runtime.stages[3].state.value, "completed")
        self.assertEqual(mission_plan_release_runtime_schema()["runtime_version"], runtime.runtime_version)
        self.assertTrue(mission_plan_release_runtime_capabilities()["independent_filesystem_verification"])

    def test_observability_is_aggregate_deterministic_and_exportable(self) -> None:
        bundle = build_mission_plan_release(self._receipt())
        observability = build_mission_plan_release_observability(bundle)
        repeated = build_mission_plan_release_observability(bundle)
        self.assertEqual(observability.to_dict(), repeated.to_dict())
        self.assertTrue(observability.accepted)
        self.assertEqual(len(observability.metrics), 16)
        metrics = {item.metric_id: item.value for item in observability.metrics}
        self.assertEqual(metrics["workflow.step_count"], 8.0)
        self.assertEqual(metrics["workflow.dependency_depth"], 8.0)
        self.assertEqual(metrics["resources.total_cpu"], 10.0)
        self.assertEqual(metrics["integrity.artifact_count"], 5.0)
        payloads = mission_plan_release_observability_export_payloads(observability)
        self.assertEqual(payloads["mission-plan-release-observability.json"], mission_plan_release_observability_json(observability))
        self.assertEqual(payloads["mission-plan-release-observability.csv"], mission_plan_release_observability_csv(observability))
        self.assertEqual(payloads["mission-plan-release-observability.md"], mission_plan_release_observability_markdown(observability))
        self.assertEqual(json.loads(payloads["mission-plan-release-observability.json"]), observability.to_dict())
        self.assertEqual(mission_plan_release_observability_schema()["observability_version"], observability.observability_version)
        self.assertTrue(mission_plan_release_observability_capabilities()["dependency_depth"])

    def test_lineage_graph_closes_release_receipt_checks_steps_and_artifacts(self) -> None:
        bundle = build_mission_plan_release(self._receipt())
        lineage = build_mission_plan_release_lineage(bundle)
        repeated = build_mission_plan_release_lineage(bundle)
        self.assertEqual(lineage.to_dict(), repeated.to_dict())
        self.assertTrue(lineage.accepted)
        self.assertEqual(len(lineage.nodes), 21)
        self.assertEqual(len(lineage.edges), 31)
        self.assertEqual(lineage.root_node_id, f"release:{bundle.release_id}")
        self.assertEqual(len({item.node_id for item in lineage.nodes}), len(lineage.nodes))
        self.assertEqual(len({item.edge_id for item in lineage.edges}), len(lineage.edges))
        self.assertIn("artifact:mission-plan.json", {item.node_id for item in lineage.nodes})
        self.assertIn("step:ingest", {item.node_id for item in lineage.nodes})
        self.assertIn("check:public-boundary", {item.node_id for item in lineage.nodes})
        payloads = mission_plan_release_lineage_export_payloads(lineage)
        self.assertEqual(payloads["mission-plan-release-lineage.json"], mission_plan_release_lineage_json(lineage))
        self.assertEqual(payloads["mission-plan-release-lineage.md"], mission_plan_release_lineage_markdown(lineage))
        self.assertEqual(payloads["mission-plan-release-lineage-nodes.csv"], mission_plan_release_lineage_nodes_csv(lineage))
        self.assertEqual(payloads["mission-plan-release-lineage-edges.csv"], mission_plan_release_lineage_edges_csv(lineage))
        self.assertIn("node_id", payloads["mission-plan-release-lineage-nodes.csv"])
        self.assertIn("source_node_id", payloads["mission-plan-release-lineage-edges.csv"])
        self.assertEqual(mission_plan_release_lineage_schema()["lineage_version"], lineage.lineage_version)
        self.assertTrue(mission_plan_release_lineage_capabilities()["addressed_edges"])

    def test_contracts_and_check_hydration_reject_bad_shapes(self) -> None:
        self.assertIn("manifest.json", mission_plan_release_schema()["required_files"])
        self.assertTrue(mission_plan_release_capabilities()["tamper_detection"])
        bundle = build_mission_plan_release(self._receipt())
        check = bundle.checks[0]
        self.assertEqual(MissionPlanReleaseCheck.from_mapping(check.to_dict()).to_dict(), check.to_dict())
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCheck.from_mapping(check.to_dict() | {"unexpected": True})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseQuery.from_mapping({"limit": 0})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseQuery.from_mapping({"unknown_filter": True})

    def test_policy_accepts_default_release_and_exports_all_projections(self) -> None:
        bundle = build_mission_plan_release(self._receipt())
        policy = default_mission_plan_release_policy()
        evaluation = evaluate_mission_plan_release_policy(bundle, policy)
        repeated = evaluate_mission_plan_release_policy(bundle, policy)
        self.assertEqual(evaluation.to_dict(), repeated.to_dict())
        self.assertTrue(evaluation.accepted, evaluation.to_dict())
        self.assertEqual(evaluation.passed_check_count, len(evaluation.checks))
        self.assertEqual(evaluation.failed_check_count, 0)
        self.assertEqual(evaluation.policy.policy_id, "default-public-release")
        payloads = mission_plan_release_policy_export_payloads(evaluation)
        self.assertEqual(payloads["mission-plan-release-policy.json"], mission_plan_release_policy_json(evaluation))
        self.assertEqual(payloads["mission-plan-release-policy.csv"], mission_plan_release_policy_csv(evaluation))
        self.assertEqual(payloads["mission-plan-release-policy.md"], mission_plan_release_policy_markdown(evaluation))
        self.assertEqual(json.loads(payloads["mission-plan-release-policy.json"]), evaluation.to_dict())
        self.assertIn("check_id", payloads["mission-plan-release-policy.csv"])
        self.assertIn("# Mission plan release policy evaluation", payloads["mission-plan-release-policy.md"])
        self.assertEqual(mission_plan_release_policy_schema()["policy_version"], evaluation.policy_version)
        self.assertTrue(mission_plan_release_policy_capabilities()["configurable_limits"])

    def test_policy_enforces_workflow_resources_artifacts_and_boundary(self) -> None:
        bundle = build_mission_plan_release(self._receipt())
        strict = MissionPlanReleasePolicy(
            policy_id="strict-review-gate",
            required_step_kinds=("review", "export"),
            forbidden_step_kinds=("network",),
            require_all_deterministic=True,
            fail_on_warnings=True,
            max_step_count=7,
            max_optional_steps=0,
            max_dependency_depth=4,
            max_total_cpu=5,
            max_peak_memory_gb=1,
            max_total_storage_gb=1,
            max_seconds=60,
            minimum_check_count=5,
        )
        evaluation = evaluate_mission_plan_release_policy(bundle, strict)
        self.assertFalse(evaluation.accepted)
        failed = {item.check_id for item in evaluation.checks if not item.passed}
        self.assertEqual(
            failed,
            {
                "workflow.step_count",
                "workflow.dependency_depth",
                "resources.total_cpu",
                "resources.peak_memory_gb",
                "resources.total_storage_gb",
                "resources.max_seconds",
            },
        )
        self.assertNotIn("agent", evaluation.to_dict())
        self.assertNotIn("language", evaluation.to_dict())

    def test_policy_mapping_is_strict_and_restricted(self) -> None:
        parsed = MissionPlanReleasePolicy.from_mapping(
            {
                "policy_id": "bounded",
                "required_step_kinds": ["review"],
                "max_step_count": 8,
                "minimum_check_count": 5,
            }
        )
        self.assertEqual(parsed.required_step_kinds, ("review",))
        self.assertEqual(parsed.max_step_count, 8)
        with self.assertRaises(ValidationError):
            MissionPlanReleasePolicy.from_mapping({"unknown": True})
        with self.assertRaises(ValidationError):
            MissionPlanReleasePolicy.from_mapping({"agent": "forbidden"})
        with self.assertRaises(ValidationError):
            MissionPlanReleasePolicy.from_mapping({"required_step_kinds": ["review", "review"]})
        with self.assertRaises(ValidationError):
            MissionPlanReleasePolicy.from_mapping({"max_seconds": -1})

    def test_catalog_diff_classifies_release_evolution_and_aggregates_deltas(self) -> None:
        left = build_mission_plan_release(self._receipt(), release_id="release-left")
        unchanged = build_mission_plan_release(self._second_receipt(), release_id="release-right")
        changed = build_mission_plan_release(self._changed_receipt(), release_id="release-left")
        left_catalog = build_mission_plan_release_catalog([left, unchanged], catalog_id="catalog-left")
        right_catalog = build_mission_plan_release_catalog([changed], catalog_id="catalog-right")
        diff = diff_mission_plan_release_catalogs(left_catalog, right_catalog)
        repeated = diff_mission_plan_release_catalogs(left_catalog, right_catalog)
        self.assertEqual(diff.to_dict(), repeated.to_dict())
        self.assertTrue(diff.accepted)
        self.assertEqual(diff.added_release_ids, ())
        self.assertEqual(diff.removed_release_ids, ("release-right",))
        self.assertEqual(diff.changed_release_ids, ("release-left",))
        self.assertEqual(diff.unchanged_release_ids, ())
        self.assertEqual(
            {item.release_id: item.status for item in diff.entry_diffs},
            {
                "release-left": MissionPlanReleaseCatalogDiffStatus.CHANGED,
                "release-right": MissionPlanReleaseCatalogDiffStatus.REMOVED,
            },
        )
        self.assertEqual(diff.aggregate_delta["entry_count"], -1)
        self.assertEqual(diff.aggregate_delta["step_count"], -14)
        changed_item = next(item for item in diff.entry_diffs if item.release_id == "release-left")
        self.assertEqual(changed_item.step_count_delta, -6)
        self.assertEqual(json.loads(mission_plan_release_catalog_diff_json(diff)), diff.to_dict())
        self.assertIn("# Mission plan release catalog diff", mission_plan_release_catalog_diff_markdown(diff))
        self.assertIn("release_id", mission_plan_release_catalog_diff_csv(diff))
        payloads = mission_plan_release_catalog_diff_export_payloads(diff)
        self.assertEqual(payloads["mission-plan-release-catalog-diff.json"], mission_plan_release_catalog_diff_json(diff))
        self.assertEqual(mission_plan_release_catalog_diff_schema()["diff_version"], diff.diff_version)
        self.assertTrue(mission_plan_release_catalog_diff_capabilities()["aggregate_deltas"])

    def test_catalog_semantic_audit_reconciles_address_counts_and_boundary(self) -> None:
        bundle = build_mission_plan_release_catalog(
            [
                build_mission_plan_release(self._receipt(), release_id="release-left"),
                build_mission_plan_release(self._second_receipt(), release_id="release-right"),
            ]
        )
        audit = build_mission_plan_release_catalog_audit(bundle)
        repeated = build_mission_plan_release_catalog_audit(bundle.catalog)
        self.assertEqual(audit.to_dict(), repeated.to_dict())
        self.assertTrue(audit.accepted, audit.to_dict())
        self.assertEqual(audit.passed_check_count, len(audit.checks))
        self.assertEqual(audit.failed_check_count, 0)
        self.assertEqual(json.loads(mission_plan_release_catalog_audit_json(audit)), audit.to_dict())
        self.assertIn("check_id", mission_plan_release_catalog_audit_csv(audit))
        self.assertIn("# Mission plan release catalog audit", mission_plan_release_catalog_audit_markdown(audit))
        payloads = mission_plan_release_catalog_audit_export_payloads(audit)
        self.assertEqual(payloads["mission-plan-release-catalog-audit.json"], mission_plan_release_catalog_audit_json(audit))
        self.assertTrue(mission_plan_release_catalog_audit_capabilities()["entry_address_reconstruction"])
        self.assertEqual(mission_plan_release_catalog_audit_schema()["audit_version"], audit.audit_version)

    def test_catalog_builds_stably_from_multiple_public_releases(self) -> None:
        left = build_mission_plan_release(self._receipt(), release_id="release-left")
        right = build_mission_plan_release(self._second_receipt(), release_id="release-right")
        first = build_mission_plan_release_catalog([right, left], catalog_id="research-catalog")
        second = build_mission_plan_release_catalog([left, right], catalog_id="research-catalog")
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertTrue(first.accepted, first.to_dict())
        self.assertEqual(first.catalog.entry_count, 2)
        self.assertEqual(first.catalog.accepted_entry_count, 2)
        self.assertEqual(
            [item.release_id for item in first.catalog.entries],
            ["release-left", "release-right"],
        )
        self.assertEqual(
            {item.filename for item in first.artifacts},
            set(MISSION_PLAN_RELEASE_CATALOG_REQUIRED_ARTIFACTS),
        )
        self.assertEqual(first.manifest["artifact_count"], 6)
        self.assertEqual(len(first.checks), 5)
        self.assertEqual(
            json.loads(mission_plan_release_catalog_json(first.catalog)),
            first.catalog.to_dict(),
        )
        payloads = mission_plan_release_catalog_export_payloads(first.catalog)
        self.assertEqual(payloads["mission-plan-release-catalog.json"], mission_plan_release_catalog_json(first.catalog))
        self.assertEqual(payloads["mission-plan-release-catalog.csv"], mission_plan_release_catalog_csv(first.catalog))
        self.assertEqual(payloads["mission-plan-release-catalog.md"], mission_plan_release_catalog_markdown(first.catalog))
        self.assertIn("release_id", payloads["mission-plan-release-catalog.csv"])
        self.assertIn("# Mission plan release catalog", payloads["mission-plan-release-catalog.md"])
        self.assertEqual(mission_plan_release_catalog_schema()["catalog_version"], first.catalog.catalog_version)
        self.assertTrue(mission_plan_release_catalog_capabilities()["multi_release_inventory"])

    def test_catalog_materialization_verification_and_offline_hydration(self) -> None:
        left = build_mission_plan_release(self._receipt(), release_id="release-left")
        right = build_mission_plan_release(self._second_receipt(), release_id="release-right")
        bundle = build_mission_plan_release_catalog([left, right])
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "catalog"
            self.assertEqual(write_mission_plan_release_catalog(bundle, destination), destination)
            verification = verify_mission_plan_release_catalog(destination)
            self.assertTrue(verification.accepted, verification.to_dict())
            self.assertTrue(verification.manifest_address_valid)
            self.assertTrue(verification.catalog_address_valid)
            self.assertTrue(verification.checks_address_valid)
            self.assertTrue(verification.summary_address_valid)
            self.assertTrue(verification.exact_bytes)
            self.assertEqual(verification.artifact_count, 6)
            self.assertEqual(verification.verified_artifact_count, 5)
            offline = load_mission_plan_release_catalog(destination)
            self.assertEqual(offline.catalog_id, bundle.catalog_id)
            self.assertEqual(offline.catalog.to_dict(), bundle.catalog.to_dict())
            self.assertEqual(len(offline.checks), 5)
            self.assertTrue(offline.accepted)

    def test_catalog_verifier_rejects_tamper_missing_extra_and_duplicates(self) -> None:
        left = build_mission_plan_release(self._receipt(), release_id="release-left")
        right = build_mission_plan_release(self._second_receipt(), release_id="release-right")
        bundle = build_mission_plan_release_catalog([left, right])
        with tempfile.TemporaryDirectory() as directory:
            destination = write_mission_plan_release_catalog(bundle, Path(directory) / "catalog")
            (destination / "mission-plan-release-catalog.csv").write_text("tampered\n", encoding="utf-8")
            verification = verify_mission_plan_release_catalog(destination)
            self.assertFalse(verification.accepted)
            self.assertIn("mission-plan-release-catalog.csv", verification.tampered_files)
            (destination / "mission-plan-release-catalog.csv").write_bytes(
                next(item.payload for item in bundle.artifacts if item.filename == "mission-plan-release-catalog.csv")
            )
            (destination / "extra.json").write_text("{}", encoding="utf-8")
            verification = verify_mission_plan_release_catalog(destination)
            self.assertFalse(verification.accepted)
            self.assertIn("extra.json", verification.unexpected_files)
            (destination / "extra.json").unlink()
            (destination / "catalog-summary.json").unlink()
            verification = verify_mission_plan_release_catalog(destination)
            self.assertFalse(verification.accepted)
            self.assertIn("catalog-summary.json", verification.missing_files)
        with self.assertRaises(ValidationError):
            build_mission_plan_release_catalog([left, left])

    def test_catalog_query_filters_pagination_and_exports_are_stable(self) -> None:
        left = build_mission_plan_release(self._receipt(), release_id="release-left")
        right = build_mission_plan_release(self._second_receipt(), release_id="release-right")
        bundle = build_mission_plan_release_catalog([left, right])
        all_entries = query_mission_plan_release_catalog(bundle, {"limit": 10})
        self.assertEqual(all_entries.total_matches, 2)
        self.assertEqual([item.release_id for item in all_entries.entries], ["release-left", "release-right"])
        selected = query_mission_plan_release_catalog(
            bundle,
            {"release_id": "release-right", "workflow_kind": "review", "limit": 1},
        )
        self.assertEqual(selected.total_matches, 1)
        self.assertEqual(selected.entries[0].release_id, "release-right")
        page = query_mission_plan_release_catalog(bundle, {"offset": 1, "limit": 1})
        self.assertEqual(page.entries[0].release_id, "release-right")
        self.assertFalse(page.has_more)
        payloads = mission_plan_release_catalog_query_export_payloads(page)
        self.assertEqual(payloads["mission-plan-release-catalog-query.json"], mission_plan_release_catalog_query_json(page))
        self.assertEqual(payloads["mission-plan-release-catalog-query.csv"], mission_plan_release_catalog_query_csv(page))
        self.assertEqual(payloads["mission-plan-release-catalog-query.md"], mission_plan_release_catalog_query_markdown(page))
        self.assertEqual(json.loads(payloads["mission-plan-release-catalog-query.json"]), page.to_dict())
        self.assertEqual(mission_plan_release_catalog_query_schema()["query_version"], page.query_version)
        self.assertTrue(mission_plan_release_catalog_query_capabilities()["workflow_kind_filter"])
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogQuery.from_mapping({"limit": 0})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogQuery.from_mapping({"unknown": True})

    def test_public_conformance_reconciles_address_shape_workflow_and_resources(self) -> None:
        receipt = self._receipt()
        report = conform_mission_plan_public(receipt)
        repeated = conform_mission_plan_public(receipt)
        self.assertEqual(report.to_dict(), repeated.to_dict())
        self.assertTrue(report.accepted, report.to_dict())
        self.assertEqual(report.passed_check_count, len(report.checks))
        self.assertEqual(report.failed_check_count, 0)
        payloads = mission_plan_public_conformance_export_payloads(report)
        self.assertEqual(payloads["mission-plan-public-conformance.json"], mission_plan_public_conformance_json(report))
        self.assertEqual(payloads["mission-plan-public-conformance.csv"], mission_plan_public_conformance_csv(report))
        self.assertEqual(payloads["mission-plan-public-conformance.md"], mission_plan_public_conformance_markdown(report))
        self.assertEqual(json.loads(payloads["mission-plan-public-conformance.json"]), report.to_dict())
        self.assertEqual(mission_plan_public_conformance_schema()["conformance_version"], report.conformance_version)
        self.assertTrue(mission_plan_public_conformance_capabilities()["resource_reconciliation"])
        self.assertNotIn("agent", report.to_dict())
        self.assertNotIn("language", report.to_dict())

    def test_public_conformance_rejects_wrong_expected_address_and_replay_is_deterministic(self) -> None:
        receipt = self._receipt()
        wrong = conform_mission_plan_public(receipt, expected_plan_address="mission-plan-public:wrong")
        self.assertFalse(wrong.accepted)
        self.assertIn("receipt.address", {item.check_id for item in wrong.checks if not item.accepted})
        replay = replay_mission_plan_public(receipt)
        repeated = replay_mission_plan_public(receipt)
        self.assertEqual(replay.to_dict(), repeated.to_dict())
        self.assertTrue(replay.accepted, replay.to_dict())
        self.assertEqual([item.ordinal for item in replay.stages], [1, 2, 3, 4, 5, 6])
        self.assertEqual(replay.completed_stage_count, 6)
        self.assertEqual(replay.failed_stage_count, 0)
        self.assertTrue(all(item.state.value == "completed" for item in replay.stages))
        payloads = mission_plan_public_replay_export_payloads(replay)
        self.assertEqual(payloads["mission-plan-public-replay.json"], mission_plan_public_replay_json(replay))
        self.assertEqual(payloads["mission-plan-public-replay.csv"], mission_plan_public_replay_csv(replay))
        self.assertEqual(payloads["mission-plan-public-replay.md"], mission_plan_public_replay_markdown(replay))
        self.assertEqual(json.loads(payloads["mission-plan-public-replay.json"]), replay.to_dict())
        self.assertEqual(mission_plan_public_replay_schema()["replay_version"], replay.replay_version)
        self.assertTrue(mission_plan_public_replay_capabilities()["stage_addressing"])

    def test_catalog_report_conserves_distributions_and_exports(self) -> None:
        left = build_mission_plan_release(self._receipt(), release_id="release-left")
        right = build_mission_plan_release(self._second_receipt(), release_id="release-right")
        bundle = build_mission_plan_release_catalog([left, right], catalog_id="report-catalog")
        report = build_mission_plan_release_catalog_report(bundle)
        repeated = build_mission_plan_release_catalog_report(bundle.catalog.to_dict())
        self.assertEqual(report.to_dict(), repeated.to_dict())
        self.assertTrue(report.accepted, report.to_dict())
        self.assertEqual(report.entry_count, 2)
        self.assertEqual(report.accepted_entry_count + report.rejected_entry_count, report.entry_count)
        self.assertEqual(sum(report.state_counts.values()), report.entry_count)
        self.assertEqual(sum(report.decision_counts.values()), report.entry_count)
        self.assertEqual(sum(report.workflow_counts.values()), report.workflow_kind_count)
        self.assertGreaterEqual(report.total_step_count, report.total_optional_step_count)
        self.assertGreaterEqual(report.total_step_count, report.total_deterministic_step_count)
        self.assertGreaterEqual(report.total_step_count, report.total_network_step_count)
        self.assertTrue(report.content_address.startswith("mission-plan-release-catalog-report:"))
        self.assertTrue(
            all(item.content_address.startswith("mission-plan-release-catalog-report-bucket:") for item in report.state_buckets)
        )
        payloads = mission_plan_release_catalog_report_export_payloads(report)
        self.assertEqual(json.loads(payloads["mission-plan-release-catalog-report.json"]), report.to_dict())
        self.assertEqual(payloads["mission-plan-release-catalog-report.json"], mission_plan_release_catalog_report_json(report))
        self.assertIn("bucket_kind", mission_plan_release_catalog_report_csv(report))
        self.assertIn("# Mission plan release catalog report", mission_plan_release_catalog_report_markdown(report))
        hydrated = MissionPlanReleaseCatalogReport.from_mapping(json.loads(payloads["mission-plan-release-catalog-report.json"]))
        self.assertEqual(hydrated.to_dict(), report.to_dict())
        self.assertEqual(mission_plan_release_catalog_report_schema()["share_unit"], "basis_points")
        self.assertTrue(mission_plan_release_catalog_report_capabilities()["address_reconstruction"])
        self.assertFalse(mission_plan_release_catalog_report_capabilities()["handler_execution"])

    def test_catalog_report_accepts_verified_offline_catalog_and_rejects_tamper(self) -> None:
        bundle = build_mission_plan_release_catalog(
            [build_mission_plan_release(self._receipt(), release_id="release-left")]
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = write_mission_plan_release_catalog(bundle, Path(directory) / "catalog")
            report = build_mission_plan_release_catalog_report(destination)
            self.assertEqual(report.catalog_address, bundle.catalog.content_address)
            payload = report.to_dict()
            payload["total_step_count"] = report.total_step_count + 1
            with self.assertRaises(ValidationError):
                MissionPlanReleaseCatalogReport.from_mapping(payload)
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogReport.from_mapping(report.to_dict() | {"unexpected": True})

    def test_catalog_gate_is_addressed_policy_complete_and_failure_visible(self) -> None:
        left = build_mission_plan_release(self._receipt(), release_id="release-left")
        right = build_mission_plan_release(self._second_receipt(), release_id="release-right")
        catalog = build_mission_plan_release_catalog([left, right], catalog_id="gate-catalog").catalog
        gate = build_mission_plan_release_catalog_gate(catalog)
        repeated = build_mission_plan_release_catalog_gate(catalog.to_dict())
        self.assertEqual(gate.to_dict(), repeated.to_dict())
        self.assertTrue(gate.accepted, gate.to_dict())
        self.assertEqual(gate.failed_check_ids, ())
        self.assertEqual(gate.passed_check_count, len(gate.checks))
        self.assertGreaterEqual(len(gate.checks), 15)
        self.assertEqual(gate.catalog_address, catalog.content_address)
        self.assertEqual(gate.policy.content_address.split(":", 1)[0], "mission-plan-release-catalog-gate-policy")
        self.assertEqual(json.loads(mission_plan_release_catalog_gate_json(gate)), gate.to_dict())
        self.assertIn("check_id", mission_plan_release_catalog_gate_csv(gate))
        self.assertIn("# Mission plan release catalog gate", mission_plan_release_catalog_gate_markdown(gate))
        payloads = mission_plan_release_catalog_gate_export_payloads(gate)
        self.assertEqual(payloads["mission-plan-release-catalog-gate.json"], mission_plan_release_catalog_gate_json(gate))
        self.assertEqual(mission_plan_release_catalog_gate_schema()["gate_version"], gate.gate_version)
        self.assertTrue(mission_plan_release_catalog_gate_capabilities()["failure_visibility"])
        hydrated = MissionPlanReleaseCatalogGate.from_mapping(gate.to_dict())
        self.assertEqual(hydrated.to_dict(), gate.to_dict())

        failure_policies = (
            {"minimum_entry_count": 3},
            {"maximum_entry_count": 1},
            {"require_all_accepted": True, "maximum_total_step_count": 0},
            {"required_states": ["missing-state"]},
            {"required_decisions": ["missing-decision"]},
            {"required_workflow_kinds": ["missing-workflow"]},
            {"maximum_total_artifact_count": 0},
            {"maximum_total_check_count": 0},
        )
        for policy in failure_policies:
            failed = build_mission_plan_release_catalog_gate(catalog, policy)
            self.assertFalse(failed.accepted, failed.to_dict())
            self.assertTrue(failed.failed_check_ids, failed.to_dict())
            self.assertEqual(
                failed.failed_check_count,
                len([item for item in failed.checks if not item.accepted]),
            )
            self.assertEqual(
                MissionPlanReleaseCatalogGate.from_mapping(failed.to_dict()).to_dict(),
                failed.to_dict(),
            )

        no_composed_evidence = build_mission_plan_release_catalog_gate(
            catalog,
            {
                "minimum_entry_count": 0,
                "require_all_accepted": False,
                "require_catalog_audit": False,
                "require_catalog_report": False,
            },
        )
        self.assertTrue(no_composed_evidence.accepted, no_composed_evidence.to_dict())
        self.assertIsNone(no_composed_evidence.report_address)
        self.assertIsNone(no_composed_evidence.audit_address)
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGatePolicy.from_mapping({"required_states": ["z", "z"]})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGatePolicy.from_mapping({"language": "forbidden"})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGatePolicy.from_mapping({"minimum_entry_count": 4, "maximum_entry_count": 2})
        too_many_required_checks = MissionPlanReleaseCatalogGatePolicy.from_mapping({"minimum_gate_check_count": 33})
        self.assertFalse(build_mission_plan_release_catalog_gate(catalog, too_many_required_checks).accepted)

    def test_catalog_gate_runtime_replays_every_stage_without_handlers(self) -> None:
        catalog = build_mission_plan_release_catalog(
            [
                build_mission_plan_release(self._receipt(), release_id="release-left"),
                build_mission_plan_release(self._second_receipt(), release_id="release-right"),
            ],
            catalog_id="runtime-catalog",
        ).catalog
        runtime = run_mission_plan_release_catalog_gate_runtime(catalog)
        repeated = run_mission_plan_release_catalog_gate_runtime(catalog.to_dict())
        self.assertEqual(runtime.to_dict(), repeated.to_dict())
        self.assertTrue(runtime.accepted, runtime.to_dict())
        self.assertEqual(runtime.completed_stage_count, 6)
        self.assertEqual(runtime.failed_stage_count, 0)
        self.assertEqual([stage.ordinal for stage in runtime.stages], [1, 2, 3, 4, 5, 6])
        self.assertEqual(runtime.replay_first_address, runtime.replay_second_address)
        self.assertTrue(runtime.replay_deterministic)
        self.assertEqual(
            MissionPlanReleaseCatalogGateRuntime.from_mapping(runtime.to_dict()).to_dict(),
            runtime.to_dict(),
        )
        self.assertEqual(
            json.loads(mission_plan_release_catalog_gate_runtime_json(runtime)),
            runtime.to_dict(),
        )
        self.assertIn("stage_id", mission_plan_release_catalog_gate_runtime_csv(runtime))
        self.assertIn("# Mission plan release catalog gate runtime", mission_plan_release_catalog_gate_runtime_markdown(runtime))
        payloads = mission_plan_release_catalog_gate_runtime_export_payloads(runtime)
        self.assertEqual(
            payloads["mission-plan-release-catalog-gate-runtime.json"],
            mission_plan_release_catalog_gate_runtime_json(runtime),
        )
        self.assertEqual(mission_plan_release_catalog_gate_runtime_schema()["max_stages"], 8)
        self.assertTrue(mission_plan_release_catalog_gate_runtime_capabilities()["timestamp_free_replay"])

        failed = run_mission_plan_release_catalog_gate_runtime(catalog, {"minimum_entry_count": 4})
        self.assertFalse(failed.accepted, failed.to_dict())
        self.assertEqual(failed.failed_stage_count, 2)
        self.assertEqual(failed.stages[1].state.value, "completed")
        self.assertEqual(failed.stages[3].state.value, "failed")
        self.assertEqual(failed.stages[5].state.value, "failed")
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateRuntime.from_mapping(runtime.to_dict() | {"accepted": "true"})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateRuntime.from_mapping(runtime.to_dict() | {"stage_count": 99})

    def test_catalog_gate_packet_is_portable_exact_byte_and_closed(self) -> None:
        catalog = build_mission_plan_release_catalog(
            [build_mission_plan_release(self._receipt(), release_id="release-left")],
            catalog_id="packet-catalog",
        ).catalog
        packet = build_mission_plan_release_catalog_gate_packet(catalog, packet_id="packet-one")
        repeated = build_mission_plan_release_catalog_gate_packet(catalog, packet_id="packet-one")
        self.assertEqual(packet.to_dict(), repeated.to_dict())
        self.assertTrue(packet.accepted, packet.to_dict())
        self.assertEqual(
            {item.filename for item in packet.artifacts},
            set(MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS),
        )
        self.assertEqual(packet.manifest["artifact_count"], 8)
        self.assertEqual(len(packet.artifacts), 8)
        self.assertNotIn("agent", packet.to_dict())
        self.assertNotIn("language", packet.to_dict())
        self.assertTrue(mission_plan_release_catalog_gate_packet_schema()["exact_utf8_bytes"])
        self.assertTrue(mission_plan_release_catalog_gate_packet_capabilities()["tamper_detection"])
        with tempfile.TemporaryDirectory() as directory:
            destination = write_mission_plan_release_catalog_gate_packet(packet, Path(directory) / "packet")
            verification = verify_mission_plan_release_catalog_gate_packet(destination)
            self.assertTrue(verification.accepted, verification.to_dict())
            self.assertTrue(verification.manifest_address_valid)
            self.assertTrue(verification.catalog_address_valid)
            self.assertTrue(verification.gate_address_valid)
            self.assertTrue(verification.report_address_valid)
            self.assertTrue(verification.audit_address_valid)
            self.assertTrue(verification.runtime_address_valid)
            self.assertTrue(verification.summary_address_valid)
            self.assertTrue(verification.exact_bytes)
            self.assertEqual(verification.artifact_count, 8)
            self.assertEqual(verification.verified_artifact_count, 7)
            offline = load_mission_plan_release_catalog_gate_packet(destination)
            self.assertTrue(offline.accepted)
            self.assertEqual(offline.packet_id, "packet-one")
            self.assertEqual(offline.catalog.to_dict(), catalog.to_dict())
            self.assertEqual(offline.gate.to_dict(), packet.gate.to_dict())
            self.assertEqual(offline.verification.to_dict(), verification.to_dict())

            gate_bytes = (destination / "catalog-gate.json").read_bytes()
            (destination / "catalog-gate.json").write_bytes(gate_bytes + b" ")
            tampered = verify_mission_plan_release_catalog_gate_packet(destination)
            self.assertFalse(tampered.accepted)
            self.assertIn("catalog-gate.json", tampered.tampered_files)
            (destination / "catalog-gate.json").write_bytes(gate_bytes)

            (destination / "catalog-gate-summary.json").unlink()
            missing = verify_mission_plan_release_catalog_gate_packet(destination)
            self.assertFalse(missing.accepted)
            self.assertIn("catalog-gate-summary.json", missing.missing_files)
            (destination / "catalog-gate-summary.json").write_bytes(
                next(item.payload for item in packet.artifacts if item.filename == "catalog-gate-summary.json")
            )

            extra = destination / "extra.json"
            extra.write_text("{}", encoding="utf-8")
            unexpected = verify_mission_plan_release_catalog_gate_packet(destination)
            self.assertFalse(unexpected.accepted)
            self.assertIn("extra.json", unexpected.unexpected_files)
            extra.unlink()

            with self.assertRaises(ValidationError):
                write_mission_plan_release_catalog_gate_packet(packet, destination)
            self.assertEqual(write_mission_plan_release_catalog_gate_packet(packet, destination, allow_existing=True), destination)
            (destination / "manifest.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                load_mission_plan_release_catalog_gate_packet(destination)

    def test_catalog_gate_query_is_bounded_filterable_and_round_trippable(self) -> None:
        catalog = build_mission_plan_release_catalog(
            [
                build_mission_plan_release(self._receipt(), release_id="release-left"),
                build_mission_plan_release(self._second_receipt(), release_id="release-right"),
            ],
            catalog_id="query-catalog",
        ).catalog
        gate = build_mission_plan_release_catalog_gate(catalog, {"required_workflow_kinds": ["missing-workflow"]})
        all_checks = query_mission_plan_release_catalog_gate(gate, {"limit": 200})
        self.assertEqual(all_checks.total_matches, len(gate.checks))
        self.assertEqual(len(all_checks.checks), len(gate.checks))
        self.assertFalse(all_checks.has_more)
        failed = query_mission_plan_release_catalog_gate(gate, {"accepted": False, "limit": 2})
        self.assertEqual(failed.total_matches, 1)
        self.assertEqual(len(failed.checks), 1)
        self.assertEqual(failed.checks[0].check_id, "policy.required_workflow.missing-workflow")
        coverage = query_mission_plan_release_catalog_gate(gate, {"category": "coverage", "limit": 10})
        self.assertEqual(coverage.total_matches, 1)
        text_match = query_mission_plan_release_catalog_gate(gate, {"text": "workflow", "limit": 10})
        self.assertGreaterEqual(text_match.total_matches, 1)
        page = query_mission_plan_release_catalog_gate(gate, {"offset": 1, "limit": 2})
        self.assertEqual(page.checks, gate.checks[1:3])
        self.assertTrue(page.has_more)
        self.assertEqual(
            MissionPlanReleaseCatalogGateQueryResult.from_mapping(page.to_dict()).to_dict(),
            page.to_dict(),
        )
        self.assertEqual(json.loads(mission_plan_release_catalog_gate_query_json(page)), page.to_dict())
        self.assertIn("check_id", mission_plan_release_catalog_gate_query_csv(page))
        self.assertIn("# Mission plan release catalog gate query", mission_plan_release_catalog_gate_query_markdown(page))
        payloads = mission_plan_release_catalog_gate_query_export_payloads(page)
        self.assertEqual(payloads["mission-plan-release-catalog-gate-query.json"], mission_plan_release_catalog_gate_query_json(page))
        self.assertEqual(mission_plan_release_catalog_gate_query_schema()["max_limit"], 200)
        self.assertTrue(mission_plan_release_catalog_gate_query_capabilities()["bounded_pagination"])
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateQuery.from_mapping({"limit": 0})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateQuery.from_mapping({"offset": 100001})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateQuery.from_mapping({"accepted": "false"})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateQueryResult.from_mapping(page.to_dict() | {"content_address": "wrong"})

        with tempfile.TemporaryDirectory() as directory:
            packet = build_mission_plan_release_catalog_gate_packet(catalog, {"required_workflow_kinds": ["missing-workflow"]})
            destination = write_mission_plan_release_catalog_gate_packet(packet, Path(directory) / "packet")
            from_disk = query_mission_plan_release_catalog_gate(destination, {"accepted": False})
            self.assertEqual(from_disk.to_dict(), query_mission_plan_release_catalog_gate(packet, {"accepted": False}).to_dict())

    def test_catalog_gate_diff_retains_check_transitions_and_policy_changes(self) -> None:
        catalog = build_mission_plan_release_catalog(
            [build_mission_plan_release(self._receipt(), release_id="release-left")],
            catalog_id="diff-catalog",
        ).catalog
        accepted_gate = build_mission_plan_release_catalog_gate(catalog)
        rejected_gate = build_mission_plan_release_catalog_gate(catalog, {"required_workflow_kinds": ["missing-workflow"]})
        diff = diff_mission_plan_release_catalog_gates(accepted_gate, rejected_gate)
        repeated = diff_mission_plan_release_catalog_gates(accepted_gate.to_dict(), rejected_gate.to_dict())
        self.assertEqual(diff.to_dict(), repeated.to_dict())
        self.assertTrue(diff.accepted)
        self.assertTrue(diff.acceptance_changed)
        self.assertTrue(diff.policy_changed)
        self.assertIn("policy.required_workflow.missing-workflow", diff.added_check_ids)
        added = next(item for item in diff.check_diffs if item.check_id == "policy.required_workflow.missing-workflow")
        self.assertIs(added.status, MissionPlanReleaseCatalogGateDiffStatus.ADDED)
        self.assertTrue(diff.unchanged_check_ids)
        self.assertEqual(
            set(diff.added_check_ids) | set(diff.removed_check_ids) | set(diff.changed_check_ids) | set(diff.unchanged_check_ids),
            {item.check_id for item in diff.check_diffs},
        )
        self.assertEqual(
            MissionPlanReleaseCatalogGateDiff.from_mapping(diff.to_dict()).to_dict(),
            diff.to_dict(),
        )
        self.assertEqual(json.loads(mission_plan_release_catalog_gate_diff_json(diff)), diff.to_dict())
        self.assertIn("check_id", mission_plan_release_catalog_gate_diff_csv(diff))
        self.assertIn("# Mission plan release catalog gate diff", mission_plan_release_catalog_gate_diff_markdown(diff))
        payloads = mission_plan_release_catalog_gate_diff_export_payloads(diff)
        self.assertEqual(payloads["mission-plan-release-catalog-gate-diff.json"], mission_plan_release_catalog_gate_diff_json(diff))
        self.assertEqual(mission_plan_release_catalog_gate_diff_schema()["diff_version"], diff.diff_version)
        self.assertTrue(mission_plan_release_catalog_gate_diff_capabilities()["acceptance_transition"])
        unchanged = diff_mission_plan_release_catalog_gates(accepted_gate, accepted_gate)
        self.assertFalse(unchanged.acceptance_changed)
        self.assertFalse(unchanged.policy_changed)
        self.assertEqual(unchanged.changed_check_ids, ())
        self.assertEqual(len(unchanged.unchanged_check_ids), len(accepted_gate.checks))
        with self.assertRaises(ValidationError):
            diff_mission_plan_release_catalog_gates(
                accepted_gate,
                build_mission_plan_release_catalog_gate(
                    build_mission_plan_release_catalog([build_mission_plan_release(self._receipt(), release_id="release-left")], catalog_id="other-catalog").catalog,
                ),
            )

    def test_catalog_gate_observability_conserves_aggregate_metrics(self) -> None:
        catalog = build_mission_plan_release_catalog(
            [
                build_mission_plan_release(self._receipt(), release_id="release-left"),
                build_mission_plan_release(self._second_receipt(), release_id="release-right"),
            ],
            catalog_id="observability-catalog",
        ).catalog
        gate = build_mission_plan_release_catalog_gate(catalog)
        runtime = run_mission_plan_release_catalog_gate_runtime(catalog)
        observability = build_mission_plan_release_catalog_gate_observability(gate, runtime)
        repeated = build_mission_plan_release_catalog_gate_observability(gate.to_dict(), runtime.to_dict())
        self.assertEqual(observability.to_dict(), repeated.to_dict())
        self.assertTrue(observability.accepted, observability.to_dict())
        self.assertEqual(observability.metric_count, len(observability.metrics))
        self.assertEqual(
            MissionPlanReleaseCatalogGateObservability.from_mapping(observability.to_dict()).to_dict(),
            observability.to_dict(),
        )
        metric_values = {item.metric_id: item.value for item in observability.metrics}
        self.assertEqual(metric_values["gate.checks.total"], len(gate.checks))
        self.assertEqual(metric_values["gate.checks.accepted"], gate.passed_check_count)
        self.assertEqual(metric_values["gate.checks.failed"], gate.failed_check_count)
        self.assertEqual(metric_values["runtime.stages.total"], len(runtime.stages))
        self.assertEqual(metric_values["runtime.stages.completed"], runtime.completed_stage_count)
        self.assertEqual(metric_values["runtime.stages.failed"], runtime.failed_stage_count)
        for category in {item.category for item in gate.checks}:
            self.assertEqual(
                metric_values[f"checks.{category}.total"],
                metric_values[f"checks.{category}.accepted"] + metric_values[f"checks.{category}.failed"],
            )
        self.assertEqual(json.loads(mission_plan_release_catalog_gate_observability_json(observability)), observability.to_dict())
        self.assertIn("metric_id", mission_plan_release_catalog_gate_observability_csv(observability))
        self.assertIn("# Mission plan release catalog gate observability", mission_plan_release_catalog_gate_observability_markdown(observability))
        payloads = mission_plan_release_catalog_gate_observability_export_payloads(observability)
        self.assertEqual(
            payloads["mission-plan-release-catalog-gate-observability.json"],
            mission_plan_release_catalog_gate_observability_json(observability),
        )
        self.assertEqual(mission_plan_release_catalog_gate_observability_schema()["max_metrics"], 64)
        self.assertTrue(mission_plan_release_catalog_gate_observability_capabilities()["aggregate_runtime_metrics"])
        gate_only = build_mission_plan_release_catalog_gate_observability(gate)
        self.assertIsNone(gate_only.runtime_address)
        failed_gate = build_mission_plan_release_catalog_gate(catalog, {"minimum_entry_count": 4})
        failed_runtime = run_mission_plan_release_catalog_gate_runtime(catalog, {"minimum_entry_count": 4})
        failed_metrics = build_mission_plan_release_catalog_gate_observability(failed_gate, failed_runtime)
        self.assertFalse(failed_metrics.accepted)
        with self.assertRaises(ValidationError):
            build_mission_plan_release_catalog_gate_observability(gate, runtime.to_dict() | {"gate_address": "wrong"})

    def test_catalog_gate_failure_matrix_keeps_each_policy_reason_inspectable(self) -> None:
        catalog = build_mission_plan_release_catalog(
            [
                build_mission_plan_release(self._receipt(), release_id="release-left"),
                build_mission_plan_release(self._second_receipt(), release_id="release-right"),
            ],
            catalog_id="failure-matrix-catalog",
        ).catalog
        cases = {
            "minimum": {"minimum_entry_count": 3},
            "maximum": {"maximum_entry_count": 1},
            "workflow": {"required_workflow_kinds": ["never-present"]},
            "state": {"required_states": ["never-present"]},
            "decision": {"required_decisions": ["never-present"]},
            "steps": {"maximum_total_step_count": 0},
            "artifacts": {"maximum_total_artifact_count": 0},
            "checks": {"maximum_total_check_count": 0},
            "minimum-checks": {"minimum_gate_check_count": 32},
        }
        expected_ids = {
            "minimum": "policy.entry_count.minimum",
            "maximum": "policy.entry_count.maximum",
            "workflow": "policy.required_workflow.never-present",
            "state": "policy.required_state.never-present",
            "decision": "policy.required_decision.never-present",
            "steps": "policy.total_steps",
            "artifacts": "policy.total_artifacts",
            "checks": "policy.total_checks",
            "minimum-checks": "policy.minimum_gate_checks",
        }
        for name, policy in cases.items():
            gate = build_mission_plan_release_catalog_gate(catalog, policy)
            self.assertFalse(gate.accepted, name)
            self.assertIn(expected_ids[name], gate.failed_check_ids, gate.to_dict())
            failed = [item for item in gate.checks if not item.accepted]
            self.assertGreaterEqual(len(failed), 1)
            self.assertEqual(gate.failed_check_count, len(failed))
            self.assertEqual(
                MissionPlanReleaseCatalogGate.from_mapping(gate.to_dict()).failed_check_ids,
                gate.failed_check_ids,
            )
        changed_catalog = build_mission_plan_release_catalog(
            [build_mission_plan_release(self._changed_receipt(), release_id="release-left")],
            catalog_id="optional-catalog",
        ).catalog
        optional_gate = build_mission_plan_release_catalog_gate(
            changed_catalog,
            {"maximum_total_optional_step_count": 0},
        )
        self.assertFalse(optional_gate.accepted)
        self.assertIn("policy.total_optional_steps", optional_gate.failed_check_ids)
        self.assertTrue(all(item.content_address for item in optional_gate.checks))
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGate.from_mapping(gate.to_dict() | {"accepted": True})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGate.from_mapping(gate.to_dict() | {"failed_check_count": 0})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGate.from_mapping(gate.to_dict() | {"policy_address": "wrong"})

    def test_catalog_gate_diff_classifies_added_removed_changed_and_unchanged_checks(self) -> None:
        catalog = build_mission_plan_release_catalog(
            [build_mission_plan_release(self._receipt(), release_id="release-left")],
            catalog_id="diff-matrix-catalog",
        ).catalog
        baseline = build_mission_plan_release_catalog_gate(catalog)
        threshold_changed = build_mission_plan_release_catalog_gate(catalog, {"minimum_entry_count": 2})
        reduced = build_mission_plan_release_catalog_gate(
            catalog,
            {
                "minimum_entry_count": 0,
                "require_all_accepted": False,
                "require_catalog_audit": False,
                "require_catalog_report": False,
            },
        )
        changed = diff_mission_plan_release_catalog_gates(baseline, threshold_changed)
        self.assertIn("policy.entry_count.minimum", changed.changed_check_ids)
        changed_item = next(item for item in changed.check_diffs if item.check_id == "policy.entry_count.minimum")
        self.assertIs(changed_item.status, MissionPlanReleaseCatalogGateDiffStatus.CHANGED)
        self.assertIn("accepted", changed_item.changed_fields)
        self.assertIn("expected", changed_item.changed_fields)
        removed = diff_mission_plan_release_catalog_gates(baseline, reduced)
        self.assertTrue(removed.removed_check_ids)
        self.assertTrue(all(item.status is MissionPlanReleaseCatalogGateDiffStatus.REMOVED for item in removed.check_diffs if item.check_id in removed.removed_check_ids))
        added = diff_mission_plan_release_catalog_gates(reduced, baseline)
        self.assertEqual(set(added.added_check_ids), set(removed.removed_check_ids))
        self.assertTrue(all(item.status is MissionPlanReleaseCatalogGateDiffStatus.ADDED for item in added.check_diffs if item.check_id in added.added_check_ids))
        self.assertEqual(
            MissionPlanReleaseCatalogGateDiff.from_mapping(removed.to_dict()).to_dict(),
            removed.to_dict(),
        )
        tampered = removed.to_dict() | {"check_count": removed.to_dict()["check_count"] + 1}
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateDiff.from_mapping(tampered)

    def test_catalog_gate_packet_manifest_describes_every_exact_artifact(self) -> None:
        catalog = build_mission_plan_release_catalog(
            [build_mission_plan_release(self._receipt(), release_id="release-left")],
            catalog_id="manifest-catalog",
        ).catalog
        packet = build_mission_plan_release_catalog_gate_packet(catalog, packet_id="manifest-packet")
        artifact_by_name = {item.filename: item for item in packet.artifacts}
        manifest_by_name = {item["filename"]: item for item in packet.manifest["artifacts"]}
        self.assertEqual(set(artifact_by_name) - {"manifest.json"}, set(manifest_by_name))
        for filename, artifact in artifact_by_name.items():
            if filename == "manifest.json":
                continue
            manifest_artifact = manifest_by_name[filename]
            self.assertEqual(manifest_artifact["artifact_id"], artifact.artifact_id)
            self.assertEqual(manifest_artifact["media_type"], "application/json")
            self.assertEqual(manifest_artifact["byte_count"], len(artifact.payload))
            self.assertEqual(manifest_artifact["line_count"], artifact.payload.count(b"\n"))
            self.assertEqual(manifest_artifact["content_address"], artifact.content_address)
            self.assertEqual(artifact.to_dict(include_payload=True)["content"], artifact.payload.decode("utf-8"))
            self.assertEqual(
                {key: value for key, value in artifact.to_dict(include_payload=True).items() if key != "content"},
                artifact.to_dict(),
            )
        self.assertEqual(
            packet.manifest["summary_address"],
            json.loads(artifact_by_name["catalog-gate-summary.json"].payload)["content_address"],
        )
        self.assertEqual(packet.manifest["artifact_count"], len(MISSION_PLAN_RELEASE_CATALOG_GATE_PACKET_REQUIRED_ARTIFACTS))
        self.assertEqual(packet.to_dict()["artifacts"], [item.to_dict() for item in packet.artifacts])
        with tempfile.TemporaryDirectory() as directory:
            destination = write_mission_plan_release_catalog_gate_packet(packet, Path(directory) / "packet")
            for filename, artifact in artifact_by_name.items():
                self.assertEqual((destination / filename).read_bytes(), artifact.payload)
            self.assertEqual(verify_mission_plan_release_catalog_gate_packet(destination).to_dict()["tampered_files"], [])

    def test_cli_materializes_verifies_queries_diffs_and_runs_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "mission.json"
            source.write_text(json.dumps(self._payload()), encoding="utf-8")
            release = root / "release"
            summary = root / "release-summary.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release",
                        str(source),
                        "--destination",
                        str(release),
                        "--output",
                        str(summary),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(summary.read_text(encoding="utf-8"))["accepted"])
            verification = root / "verification.json"
            self.assertEqual(
                main(["mission-plan-release-verify", str(release), "--output", str(verification)]),
                0,
            )
            self.assertTrue(json.loads(verification.read_text(encoding="utf-8"))["accepted"])
            query = root / "query.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-query",
                        str(release),
                        "--kind",
                        "review",
                        "--output",
                        str(query),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(query.read_text(encoding="utf-8"))["total_matches"], 1)
            left = root / "left.json"
            right_source = root / "right.json"
            right_source.write_text(
                json.dumps(self._payload() | {"workflow_id": "changed-workflow"}),
                encoding="utf-8",
            )
            self.assertEqual(main(["mission-plan", str(source), "--output", str(left)]), 0)
            self.assertEqual(main(["mission-plan", str(right_source), "--output", str(right_source.with_suffix(".plan.json"))]), 0)
            right = right_source.with_suffix(".plan.json")
            diff = root / "diff.md"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-diff",
                        str(left),
                        str(right),
                        "--format",
                        "markdown",
                        "--output",
                        str(diff),
                    ]
                ),
                0,
            )
            self.assertIn("# Mission plan release diff", diff.read_text(encoding="utf-8"))
            right_release = root / "right-release"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release",
                        str(right_source),
                        "--destination",
                        str(right_release),
                        "--output",
                        str(root / "right-release.json"),
                    ]
                ),
                0,
            )
            runtime = root / "runtime.json"
            runtime_release = root / "runtime-release"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-runtime",
                        str(source),
                        "--destination",
                        str(runtime_release),
                        "--output",
                        str(runtime),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(runtime.read_text(encoding="utf-8"))["accepted"])
            for command in (
                "mission-plan-release-schema",
                "mission-plan-release-capabilities",
                "mission-plan-release-query-schema",
                "mission-plan-release-query-capabilities",
                "mission-plan-release-diff-schema",
                "mission-plan-release-diff-capabilities",
                "mission-plan-release-runtime-schema",
                "mission-plan-release-runtime-capabilities",
                "mission-plan-release-observability-schema",
                "mission-plan-release-observability-capabilities",
                "mission-plan-release-lineage-schema",
                "mission-plan-release-lineage-capabilities",
                "mission-plan-release-policy-schema",
                "mission-plan-release-policy-capabilities",
                "mission-plan-release-catalog-schema",
                "mission-plan-release-catalog-capabilities",
                "mission-plan-release-catalog-query-schema",
                "mission-plan-release-catalog-query-capabilities",
                "mission-plan-release-catalog-report-schema",
                "mission-plan-release-catalog-report-capabilities",
                "mission-plan-release-catalog-gate-schema",
                "mission-plan-release-catalog-gate-capabilities",
                "mission-plan-release-catalog-gate-runtime-schema",
                "mission-plan-release-catalog-gate-runtime-capabilities",
                "mission-plan-release-catalog-gate-packet-schema",
                "mission-plan-release-catalog-gate-packet-capabilities",
                "mission-plan-release-catalog-gate-query-schema",
                "mission-plan-release-catalog-gate-query-capabilities",
                "mission-plan-release-catalog-gate-diff-schema",
                "mission-plan-release-catalog-gate-diff-capabilities",
                "mission-plan-release-catalog-gate-observability-schema",
                "mission-plan-release-catalog-gate-observability-capabilities",
                "mission-plan-conformance-schema",
                "mission-plan-conformance-capabilities",
                "mission-plan-replay-schema",
                "mission-plan-replay-capabilities",
            ):
                self.assertEqual(main([command]), 0)
            policy = root / "policy.json"
            policy.write_text(
                json.dumps({"policy_id": "cli-policy", "required_step_kinds": ["review"]}),
                encoding="utf-8",
            )
            policy_output = root / "policy-output.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-policy",
                        str(release),
                        "--policy",
                        str(policy),
                        "--output",
                        str(policy_output),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(policy_output.read_text(encoding="utf-8"))["accepted"])
            catalog = root / "catalog"
            catalog_json = root / "catalog.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog",
                        str(release),
                        str(right_release),
                        "--catalog-id",
                        "cli-catalog",
                        "--destination",
                        str(catalog),
                        "--output",
                        str(catalog_json),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(catalog_json.read_text(encoding="utf-8"))["entry_count"], 2)
            catalog_verification = root / "catalog-verification.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-verify",
                        str(catalog),
                        "--output",
                        str(catalog_verification),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(catalog_verification.read_text(encoding="utf-8"))["accepted"])
            catalog_query = root / "catalog-query.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-query",
                        str(catalog),
                        "--workflow-kind",
                        "review",
                        "--output",
                        str(catalog_query),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(catalog_query.read_text(encoding="utf-8"))["total_matches"], 2)
            catalog_diff = root / "catalog-diff.md"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-diff",
                        str(catalog),
                        str(catalog),
                        "--format",
                        "markdown",
                        "--output",
                        str(catalog_diff),
                    ]
                ),
                0,
            )
            self.assertIn("# Mission plan release catalog diff", catalog_diff.read_text(encoding="utf-8"))
            catalog_audit = root / "catalog-audit.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-audit",
                        str(catalog),
                        "--output",
                        str(catalog_audit),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(catalog_audit.read_text(encoding="utf-8"))["accepted"])
            catalog_report = root / "catalog-report.md"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-report",
                        str(catalog),
                        "--format",
                        "markdown",
                        "--output",
                        str(catalog_report),
                    ]
                ),
                0,
            )
            self.assertIn("# Mission plan release catalog report", catalog_report.read_text(encoding="utf-8"))
            gate_output = root / "catalog-gate.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-gate",
                        str(catalog),
                        "--output",
                        str(gate_output),
                    ]
                ),
                0,
            )
            gate_payload = json.loads(gate_output.read_text(encoding="utf-8"))
            self.assertTrue(gate_payload["accepted"])
            self.assertNotIn("agent", gate_payload)
            runtime_output = root / "catalog-gate-runtime.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-gate-runtime",
                        str(catalog),
                        "--output",
                        str(runtime_output),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(runtime_output.read_text(encoding="utf-8"))["accepted"])
            packet_destination = root / "catalog-gate-packet"
            packet_output = root / "catalog-gate-packet.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-gate-packet",
                        str(catalog),
                        "--packet-id",
                        "cli-packet",
                        "--destination",
                        str(packet_destination),
                        "--output",
                        str(packet_output),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(packet_output.read_text(encoding="utf-8"))["accepted"])
            packet_verification = root / "catalog-gate-packet-verification.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-gate-packet-verify",
                        str(packet_destination),
                        "--output",
                        str(packet_verification),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(packet_verification.read_text(encoding="utf-8"))["accepted"])
            gate_query = root / "catalog-gate-query.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-gate-query",
                        str(packet_destination),
                        "--category",
                        "acceptance",
                        "--output",
                        str(gate_query),
                    ]
                ),
                0,
            )
            self.assertGreaterEqual(json.loads(gate_query.read_text(encoding="utf-8"))["total_matches"], 1)
            gate_diff = root / "catalog-gate-diff.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-gate-diff",
                        str(gate_output),
                        str(gate_output),
                        "--output",
                        str(gate_diff),
                    ]
                ),
                0,
            )
            self.assertEqual(json.loads(gate_diff.read_text(encoding="utf-8"))["changed_check_ids"], [])
            gate_observability = root / "catalog-gate-observability.json"
            self.assertEqual(
                main(
                    [
                        "mission-plan-release-catalog-gate-observability",
                        str(gate_output),
                        "--runtime",
                        str(runtime_output),
                        "--format",
                        "markdown",
                        "--output",
                        str(gate_observability),
                    ]
                ),
                0,
            )
            self.assertIn("# Mission plan release catalog gate observability", gate_observability.read_text(encoding="utf-8"))
            conformance = root / "conformance.json"
            self.assertEqual(main(["mission-plan-conformance", str(left), "--output", str(conformance)]), 0)
            self.assertTrue(json.loads(conformance.read_text(encoding="utf-8"))["accepted"])
            replay_output = root / "replay.json"
            self.assertEqual(main(["mission-plan-replay", str(left), "--output", str(replay_output)]), 0)
            self.assertTrue(json.loads(replay_output.read_text(encoding="utf-8"))["accepted"])
    def test_catalog_gate_api_fails_closed_for_malformed_and_incompatible_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)

                def post(path: str, payload: object) -> tuple[int, dict[str, object]]:
                    body = json.dumps(payload).encode("utf-8")
                    connection.request(
                        "POST",
                        path,
                        body=body,
                        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
                    )
                    response = connection.getresponse()
                    return response.status, json.loads(response.read())

                status, payload = post("/v1/mission/plan/release/catalog/gate", {})
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"], "invalid_mission_plan_catalog_gate")
                status, payload = post(
                    "/v1/mission/plan/release/catalog/gate",
                    {"catalog": self._payload(), "policy": "not-an-object"},
                )
                self.assertEqual(status, 400)
                self.assertIn("policy", str(payload["message"]))
                status, payload = post(
                    "/v1/mission/plan/release/catalog/gate/runtime",
                    {"catalog": self._payload(), "policy": {"minimum_entry_count": -1}},
                )
                self.assertEqual(status, 422)
                self.assertEqual(payload["error"], "validation_error")
                status, payload = post(
                    "/v1/mission/plan/release/catalog/gate/packet",
                    {"catalog": self._payload(), "policy": {"language": "private"}},
                )
                self.assertEqual(status, 422)
                self.assertEqual(payload["error"], "validation_error")
                status, payload = post(
                    "/v1/mission/plan/release/catalog/gate/query",
                    {"gate": self._payload(), "query": {"limit": 0}},
                )
                self.assertEqual(status, 422)
                self.assertEqual(payload["error"], "validation_error")
                status, payload = post(
                    "/v1/mission/plan/release/catalog/gate/diff",
                    {"left": self._payload(), "right": self._payload()},
                )
                self.assertEqual(status, 422)
                self.assertEqual(payload["error"], "validation_error")
                status, payload = post(
                    "/v1/mission/plan/release/catalog/gate/observability",
                    {"gate": self._payload(), "runtime": "not-an-object"},
                )
                self.assertEqual(status, 400)
                self.assertIn("runtime", str(payload["message"]))
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_catalog_gate_hydration_rejects_shape_and_address_drift(self) -> None:
        catalog = build_mission_plan_release_catalog(
            [build_mission_plan_release(self._receipt(), release_id="release-left")],
            catalog_id="hydration-catalog",
        ).catalog
        gate = build_mission_plan_release_catalog_gate(catalog)
        runtime = run_mission_plan_release_catalog_gate_runtime(catalog)
        observability = build_mission_plan_release_catalog_gate_observability(gate, runtime)
        diff = diff_mission_plan_release_catalog_gates(gate, gate)
        query = query_mission_plan_release_catalog_gate(gate, {"limit": 2})
        check = gate.checks[0]
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateCheck.from_mapping(check.to_dict() | {"content_address": "wrong"})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateCheck.from_mapping(check.to_dict() | {"accepted": "true"})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGate.from_mapping(gate.to_dict() | {"checks": []})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGate.from_mapping(gate.to_dict() | {"unknown": True})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateRuntime.from_mapping(runtime.to_dict() | {"replay_deterministic": 1})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateRuntime.from_mapping(runtime.to_dict() | {"unknown": True})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateQueryResult.from_mapping(query.to_dict() | {"total_matches": -1})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateQueryResult.from_mapping(query.to_dict() | {"unknown": True})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateDiff.from_mapping(diff.to_dict() | {"accepted": "true"})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateDiff.from_mapping(diff.to_dict() | {"check_diffs": []})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateObservability.from_mapping(observability.to_dict() | {"metric_count": 0})
        with self.assertRaises(ValidationError):
            MissionPlanReleaseCatalogGateObservability.from_mapping(observability.to_dict() | {"unknown": True})
        self.assertEqual(MissionPlanReleaseCatalogGate.from_mapping(gate.to_dict()).content_address, gate.content_address)
        self.assertEqual(MissionPlanReleaseCatalogGateRuntime.from_mapping(runtime.to_dict()).content_address, runtime.content_address)
        self.assertEqual(MissionPlanReleaseCatalogGateQueryResult.from_mapping(query.to_dict()).content_address, query.content_address)
        self.assertEqual(MissionPlanReleaseCatalogGateDiff.from_mapping(diff.to_dict()).content_address, diff.content_address)
        self.assertEqual(MissionPlanReleaseCatalogGateObservability.from_mapping(observability.to_dict()).content_address, observability.content_address)

    def test_catalog_gate_policy_round_trip_preserves_sorted_coverage_and_limits(self) -> None:
        policy = MissionPlanReleaseCatalogGatePolicy.from_mapping(
            {
                "policy_id": "bounded-policy",
                "minimum_entry_count": 1,
                "maximum_entry_count": 12,
                "require_all_accepted": False,
                "required_states": ["accepted", "review"],
                "required_decisions": ["allow", "review"],
                "required_workflow_kinds": ["ingest", "review"],
                "maximum_total_step_count": 80,
                "maximum_total_optional_step_count": 20,
                "maximum_total_artifact_count": 40,
                "maximum_total_check_count": 60,
                "maximum_total_warning_count": 4,
                "minimum_gate_check_count": 8,
                "require_catalog_audit": True,
                "require_catalog_report": True,
            }
        )
        self.assertEqual(
            MissionPlanReleaseCatalogGatePolicy.from_mapping(policy.to_dict()).to_dict(),
            policy.to_dict(),
        )
        self.assertEqual(policy.required_states, ("accepted", "review"))
        self.assertEqual(policy.required_decisions, ("allow", "review"))
        self.assertEqual(policy.required_workflow_kinds, ("ingest", "review"))
        self.assertEqual(policy.content_address.split(":", 1)[0], "mission-plan-release-catalog-gate-policy")
        invalid_policies = (
            {"require_all_accepted": "false"},
            {"require_catalog_audit": 1},
            {"minimum_entry_count": True},
            {"maximum_total_step_count": -1},
            {"required_states": ["review", "accepted"]},
            {"required_decisions": ["review", "review"]},
            {"required_workflow_kinds": ["review"] * 33},
            {"policy_version": "old-policy"},
            {"unexpected_policy_field": True},
        )
        for invalid in invalid_policies:
            with self.assertRaises(ValidationError):
                MissionPlanReleaseCatalogGatePolicy.from_mapping(invalid)

    def test_catalog_gate_query_edge_pages_remain_deterministic_and_empty(self) -> None:
        catalog = build_mission_plan_release_catalog(
            [build_mission_plan_release(self._receipt(), release_id="release-left")],
            catalog_id="query-edge-catalog",
        ).catalog
        gate = build_mission_plan_release_catalog_gate(catalog)
        empty = query_mission_plan_release_catalog_gate(
            gate,
            {"check_id": "does-not-exist", "offset": 0, "limit": 1},
        )
        self.assertTrue(empty.accepted)
        self.assertEqual(empty.total_matches, 0)
        self.assertEqual(empty.checks, ())
        self.assertFalse(empty.has_more)
        beyond = query_mission_plan_release_catalog_gate(
            gate,
            {"offset": len(gate.checks), "limit": 1},
        )
        self.assertEqual(beyond.total_matches, len(gate.checks))
        self.assertEqual(beyond.checks, ())
        self.assertFalse(beyond.has_more)
        combined = query_mission_plan_release_catalog_gate(
            gate,
            {"category": "threshold", "accepted": True, "text": "within", "limit": 1},
        )
        expected = tuple(
            item
            for item in gate.checks
            if item.category == "threshold" and item.accepted and "within" in item.message
        )
        self.assertEqual(combined.checks, expected[:1])
        self.assertEqual(combined.total_matches, len(expected))
        self.assertEqual(combined.query.limit, 1)
        self.assertEqual(combined.query.category, "threshold")
        self.assertEqual(combined.query.accepted, True)
        self.assertEqual(combined.query.text, "within")
        self.assertEqual(combined.catalog_id, gate.catalog_id)
        self.assertEqual(combined.catalog_address, gate.catalog_address)
        self.assertTrue(combined.content_address.startswith("mission-plan-release-catalog-gate-query:"))
        self.assertEqual(len(combined.checks), 1)
        self.assertIsInstance(combined.to_dict(), dict)
        self.assertIn("content_address", combined.to_dict())
        self.assertIn("has_more", combined.to_dict())
        self.assertEqual(
            query_mission_plan_release_catalog_gate(gate, combined.query.to_dict()).to_dict()["checks"],
            [item.to_dict() for item in combined.checks],
        )

    def test_api_exposes_release_query_diff_runtime_and_contract_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)

                def post(path: str, payload: object) -> tuple[int, dict[str, object]]:
                    body = json.dumps(payload).encode("utf-8")
                    connection.request(
                        "POST",
                        path,
                        body=body,
                        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
                    )
                    response = connection.getresponse()
                    return response.status, json.loads(response.read())

                status, bundle = post("/v1/mission/plan/release", self._payload())
                self.assertEqual(status, 200)
                self.assertTrue(bundle["accepted"])
                self.assertEqual(bundle["manifest"]["artifact_count"], 5)
                status, query = post(
                    "/v1/mission/plan/release/query",
                    {"receipt": bundle["receipt"], "query": {"kind": "review"}},
                )
                self.assertEqual(status, 200)
                self.assertEqual(query["total_matches"], 1)
                status, diff = post(
                    "/v1/mission/plan/release/diff",
                    {"left": bundle["receipt"], "right": bundle["receipt"]},
                )
                self.assertEqual(status, 200)
                self.assertFalse(diff["workflow_changed"])
                status, runtime = post("/v1/mission/plan/release/runtime", self._payload())
                self.assertEqual(status, 200)
                self.assertTrue(runtime["accepted"])
                status, observability = post(
                    "/v1/mission/plan/release/observability",
                    {"receipt": bundle["receipt"]},
                )
                self.assertEqual(status, 200)
                self.assertEqual(observability["metric_count"], 16)
                status, lineage = post(
                    "/v1/mission/plan/release/lineage",
                    {"receipt": bundle["receipt"]},
                )
                self.assertEqual(status, 200)
                self.assertEqual(lineage["node_count"], 21)
                status, policy = post(
                    "/v1/mission/plan/release/policy",
                    {"receipt": bundle["receipt"], "policy": {"required_step_kinds": ["review"]}},
                )
                self.assertEqual(status, 200)
                self.assertTrue(policy["accepted"])
                status, catalog = post(
                    "/v1/mission/plan/release/catalog",
                    {"catalog_id": "api-catalog", "releases": [bundle["receipt"]]},
                )
                self.assertEqual(status, 200)
                self.assertTrue(catalog["accepted"])
                self.assertEqual(catalog["catalog"]["entry_count"], 1)
                status, catalog_query = post(
                    "/v1/mission/plan/release/catalog/query",
                    {"catalog": catalog["catalog"], "query": {"workflow_kind": "review"}},
                )
                self.assertEqual(status, 200)
                self.assertEqual(catalog_query["total_matches"], 1)
                status, catalog_diff = post(
                    "/v1/mission/plan/release/catalog/diff",
                    {"left": catalog["catalog"], "right": catalog["catalog"]},
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    catalog_diff["unchanged_release_ids"],
                    [catalog["catalog"]["entries"][0]["release_id"]],
                )
                status, catalog_audit = post(
                    "/v1/mission/plan/release/catalog/audit",
                    {"catalog": catalog["catalog"]},
                )
                self.assertEqual(status, 200)
                self.assertTrue(catalog_audit["accepted"])
                status, catalog_report = post(
                    "/v1/mission/plan/release/catalog/report",
                    {"catalog": catalog["catalog"]},
                )
                self.assertEqual(status, 200)
                self.assertEqual(catalog_report["entry_count"], 1)
                self.assertTrue(catalog_report["accepted"])
                status, catalog_gate = post(
                    "/v1/mission/plan/release/catalog/gate",
                    {"catalog": catalog["catalog"]},
                )
                self.assertEqual(status, 200)
                self.assertTrue(catalog_gate["accepted"])
                self.assertEqual(catalog_gate["catalog_address"], catalog["catalog"]["content_address"])
                status, catalog_runtime = post(
                    "/v1/mission/plan/release/catalog/gate/runtime",
                    {"catalog": catalog["catalog"]},
                )
                self.assertEqual(status, 200)
                self.assertTrue(catalog_runtime["accepted"])
                self.assertEqual(catalog_runtime["stage_count"], 6)
                status, catalog_packet = post(
                    "/v1/mission/plan/release/catalog/gate/packet",
                    {"catalog": catalog["catalog"], "packet_id": "api-packet"},
                )
                self.assertEqual(status, 200)
                self.assertTrue(catalog_packet["accepted"])
                self.assertEqual(catalog_packet["manifest"]["artifact_count"], 8)
                status, catalog_gate_query = post(
                    "/v1/mission/plan/release/catalog/gate/query",
                    {"gate": catalog_gate, "query": {"category": "acceptance"}},
                )
                self.assertEqual(status, 200)
                self.assertGreaterEqual(catalog_gate_query["total_matches"], 1)
                status, catalog_gate_diff = post(
                    "/v1/mission/plan/release/catalog/gate/diff",
                    {"left": catalog_gate, "right": catalog_gate},
                )
                self.assertEqual(status, 200)
                self.assertEqual(
                    catalog_gate_diff["unchanged_check_ids"],
                    [item["check_id"] for item in catalog_gate_diff["check_diffs"]],
                )
                status, catalog_gate_observability = post(
                    "/v1/mission/plan/release/catalog/gate/observability",
                    {"gate": catalog_gate, "runtime": catalog_runtime},
                )
                self.assertEqual(status, 200)
                self.assertTrue(catalog_gate_observability["accepted"])
                self.assertGreater(catalog_gate_observability["metric_count"], 0)
                status, conformance = post("/v1/mission/plan/conformance", {"receipt": bundle["receipt"]})
                self.assertEqual(status, 200)
                self.assertTrue(conformance["accepted"])
                status, replay = post("/v1/mission/plan/replay", {"receipt": bundle["receipt"]})
                self.assertEqual(status, 200)
                self.assertTrue(replay["accepted"])
                for suffix in (
                    "schema",
                    "capabilities",
                    "query/schema",
                    "query/capabilities",
                    "diff/schema",
                    "diff/capabilities",
                    "runtime/schema",
                    "runtime/capabilities",
                    "observability/schema",
                    "observability/capabilities",
                    "lineage/schema",
                    "lineage/capabilities",
                    "policy/schema",
                    "policy/capabilities",
                ):
                    connection.request("GET", f"/v1/mission/plan/release/{suffix}")
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertIsInstance(json.loads(response.read()), dict)
                for path in (
                    "/v1/mission/plan/release/catalog/schema",
                    "/v1/mission/plan/release/catalog/capabilities",
                    "/v1/mission/plan/release/catalog/query/schema",
                    "/v1/mission/plan/release/catalog/query/capabilities",
                    "/v1/mission/plan/release/catalog/diff/schema",
                    "/v1/mission/plan/release/catalog/diff/capabilities",
                    "/v1/mission/plan/release/catalog/audit/schema",
                    "/v1/mission/plan/release/catalog/audit/capabilities",
                    "/v1/mission/plan/release/catalog/report/schema",
                    "/v1/mission/plan/release/catalog/report/capabilities",
                    "/v1/mission/plan/release/catalog/gate/schema",
                    "/v1/mission/plan/release/catalog/gate/capabilities",
                    "/v1/mission/plan/release/catalog/gate/runtime/schema",
                    "/v1/mission/plan/release/catalog/gate/runtime/capabilities",
                    "/v1/mission/plan/release/catalog/gate/packet/schema",
                    "/v1/mission/plan/release/catalog/gate/packet/capabilities",
                    "/v1/mission/plan/release/catalog/gate/query/schema",
                    "/v1/mission/plan/release/catalog/gate/query/capabilities",
                    "/v1/mission/plan/release/catalog/gate/diff/schema",
                    "/v1/mission/plan/release/catalog/gate/diff/capabilities",
                    "/v1/mission/plan/release/catalog/gate/observability/schema",
                    "/v1/mission/plan/release/catalog/gate/observability/capabilities",
                    "/v1/mission/plan/conformance/schema",
                    "/v1/mission/plan/conformance/capabilities",
                    "/v1/mission/plan/replay/schema",
                    "/v1/mission/plan/replay/capabilities",
                ):
                    connection.request("GET", path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertIsInstance(json.loads(response.read()), dict)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()

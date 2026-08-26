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
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()

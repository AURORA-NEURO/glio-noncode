from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.review_workspace import build_persisted_review_workspace
from glio_noncode.review_workspace_execution import (
    ReviewWorkspaceExecutionQuery,
    replay_review_workspace_plan_execution,
)
from glio_noncode.review_workspace_execution_release import (
    build_review_workspace_execution_release,
    diff_review_workspace_execution_releases,
    load_review_workspace_execution_release,
    query_review_workspace_execution_release,
    query_review_workspace_execution_release_operations,
    query_review_workspace_execution_release_transitions_view,
    query_review_workspace_execution_release_timeline,
    review_workspace_execution_release_capabilities,
    review_workspace_execution_release_schema,
    verify_review_workspace_execution_release,
    write_review_workspace_execution_release,
)
from glio_noncode.review_workspace_execution_timeline import ReviewWorkspaceExecutionTimelineQuery
from glio_noncode.review_workspace_plan import build_review_workspace_plan, review_workspace_plan_from_mapping
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import canonical_json, content_hash, hash_bytes

from .helpers import fixture_manifest


class ReviewWorkspaceExecutionReleaseTests(unittest.TestCase):
    def _report(self, directory: str):
        runtime = CaseRuntime(directory)
        dossier = runtime.evaluate(fixture_manifest())
        workspace = build_persisted_review_workspace(runtime, dossier.run_id)
        plan = build_review_workspace_plan(workspace)
        return dossier, plan, replay_review_workspace_plan_execution(plan)

    def test_release_round_trip_query_and_identity_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier, plan, report = self._report(directory)
            bundle = build_review_workspace_execution_release(report, plan)
            destination = Path(directory) / "execution-release"
            write_review_workspace_execution_release(bundle, destination)
            verification = verify_review_workspace_execution_release(destination)
            self.assertTrue(verification.accepted, verification.to_dict())
            self.assertEqual(verification.artifact_count, 20)
            self.assertEqual(verification.verified_artifact_count, 20)
            loaded = load_review_workspace_execution_release(destination)
            self.assertEqual(loaded.execution_address, report.content_address)
            self.assertEqual(loaded.plan.content_address, plan.content_address)
            self.assertEqual(loaded.metrics.plan_address, plan.content_address)
            self.assertEqual(loaded.metrics.event_count, report.event_count)
            self.assertTrue(verification.metrics_valid)
            self.assertTrue(verification.operations_valid)
            self.assertTrue(verification.transitions_valid)
            self.assertEqual(loaded.operations.queue_count, report.action_count)
            self.assertEqual(
                query_review_workspace_execution_release_operations(loaded).to_dict(),
                loaded.operations.to_dict(),
            )
            transition_view = query_review_workspace_execution_release_transitions_view(loaded)
            self.assertTrue(transition_view.accepted)
            self.assertEqual(transition_view.total_count, loaded.transitions.option_count)
            executable_view = query_review_workspace_execution_release_transitions_view(
                loaded,
                {"kind": "start", "executable": True, "limit": 3},
            )
            self.assertTrue(executable_view.accepted)
            self.assertLessEqual(len(executable_view.rows), 3)
            self.assertEqual(loaded.report.to_dict(), report.to_dict())
            query = query_review_workspace_execution_release(
                loaded,
                ReviewWorkspaceExecutionQuery(status="open", lane="intake", limit=2),
            )
            self.assertTrue(query.accepted)
            self.assertEqual(query.total_count, 1)
            identity = diff_review_workspace_execution_releases(destination, destination)
            self.assertTrue(identity.accepted)
            self.assertFalse(identity.plan_changed)
            self.assertEqual(identity.left_plan_address, plan.content_address)
            self.assertEqual(identity.added_plan_action_ids, ())
            self.assertFalse(identity.metrics_diff.metrics_changed)
            self.assertEqual(identity.metrics_diff.event_count_delta, 0)
            self.assertEqual(identity.operations_diff.queue_count_delta, 0)
            self.assertFalse(identity.operations_diff.recommendation_changed)
            self.assertFalse(identity.transitions_diff.recommendation_changed)
            self.assertEqual(identity.transitions_diff.changed_transition_ids, ())
            self.assertEqual(identity.operations_diff.changed_action_ids, ())
            self.assertEqual(identity.added_event_ids, ())
            self.assertEqual(identity.changed_artifact_ids, ())
            self.assertEqual(identity.content_address, diff_review_workspace_execution_releases(loaded, loaded).content_address)
            timeline = query_review_workspace_execution_release_timeline(
                loaded,
                ReviewWorkspaceExecutionTimelineQuery(limit=3),
            )
            self.assertTrue(timeline.accepted)
            self.assertEqual(timeline.total_count, report.event_count)
            self.assertTrue(dossier.run_id)

    def test_report_hydration_rejects_derived_address_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, plan, report = self._report(directory)
            bundle = build_review_workspace_execution_release(report, plan)
            destination = Path(directory) / "execution-release"
            write_review_workspace_execution_release(bundle, destination)
            report_path = destination / "review-workspace-execution.json"
            payload = json.loads(report_path.read_text(encoding="utf-8"))
            payload["actions"][0]["ready"] = not payload["actions"][0]["ready"]
            report_path.write_text(json.dumps(payload), encoding="utf-8")
            verification = verify_review_workspace_execution_release(destination)
            self.assertFalse(verification.accepted)
            self.assertIn("review-workspace-execution.json", verification.tampered_files)
            with self.assertRaises(ValidationError):
                load_review_workspace_execution_release(destination)

    def test_release_rejects_event_stream_manifest_and_unexpected_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, plan, report = self._report(directory)
            bundle = build_review_workspace_execution_release(report, plan)
            destination = Path(directory) / "execution-release"
            write_review_workspace_execution_release(bundle, destination)
            (destination / "events.jsonl").write_bytes((destination / "events.jsonl").read_bytes() + b"\n")
            (destination / "unexpected.txt").write_text("unexpected", encoding="utf-8")
            verification = verify_review_workspace_execution_release(destination)
            self.assertFalse(verification.accepted)
            self.assertIn("events.jsonl", verification.tampered_files)
            self.assertIn("unexpected.txt", verification.unexpected_files)

    def test_event_stream_reconciliation_survives_manifest_readdressing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, plan, report = self._report(directory)
            bundle = build_review_workspace_execution_release(report, plan)
            destination = Path(directory) / "execution-release"
            write_review_workspace_execution_release(bundle, destination)
            stream = destination / "events.jsonl"
            stream.write_bytes(b"{\"event_id\":\"forged\"}\n")
            manifest_path = destination / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            artifact = next(item for item in manifest["artifacts"] if item["filename"] == "events.jsonl")
            payload = stream.read_bytes()
            artifact["byte_count"] = len(payload)
            artifact["line_count"] = len(payload.splitlines())
            artifact["content_address"] = hash_bytes(
                payload,
                prefix="review-workspace-execution-release-artifact",
            )
            manifest_body = dict(manifest)
            manifest_body.pop("manifest_address", None)
            manifest["manifest_address"] = content_hash(
                manifest_body,
                prefix="review-workspace-execution-release-manifest",
            )
            manifest_path.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
            verification = verify_review_workspace_execution_release(destination)
            self.assertFalse(verification.accepted)
            self.assertIn("events.jsonl", verification.tampered_files)

    def test_release_schema_and_capabilities_are_public_and_bounded(self) -> None:
        schema = review_workspace_execution_release_schema()
        capabilities = review_workspace_execution_release_capabilities()
        self.assertEqual(schema["version"], "review-workspace-execution-release-schema-v1")
        self.assertEqual(len(schema["artifact_filenames"]), 20)
        self.assertEqual(
            schema["query_views"],
            ["actions", "events", "metrics", "operations", "transitions"],
        )
        self.assertEqual(
            schema["operations"]["query_version"],
            "review-workspace-execution-operations-query-v1",
        )
        self.assertTrue(schema["operations"]["complete_match_facets"])
        self.assertTrue(schema["transitions"]["state_machine_preflight"])
        self.assertTrue(schema["event_timeline"]["replay_verified"])
        self.assertTrue(schema["diff"]["metrics_diff_version"])
        self.assertTrue(schema["diff"]["operations_diff_version"])
        self.assertTrue(schema["diff"]["transitions_diff_version"])
        self.assertTrue(capabilities["independent_manifest_verification"])
        self.assertTrue(capabilities["event_timeline_query"])
        self.assertTrue(capabilities["execution_metrics"])
        self.assertTrue(capabilities["metrics_diff"])
        self.assertTrue(capabilities["operations_diff"])
        self.assertTrue(capabilities["execution_operations"])
        self.assertTrue(capabilities["operations_verification"])
        self.assertTrue(capabilities["operations_query"])
        self.assertTrue(capabilities["operations_query_facets"])
        self.assertTrue(capabilities["execution_transitions"])
        self.assertTrue(capabilities["transition_verification"])
        self.assertTrue(capabilities["public_boundary_audit"])

    def test_metrics_artifact_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, plan, report = self._report(directory)
            bundle = build_review_workspace_execution_release(report, plan)
            destination = Path(directory) / "execution-release"
            write_review_workspace_execution_release(bundle, destination)
            metrics_path = destination / "review-workspace-execution-metrics.json"
            payload = json.loads(metrics_path.read_text(encoding="utf-8"))
            payload["completion_basis_points"] = 10_000
            metrics_path.write_text(json.dumps(payload), encoding="utf-8")
            verification = verify_review_workspace_execution_release(destination)
            self.assertFalse(verification.accepted)
            self.assertFalse(verification.metrics_valid)
            self.assertIn("review-workspace-execution-metrics.json", verification.tampered_files)

    def test_operations_artifact_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, plan, report = self._report(directory)
            bundle = build_review_workspace_execution_release(report, plan)
            destination = Path(directory) / "execution-release"
            write_review_workspace_execution_release(bundle, destination)
            operations_path = destination / "review-workspace-execution-operations.json"
            payload = json.loads(operations_path.read_text(encoding="utf-8"))
            payload["recommended_transition"] = "forged-transition"
            operations_path.write_text(json.dumps(payload), encoding="utf-8")
            verification = verify_review_workspace_execution_release(destination)
            self.assertFalse(verification.accepted)
            self.assertFalse(verification.operations_valid)
            self.assertIn("review-workspace-execution-operations.json", verification.tampered_files)

    def test_transitions_artifact_tampering_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, plan, report = self._report(directory)
            bundle = build_review_workspace_execution_release(report, plan)
            destination = Path(directory) / "execution-release"
            write_review_workspace_execution_release(bundle, destination)
            transitions_path = destination / "review-workspace-execution-transitions.json"
            payload = json.loads(transitions_path.read_text(encoding="utf-8"))
            payload["executable_option_count"] = int(payload["executable_option_count"]) + 1
            transitions_path.write_text(json.dumps(payload), encoding="utf-8")
            verification = verify_review_workspace_execution_release(destination)
            self.assertFalse(verification.accepted)
            self.assertFalse(verification.transitions_valid)
            self.assertIn(
                "review-workspace-execution-transitions.json",
                verification.tampered_files,
            )

    def test_source_plan_hydration_rejects_graph_address_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, plan, _ = self._report(directory)
            hydrated = review_workspace_plan_from_mapping(plan.to_dict())
            self.assertEqual(hydrated.to_dict(), plan.to_dict())
            forged = plan.to_dict()
            forged["actions"][0]["depends_on"] = ["forged-dependency"]
            with self.assertRaises(ValidationError):
                review_workspace_plan_from_mapping(forged)


if __name__ == "__main__":
    unittest.main()

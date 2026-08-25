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
    review_workspace_execution_release_capabilities,
    review_workspace_execution_release_schema,
    verify_review_workspace_execution_release,
    write_review_workspace_execution_release,
)
from glio_noncode.review_workspace_plan import build_review_workspace_plan
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class ReviewWorkspaceExecutionReleaseTests(unittest.TestCase):
    def _report(self, directory: str):
        runtime = CaseRuntime(directory)
        dossier = runtime.evaluate(fixture_manifest())
        workspace = build_persisted_review_workspace(runtime, dossier.run_id)
        plan = build_review_workspace_plan(workspace)
        return dossier, replay_review_workspace_plan_execution(plan)

    def test_release_round_trip_query_and_identity_diff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier, report = self._report(directory)
            bundle = build_review_workspace_execution_release(report)
            destination = Path(directory) / "execution-release"
            write_review_workspace_execution_release(bundle, destination)
            verification = verify_review_workspace_execution_release(destination)
            self.assertTrue(verification.accepted, verification.to_dict())
            self.assertEqual(verification.artifact_count, 6)
            self.assertEqual(verification.verified_artifact_count, 6)
            loaded = load_review_workspace_execution_release(destination)
            self.assertEqual(loaded.execution_address, report.content_address)
            self.assertEqual(loaded.report.to_dict(), report.to_dict())
            query = query_review_workspace_execution_release(
                loaded,
                ReviewWorkspaceExecutionQuery(status="open", lane="intake", limit=2),
            )
            self.assertTrue(query.accepted)
            self.assertEqual(query.total_count, 1)
            identity = diff_review_workspace_execution_releases(destination, destination)
            self.assertTrue(identity.accepted)
            self.assertEqual(identity.added_event_ids, ())
            self.assertEqual(identity.changed_artifact_ids, ())
            self.assertEqual(identity.content_address, diff_review_workspace_execution_releases(loaded, loaded).content_address)
            self.assertTrue(dossier.run_id)

    def test_report_hydration_rejects_derived_address_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, report = self._report(directory)
            bundle = build_review_workspace_execution_release(report)
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
            _, report = self._report(directory)
            bundle = build_review_workspace_execution_release(report)
            destination = Path(directory) / "execution-release"
            write_review_workspace_execution_release(bundle, destination)
            (destination / "events.jsonl").write_bytes((destination / "events.jsonl").read_bytes() + b"\n")
            (destination / "unexpected.txt").write_text("unexpected", encoding="utf-8")
            verification = verify_review_workspace_execution_release(destination)
            self.assertFalse(verification.accepted)
            self.assertIn("events.jsonl", verification.tampered_files)
            self.assertIn("unexpected.txt", verification.unexpected_files)

    def test_release_schema_and_capabilities_are_public_and_bounded(self) -> None:
        schema = review_workspace_execution_release_schema()
        capabilities = review_workspace_execution_release_capabilities()
        self.assertEqual(schema["version"], "review-workspace-execution-release-schema-v1")
        self.assertEqual(len(schema["artifact_filenames"]), 6)
        self.assertTrue(capabilities["independent_manifest_verification"])
        self.assertTrue(capabilities["public_boundary_audit"])


if __name__ == "__main__":
    unittest.main()

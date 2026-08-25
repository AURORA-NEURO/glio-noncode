"""Deep tests for portable, verified workspace release bundles."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.models import ReviewDecision, ReviewState
from glio_noncode.runtime import CaseRuntime
from glio_noncode.workspace_history import build_persisted_workspace_history
from glio_noncode.workspace_release import (
    WORKSPACE_RELEASE_MANIFEST,
    build_persisted_workspace_release,
    build_workspace_release_bundle,
    verify_workspace_release_bundle,
    write_workspace_release_bundle,
)

from .helpers import fixture_manifest


def accepted_review(case_id: str, hypothesis_id: str, claim_ids: tuple[str, ...]) -> ReviewDecision:
    return ReviewDecision(
        review_id="workspace-release-review",
        case_id=case_id,
        reviewer="scientific-reviewer",
        state=ReviewState.ACCEPTED,
        reviewed_hypothesis_ids=(hypothesis_id,),
        rationale="The portable workspace handoff preserves the research boundary.",
        checked_claim_ids=claim_ids,
    )


class WorkspaceReleaseTests(unittest.TestCase):
    def _reviewed_runtime(self, directory: str) -> tuple[CaseRuntime, object]:
        runtime = CaseRuntime(directory)
        original = runtime.evaluate(fixture_manifest())
        runtime.review_run(
            original.run_id,
            accepted_review(
                original.case_id,
                original.hypotheses[0].hypothesis_id,
                tuple(item.evidence_id for item in original.evidence),
            ),
        )
        return runtime, original

    def test_bundle_builds_eight_public_artifacts_and_verifies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, original = self._reviewed_runtime(directory)
            bundle = build_persisted_workspace_release(runtime, original.run_id)
            self.assertTrue(bundle.accepted)
            self.assertEqual(bundle.artifact_count, 8)
            self.assertEqual(bundle.failed_check_ids, ())
            self.assertEqual(
                {item.filename for item in bundle.artifacts},
                {
                    "workspace-history.json",
                    "workspace-current.json",
                    "workspace-summary.json",
                    "workspace-snapshots.csv",
                    "workspace-records.csv",
                    "workspace-transitions.csv",
                    "release-gate.json",
                    "workspace-report.md",
                },
            )
            destination = Path(directory) / "release"
            write_workspace_release_bundle(bundle, destination)
            verification = verify_workspace_release_bundle(destination)
            self.assertTrue(verification.accepted)
            self.assertTrue(verification.manifest_address_valid)
            self.assertTrue(verification.public_boundary_valid)
            self.assertEqual(verification.artifact_count, 8)
            self.assertEqual(verification.verified_artifact_count, 8)
            self.assertEqual(verification.failed_artifact_ids, ())
            self.assertEqual(verification.unexpected_filenames, ())

    def test_build_is_deterministic_and_manifest_reconstructs_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, original = self._reviewed_runtime(directory)
            first = build_persisted_workspace_release(runtime, original.run_id)
            second = build_persisted_workspace_release(runtime, original.run_id)
            self.assertEqual(first.to_dict(), second.to_dict())
            self.assertEqual(first.manifest_dict(), second.manifest_dict())
            destination = Path(directory) / "release"
            write_workspace_release_bundle(first, destination)
            manifest = json.loads(
                (destination / WORKSPACE_RELEASE_MANIFEST).read_text(encoding="utf-8")
            )
            self.assertNotIn("payload", manifest["artifacts"][0])
            self.assertEqual(manifest["content_address"], first.content_address)
            self.assertEqual(
                json.loads((destination / "workspace-summary.json").read_text(encoding="utf-8"))["history_address"],
                first.history_address,
            )

    def test_tampering_missing_and_extra_files_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, original = self._reviewed_runtime(directory)
            destination = Path(directory) / "release"
            write_workspace_release_bundle(
                build_persisted_workspace_release(runtime, original.run_id),
                destination,
            )
            history_path = destination / "workspace-history.json"
            history_path.write_text(history_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            tampered = verify_workspace_release_bundle(destination)
            self.assertFalse(tampered.accepted)
            self.assertIn("workspace-history", tampered.failed_artifact_ids)

            history_path.unlink()
            (destination / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            missing = verify_workspace_release_bundle(destination)
            self.assertFalse(missing.accepted)
            self.assertIn("workspace-history", missing.failed_artifact_ids)
            self.assertEqual(missing.unexpected_filenames, ("unexpected.txt",))

    def test_blocked_history_is_exportable_but_never_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, original = self._reviewed_runtime(directory)
            run_record = runtime.get_run(original.run_id)
            old_address = str(run_record["dossier_history"][0]).split(":", 1)[1]
            old_path = runtime.store.store.objects / f"{old_address}.json"
            old_payload = json.loads(old_path.read_text(encoding="utf-8"))
            old_payload["status"] = "tampered"
            old_path.write_text(json.dumps(old_payload), encoding="utf-8")

            history = build_persisted_workspace_history(runtime, original.run_id)
            self.assertFalse(history.accepted)
            bundle = build_workspace_release_bundle(history)
            self.assertFalse(bundle.accepted)
            self.assertIn("history-accepted", bundle.failed_check_ids)
            destination = Path(directory) / "blocked-release"
            write_workspace_release_bundle(bundle, destination)
            verification = verify_workspace_release_bundle(destination)
            self.assertFalse(verification.accepted)
            self.assertEqual(verification.verified_artifact_count, 8)
            self.assertTrue(verification.manifest_address_valid)

    def test_public_boundary_excludes_private_and_attribution_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, original = self._reviewed_runtime(directory)
            bundle = build_persisted_workspace_release(runtime, original.run_id)
            serialized = json.dumps(bundle.to_dict(), sort_keys=True).lower()
            for forbidden in (
                "subject_id",
                "sample_id",
                "agent_id",
                "agent_name",
                "assistant_id",
                "generated_by",
                "model_name",
                "author_name",
                "programming_language",
            ):
                self.assertNotIn(forbidden, serialized)

    def test_cli_and_http_release_surfaces_return_addressed_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, original = self._reviewed_runtime(directory)
            destination = Path(directory) / "cli-release"
            verification_path = Path(directory) / "cli-verification.json"
            self.assertEqual(
                main(
                    [
                        "run-workspace-release",
                        original.run_id,
                        "--data-root",
                        directory,
                        "--output",
                        str(destination),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "run-workspace-release-verify",
                        str(destination),
                        "--output",
                        str(verification_path),
                    ]
                ),
                0,
            )
            verification = json.loads(verification_path.read_text(encoding="utf-8"))
            self.assertTrue(verification["accepted"])
            self.assertEqual(verification["verified_artifact_count"], 8)

            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", f"/v1/runs/{original.run_id}/workspace/release")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertTrue(payload["accepted"])
                self.assertEqual(payload["artifact_count"], 8)
                self.assertTrue(payload["content_address"].startswith("workspace-release:"))
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()

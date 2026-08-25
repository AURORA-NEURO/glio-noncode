"""Deep tests for portable comparison handoff bundles and verification."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.comparison_release import (
    build_comparison_release_bundle,
    build_persisted_comparison_release,
    verify_comparison_release_bundle,
    write_comparison_release_bundle,
)
from glio_noncode.models import ReviewDecision, ReviewState
from glio_noncode.run_comparison import compare_run_snapshots
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


def accepted_review(run_id: str, case_id: str, hypothesis_id: str, claim_ids: tuple[str, ...]) -> ReviewDecision:
    return ReviewDecision(
        review_id=f"review-comparison-release-{run_id}",
        case_id=case_id,
        reviewer="scientific-reviewer",
        state=ReviewState.ACCEPTED,
        reviewed_hypothesis_ids=(hypothesis_id,),
        rationale="The comparison handoff preserves a research-only review transition.",
        checked_claim_ids=claim_ids,
    )


class ComparisonReleaseTests(unittest.TestCase):
    def _reviewed_runtime(self, directory: str) -> tuple[CaseRuntime, str]:
        runtime = CaseRuntime(directory)
        original = runtime.evaluate(fixture_manifest())
        runtime.review_run(
            original.run_id,
            accepted_review(
                original.run_id,
                original.case_id,
                original.hypotheses[0].hypothesis_id,
                tuple(item.evidence_id for item in original.evidence),
            ),
        )
        return runtime, original.run_id

    def test_accepted_bundle_contains_ten_artifacts_and_reopens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, run_id = self._reviewed_runtime(directory)
            bundle = build_persisted_comparison_release(
                runtime,
                run_id,
                run_id,
                source_snapshot=0,
                target_snapshot=1,
            )
            self.assertTrue(bundle.accepted)
            self.assertEqual(bundle.state, "ready")
            self.assertEqual(bundle.artifact_count, 10)
            self.assertEqual(bundle.failed_check_ids, ())
            self.assertTrue(bundle.content_address.startswith("comparison-release:"))

            destination = Path(directory) / "comparison-release"
            write_comparison_release_bundle(bundle, destination)
            self.assertEqual(len(list(destination.iterdir())), 11)
            self.assertTrue((destination / "comparison.md").read_text(encoding="utf-8").startswith("# Dossier comparison"))
            verification = verify_comparison_release_bundle(destination)
            self.assertTrue(verification.accepted)
            self.assertTrue(verification.manifest_address_valid)
            self.assertEqual(verification.artifact_count, 10)
            self.assertEqual(verification.verified_artifact_count, 10)
            self.assertEqual(verification.failed_artifact_ids, ())

    def test_direct_bundle_without_history_is_blocked_but_inspectable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, run_id = self._reviewed_runtime(directory)
            comparison = compare_run_snapshots(runtime, run_id, 0, 1)
            bundle = build_comparison_release_bundle(comparison)

            self.assertFalse(bundle.accepted)
            self.assertEqual(bundle.state, "blocked")
            self.assertIn("history-available", bundle.failed_check_ids)
            self.assertEqual(bundle.artifact_count, 10)

    def test_tampered_csv_and_unsafe_path_fail_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, run_id = self._reviewed_runtime(directory)
            bundle = build_persisted_comparison_release(
                runtime,
                run_id,
                run_id,
                source_snapshot=0,
                target_snapshot=1,
            )
            destination = Path(directory) / "comparison-release"
            write_comparison_release_bundle(bundle, destination)
            csv_path = destination / "hypotheses-diff.csv"
            csv_path.write_text(csv_path.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
            tampered = verify_comparison_release_bundle(destination)
            self.assertFalse(tampered.accepted)
            self.assertIn("hypotheses-diff", tampered.failed_artifact_ids)
            self.assertFalse(tampered.manifest_address_valid)

            manifest_path = destination / "release.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"][0]["filename"] = "../outside.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            unsafe = verify_comparison_release_bundle(destination)
            self.assertFalse(unsafe.accepted)
            self.assertTrue(any("unsafe artifact path" in warning for warning in unsafe.warnings))

    def test_cli_build_and_verify_commands_write_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime, run_id = self._reviewed_runtime(directory)
            destination = Path(directory) / "cli-comparison-release"
            verification_path = Path(directory) / "verification.json"
            self.assertEqual(
                main(
                    [
                        "run-compare-release",
                        run_id,
                        run_id,
                        "--source-snapshot",
                        "0",
                        "--target-snapshot",
                        "1",
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
                        "run-compare-release-verify",
                        str(destination),
                        "--output",
                        str(verification_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])

    def test_http_comparison_release_route_returns_gated_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request(
                    "POST",
                    "/v1/evaluate",
                    body=json.dumps(fixture_manifest().to_dict()).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                evaluated = connection.getresponse()
                self.assertEqual(evaluated.status, 200)
                dossier = json.loads(evaluated.read())
                run_id = dossier["run_id"]
                review = accepted_review(
                    run_id,
                    dossier["case_id"],
                    dossier["hypotheses"][0]["hypothesis_id"],
                    tuple(item["evidence_id"] for item in dossier["evidence"]),
                )
                connection.request(
                    "POST",
                    f"/v1/runs/{run_id}/review",
                    body=json.dumps(review.to_dict()).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                reviewed = connection.getresponse()
                self.assertEqual(reviewed.status, 200)
                reviewed.read()

                connection.request(
                    "GET",
                    f"/v1/runs/{run_id}/compare/{run_id}/release?source_snapshot=0&target_snapshot=1",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read())
                self.assertTrue(payload["accepted"])
                self.assertEqual(payload["artifact_count"], 10)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()

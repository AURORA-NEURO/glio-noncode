"""Deep contract tests for gated dossier release bundles."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.dossier_release import (
    build_dossier_release_bundle,
    build_persisted_dossier_release,
    verify_dossier_release_bundle,
    write_dossier_release_bundle,
)
from glio_noncode.errors import ValidationError
from glio_noncode.models import ReviewDecision, ReviewState
from glio_noncode.run_catalog import inspect_run
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


def accepted_review(run_id: str, case_id: str, hypothesis_id: str, claim_ids: tuple[str, ...]) -> ReviewDecision:
    return ReviewDecision(
        review_id=f"review-release-{run_id}",
        case_id=case_id,
        reviewer="scientific-reviewer",
        state=ReviewState.ACCEPTED,
        reviewed_hypothesis_ids=(hypothesis_id,),
        rationale="The dossier was reviewed with uncertainty and research-only boundaries retained.",
        checked_claim_ids=claim_ids,
    )


class DossierReleaseTests(unittest.TestCase):
    def test_unreviewed_release_is_explicitly_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            bundle = build_dossier_release_bundle(dossier, inspect_run(runtime, dossier.run_id))

            self.assertFalse(bundle.accepted)
            self.assertEqual(bundle.state, "blocked")
            self.assertIn("review-accepted", bundle.failed_check_ids)
            self.assertEqual(bundle.artifact_count, 10)
            self.assertTrue(all(item.content_address.startswith("dossier-release-artifact:") for item in bundle.artifacts))

    def test_accepted_release_writes_ten_artifacts_and_reopens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
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
            bundle = build_persisted_dossier_release(runtime, original.run_id)
            self.assertTrue(bundle.accepted)
            self.assertEqual(bundle.state, "ready")
            self.assertEqual(bundle.failed_check_ids, ())

            destination = Path(directory) / "release"
            write_dossier_release_bundle(bundle, destination)
            self.assertTrue((destination / "release.json").is_file())
            self.assertEqual(len(list(destination.iterdir())), 11)
            verification = verify_dossier_release_bundle(destination)
            self.assertTrue(verification.accepted)
            self.assertTrue(verification.manifest_address_valid)
            self.assertEqual(verification.artifact_count, 10)
            self.assertEqual(verification.verified_artifact_count, 10)
            self.assertEqual(verification.failed_artifact_ids, ())

    def test_tampered_payload_and_unsafe_manifest_path_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
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
            destination = Path(directory) / "release"
            write_dossier_release_bundle(build_persisted_dossier_release(runtime, original.run_id), destination)
            (destination / "dossier.md").write_text(
                (destination / "dossier.md").read_text(encoding="utf-8") + "\ntampered\n",
                encoding="utf-8",
            )
            tampered = verify_dossier_release_bundle(destination)
            self.assertFalse(tampered.accepted)
            self.assertIn("dossier-markdown", tampered.failed_artifact_ids)
            self.assertFalse(tampered.manifest_address_valid)

            manifest_path = destination / "release.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["artifacts"][0]["filename"] = "../outside.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            unsafe = verify_dossier_release_bundle(destination)
            self.assertFalse(unsafe.accepted)
            self.assertIn(manifest["artifacts"][0]["artifact_id"], unsafe.failed_artifact_ids)
            self.assertTrue(any("unsafe artifact path" in warning for warning in unsafe.warnings))

    def test_cli_release_and_verify_commands_write_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
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
            destination = Path(directory) / "cli-release"
            verification_path = Path(directory) / "verification.json"
            self.assertEqual(
                main(
                    [
                        "run-release",
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
                        "run-release-verify",
                        str(destination),
                        "--output",
                        str(verification_path),
                    ]
                ),
                0,
            )
            self.assertTrue(json.loads(verification_path.read_text(encoding="utf-8"))["accepted"])

    def test_http_release_route_is_gated_before_and_after_review(self) -> None:
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

                connection.request("GET", f"/v1/runs/{run_id}/release")
                blocked = connection.getresponse()
                self.assertEqual(blocked.status, 200)
                self.assertFalse(json.loads(blocked.read())["accepted"])

                review_body = json.dumps(
                    accepted_review(
                        run_id,
                        dossier["case_id"],
                        dossier["hypotheses"][0]["hypothesis_id"],
                        tuple(item["evidence_id"] for item in dossier["evidence"]),
                    ).to_dict()
                ).encode("utf-8")
                connection.request(
                    "POST",
                    f"/v1/runs/{run_id}/review",
                    body=review_body,
                    headers={"Content-Type": "application/json"},
                )
                reviewed = connection.getresponse()
                self.assertEqual(reviewed.status, 200)
                reviewed.read()

                connection.request("GET", f"/v1/runs/{run_id}/release")
                released = connection.getresponse()
                self.assertEqual(released.status, 200)
                payload = json.loads(released.read())
                self.assertTrue(payload["accepted"])
                self.assertEqual(payload["artifact_count"], 10)
                self.assertEqual(payload["failed_check_ids"], [])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_persisted_integrity_failure_cannot_be_released(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            run_record = runtime.get_run(dossier.run_id)
            event_path = runtime.store.store.objects / f"{run_record['event_address'].split(':', 1)[1]}.json"
            event_record = json.loads(event_path.read_text(encoding="utf-8"))
            event_record["events"][1]["event_hash"] = "sha256:corrupted"
            event_path.write_text(json.dumps(event_record), encoding="utf-8")
            with self.assertRaises(ValidationError):
                build_persisted_dossier_release(runtime, dossier.run_id)


if __name__ == "__main__":
    unittest.main()

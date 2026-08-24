"""Deep verification for the portable architecture program release bundle."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.program_runtime_bundle import (
    PROGRAM_RELEASE_ARTIFACT_COUNT,
    PROGRAM_RELEASE_CHECK_COUNT,
    build_program_release,
    load_program_release_manifest,
    program_release_payloads,
    verify_program_release,
    write_program_release,
)
from glio_noncode.program_runtime_execution import run_program_runtime
from glio_noncode.program_runtime_release_contracts import ProgramReleaseState


class ProgramRuntimeBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = run_program_runtime()
        cls.release = build_program_release(cls.runtime)

    def test_release_inventory_is_published_and_addressed(self) -> None:
        self.assertTrue(self.release.accepted)
        self.assertEqual(self.release.state, ProgramReleaseState.PUBLISHED)
        self.assertEqual(len(self.release.artifacts), PROGRAM_RELEASE_ARTIFACT_COUNT)
        self.assertEqual(len(self.release.checks), PROGRAM_RELEASE_CHECK_COUNT)
        self.assertEqual(self.release.passed_checks, PROGRAM_RELEASE_CHECK_COUNT)
        self.assertEqual(self.release.failed_checks, 0)
        self.assertEqual(self.release.manifest.artifact_count, PROGRAM_RELEASE_ARTIFACT_COUNT)
        self.assertEqual(
            set(self.release.manifest.artifact_filenames),
            {item.filename for item in self.release.artifacts},
        )
        self.assertTrue(all(item.content_address.startswith("sha256:") for item in self.release.artifacts))

    def test_payloads_are_complete_and_public(self) -> None:
        payloads = program_release_payloads(self.runtime)
        self.assertEqual(len(payloads), PROGRAM_RELEASE_ARTIFACT_COUNT)
        self.assertEqual(payloads["program-checks.csv"].count("\n") - 1, 172)
        self.assertEqual(payloads["program-receipts.csv"].count("\n") - 1, 16)
        self.assertNotIn("subject_id", "".join(payloads.values()).lower())
        self.assertIn('"accepted": true', payloads["program-summary.json"])

    def test_bundle_can_be_written_reopened_and_verified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glio-program-release-") as directory:
            release = write_program_release(directory, self.runtime, release=self.release)
            self.assertEqual(release.content_address, self.release.content_address)
            files = {item.name for item in Path(directory).iterdir()}
            self.assertEqual(len(files), PROGRAM_RELEASE_ARTIFACT_COUNT + 2)
            manifest = load_program_release_manifest(directory)
            self.assertEqual(manifest.content_address, self.release.manifest.content_address)
            verification = verify_program_release(directory, release=self.release)
            self.assertTrue(verification.accepted)
            self.assertEqual(verification.failed_checks, 0)
            reopened = verify_program_release(directory)
            self.assertTrue(reopened.accepted)
            self.assertEqual(reopened.failed_checks, 0)

    def test_mutated_artifact_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glio-program-release-") as directory:
            write_program_release(directory, self.runtime, release=self.release)
            path = Path(directory) / "program-summary.json"
            path.write_text(path.read_text(encoding="utf-8") + "x", encoding="utf-8")
            verification = verify_program_release(directory, release=self.release)
            self.assertFalse(verification.accepted)
            self.assertGreaterEqual(verification.failed_checks, 2)
            self.assertTrue(any(item.check_id == "program-summary:hash" for item in verification.checks if not item.passed))

    def test_mutated_manifest_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glio-program-release-") as directory:
            write_program_release(directory, self.runtime, release=self.release)
            path = Path(directory) / "program-release-manifest.json"
            manifest = json.loads(path.read_text(encoding="utf-8"))
            manifest["state"] = "review"
            path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            verification = verify_program_release(directory, release=self.release)
            self.assertFalse(verification.accepted)
            self.assertTrue(any(item.check_id == "manifest-self-address" for item in verification.checks if not item.passed))

    def test_manifest_and_descriptor_are_json_reopenable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glio-program-release-") as directory:
            write_program_release(directory, self.runtime, release=self.release)
            manifest = json.loads((Path(directory) / "program-release-manifest.json").read_text(encoding="utf-8"))
            descriptor = json.loads((Path(directory) / "program-release.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["artifact_count"], PROGRAM_RELEASE_ARTIFACT_COUNT)
            self.assertEqual(len(descriptor["checks"]), PROGRAM_RELEASE_CHECK_COUNT)
            self.assertEqual(descriptor["state"], "published")

    def test_checked_in_closure_matches_release_denominators(self) -> None:
        path = Path(__file__).parents[1] / "data" / "architecture-program-release-closure.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["release"]["state"], "published")
        self.assertEqual(payload["release"]["artifact_count"], PROGRAM_RELEASE_ARTIFACT_COUNT)
        self.assertEqual(payload["release"]["check_count"], PROGRAM_RELEASE_CHECK_COUNT)
        self.assertTrue(payload["verification"]["accepted"])


if __name__ == "__main__":
    unittest.main()

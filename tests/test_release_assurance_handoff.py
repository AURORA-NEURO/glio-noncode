"""Tests for durable release-assurance handoffs."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from glio_noncode.release_assurance_contracts import RELEASE_ASSURANCE_HANDOFF_ARTIFACT_COUNT
from glio_noncode.release_assurance_handoff import (
    build_release_assurance_handoff,
    diff_release_assurance_handoffs,
    inspect_release_assurance_handoff,
    query_release_assurance_handoff,
    release_assurance_handoff_status,
    replay_release_assurance_handoff,
    verify_release_assurance_handoff,
    write_release_assurance_handoff,
)
from glio_noncode.release_assurance_runtime import run_release_assurance
from glio_noncode.release_assurance_support import forbidden_keys
from glio_noncode.service_surface import build_service_surface_snapshot


class ReleaseAssuranceHandoffTests(unittest.TestCase):
    """Exercise the durable handoff as an offline release artifact."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = build_service_surface_snapshot()
        cls.public_audit = build_default_public_surface_audit(snapshot=cls.service)
        cls.runtime = run_release_assurance(
            cls.service,
            public_audit=cls.public_audit,
            bundle_id="handoff-test-bundle",
            run_id="handoff-test-run",
        )
        cls.packet = build_release_assurance_handoff(cls.runtime)

    def test_packet_closes_nineteen_artifacts_and_public_boundary(self) -> None:
        self.assertTrue(self.packet.accepted)
        self.assertEqual(len(self.packet.artifacts), RELEASE_ASSURANCE_HANDOFF_ARTIFACT_COUNT)
        self.assertEqual(self.packet.manifest.artifact_count, 19)
        self.assertEqual(self.packet.manifest.required_artifact_count, 19)
        self.assertEqual(
            len({item.artifact_id for item in self.packet.artifacts}),
            RELEASE_ASSURANCE_HANDOFF_ARTIFACT_COUNT,
        )
        self.assertEqual(
            len({item.relative_path for item in self.packet.artifacts}),
            RELEASE_ASSURANCE_HANDOFF_ARTIFACT_COUNT,
        )
        self.assertEqual(forbidden_keys(self.packet.to_dict()), ())
        self.assertNotIn(b"agent_id", json.dumps(self.packet.to_dict()).encode().lower())
        self.assertNotIn(b"model_name", json.dumps(self.packet.to_dict()).encode().lower())

    def test_write_verify_inspect_status_query_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_handoff(self.packet, directory)
            verification = verify_release_assurance_handoff(directory)
            self.assertTrue(verification.accepted)
            self.assertEqual(verification.checked_artifact_count, 19)
            self.assertEqual(verification.missing_paths, ())
            self.assertEqual(verification.unexpected_paths, ())
            self.assertEqual(verification.tampered_paths, ())
            inspection = inspect_release_assurance_handoff(directory)
            self.assertEqual(inspection.state.value, "inspected")
            self.assertEqual(inspection.artifact_count, 19)
            status = release_assurance_handoff_status(directory)
            self.assertTrue(status["accepted"])
            self.assertEqual(status["checked_artifact_count"], 19)
            query = query_release_assurance_handoff(
                directory,
                resource="artifacts",
                role="runtime",
                limit=2,
            )
            self.assertTrue(query.accepted)
            self.assertEqual(query.total, 1)
            self.assertEqual(query.items[0]["artifact_id"], "runtime-json")
            status_query = query_release_assurance_handoff(directory, resource="status")
            self.assertEqual(status_query.total, 1)
            replay = replay_release_assurance_handoff(directory)
            self.assertTrue(replay["accepted"])
            self.assertTrue(replay["deterministic"])
            self.assertEqual(replay["first_address"], replay["second_address"])

    def test_tamper_and_unexpected_file_controls_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_handoff(self.packet, directory)
            target = Path(directory) / "runtime" / "release-assurance.json"
            payload = json.loads(target.read_text(encoding="utf-8"))
            payload["accepted"] = False
            target.write_text(json.dumps(payload), encoding="utf-8")
            tampered = verify_release_assurance_handoff(directory)
            self.assertFalse(tampered.accepted)
            self.assertIn("runtime/release-assurance.json", tampered.tampered_paths)

        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_handoff(self.packet, directory)
            (Path(directory) / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            unexpected = verify_release_assurance_handoff(directory)
            self.assertFalse(unexpected.accepted)
            self.assertIn("unexpected.txt", unexpected.unexpected_paths)

    def test_symlinked_artifact_parent_is_an_unsafe_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external:
            write_release_assurance_handoff(self.packet, directory)
            runtime = Path(directory) / "runtime"
            external_runtime = Path(external) / "runtime"
            external_runtime.mkdir()
            for item in runtime.iterdir():
                item.replace(external_runtime / item.name)
            runtime.rmdir()
            try:
                runtime.symlink_to(external_runtime, target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation is unavailable in this environment")
            verification = verify_release_assurance_handoff(directory)
            self.assertFalse(verification.accepted)
            self.assertIn("runtime/release-assurance.json", verification.unsafe_paths)

    def test_overwrite_requires_explicit_opt_in_and_manifest_drift_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_handoff(self.packet, directory)
            with self.assertRaises(Exception):
                write_release_assurance_handoff(self.packet, directory)
            write_release_assurance_handoff(self.packet, directory, allow_existing=True)
            manifest = Path(directory) / "manifest.json"
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["artifact_count"] = 18
            manifest.write_text(json.dumps(value), encoding="utf-8")
            drift = verify_release_assurance_handoff(directory)
            self.assertFalse(drift.accepted)
            self.assertIn("manifest.artifact_count", drift.manifest_drift)

    def test_manifest_diff_detects_changed_run_without_source_rebuild(self) -> None:
        other_runtime = run_release_assurance(
            self.service,
            public_audit=self.public_audit,
            bundle_id="handoff-other-bundle",
            run_id="handoff-other-run",
        )
        other_packet = build_release_assurance_handoff(other_runtime)
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            write_release_assurance_handoff(self.packet, left)
            write_release_assurance_handoff(other_packet, right)
            diff = diff_release_assurance_handoffs(left, right)
            self.assertTrue(diff.accepted)
            self.assertFalse(diff.identical)
            self.assertEqual(diff.added_artifact_ids, ())
            self.assertEqual(diff.removed_artifact_ids, ())
            self.assertGreater(len(diff.changed_artifact_ids), 0)
            self.assertEqual(len(diff.unchanged_artifact_ids) + len(diff.changed_artifact_ids), 19)

    def test_api_handoff_routes_verify_and_query_existing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_release_assurance_handoff(self.packet, directory)
            server = create_server("127.0.0.1", 0, directory)
            server.glio_service_surface = self.service
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=120)
                encoded = directory.replace("\\", "/")
                connection.request("GET", f"/v1/release-assurance/handoff/status?directory={encoded}")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["accepted"])
                connection.request("GET", f"/v1/release-assurance/handoff/query?directory={encoded}&role=history")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["total"], 1)
                connection.request("GET", f"/v1/release-assurance/handoff/verify?directory={encoded}")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["accepted"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_cli_handoff_status_and_verify_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as output:
            write_release_assurance_handoff(self.packet, directory)
            status_path = str(Path(output) / "status.json")
            verify_path = str(Path(output) / "verify.json")
            self.assertEqual(
                main(["release-assurance-handoff", "--plane", "status", "--directory", directory, "--output", status_path]),
                0,
            )
            self.assertEqual(
                main(["release-assurance-handoff-verify", directory, "--output", verify_path]),
                0,
            )
            self.assertTrue(json.loads(Path(status_path).read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(Path(verify_path).read_text(encoding="utf-8"))["accepted"])

    def test_cli_handoff_build_keeps_receipt_outside_verified_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as output:
            packet_path = str(Path(output) / "packet.json")
            verify_path = str(Path(output) / "verification.json")
            self.assertEqual(
                main([
                    "release-assurance-handoff",
                    "--plane",
                    "build",
                    "--destination",
                    directory,
                    "--output",
                    packet_path,
                ]),
                0,
            )
            self.assertEqual(
                main(["release-assurance-handoff-verify", directory, "--output", verify_path]),
                0,
            )
            self.assertTrue(json.loads(Path(packet_path).read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(Path(verify_path).read_text(encoding="utf-8"))["accepted"])


if __name__ == "__main__":
    unittest.main()

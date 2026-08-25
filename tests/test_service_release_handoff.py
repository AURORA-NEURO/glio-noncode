"""Deep contract tests for the durable service-release handoff."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.service_release_contracts import SERVICE_RELEASE_HANDOFF_ARTIFACT_COUNT
from glio_noncode.service_release_handoff import (
    build_service_release_handoff,
    diff_service_release_handoffs,
    inspect_service_release_handoff,
    query_service_release_handoff,
    replay_service_release_handoff,
    service_release_handoff_status,
    verify_service_release_handoff,
    write_service_release_handoff,
)
from glio_noncode.service_release_runtime import run_service_release
from glio_noncode.service_release_support import forbidden_keys
from glio_noncode.service_surface import build_service_surface_snapshot


class ServiceReleaseHandoffTests(unittest.TestCase):
    """Exercise the handoff as an independent offline service boundary."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.service = build_service_surface_snapshot()
        cls.runtime = run_service_release(
            cls.service,
            bundle_id="service-handoff-test-bundle",
            run_id="service-handoff-test-run",
        )
        cls.packet = build_service_release_handoff(cls.runtime, cls.service)

    def test_packet_closes_thirteen_artifacts_and_public_boundary(self) -> None:
        self.assertTrue(self.packet.accepted)
        self.assertEqual(len(self.packet.artifacts), SERVICE_RELEASE_HANDOFF_ARTIFACT_COUNT)
        self.assertEqual(self.packet.manifest.artifact_count, 13)
        self.assertEqual(self.packet.manifest.required_artifact_count, 13)
        self.assertEqual(
            len({item.artifact_id for item in self.packet.artifacts}),
            SERVICE_RELEASE_HANDOFF_ARTIFACT_COUNT,
        )
        self.assertEqual(
            len({item.relative_path for item in self.packet.artifacts}),
            SERVICE_RELEASE_HANDOFF_ARTIFACT_COUNT,
        )
        self.assertEqual(forbidden_keys(self.packet.to_dict()), ())
        serialized = json.dumps(self.packet.to_dict(), sort_keys=True).encode("utf-8").lower()
        self.assertNotIn(b"agent_id", serialized)
        self.assertNotIn(b"model_name", serialized)

    def test_write_verify_inspect_status_query_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_service_release_handoff(self.packet, directory)
            verification = verify_service_release_handoff(directory)
            self.assertTrue(verification.accepted, verification.to_dict())
            self.assertEqual(verification.checked_artifact_count, 13)
            self.assertEqual(verification.missing_paths, ())
            self.assertEqual(verification.unexpected_paths, ())
            self.assertEqual(verification.tampered_paths, ())
            inspection = inspect_service_release_handoff(directory)
            self.assertEqual(inspection.state.value, "inspected")
            self.assertEqual(inspection.artifact_count, 13)
            status = service_release_handoff_status(directory)
            self.assertTrue(status["accepted"])
            self.assertEqual(status["checked_artifact_count"], 13)
            query = query_service_release_handoff(
                directory,
                resource="artifacts",
                surface_id="program-release",
                limit=10,
            )
            self.assertTrue(query.accepted)
            self.assertEqual(query.total, 4)
            self.assertTrue(all(item["surface_id"] == "program-release" for item in query.items))
            status_query = query_service_release_handoff(directory, resource="status")
            self.assertEqual(status_query.total, 1)
            replay = replay_service_release_handoff(directory)
            self.assertTrue(replay["accepted"])
            self.assertTrue(replay["deterministic"])
            self.assertEqual(replay["first_address"], replay["second_address"])

    def test_tamper_and_unexpected_file_controls_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_service_release_handoff(self.packet, directory)
            target = Path(directory) / "surfaces" / "status.json"
            payload = json.loads(target.read_text(encoding="utf-8"))
            payload["accepted"] = False
            target.write_text(json.dumps(payload), encoding="utf-8")
            tampered = verify_service_release_handoff(directory)
            self.assertFalse(tampered.accepted)
            self.assertIn("surfaces/status.json", tampered.tampered_paths)

        with tempfile.TemporaryDirectory() as directory:
            write_service_release_handoff(self.packet, directory)
            (Path(directory) / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")
            unexpected = verify_service_release_handoff(directory)
            self.assertFalse(unexpected.accepted)
            self.assertIn("unexpected.txt", unexpected.unexpected_paths)

    def test_overwrite_requires_opt_in_and_manifest_drift_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_service_release_handoff(self.packet, directory)
            with self.assertRaises(Exception):
                write_service_release_handoff(self.packet, directory)
            write_service_release_handoff(self.packet, directory, allow_existing=True)
            manifest = Path(directory) / "manifest.json"
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["artifact_count"] = 12
            manifest.write_text(json.dumps(value), encoding="utf-8")
            drift = verify_service_release_handoff(directory)
            self.assertFalse(drift.accepted)
            self.assertIn("manifest.artifact_count", drift.manifest_drift)

    def test_symlinked_artifact_parent_is_unsafe(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external:
            write_service_release_handoff(self.packet, directory)
            surfaces = Path(directory) / "surfaces"
            external_surfaces = Path(external) / "surfaces"
            external_surfaces.mkdir()
            for item in surfaces.iterdir():
                item.replace(external_surfaces / item.name)
            surfaces.rmdir()
            try:
                surfaces.symlink_to(external_surfaces, target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation is unavailable in this environment")
            verification = verify_service_release_handoff(directory)
            self.assertFalse(verification.accepted)
            self.assertIn("surfaces/status.json", verification.unsafe_paths)

    def test_manifest_diff_detects_changed_run(self) -> None:
        other_runtime = run_service_release(
            self.service,
            bundle_id="service-handoff-other-bundle",
            run_id="service-handoff-other-run",
        )
        other_packet = build_service_release_handoff(other_runtime, self.service)
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            write_service_release_handoff(self.packet, left)
            write_service_release_handoff(other_packet, right)
            diff = diff_service_release_handoffs(left, right)
            self.assertTrue(diff.accepted)
            self.assertFalse(diff.identical)
            self.assertEqual(diff.added_artifact_ids, ())
            self.assertEqual(diff.removed_artifact_ids, ())
            self.assertEqual(diff.changed_artifact_ids, ())
            self.assertEqual(diff.unchanged_artifact_ids, tuple(sorted(item.artifact_id for item in self.packet.artifacts)))

    def test_http_handoff_routes_build_verify_and_query(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_service_release_handoff(self.packet, directory)
            server = create_server("127.0.0.1", 0, directory)
            server.glio_service_surface = self.service
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=120)
                connection.request("GET", "/v1/service-release/handoff?bundle_id=http-handoff&run_id=http-handoff-run")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["accepted"])
                encoded = directory.replace("\\", "/")
                connection.request("GET", f"/v1/service-release/handoff/status?directory={encoded}")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["accepted"])
                connection.request(
                    "GET",
                    f"/v1/service-release/handoff/query?directory={encoded}&surface_id=program-release",
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(json.loads(response.read())["total"], 4)
                connection.request("GET", f"/v1/service-release/handoff/verify?directory={encoded}")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertTrue(json.loads(response.read())["accepted"])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_cli_handoff_build_status_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as output:
            packet_path = str(Path(output) / "packet.json")
            status_path = str(Path(output) / "status.json")
            verify_path = str(Path(output) / "verify.json")
            self.assertEqual(
                main([
                    "service-release-handoff",
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
                main([
                    "service-release-handoff",
                    "--plane",
                    "status",
                    "--directory",
                    directory,
                    "--output",
                    status_path,
                ]),
                0,
            )
            self.assertEqual(
                main(["service-release-handoff-verify", directory, "--output", verify_path]),
                0,
            )
            self.assertTrue(json.loads(Path(packet_path).read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(Path(status_path).read_text(encoding="utf-8"))["accepted"])
            self.assertTrue(json.loads(Path(verify_path).read_text(encoding="utf-8"))["accepted"])


if __name__ == "__main__":
    unittest.main()

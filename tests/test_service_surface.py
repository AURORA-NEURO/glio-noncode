"""Contract tests for the local service surface and its public projections."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.service_surface import (
    build_service_surface_closure,
    build_service_surface_snapshot,
    service_capability_projection,
    service_program_projection,
    service_surface_status,
)


class ServiceSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = build_service_surface_snapshot()

    def test_snapshot_closes_all_published_planes(self) -> None:
        self.assertTrue(self.snapshot.accepted)
        self.assertTrue(self.snapshot.content_address.startswith("service-surface:"))
        status = service_surface_status(self.snapshot)
        self.assertTrue(status["public_boundary"]["safe"])
        self.assertEqual(status["capability_certification"]["capability_count"], 256)
        self.assertEqual(status["capability_certification"]["certification_percent"], 100.0)
        self.assertEqual(status["architecture_program"]["domain_count"], 16)
        self.assertEqual(status["architecture_program"]["program_percent"], 100.0)
        self.assertEqual(status["operational"]["stage_count"], 12)
        self.assertEqual(status["operational"]["artifact_count"], 11)

    def test_capability_projection_supports_mvp_and_domain_filters(self) -> None:
        projection = service_capability_projection(self.snapshot, domain_id="D05", mvp_only=True)
        self.assertGreater(projection["count"], 0)
        self.assertTrue(all(row["domain_id"] == "D05" for row in projection["rows"]))
        self.assertTrue(all(row["mvp_64"] for row in projection["rows"]))

    def test_program_projection_supports_acceptance_filter(self) -> None:
        projection = service_program_projection(self.snapshot, domain_id="D08", accepted_only=True)
        self.assertEqual(projection["count"], 1)
        self.assertEqual(projection["rows"][0]["domain_id"], "D08")
        self.assertTrue(projection["rows"][0]["accepted"])

    def test_closure_is_detailed_and_addressed(self) -> None:
        closure = build_service_surface_closure(self.snapshot)
        self.assertTrue(closure["accepted"])
        self.assertTrue(closure["content_address"].startswith("service-surface-closure:"))
        self.assertEqual(
            closure["capability_certification"]["capability_count"],
            256,
        )
        self.assertEqual(
            closure["architecture_program_runtime"]["stage_count"],
            12,
        )
        self.assertNotIn("agent_id", json.dumps(closure, sort_keys=True).lower())
        self.assertNotIn("model_name", json.dumps(closure, sort_keys=True).lower())

    def test_http_service_contracts_and_invalid_queries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            server.glio_service_surface = self.snapshot
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)

                connection.request("GET", "/v1/status")
                status = connection.getresponse()
                self.assertEqual(status.status, 200)
                status_payload = json.loads(status.read())
                self.assertTrue(status_payload["accepted"])
                self.assertEqual(status_payload["content_address"], self.snapshot.content_address)

                connection.request("GET", "/v1/capabilities?domain_id=D05&mvp_only=true")
                capabilities = connection.getresponse()
                self.assertEqual(capabilities.status, 200)
                capability_payload = json.loads(capabilities.read())
                self.assertGreater(capability_payload["count"], 0)

                connection.request("GET", "/v1/architecture/program?domain_id=D08&accepted_only=1")
                program = connection.getresponse()
                self.assertEqual(program.status, 200)
                self.assertEqual(json.loads(program.read())["count"], 1)

                connection.request("GET", "/v1/architecture/operational")
                operational = connection.getresponse()
                self.assertEqual(operational.status, 200)
                self.assertTrue(json.loads(operational.read())["accepted"])

                connection.request("GET", "/v1/capabilities?state=not-a-state")
                invalid_state = connection.getresponse()
                self.assertEqual(invalid_state.status, 400)
                self.assertEqual(json.loads(invalid_state.read())["error"], "invalid_query")

                connection.request("GET", "/v1/architecture/diff?control=not-a-control")
                invalid_control = connection.getresponse()
                self.assertEqual(invalid_control.status, 400)
                self.assertEqual(json.loads(invalid_control.read())["error"], "invalid_query")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

    def test_checked_in_closure_has_public_status_shape(self) -> None:
        path = Path(__file__).parents[1] / "data" / "service-surface-closure.json"
        if not path.exists():
            self.skipTest("service surface closure is generated during the release build")
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(payload["accepted"])
        self.assertEqual(payload["status"]["capability_certification"]["capability_count"], 256)
        self.assertEqual(payload["status"]["architecture_program"]["domain_count"], 16)


if __name__ == "__main__":
    unittest.main()

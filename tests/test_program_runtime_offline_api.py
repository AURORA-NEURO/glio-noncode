"""HTTP coverage for the architecture-program offline service routes."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from threading import Thread

from glio_noncode.api import create_server


class ProgramRuntimeOfflineApiTests(unittest.TestCase):
    def test_schema_query_audit_and_certification_routes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="glio-program-offline-api-") as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=60)
                connection.request("GET", "/v1/architecture/offline/schema")
                schema = connection.getresponse()
                self.assertEqual(schema.status, 200)
                self.assertEqual(
                    json.loads(schema.read())["schema_version"], "program-runtime-offline-schema-v1"
                )

                connection.request(
                    "GET", "/v1/architecture/offline/query?resource=domains&domain_id=D08"
                )
                query = connection.getresponse()
                self.assertEqual(query.status, 200)
                query_payload = json.loads(query.read())
                self.assertTrue(query_payload["accepted"])
                self.assertEqual(query_payload["total"], 1)

                connection.request("GET", "/v1/architecture/offline/audit")
                audit = connection.getresponse()
                self.assertEqual(audit.status, 200)
                self.assertTrue(json.loads(audit.read())["accepted"])

                connection.request("GET", "/v1/architecture/offline/certification")
                certification = connection.getresponse()
                self.assertEqual(certification.status, 200)
                certification_payload = json.loads(certification.read())
                self.assertTrue(certification_payload["accepted"])
                self.assertEqual(certification_payload["coverage_percent"], 100.0)
                connection.request("GET", "/v1/architecture/offline/observability")
                observability = connection.getresponse()
                self.assertEqual(observability.status, 200)
                observability_payload = json.loads(observability.read())
                self.assertTrue(observability_payload["audit"]["accepted"])
                self.assertEqual(observability_payload["observability"]["metric_count"], 12)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()

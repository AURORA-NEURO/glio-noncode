"""HTTP schema and capability routes for packet catalog comparison."""

from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from threading import Thread

from glio_noncode.api import create_server


class PacketCatalogDiffPolicyApiTest(unittest.TestCase):
    def test_schema_and_capability_routes_are_public(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=10)
                paths = (
                    "/v1/module-workbench/release-bundle/catalog/diff/policy-set/packet/diff/policy/packet/catalog/diff/schema",
                    "/v1/module-workbench/release-bundle/catalog/diff/policy-set/packet/diff/policy/packet/catalog/diff/capabilities",
                    "/v1/module-workbench/release-bundle/catalog/diff/policy-set/packet/diff/policy/packet/catalog/diff/policy/schema",
                    "/v1/module-workbench/release-bundle/catalog/diff/policy-set/packet/diff/policy/packet/catalog/diff/policy/capabilities",
                    "/v1/module-workbench/release-bundle/catalog/diff/policy-set/packet/diff/policy/packet/catalog/diff/policy/audit/schema",
                    "/v1/module-workbench/release-bundle/catalog/diff/policy-set/packet/diff/policy/packet/catalog/diff/policy/audit/capabilities",
                    "/v1/module-workbench/release-bundle/catalog/diff/policy-set/packet/diff/policy/packet/catalog/diff/policy/packet/schema",
                    "/v1/module-workbench/release-bundle/catalog/diff/policy-set/packet/diff/policy/packet/catalog/diff/policy/packet/capabilities",
                )
                for path in paths:
                    connection.request("GET", path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200, path)
                    body = json.loads(response.read())
                    self.assertTrue(body.get("source_free"), path)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()

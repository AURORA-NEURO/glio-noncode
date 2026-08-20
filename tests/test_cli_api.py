from __future__ import annotations

import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main

from .helpers import ROOT


class CliApiTests(unittest.TestCase):
    def test_schema_command_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "schema.json"
            self.assertEqual(main(["schema", "--output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("$defs", payload)

    def test_health_and_evaluate_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = create_server("127.0.0.1", 0, directory)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=5)
                connection.request("GET", "/healthz")
                health = connection.getresponse()
                self.assertEqual(health.status, 200)
                self.assertEqual(json.loads(health.read())["status"], "ok")
                manifest = (ROOT / "examples" / "case-small.json").read_bytes()
                connection.request("POST", "/v1/evaluate", body=manifest, headers={"Content-Type": "application/json"})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                dossier = json.loads(response.read())
                self.assertEqual(dossier["case_id"], "case-demo-001")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)

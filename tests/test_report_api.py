from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch

from glio_noncode.api import create_server
from glio_noncode.reports import (
    DossierReport,
    build_report,
    render_report,
    report_capabilities,
)
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class ReportApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.runtime = CaseRuntime(self.temporary.name)
        self.dossier = self.runtime.evaluate(fixture_manifest())
        self.server = create_server("127.0.0.1", 0, self.temporary.name)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def _get(self, path: str) -> tuple[int, bytes, dict[str, str]]:
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            body = response.read()
            headers = {name.lower(): value for name, value in response.getheaders()}
            return response.status, body, headers
        finally:
            connection.close()

    def test_capabilities_advertise_bounded_audience_aware_reports(self) -> None:
        status, body, headers = self._get("/v1/reports/capabilities")
        payload = json.loads(body)

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(payload, report_capabilities())
        self.assertEqual(payload["audiences"], ["review", "public"])
        self.assertEqual(payload["formats"], ["json", "markdown"])
        self.assertIn("rendered_report_bytes", payload["hard_limits"])

        status, body, _ = self._get("/v1/reports/capabilities?audience=public")
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["error"], "invalid_query")

    def test_default_run_report_is_exact_public_json_with_address_headers(self) -> None:
        server_runtime = self.server.glio_runtime
        with patch.object(
            server_runtime,
            "load_run_snapshot",
            wraps=server_runtime.load_run_snapshot,
        ) as load_snapshot:
            status, body, headers = self._get(f"/v1/runs/{self.dossier.run_id}/report")

        self.assertEqual(status, 200)
        load_snapshot.assert_called_once_with(self.dossier.run_id)
        report = DossierReport.from_dict(json.loads(body))
        expected = render_report(build_report(self.dossier, audience="public"), format="json")
        self.assertEqual(body, expected.payload.encode("utf-8"))
        self.assertEqual(headers["content-type"], expected.media_type)
        self.assertEqual(headers["x-glio-report-address"], expected.report_address)
        self.assertEqual(headers["x-glio-dossier-address"], self.dossier.content_address)
        self.assertEqual(headers["x-glio-summary-address"], report.summary_address)
        self.assertEqual(headers["x-glio-payload-address"], expected.payload_address)
        self.assertEqual(
            headers["x-glio-rendered-report-address"], expected.content_address
        )
        self.assertEqual(headers["x-glio-report-audience"], "public")
        self.assertNotIn("case_id", report.projection)
        self.assertNotIn("run_id", report.projection)
        self.assertTrue(report.verify(self.dossier))

    def test_review_markdown_report_is_exact_and_explicitly_requested(self) -> None:
        status, body, headers = self._get(
            f"/v1/runs/{self.dossier.run_id}/report?audience=review&format=markdown"
        )

        self.assertEqual(status, 200)
        expected = render_report(build_report(self.dossier, audience="review"), format="markdown")
        self.assertEqual(body, expected.payload.encode("utf-8"))
        self.assertEqual(headers["content-type"], "text/markdown; charset=utf-8")
        self.assertEqual(headers["x-glio-report-audience"], "review")
        self.assertIn(self.dossier.case_id, body.decode("utf-8"))
        self.assertIn("# Review Dossier Report", body.decode("utf-8"))

    def test_report_query_is_exact_and_missing_runs_are_not_rendered(self) -> None:
        cases = (
            (
                f"/v1/runs/{self.dossier.run_id}/report?audience=internal",
                400,
                "invalid_query",
            ),
            (
                f"/v1/runs/{self.dossier.run_id}/report?format=html",
                400,
                "invalid_query",
            ),
            (
                f"/v1/runs/{self.dossier.run_id}/report?audience=",
                400,
                "invalid_query",
            ),
            (
                f"/v1/runs/{self.dossier.run_id}/report?audience=review&audience=public",
                400,
                "invalid_query",
            ),
            (
                f"/v1/runs/{self.dossier.run_id}/report?data_root=elsewhere",
                400,
                "invalid_query",
            ),
            (
                f"/v1/runs/{self.dossier.run_id}/report/extra",
                404,
                "not_found",
            ),
            ("/v1/runs/run-000000000000000000000000/report", 404, "not_found"),
        )
        for path, expected_status, expected_error in cases:
            with self.subTest(path=path):
                status, body, _ = self._get(path)
                payload = json.loads(body)
                self.assertEqual(status, expected_status)
                self.assertEqual(payload["error"], expected_error)


if __name__ == "__main__":
    unittest.main()

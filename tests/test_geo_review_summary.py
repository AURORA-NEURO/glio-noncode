from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode._cli_geo_review_summary import main as summary_main
from glio_noncode.api import create_server
from glio_noncode.geo_analysis_store import GeoAnalysisStore
from glio_noncode.geo_review_summary import build_geo_review_summary

from .test_geo_count_consistency import _report


class GeoReviewSummaryTests(unittest.TestCase):
    def test_summary_verifies_saved_real_shape_without_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            GeoAnalysisStore(workspace).save(_report(root / "source", "GSE141945"))
            summary = build_geo_review_summary(workspace)
            skipped = build_geo_review_summary(workspace, verify_reports=False)

        self.assertEqual(summary["schema"], "glio-noncode.geo-review-summary.v1")
        self.assertEqual(summary["status"], "ready")
        self.assertEqual(summary["integrity"]["report_objects"], "verified")
        self.assertEqual(summary["catalogs"]["paired_count_analyses"]["record_count"], 1)
        self.assertEqual(
            summary["catalogs"]["paired_count_analyses"]["accessions"], ["GSE141945"]
        )
        self.assertEqual(skipped["integrity"]["report_objects"], "not_requested")
        public = json.dumps(summary)
        self.assertNotIn("PRIVATE_SUBJECT_", public)
        self.assertNotIn("sample_ids", public)

    def test_cli_and_http_surface_return_the_same_aggregate_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            GeoAnalysisStore(workspace).save(_report(root / "source", "GSE141945"))

            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = summary_main(["--data-root", str(workspace)])
            self.assertEqual(result, 0)
            cli_summary = json.loads(stdout.getvalue())
            self.assertEqual(stderr.getvalue(), "")

            server = create_server("127.0.0.1", 0, str(workspace))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/v1/geo-review/summary?verify_reports=true")
                response = connection.getresponse()
                api_summary = json.loads(response.read())
                connection.close()
                self.assertEqual(response.status, 200)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(api_summary["content_address"], cli_summary["content_address"])
        self.assertEqual(api_summary["catalogs"], cli_summary["catalogs"])
        self.assertEqual(api_summary["integrity"], cli_summary["integrity"])


if __name__ == "__main__":
    unittest.main()

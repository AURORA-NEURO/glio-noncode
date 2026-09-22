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
from glio_noncode.geo_review_summary import (
    build_geo_review_summary,
    geo_review_ledger_csv,
)

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

            stdout_csv, stderr_csv = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout_csv), redirect_stderr(stderr_csv):
                csv_result = summary_main(["--data-root", str(workspace), "--csv"])
            self.assertEqual(csv_result, 0)
            self.assertEqual(stderr_csv.getvalue(), "")
            self.assertIn(
                "catalog,record_id,accessions,feature_count,tested_feature_count,"
                "fdr_significant_feature_count,verification,state\n",
                stdout_csv.getvalue(),
            )
            self.assertIn("GSE141945", stdout_csv.getvalue())

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

                csv_connection = HTTPConnection(host, port, timeout=30)
                csv_connection.request(
                    "GET", "/v1/geo-review/summary.csv?verify_reports=true"
                )
                csv_response = csv_connection.getresponse()
                ledger_csv = csv_response.read().decode("utf-8")
                csv_connection.close()
                self.assertEqual(csv_response.status, 200)
                self.assertEqual(
                    csv_response.getheader("Content-Type"), "text/csv; charset=utf-8"
                )
                self.assertIn(
                    'attachment; filename="GLIO-NONCODE-geo-review-ledger.csv"',
                    csv_response.getheader("Content-Disposition", ""),
                )
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(api_summary["content_address"], cli_summary["content_address"])
        self.assertEqual(api_summary["catalogs"], cli_summary["catalogs"])
        self.assertEqual(api_summary["integrity"], cli_summary["integrity"])
        self.assertIn(
            "catalog,record_id,accessions,feature_count,tested_feature_count,fdr_significant_feature_count,verification,state\n",
            ledger_csv,
        )
        self.assertIn("paired_count_analyses", ledger_csv)
        self.assertIn("GSE141945", ledger_csv)

    def test_ledger_is_aggregate_only_and_can_skip_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            GeoAnalysisStore(workspace).save(_report(root / "source", "GSE141945"))

            ledger = geo_review_ledger_csv(workspace, verify_reports=False)

        self.assertIn("paired_count_analyses", ledger)
        self.assertIn("GSE141945", ledger)
        self.assertIn(",not_requested,cataloged\n", ledger)
        self.assertNotIn("PRIVATE_SUBJECT_", ledger)
        self.assertNotIn("sample_ids", ledger)
        self.assertNotIn("agent", ledger.lower())
        self.assertNotIn("language", ledger.lower())


if __name__ == "__main__":
    unittest.main()

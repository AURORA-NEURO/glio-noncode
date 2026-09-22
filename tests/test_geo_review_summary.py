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
from glio_noncode.geo_count_consistency import build_geo_count_consistency_report
from glio_noncode.geo_count_consistency_store import GeoCountConsistencyStore
from glio_noncode.geo_count_sensitivity import build_geo_count_sensitivity_report
from glio_noncode.geo_count_sensitivity_store import GeoCountSensitivityStore
from glio_noncode.geo_preflight_store import GeoPreflightStore
from glio_noncode.geo_review_summary import (
    build_geo_preflight_ledger,
    build_geo_review_ledger,
    build_geo_review_summary,
    geo_preflight_ledger_csv,
    geo_review_ledger_csv,
    render_geo_preflight_ledger_csv,
    render_geo_review_ledger_csv,
)

from .test_geo_count_consistency import _report
from .test_geo_count_contrast import _build_report, _write_files
from .test_geo_preflight_store import _quality_report


class GeoReviewSummaryTests(unittest.TestCase):
    def test_summary_verifies_saved_real_shape_without_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            GeoAnalysisStore(workspace).save(_report(root / "source", "GSE141945"))
            GeoPreflightStore(workspace).save(_quality_report())
            summary = build_geo_review_summary(workspace)
            skipped = build_geo_review_summary(workspace, verify_reports=False)

        self.assertEqual(summary["schema"], "glio-noncode.geo-review-summary.v1")
        self.assertEqual(summary["status"], "ready")
        self.assertEqual(summary["integrity"]["report_objects"], "verified")
        self.assertEqual(summary["catalogs"]["paired_count_analyses"]["record_count"], 1)
        self.assertEqual(
            summary["catalogs"]["paired_count_analyses"]["reported_feature_count_total"],
            4,
        )
        self.assertEqual(
            summary["catalogs"]["paired_count_analyses"]["accessions"], ["GSE141945"]
        )
        self.assertEqual(summary["catalogs"]["preflights"]["record_count"], 1)
        self.assertEqual(
            summary["catalogs"]["preflights"]["kind_counts"],
            {"expression_quality": 1},
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
                "reported_feature_count,ranked_feature_count,"
                "additional_tracked_feature_count,tracked_feature_id_count,"
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
            "catalog,record_id,accessions,feature_count,tested_feature_count,"
            "reported_feature_count,ranked_feature_count,"
            "additional_tracked_feature_count,tracked_feature_id_count,"
            "fdr_significant_feature_count,verification,state\n",
            ledger_csv,
        )
        self.assertIn("paired_count_analyses", ledger_csv)
        self.assertIn("GSE141945", ledger_csv)

    def test_summary_exposes_normalization_coverage_totals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            (root / "source").mkdir(parents=True)
            counts, metadata = _write_files(root / "source", include_date_like_feature=True)
            left = _build_report(
                counts_file=counts,
                metadata_file=metadata,
                top=1,
                track_feature_ids=("2-Sep",),
                normalization_method="tmm_log2_cpm",
                fdr_threshold=1.0,
            )
            right = _build_report(
                counts_file=counts,
                metadata_file=metadata,
                top=1,
                track_feature_ids=("2-Sep",),
                normalization_method="log2_cpm",
                fdr_threshold=1.0,
            )
            GeoCountSensitivityStore(workspace).save(
                build_geo_count_sensitivity_report(
                    (left, right), feature_ids=("2-Sep",)
                )
            )
            first = _report(root / "first", "GSE141945")
            second = _report(root / "second", "GSE141946", direction_fixture=True)
            GeoCountConsistencyStore(workspace).save(
                build_geo_count_consistency_report(
                    (first, second), feature_ids=("SIGNAL",)
                )
            )
            summary = build_geo_review_summary(workspace)
            ledger_rows = build_geo_review_ledger(workspace, verify_reports=False)

        catalog = summary["catalogs"]["paired_count_sensitivity_comparisons"]
        self.assertEqual(catalog["reported_feature_count_total"], 4)
        self.assertEqual(catalog["ranked_feature_count_total"], 2)
        self.assertEqual(catalog["additional_tracked_feature_count_total"], 2)
        self.assertEqual(catalog["tracked_feature_id_count_total"], 2)
        consistency = summary["catalogs"]["paired_count_comparisons"]
        expected_reported = first["summary"]["reported_feature_count"] + second["summary"][
            "reported_feature_count"
        ]
        self.assertEqual(consistency["reported_feature_count_total"], expected_reported)
        self.assertEqual(consistency["ranked_feature_count_total"], expected_reported)
        self.assertEqual(consistency["additional_tracked_feature_count_total"], 0)
        ledger_by_catalog = {
            row["catalog"]: row
            for row in ledger_rows
            if row["catalog"] in {
                "paired_count_comparisons",
                "paired_count_sensitivity_comparisons",
            }
        }
        self.assertEqual(
            ledger_by_catalog["paired_count_comparisons"]["reported_feature_count"],
            expected_reported,
        )
        self.assertEqual(
            ledger_by_catalog["paired_count_sensitivity_comparisons"][
                "ranked_feature_count"
            ],
            2,
        )
        self.assertEqual(
            ledger_by_catalog["paired_count_sensitivity_comparisons"][
                "additional_tracked_feature_count"
            ],
            2,
        )

    def test_ledger_is_aggregate_only_and_can_skip_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            GeoAnalysisStore(workspace).save(_report(root / "source", "GSE141945"))

            ledger = geo_review_ledger_csv(workspace, verify_reports=False)

        self.assertIn("paired_count_analyses", ledger)
        self.assertIn("GSE141945", ledger)
        self.assertIn(",4,4,0,0,", ledger)
        self.assertIn(",not_requested,cataloged\n", ledger)
        self.assertNotIn("PRIVATE_SUBJECT_", ledger)
        self.assertNotIn("sample_ids", ledger)
        self.assertNotIn("agent", ledger.lower())
        self.assertNotIn("language", ledger.lower())

    def test_ledger_renderer_does_not_reopen_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "workspace"
            GeoAnalysisStore(workspace).save(_report(root / "source", "GSE141945"))
            rows = build_geo_review_ledger(workspace, verify_reports=False)
            rendered = render_geo_review_ledger_csv(rows)
            expected = geo_review_ledger_csv(workspace, verify_reports=False)

        self.assertIn("GSE141945", rendered)
        self.assertEqual(rendered, expected)

    def test_preflight_ledger_preserves_kind_dimensions_and_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            GeoPreflightStore(workspace).save(_quality_report())
            rows = build_geo_preflight_ledger(workspace)
            rendered = render_geo_preflight_ledger_csv(rows)
            skipped = geo_preflight_ledger_csv(workspace, verify_reports=False)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["kind"], "expression_quality")
        self.assertEqual(rows[0]["sample_count"], 81)
        self.assertEqual(rows[0]["feature_count"], 56832)
        self.assertEqual(rows[0]["verification"], "verified")
        self.assertIn("preflight_id,kind,report_schema,accession", rendered)
        self.assertIn("expression_quality", rendered)
        self.assertIn(",not_requested\n", skipped)
        self.assertNotIn("sample_ids", rendered)
        self.assertNotIn("agent", rendered.lower())
        self.assertNotIn("language", rendered.lower())

    def test_preflight_ledger_cli_and_http_exports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            GeoPreflightStore(workspace).save(_quality_report())
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = summary_main(["--data-root", str(workspace), "--preflights-csv"])
            self.assertEqual(result, 0)
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("expression_quality", stdout.getvalue())

            server = create_server("127.0.0.1", 0, str(workspace))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                connection = HTTPConnection("127.0.0.1", server.server_port, timeout=30)
                connection.request("GET", "/v1/geo-preflights.csv?verify_reports=true")
                response = connection.getresponse()
                payload = response.read().decode("utf-8")
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "text/csv; charset=utf-8")
        self.assertIn(
            'attachment; filename="GLIO-NONCODE-geo-preflight-ledger.csv"',
            response.getheader("Content-Disposition", ""),
        )
        self.assertIn("GSE141945", payload)


if __name__ == "__main__":
    unittest.main()

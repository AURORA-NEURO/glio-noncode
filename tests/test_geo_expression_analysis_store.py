from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stderr
from http.client import HTTPConnection
from io import StringIO
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.geo_expression import build_expression_contrast_report
from glio_noncode.geo_expression_analysis_store import GeoExpressionAnalysisStore
from glio_noncode.geo_review_summary import build_geo_review_summary

from .test_geo_contrast import _matrix_payload


class GeoExpressionAnalysisStoreTests(unittest.TestCase):
    def _report(self, root: Path) -> dict[str, object]:
        matrix = root / "GSE123456_series_matrix.txt.gz"
        matrix.write_bytes(_matrix_payload())
        return build_expression_contrast_report(
            "GSE123456",
            case_filters=(("diagnosis", "glioblastoma"),),
            reference_filters=(("diagnosis", "normal"),),
            scale="normalized_intensity",
            matrix_file=matrix,
            top=2,
            track_feature_ids=("probe-null",),
        )

    def test_save_catalog_page_and_csv_are_immutable_and_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._report(root)
            store = GeoExpressionAnalysisStore(root / "workspace")
            first = store.save(report)
            self.assertEqual(store.save(report), first)
            self.assertEqual(store.list_reports()["total_count"], 1)
            expected_ranked = report["summary"]["reported_feature_count"] - report["summary"][
                "additional_feature_result_count"
            ]
            expected_tracked = len(report["comparison"]["tracked_feature_ids"])
            self.assertEqual(first["summary"]["ranked_feature_count_total"], expected_ranked)
            self.assertEqual(first["summary"]["additional_tracked_feature_count_total"], 1)
            self.assertEqual(first["summary"]["tracked_feature_id_count_total"], expected_tracked)
            health = build_geo_review_summary(root / "workspace")
            expression_catalog = health["catalogs"]["expression_analyses"]
            self.assertEqual(expression_catalog["ranked_feature_count_total"], expected_ranked)
            self.assertEqual(expression_catalog["additional_tracked_feature_count_total"], 1)
            self.assertEqual(expression_catalog["tracked_feature_id_count_total"], expected_tracked)
            self.assertNotIn("case_sample_ids", json.dumps(store.list_reports()))

            page = store.page_results(first["analysis_id"], limit=2)
            self.assertEqual(page["schema"], "glio-noncode.geo-expression-analysis-page.v1")
            self.assertEqual(page["total_results"], 3)
            self.assertEqual(len(page["results"]), 2)
            self.assertEqual(page["filtered_result_summary"]["result_count"], 3)
            self.assertEqual(
                sum(page["filtered_result_summary"]["effect_direction_counts"].values()),
                3,
            )
            self.assertNotIn("case_sample_ids", json.dumps(page))
            self.assertNotIn("reference_sample_ids", json.dumps(page))

            filtered = store.page_results(
                first["analysis_id"], feature_contains="PROBE-UP", fdr_significant=True
            )
            self.assertTrue(filtered["results"])
            self.assertTrue(all(row["fdr_significant"] for row in filtered["results"]))
            self.assertEqual(
                filtered["filtered_result_summary"]["fdr_significant_count"],
                filtered["total_results"],
            )
            csv_body = store.results_csv(first["analysis_id"], effect_direction="case_higher")
            self.assertIn("feature_id", csv_body.splitlines()[0])
            self.assertIn("probe-up-1", csv_body)
            self.assertNotIn("GSM000", csv_body)

    def test_cli_can_persist_a_downloaded_series_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            matrix = root / "downloaded.txt.gz"
            output = root / "contrast.json"
            workspace = root / "workspace"
            matrix.write_bytes(_matrix_payload())
            stderr = StringIO()
            with redirect_stderr(stderr):
                exit_code = cli_main(
                    [
                        "geo-contrast", "GSE123456",
                        "--case-filter", "diagnosis=glioblastoma",
                        "--reference-filter", "diagnosis=normal",
                        "--scale", "normalized_intensity",
                        "--matrix-file", str(matrix),
                        "--save-to-workspace", "--data-root", str(workspace),
                        "--output", str(output),
                    ]
                )
            document = json.loads(output.read_text(encoding="utf-8"))
            catalog = GeoExpressionAnalysisStore(workspace).list_reports()
        self.assertEqual(exit_code, 0)
        self.assertEqual(document["status"], "completed")
        self.assertEqual(catalog["total_count"], 1)
        self.assertIn("Saved GEO expression analysis geo-expression-", stderr.getvalue())

    def test_invalid_content_address_and_unknown_effect_filter_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._report(root)
            report["content_address"] = "geo-expression-contrast:0000000000000000000000000000000000000000000000000000000000000000"
            with self.assertRaises(ValidationError):
                GeoExpressionAnalysisStore(root / "workspace").save(report)
            report = self._report(root)
            store = GeoExpressionAnalysisStore(root / "workspace")
            analysis_id = store.save(report)["analysis_id"]
            with self.assertRaises(ValidationError):
                store.page_results(analysis_id, effect_direction="not-a-direction")

    def test_http_catalog_page_and_export_use_the_store_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = GeoExpressionAnalysisStore(root)
            report = self._report(root)
            record = store.save(report)
            server = create_server("127.0.0.1", 0, str(root))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/v1/geo-expression-analyses?limit=5")
                response = connection.getresponse()
                catalog = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(catalog["total_count"], 1)
                self.assertEqual(catalog["rows"][0]["analysis_id"], record["analysis_id"])
                self.assertNotIn("case_sample_ids", json.dumps(catalog))

                connection.request(
                    "GET",
                    f"/v1/geo-expression-analyses/{record['analysis_id']}?feature_contains=probe-up&limit=1",
                )
                response = connection.getresponse()
                page = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(page["total_results"], 2)
                self.assertEqual(len(page["results"]), 1)
                self.assertNotIn("case_sample_ids", json.dumps(page))

                connection.request(
                    "GET", f"/v1/geo-expression-analyses/{record['analysis_id']}/results.csv"
                )
                response = connection.getresponse()
                csv_body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("probe-up-1", csv_body)
                self.assertNotIn("GSM000", csv_body)

                connection.request(
                    "GET", f"/v1/geo-expression-analyses/{record['analysis_id']}?fdr_significant=maybe"
                )
                self.assertEqual(connection.getresponse().status, 400)

                connection.request(
                    "POST",
                    "/v1/geo-expression-analyses",
                    body=json.dumps(report),
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                created = json.loads(response.read())
                self.assertEqual(response.status, 201)
                self.assertEqual(created["record"]["analysis_id"], record["analysis_id"])
                self.assertNotIn("case_sample_ids", json.dumps(created))
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()

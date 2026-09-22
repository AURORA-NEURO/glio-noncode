import json
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode.api import create_server
from glio_noncode.errors import ValidationError
from glio_noncode.geo_analysis_store import GeoAnalysisStore
from glio_noncode.geo_count_sensitivity import (
    CountSensitivityCompatibilityError,
    build_geo_count_sensitivity_report,
    summarize_geo_count_sensitivity_report,
)
from glio_noncode.geo_count_sensitivity_store import GeoCountSensitivityStore
from glio_noncode.geo_expression import build_geo_count_contrast_report

from .test_geo_count_contrast import _build_report, _write_files


class GeoCountSensitivityTests(unittest.TestCase):
    def _reports(self, root: Path) -> tuple[dict[str, object], dict[str, object]]:
        counts, metadata = _write_files(root, include_date_like_feature=True)
        left = _build_report(counts_file=counts, metadata_file=metadata, top=5)
        right = _build_report(
            counts_file=counts,
            metadata_file=metadata,
            top=5,
            normalization_method="tmm_log2_cpm",
        )
        return left, right

    def test_same_source_normalization_report_is_aggregate_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._reports(root)
            report = build_geo_count_sensitivity_report(
                (left, right), feature_ids=("SIGNAL", "INFLUENTIAL", "2-Sep")
            )
            self.assertEqual(report["schema"], "glio-noncode.geo-count-sensitivity.v1")
            self.assertEqual(report["comparison"]["accession"], "GSE141945")
            self.assertEqual(report["summary"]["run_count"], 2)
            self.assertEqual(report["summary"]["feature_count"], 3)
            catalog_summary = summarize_geo_count_sensitivity_report(report)
            self.assertEqual(catalog_summary["reported_feature_count_total"], 10)
            self.assertEqual(catalog_summary["ranked_feature_count_total"], 10)
            self.assertEqual(catalog_summary["additional_tracked_feature_count_total"], 0)
            self.assertEqual(catalog_summary["tracked_feature_id_count_total"], 0)
            self.assertEqual(
                report["summary"]["stable_direction_feature_count"]
                + report["summary"]["changed_direction_feature_count"]
                + report["summary"]["insufficient_direction_feature_count"]
                + report["summary"]["not_reported_direction_feature_count"],
                3,
            )
            serialized = json.dumps(report, sort_keys=True)
            self.assertNotIn("PRIVATE_TUMOR_", serialized)
            self.assertNotIn("PRIVATE_SUBJECT_", serialized)
            self.assertNotIn('"agent"', serialized)
            self.assertNotIn('"language"', serialized)
            for run in report["runs"]:
                self.assertEqual(run["ranked_feature_count"], 5)
                self.assertEqual(run["additional_tracked_feature_count"], 0)
                self.assertEqual(run["tracked_feature_ids"], [])

    def test_tracked_rows_retain_normalization_coverage_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts, metadata = _write_files(root, include_date_like_feature=True)
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
            report = build_geo_count_sensitivity_report(
                (left, right), feature_ids=("2-Sep",)
            )

        for run in report["runs"]:
            self.assertEqual(run["ranked_feature_count"], 1)
            self.assertEqual(run["additional_tracked_feature_count"], 1)
            self.assertEqual(run["tracked_feature_ids"], ["2-Sep"])
        catalog_summary = summarize_geo_count_sensitivity_report(report)
        self.assertEqual(catalog_summary["reported_feature_count_total"], 4)
        self.assertEqual(catalog_summary["ranked_feature_count_total"], 2)
        self.assertEqual(catalog_summary["additional_tracked_feature_count_total"], 2)
        self.assertEqual(catalog_summary["tracked_feature_id_count_total"], 2)

    def test_sensitivity_requires_different_normalization_and_same_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts, metadata = _write_files(root)
            first = _build_report(counts_file=counts, metadata_file=metadata, top=5)
            same = _build_report(counts_file=counts, metadata_file=metadata, top=5)
            with self.assertRaises(CountSensitivityCompatibilityError):
                build_geo_count_sensitivity_report((first, same), feature_ids=("SIGNAL",))

            other = build_geo_count_contrast_report(
                "GSE141946",
                case_filters=(("Timepoint", "Tumor"),),
                reference_filters=(("Timepoint", "1wk"),),
                sample_key_column="",
                pair_key_column="Patient",
                counts_file=counts,
                metadata_file=metadata,
                top=5,
            )
            with self.assertRaises(CountSensitivityCompatibilityError):
                build_geo_count_sensitivity_report((first, other), feature_ids=("SIGNAL",))

    def test_store_verifies_catalog_page_filters_and_csv_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._reports(root)
            report = build_geo_count_sensitivity_report(
                (left, right), feature_ids=("SIGNAL", "INFLUENTIAL", "2-Sep")
            )
            store = GeoCountSensitivityStore(root / "workspace")
            record = store.save(report)
            self.assertEqual(store.save(report), record)
            self.assertEqual(record["summary"]["ranked_feature_count_total"], 10)
            self.assertEqual(record["summary"]["additional_tracked_feature_count_total"], 0)
            catalog = store.list_reports(limit=1)
            self.assertEqual(catalog["total_count"], 1)
            self.assertEqual(catalog["rows"][0]["comparison_id"], record["comparison_id"])
            page = store.page_features(
                record["comparison_id"],
                direction_sensitivity="changed_direction",
            )
            self.assertEqual(page["total_features"], 1)
            self.assertEqual(page["features"][0]["feature_id"], "2-Sep")
            self.assertIn("left_result_state", store.features_csv(record["comparison_id"]))
            runs_csv = store.runs_csv(record["comparison_id"])
            self.assertIn("ranked_feature_count", runs_csv.splitlines()[0])
            self.assertIn("tracked_feature_ids", runs_csv.splitlines()[0])
            self.assertNotIn("PRIVATE_SUBJECT_", runs_csv)
            with self.assertRaises(ValidationError):
                store.page_features(record["comparison_id"], direction_sensitivity="unknown")

    def test_http_persistence_and_public_projections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right = self._reports(root)
            workspace = root / "workspace"
            source = GeoAnalysisStore(workspace)
            left_id = source.save(left)["analysis_id"]
            right_id = source.save(right)["analysis_id"]
            server = create_server("127.0.0.1", 0, str(workspace))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                payload = json.dumps(
                    {
                        "analysis_ids": [left_id, right_id],
                        "feature_ids": ["SIGNAL", "INFLUENTIAL", "2-Sep"],
                    }
                ).encode("utf-8")
                connection.request(
                    "POST",
                    "/v1/geo-count-sensitivity",
                    body=payload,
                    headers={"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                created = json.loads(response.read())
                self.assertEqual(response.status, 201)
                comparison_id = created["record"]["comparison_id"]

                connection.request("GET", "/v1/geo-count-sensitivity?limit=10&offset=0")
                response = connection.getresponse()
                catalog = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(catalog["total_count"], 1)

                connection.request(
                    "GET",
                    f"/v1/geo-count-sensitivity/{comparison_id}?direction_sensitivity=changed_direction",
                )
                response = connection.getresponse()
                page = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(page["schema"], "glio-noncode.geo-count-sensitivity-page.v1")
                self.assertEqual(page["total_features"], 1)
                self.assertNotIn("PRIVATE_SUBJECT_", json.dumps(page))

                connection.request(
                    "GET",
                    f"/v1/geo-count-sensitivity/{comparison_id}/features.csv",
                )
                response = connection.getresponse()
                csv_payload = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("direction_sensitivity", csv_payload.splitlines()[0])

                connection.request(
                    "GET",
                    f"/v1/geo-count-sensitivity/{comparison_id}/runs.csv",
                )
                response = connection.getresponse()
                runs_csv_payload = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("ranked_feature_count", runs_csv_payload.splitlines()[0])
                self.assertIn("tracked_feature_ids", runs_csv_payload.splitlines()[0])

                connection.request(
                    "GET",
                    "/v1/geo-count-sensitivity?unexpected=1",
                )
                self.assertEqual(connection.getresponse().status, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()

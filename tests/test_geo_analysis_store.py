from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode._cli_geo_count_contrast import main as paired_contrast_main
from glio_noncode.api import create_server
from glio_noncode.errors import StoreError, ValidationError
from glio_noncode.geo_analysis_store import GeoAnalysisStore
from glio_noncode.geo_expression import geo_series_supplementary_url
from glio_noncode.serialization import canonical_json, content_hash

from .test_geo_count_contrast import _build_report, _write_files


class GeoAnalysisStoreTests(unittest.TestCase):
    def _report(self, root: Path) -> dict[str, object]:
        counts, metadata = _write_files(root)
        return _build_report(counts_file=counts, metadata_file=metadata)

    @staticmethod
    def _readdress(report: dict[str, object]) -> dict[str, object]:
        body = {key: value for key, value in report.items() if key != "content_address"}
        report["content_address"] = content_hash(body, prefix="geo-paired-count-contrast")
        return report

    def test_save_is_immutable_content_addressed_and_result_pages_are_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._report(root)
            store = GeoAnalysisStore(root / "workspace")
            first = store.save(report)
            second = store.save(report)

            self.assertEqual(first, second)
            self.assertEqual(store.get_report(first["analysis_id"])["report"], report)
            catalog = store.list_reports(limit=1)
            self.assertEqual(catalog["total_count"], 1)
            self.assertEqual(catalog["rows"][0]["analysis_id"], first["analysis_id"])
            self.assertNotIn("results", catalog["rows"][0])
            page = store.page_results(first["analysis_id"], limit=2)
            self.assertEqual(len(page["results"]), 2)
            self.assertTrue(page["has_more"])
            self.assertEqual(
                page["filtered_result_summary"]["result_count"],
                page["total_results"],
            )
            self.assertEqual(
                sum(page["filtered_result_summary"]["effect_direction_counts"].values()),
                page["total_results"],
            )
            serialized = canonical_json(catalog)
            self.assertNotIn("PRIVATE_TUMOR_", serialized)
            self.assertNotIn("PRIVATE_SUBJECT_", serialized)

    def test_result_pages_support_bounded_aggregate_filters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = GeoAnalysisStore(root / "workspace")
            analysis_id = store.save(self._report(root))["analysis_id"]

            feature_page = store.page_results(analysis_id, feature_contains="SIGN")
            self.assertEqual(feature_page["total_results"], 1)
            self.assertEqual(feature_page["results"][0]["feature_id"], "SIGNAL")
            self.assertEqual(feature_page["filters"]["feature_contains"], "sign")

            direction_page = store.page_results(analysis_id, effect_direction="case_higher")
            self.assertTrue(direction_page["results"])
            self.assertTrue(
                all(item["effect_direction"] == "case_higher" for item in direction_page["results"])
            )
            self.assertEqual(
                direction_page["filtered_result_summary"]["effect_direction_counts"][
                    "case_higher"
                ],
                direction_page["total_results"],
            )

            significant_page = store.page_results(analysis_id, fdr_significant=False)
            self.assertTrue(significant_page["results"])
            self.assertTrue(
                all(not item["fdr_significant"] for item in significant_page["results"])
            )

            magnitude_page = store.page_results(analysis_id, min_abs_median_effect=0.4)
            self.assertTrue(magnitude_page["results"])
            self.assertTrue(
                all(
                    abs(item["median_paired_difference_log2_cpm"]) >= 0.4
                    for item in magnitude_page["results"]
                )
            )
            self.assertEqual(magnitude_page["unfiltered_result_count"], 4)

            with self.assertRaises(ValidationError):
                store.page_results(analysis_id, effect_direction="unknown")
            with self.assertRaises(ValidationError):
                store.page_results(analysis_id, feature_contains="x" * 257)
            with self.assertRaises(ValidationError):
                store.page_results(analysis_id, min_abs_median_effect=-1.0)

    def test_report_integrity_and_individual_key_boundary_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self._report(root)
            store = GeoAnalysisStore(root / "workspace")
            changed = json.loads(json.dumps(report))
            changed["summary"]["tested_feature_count"] += 1
            with self.assertRaises(ValidationError):
                store.save(changed)

            keyed = json.loads(json.dumps(report))
            keyed["comparison"]["sample_ids"] = ["PRIVATE_TUMOR_0"]
            body = {key: value for key, value in keyed.items() if key != "content_address"}
            keyed["content_address"] = content_hash(
                body, prefix="geo-paired-count-contrast"
            )
            with self.assertRaisesRegex(ValidationError, "individual sample or pair key"):
                store.save(keyed)

            malformed = json.loads(json.dumps(report))
            malformed["results"][0]["pair_subject_labels"] = ["PRIVATE_SUBJECT_0"]
            malformed_body = {
                key: value for key, value in malformed.items() if key != "content_address"
            }
            malformed["content_address"] = content_hash(
                malformed_body, prefix="geo-paired-count-contrast"
            )
            with self.assertRaisesRegex(ValidationError, "feature result has an invalid v1 shape"):
                store.save(malformed)

            invalid_q = json.loads(json.dumps(report))
            invalid_q["results"][0]["q_value"] = 1.5
            invalid_q_body = {
                key: value for key, value in invalid_q.items() if key != "content_address"
            }
            invalid_q["content_address"] = content_hash(
                invalid_q_body, prefix="geo-paired-count-contrast"
            )
            with self.assertRaisesRegex(ValidationError, "feature q_value"):
                store.save(invalid_q)

    def test_https_source_accepts_canonical_geo_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = json.loads(json.dumps(self._report(root)))
            source = report["source"]
            source["retrieval"] = "https"
            source["count_matrix"]["response_url"] = geo_series_supplementary_url(
                "GSE141945", "counts.csv.gz"
            )
            self._readdress(report)
            GeoAnalysisStore(root / "workspace").save(report)

    def test_https_source_rejects_non_ncbi_origins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = json.loads(json.dumps(self._report(root)))
            source = report["source"]
            source["retrieval"] = "https"
            source["count_matrix"]["response_url"] = geo_series_supplementary_url(
                "GSE141945", "counts.csv.gz"
            ).replace("ftp.ncbi.nlm.nih.gov", "example.org")
            self._readdress(report)
            with self.assertRaisesRegex(ValidationError, "canonical NCBI GEO file"):
                GeoAnalysisStore(root / "workspace").save(report)

    def test_https_source_rejects_noncanonical_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = json.loads(json.dumps(self._report(root)))
            source = report["source"]
            source["retrieval"] = "https"
            source["count_matrix"]["response_url"] = geo_series_supplementary_url(
                "GSE141945", "counts.csv.gz"
            ).replace("counts.csv.gz", "other.csv.gz")
            self._readdress(report)
            with self.assertRaisesRegex(ValidationError, "canonical NCBI GEO file"):
                GeoAnalysisStore(root / "workspace").save(report)

    def test_https_retrieval_requires_response_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = json.loads(json.dumps(self._report(root)))
            report["source"]["retrieval"] = "https"
            self._readdress(report)
            with self.assertRaisesRegex(ValidationError, "retrieval mode"):
                GeoAnalysisStore(root / "workspace").save(report)

    def test_filenames_cannot_escape_the_source_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = json.loads(json.dumps(self._report(root)))
            report["source"]["count_matrix"]["file_name"] = "../counts.csv.gz"
            self._readdress(report)
            with self.assertRaisesRegex(ValidationError, "simple file name"):
                GeoAnalysisStore(root / "workspace").save(report)

    def test_catalog_record_tampering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = GeoAnalysisStore(root / "workspace")
            record = store.save(self._report(root))
            path = store.records / f"{record['analysis_id']}.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw["summary"]["tested_feature_count"] += 1
            path.write_text(canonical_json(raw), encoding="utf-8")
            with self.assertRaises(StoreError):
                store.list_reports()

    def test_paired_contrast_cli_can_explicitly_save_a_completed_local_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            counts, metadata = _write_files(source)
            stdout, stderr = io.StringIO(), io.StringIO()
            arguments = [
                "GSE141945",
                "--case-filter", "Timepoint=Tumor",
                "--reference-filter", "Timepoint=1wk",
                "--sample-key-column", "",
                "--pair-key-column", "Patient",
                "--counts-file", str(counts),
                "--metadata-file", str(metadata),
                "--save-to-workspace",
                "--data-root", str(root / "workspace"),
                "--top", "5",
            ]
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = paired_contrast_main(arguments)
            self.assertEqual(result, 0)
            output = json.loads(stdout.getvalue())
            self.assertEqual(output["schema"], "glio-noncode.geo-paired-count-contrast.v1")
            self.assertIn("Saved GEO analysis geo-", stderr.getvalue())
            self.assertEqual(GeoAnalysisStore(root / "workspace").list_reports()["total_count"], 1)

    def test_http_catalog_and_detail_use_validated_aggregate_projections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = GeoAnalysisStore(root)
            record = store.save(self._report(root))
            server = create_server("127.0.0.1", 0, str(root))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/v1/geo-analyses?limit=5")
                catalog_response = connection.getresponse()
                catalog = json.loads(catalog_response.read())
                self.assertEqual(catalog_response.status, 200)
                self.assertEqual(catalog["total_count"], 1)
                self.assertEqual(catalog["rows"][0]["analysis_id"], record["analysis_id"])

                connection.request(
                    "GET", f"/v1/geo-analyses/{record['analysis_id']}?limit=2"
                )
                page_response = connection.getresponse()
                page = json.loads(page_response.read())
                self.assertEqual(page_response.status, 200)
                self.assertEqual(len(page["results"]), 2)
                self.assertNotIn("PRIVATE_SUBJECT_", json.dumps(page))

                connection.request(
                    "GET",
                    f"/v1/geo-analyses/{record['analysis_id']}?feature_contains=SIGN"
                    "&effect_direction=case_higher&limit=5",
                )
                filtered_response = connection.getresponse()
                filtered_page = json.loads(filtered_response.read())
                self.assertEqual(filtered_response.status, 200)
                self.assertEqual(filtered_page["total_results"], 1)
                self.assertEqual(filtered_page["results"][0]["feature_id"], "SIGNAL")

                connection.request(
                    "GET",
                    f"/v1/geo-analyses/{record['analysis_id']}/results.csv"
                    "?feature_contains=SIGN&effect_direction=case_higher",
                )
                csv_response = connection.getresponse()
                csv_body = csv_response.read().decode("utf-8")
                self.assertEqual(csv_response.status, 200)
                self.assertTrue(csv_response.getheader("Content-Type", "").startswith("text/csv"))
                self.assertIn("results.csv", csv_response.getheader("Content-Disposition", ""))
                self.assertIn("feature_id", csv_body.splitlines()[0])
                self.assertIn("SIGNAL", csv_body)
                self.assertNotIn("PRIVATE_SUBJECT_", csv_body)

                connection.request(
                    "GET", f"/v1/geo-analyses/{record['analysis_id']}/results.csv?limit=1"
                )
                self.assertEqual(connection.getresponse().status, 400)

                connection.request(
                    "GET", f"/v1/geo-analyses/{record['analysis_id']}?fdr_significant=maybe"
                )
                self.assertEqual(connection.getresponse().status, 400)

                expected_report = store.get_report(record["analysis_id"])["report"]
                connection.request(
                    "GET", f"/v1/geo-analyses/{record['analysis_id']}/report.json"
                )
                export_response = connection.getresponse()
                export_body = json.loads(export_response.read())
                self.assertEqual(export_response.status, 200)
                self.assertEqual(export_body, expected_report)
                self.assertTrue(
                    export_response.getheader("Content-Type", "").startswith("application/json")
                )
                self.assertEqual(
                    export_response.getheader("Content-Disposition"),
                    f'attachment; filename="GLIO-NONCODE-GSE141945-{record["analysis_id"]}.json"',
                )
                self.assertNotIn("PRIVATE_SUBJECT_", json.dumps(export_body))

                connection.request(
                    "GET", f"/v1/geo-analyses/{record['analysis_id']}/report.json?limit=1"
                )
                self.assertEqual(connection.getresponse().status, 400)

                connection.request("GET", "/v1/geo-analyses?unexpected=1")
                self.assertEqual(connection.getresponse().status, 400)
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()

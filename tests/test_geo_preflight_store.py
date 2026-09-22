from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread
from unittest.mock import patch

from glio_noncode._cli_geo_qc import main as quality_main
from glio_noncode.api import create_server
from glio_noncode.errors import ValidationError
from glio_noncode.geo_preflight_store import (
    GEO_PREFLIGHT_CATALOG_SCHEMA,
    GeoPreflightStore,
    validate_geo_preflight_report,
)
from glio_noncode.serialization import content_hash


def _quality_report(accession: str = "GSE141945") -> dict[str, object]:
    body: dict[str, object] = {
        "schema": "glio-noncode.geo-expression-quality.v1",
        "status": "completed",
        "source": {
            "accession": accession,
            "retrieval": "local_file",
            "source_sha256": "sha256:" + "a" * 64,
            "sample_count": 81,
            "feature_count": 56832,
        },
        "summary": {
            "measurement_count": 100,
            "observed_measurement_count": 90,
            "missing_measurement_count": 10,
            "overall_missing_fraction": 0.1,
            "complete_feature_count": 20,
            "feature_with_missing_measurement_count": 5,
            "exact_duplicate_profile_group_count": 1,
            "samples_in_exact_duplicate_profile_groups": 2,
        },
    }
    return body | {"content_address": content_hash(body, prefix="geo-expression-quality")}


def _count_metadata_report() -> dict[str, object]:
    body: dict[str, object] = {
        "schema": "glio-noncode.geo-count-metadata.v1",
        "status": "completed",
        "source": {
            "accession": "GSE141945",
            "retrieval": "https",
            "source_sha256": "sha256:" + "b" * 64,
        },
        "summary": {
            "sample_count": 81,
            "column_count": 3,
            "distinct_non_key_category_count_lower_bound": 6,
            "fields_with_suppressed_values_count": 2,
        },
    }
    return body | {"content_address": content_hash(body, prefix="geo-count-metadata")}


def _count_design_report() -> dict[str, object]:
    body: dict[str, object] = {
        "schema": "glio-noncode.geo-count-contrast-design.v1",
        "status": "completed",
        "source": {
            "accession": "GSE141945",
            "retrieval": "https",
            "source_sha256": "sha256:" + "c" * 64,
        },
        "matrix": {"sample_count": 81, "feature_row_count": 56832},
        "summary": {
            "case_sample_count": 17,
            "reference_sample_count": 17,
            "overlap_sample_count": 0,
            "matched_pair_count": 17,
            "feature_row_count": 56832,
            "uniquely_labeled_feature_count": 56828,
            "design_estimable": True,
        },
    }
    return body | {"content_address": content_hash(body, prefix="geo-count-contrast-design")}


class GeoPreflightStoreTests(unittest.TestCase):
    def test_save_list_and_reopen_uses_bounded_catalog_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = GeoPreflightStore(Path(directory) / "workspace")
            record = store.save(_quality_report())
            page = store.list_reports(kind="expression_quality", accession="GSE141945")
            reopened = store.get_report(record["preflight_id"])

        self.assertEqual(page["schema"], GEO_PREFLIGHT_CATALOG_SCHEMA)
        self.assertEqual(page["total_count"], 1)
        self.assertEqual(page["rows"][0]["kind"], "expression_quality")
        self.assertEqual(page["rows"][0]["metrics"]["missing_measurement_count"], 10)
        self.assertEqual(reopened["report"]["source"]["accession"], "GSE141945")
        self.assertNotIn("samples", page["rows"][0])

    def test_duplicate_save_is_idempotent_and_tampering_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = GeoPreflightStore(Path(directory) / "workspace")
            report = _quality_report()
            first = store.save(report)
            second = store.save(copy.deepcopy(report))
            tampered = copy.deepcopy(report)
            tampered["summary"]["missing_measurement_count"] = 11

        self.assertEqual(first, second)
        with self.assertRaises(ValidationError):
            validate_geo_preflight_report(tampered)

    def test_schema_specific_count_projection_preserves_real_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = GeoPreflightStore(Path(directory) / "workspace")
            metadata = store.save(_count_metadata_report())
            design = store.save(_count_design_report())
            rows = store.list_reports()["rows"]

        by_id = {row["preflight_id"]: row for row in rows}
        self.assertEqual(by_id[metadata["preflight_id"]]["sample_count"], 81)
        self.assertIsNone(by_id[metadata["preflight_id"]]["feature_count"])
        self.assertEqual(by_id[design["preflight_id"]]["sample_count"], 81)
        self.assertEqual(by_id[design["preflight_id"]]["feature_count"], 56832)

    def test_unsupported_schema_and_filters_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = GeoPreflightStore(Path(directory) / "workspace")
            with self.assertRaises(ValidationError):
                store.save({"schema": "unknown", "status": "completed"})
            with self.assertRaises(ValidationError):
                store.list_reports(kind="unknown")
            with self.assertRaises(ValidationError):
                store.list_reports(accession="not-a-series")

    def test_http_catalog_and_explicit_report_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            record = GeoPreflightStore(workspace).save(_quality_report())
            server = create_server("127.0.0.1", 0, str(workspace))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request("GET", "/v1/geo-preflights?kind=expression_quality")
                response = connection.getresponse()
                catalog = json.loads(response.read())
                connection.close()
                self.assertEqual(response.status, 200)
                self.assertEqual(catalog["rows"][0]["preflight_id"], record["preflight_id"])
                self.assertNotIn("samples", catalog["rows"][0])

                connection = HTTPConnection(host, port, timeout=30)
                connection.request(
                    "GET",
                    f"/v1/geo-preflights/{record['preflight_id']}/report.json",
                )
                response = connection.getresponse()
                report = json.loads(response.read())
                connection.close()
                self.assertEqual(response.status, 200)
                self.assertEqual(report["schema"], "glio-noncode.geo-expression-quality.v1")
                self.assertIn("attachment", response.getheader("Content-Disposition", ""))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

    def test_quality_cli_save_flag_retains_completed_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "workspace"
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch(
                "glio_noncode._cli_geo_qc.build_expression_quality_report",
                return_value=_quality_report(),
            ):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    result = quality_main(
                        [
                            "GSE141945",
                            "--scale",
                            "normalized_intensity",
                            "--save-to-workspace",
                            "--data-root",
                            str(workspace),
                        ]
                    )
            page = GeoPreflightStore(workspace).list_reports()

        self.assertEqual(result, 0)
        self.assertIn("Saved GEO preflight", stderr.getvalue())
        self.assertIn("GSE141945", stdout.getvalue())
        self.assertEqual(page["total_count"], 1)


if __name__ == "__main__":
    unittest.main()

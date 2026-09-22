from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.client import HTTPConnection
from pathlib import Path
from threading import Thread

from glio_noncode._cli_geo_count_consistency import main as count_consistency_main
from glio_noncode.api import create_server
from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.geo_analysis_store import GeoAnalysisStore
from glio_noncode.geo_count_consistency import (
    CountContrastCompatibilityError,
    build_geo_count_consistency_report,
)
from glio_noncode.geo_expression import build_geo_count_contrast_report
from glio_noncode.serialization import content_hash

from .test_geo_count_contrast import _write_files


def _report(root: Path, accession: str, *, direction_fixture: bool = False) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    counts, metadata = _write_files(root, include_direction_discordance=direction_fixture)
    return build_geo_count_contrast_report(
        accession,
        case_filters=(("Timepoint", "Tumor"),),
        reference_filters=(("Timepoint", "1wk"),),
        sample_key_column="",
        pair_key_column="Patient",
        counts_file=counts,
        metadata_file=metadata,
        fdr_threshold=1.0,
        top=5,
    )


class GeoCountConsistencyTests(unittest.TestCase):
    def test_exact_source_features_are_compared_without_pooling_or_identifier_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = _report(root / "first", "GSE141945")
            second = _report(root / "second", "GSE141946", direction_fixture=True)

            report = build_geo_count_consistency_report(
                (first, second),
                feature_ids=("SIGNAL", "SKEWED_DIRECTION", "NOT_REPORTED"),
            )

        self.assertEqual(report["schema"], "glio-noncode.geo-count-consistency.v1")
        self.assertEqual(report["summary"]["study_count"], 2)
        by_feature = {item["feature_id"]: item for item in report["features"]}
        self.assertEqual(
            by_feature["SIGNAL"]["summary"]["direction_consistency"],
            "concordant_among_tested",
        )
        self.assertEqual(
            by_feature["SIGNAL"]["summary"]["fdr_significant_direction_consistency"],
            "concordant_among_fdr_significant",
        )
        self.assertEqual(
            by_feature["SKEWED_DIRECTION"]["summary"]["not_reported_count"],
            1,
        )
        self.assertEqual(
            by_feature["SKEWED_DIRECTION"]["studies"][0]["result_state"],
            "not_reported_in_bounded_results",
        )
        self.assertEqual(
            by_feature["SKEWED_DIRECTION"]["summary"]["direction_consistency"],
            "insufficient_tested_reports",
        )
        self.assertEqual(
            by_feature["NOT_REPORTED"]["summary"]["not_reported_count"],
            2,
        )
        serialized = json.dumps(report, sort_keys=True)
        self.assertNotIn("PRIVATE_TUMOR_", serialized)
        self.assertNotIn("PRIVATE_SUBJECT_", serialized)
        self.assertFalse(report["analysis"]["effect_sizes_pooled"])
        self.assertFalse(report["analysis"]["p_values_combined"])
        self.assertFalse(report["analysis"]["missing_report_rows_treated_as_negative"])
        self.assertEqual(
            report["content_address"],
            content_hash(
                {key: value for key, value in report.items() if key != "content_address"},
                prefix="geo-count-consistency",
            ),
        )

    def test_saved_store_comparison_reopens_and_revalidates_immutable_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = _report(root / "first", "GSE141945")
            second = _report(root / "second", "GSE141946", direction_fixture=True)
            store = GeoAnalysisStore(root / "workspace")
            first_id = store.save(first)["analysis_id"]
            second_id = store.save(second)["analysis_id"]

            report = store.compare_consistency(
                (first_id, second_id), feature_ids=("SIGNAL",)
            )

        self.assertEqual(report["features"][0]["feature_id"], "SIGNAL")
        self.assertEqual(report["studies"][0]["accession"], "GSE141945")
        self.assertEqual(report["studies"][1]["accession"], "GSE141946")
        self.assertNotIn("analysis_id", report["studies"][0])

    def test_incompatible_normalization_is_rejected_before_feature_join(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = _report(root / "first", "GSE141945")
            (root / "second").mkdir(parents=True, exist_ok=True)
            counts, metadata = _write_files(
                root / "second", include_direction_discordance=True
            )
            second = build_geo_count_contrast_report(
                "GSE141946",
                case_filters=(("Timepoint", "Tumor"),),
                reference_filters=(("Timepoint", "1wk"),),
                sample_key_column="",
                pair_key_column="Patient",
                counts_file=counts,
                metadata_file=metadata,
                fdr_threshold=1.0,
                top=5,
                normalization_method="tmm_log2_cpm",
            )

            with self.assertRaises(CountContrastCompatibilityError):
                build_geo_count_consistency_report((first, second), feature_ids=("SIGNAL",))

    def test_duplicate_series_or_feature_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = _report(root / "first", "GSE141945")
            second = _report(root / "second", "GSE141946", direction_fixture=True)
            with self.assertRaisesRegex(ValidationError, "feature IDs must be unique"):
                build_geo_count_consistency_report(
                    (first, second), feature_ids=("SIGNAL", "SIGNAL")
                )
            with self.assertRaisesRegex(ValidationError, "distinct Series accessions"):
                build_geo_count_consistency_report((first, first), feature_ids=("SIGNAL",))

    def test_focused_cli_accepts_report_paths_and_saved_analysis_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = _report(root / "first", "GSE141945")
            second = _report(root / "second", "GSE141946", direction_fixture=True)
            first_path = root / "first.json"
            second_path = root / "second.json"
            first_path.write_text(json.dumps(first), encoding="utf-8")
            second_path.write_text(json.dumps(second), encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = count_consistency_main(
                    [
                        str(first_path),
                        str(second_path),
                        "--feature-id",
                        "SIGNAL",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(stdout.getvalue())["status"], "completed")
            self.assertEqual(stderr.getvalue(), "")

            store = GeoAnalysisStore(root / "workspace")
            first_id = store.save(first)["analysis_id"]
            second_id = store.save(second)["analysis_id"]
            stdout = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
                result = count_consistency_main(
                    [
                        "--data-root",
                        str(root / "workspace"),
                        "--analysis-id",
                        first_id,
                        "--analysis-id",
                        second_id,
                        "--feature-id",
                        "SIGNAL",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(stdout.getvalue())["summary"]["study_count"], 2)

            stdout = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
                result = cli_main(["commands", "show", "geo-count-consistency"])
            self.assertEqual(result, 0)
            self.assertIn("geo-count-consistency", stdout.getvalue())

    def test_http_consistency_endpoint_is_aggregate_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = _report(root / "first", "GSE141945")
            second = _report(root / "second", "GSE141946", direction_fixture=True)
            store = GeoAnalysisStore(root / "workspace")
            first_id = store.save(first)["analysis_id"]
            second_id = store.save(second)["analysis_id"]
            server = create_server("127.0.0.1", 0, str(root / "workspace"))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                connection = HTTPConnection(host, port, timeout=30)
                connection.request(
                    "GET",
                    "/v1/geo-analyses/consistency"
                    f"?analysis_id={first_id}&analysis_id={second_id}&feature_id=SIGNAL",
                )
                response = connection.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(response.status, 200)
                self.assertEqual(payload["schema"], "glio-noncode.geo-count-consistency.v1")
                self.assertNotIn("PRIVATE_SUBJECT_", json.dumps(payload))
                self.assertNotIn("analysis_id", payload["studies"][0])

                connection.request(
                    "GET",
                    f"/v1/geo-analyses/consistency?analysis_id={first_id}"
                    "&feature_id=SIGNAL&unexpected=1",
                )
                self.assertEqual(connection.getresponse().status, 400)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

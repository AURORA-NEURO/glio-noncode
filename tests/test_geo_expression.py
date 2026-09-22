from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from glio_noncode._cli_geo import main as geo_cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.expression_evidence import ExpressionScale
from glio_noncode.geo_expression import (
    build_expression_outlier_report,
    parse_series_matrix,
    series_matrix_url,
)

SAMPLE_IDS = tuple(f"GSM00000{index}" for index in range(1, 7))


def _matrix_payload() -> bytes:
    samples = "\t".join(f'"{sample}"' for sample in SAMPLE_IDS)
    diagnoses = "\t".join(['"diagnosis: normal"'] * 5 + ['"diagnosis: glioblastoma"'])
    rows = (
        '!Series_geo_accession\t"GSE123456"\n'
        '!Series_title\t"Fixture glioblastoma expression series"\n'
        '!Series_type\t"Expression profiling by array"\n'
        '!Series_platform_id\t"GPL123"\n'
        f"!Sample_geo_accession\t{samples}\n"
        f"!Sample_characteristics_ch1\t{diagnoses}\n"
        "!series_matrix_table_begin\n"
        f"ID_REF\t{samples}\n"
        "probe-1\t1\t2\t3\t4\t5\t10\n"
        "probe-2\t12\t12\t12\t12\t12\t12\n"
        "!series_matrix_table_end\n"
    )
    return gzip.compress(rows.encode("utf-8"), mtime=0)


class GeoExpressionTests(unittest.TestCase):
    def test_short_accession_range_is_valid(self) -> None:
        self.assertIn("/GSEnnn/GSE1/", series_matrix_url("GSE1"))

    def test_parser_retains_metadata_and_only_the_selected_feature(self) -> None:
        matrix = parse_series_matrix(_matrix_payload(), accession="GSE123456", feature_id="probe-1")
        text_matrix = parse_series_matrix(
            gzip.decompress(_matrix_payload()), accession="GSE123456", feature_id="probe-1"
        )
        self.assertEqual(matrix.feature_count, 2)
        self.assertEqual(matrix.feature_values, (1, 2, 3, 4, 5, 10))
        self.assertEqual(text_matrix.feature_values, matrix.feature_values)
        self.assertEqual(matrix.platform_ids, ("GPL123",))
        self.assertEqual(matrix.samples[-1].characteristics, (("diagnosis", "glioblastoma"),))
        self.assertEqual(len(matrix.source_sha256), 64)

    def test_normalized_array_intensities_are_comparable_but_raw_counts_are_not(self) -> None:
        self.assertTrue(ExpressionScale.NORMALIZED_INTENSITY.cohort_comparable)
        self.assertFalse(ExpressionScale.RAW_COUNT.cohort_comparable)

    def test_parser_rejects_bad_accessions_features_and_truncated_gzip(self) -> None:
        with self.assertRaises(ValidationError):
            parse_series_matrix(_matrix_payload(), accession="GSE123456", feature_id="missing")
        with self.assertRaises(ValidationError):
            parse_series_matrix(_matrix_payload()[:-5], accession="GSE123456", feature_id="probe-1")
        with self.assertRaises(ValidationError):
            parse_series_matrix(
                _matrix_payload(), accession="GSE123456/../bad", feature_id="probe-1"
            )
        with self.assertRaises(ValidationError):
            parse_series_matrix(
                _matrix_payload(),
                accession="GSE123456",
                feature_id="probe-1",
                source_file_name="C:\\private\\matrix.txt.gz",
            )

    def test_https_report_uses_selected_references_and_retains_source_digest(self) -> None:
        response_url = series_matrix_url("GSE123456")
        fake_response = SimpleNamespace(status=200, url=response_url, body=_matrix_payload())
        with patch(
            "glio_noncode.geo_expression.UrllibTransport.request", return_value=fake_response
        ) as request:
            report = build_expression_outlier_report(
                "GSE123456",
                feature_id="probe-1",
                target_sample_id=SAMPLE_IDS[-1],
                reference_filters=(("diagnosis", "normal"),),
                scale=ExpressionScale.NORMALIZED_INTENSITY,
            )

        request.assert_called_once()
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["comparison"]["reference_sample_ids"], list(SAMPLE_IDS[:5]))
        self.assertFalse(report["comparison"]["matched_to_case_sample"])
        self.assertFalse(report["comparison"]["population_level_test"])
        self.assertEqual(report["result"]["call"], "descriptive_outlier")
        self.assertGreater(report["result"]["robust_z"], report["result"]["z_threshold"])
        self.assertEqual(report["source"]["response_url"], response_url)
        self.assertTrue(report["source"]["source_sha256"].startswith("sha256:"))

    def test_cli_runs_with_a_local_matrix_without_leaking_its_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix_path = root / "downloaded.txt.gz"
            output_path = root / "report.json"
            matrix_path.write_bytes(_matrix_payload())

            result = geo_cli_main(
                [
                    "GSE123456",
                    "--feature-id",
                    "probe-1",
                    "--target-sample",
                    SAMPLE_IDS[-1],
                    "--reference-filter",
                    "diagnosis=normal",
                    "--scale",
                    "normalized_intensity",
                    "--matrix-file",
                    str(matrix_path),
                    "--output",
                    str(output_path),
                ]
            )

            serialized = output_path.read_text(encoding="utf-8")
            report = json.loads(serialized)

        self.assertEqual(result, 0)
        self.assertEqual(report["source"]["retrieval"], "local_file")
        self.assertEqual(report["source"]["source_file_name"], "downloaded.txt.gz")
        self.assertNotIn(str(root), serialized)
        self.assertNotIn("state", report)

    def test_target_cannot_be_included_in_its_own_reference_group(self) -> None:
        response = SimpleNamespace(
            status=200, url=series_matrix_url("GSE123456"), body=_matrix_payload()
        )
        with patch("glio_noncode.geo_expression.UrllibTransport.request", return_value=response):
            with self.assertRaises(ValidationError):
                build_expression_outlier_report(
                    "GSE123456",
                    feature_id="probe-1",
                    target_sample_id=SAMPLE_IDS[-1],
                    reference_filters=(("diagnosis", "glioblastoma"),),
                    scale="normalized_intensity",
                )

    def test_empty_reference_group_produces_an_explicit_unresolved_result(self) -> None:
        response = SimpleNamespace(
            status=200, url=series_matrix_url("GSE123456"), body=_matrix_payload()
        )
        with patch("glio_noncode.geo_expression.UrllibTransport.request", return_value=response):
            report = build_expression_outlier_report(
                "GSE123456",
                feature_id="probe-1",
                target_sample_id=SAMPLE_IDS[-1],
                reference_filters=(("diagnosis", "control"),),
                scale="normalized_intensity",
            )

        self.assertEqual(report["result"]["call"], "unresolved")
        self.assertEqual(
            report["result"]["reason_codes"], ["reference_group_has_no_feature_values"]
        )

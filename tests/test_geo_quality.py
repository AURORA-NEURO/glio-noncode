from __future__ import annotations

import gzip
import io
import json
import math
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.geo_expression import series_matrix_url
from glio_noncode.geo_quality import build_expression_quality_report
from glio_noncode.serialization import content_hash

SAMPLE_IDS = ("GSM000001", "GSM000002", "GSM000003")


def _matrix_payload(*, platform_ids: tuple[str, ...] = ("GPL123",)) -> bytes:
    samples = "\t".join(f'"{sample}"' for sample in SAMPLE_IDS)
    platforms = "\t".join(f'"{item}"' for item in platform_ids)
    diagnoses = '\t"diagnosis: normal"' * len(SAMPLE_IDS)
    rows = (
        '!Series_geo_accession\t"GSE123456"\n'
        '!Series_title\t"Fixture GEO expression quality series"\n'
        '!Series_type\t"Expression profiling by array"\n'
        f"!Series_platform_id\t{platforms}\n"
        f"!Sample_geo_accession\t{samples}\n"
        f"!Sample_characteristics_ch1{diagnoses}\n"
        "!series_matrix_table_begin\n"
        f"ID_REF\t{samples}\n"
        "probe-1\t1\t2\tNA\n"
        "probe-2\t3\t4\tNA\n"
        "probe-3\t5\t6\t10\n"
        "probe-4\tNA\t8\t10\n"
        "!series_matrix_table_end\n"
    )
    return gzip.compress(rows.encode("utf-8"), mtime=0)


class GeoExpressionQualityTests(unittest.TestCase):
    def test_sample_and_feature_missingness_summaries_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "matrix.txt.gz"
            matrix_path.write_bytes(_matrix_payload())

            report = build_expression_quality_report(
                "GSE123456",
                scale="normalized_intensity",
                matrix_file=matrix_path,
            )
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["analysis"]["scale"], "normalized_intensity")
        self.assertFalse(report["analysis"]["transformed_values"])
        self.assertFalse(report["analysis"]["feature_vectors_retained"])
        self.assertEqual(report["analysis"]["streaming_summary_passes"], 1)
        self.assertFalse(report["analysis"]["automatic_sample_exclusion"])
        self.assertFalse(report["analysis"]["automatic_quality_classification"])
        summary = report["summary"]
        self.assertEqual(summary["measurement_count"], 12)
        self.assertEqual(summary["observed_measurement_count"], 9)
        self.assertEqual(summary["missing_measurement_count"], 3)
        self.assertEqual(summary["overall_missing_fraction"], 0.25)
        self.assertEqual(summary["complete_feature_count"], 1)
        self.assertEqual(summary["feature_with_missing_measurement_count"], 3)
        self.assertEqual(
            [item["feature_count"] for item in summary["features_by_missing_sample_count"]],
            [1, 3, 0, 0],
        )
        first, second, third = report["samples"]
        self.assertEqual(first["sample_accession"], SAMPLE_IDS[0])
        self.assertEqual(first["observed_feature_count"], 3)
        self.assertEqual(first["missing_feature_count"], 1)
        self.assertAlmostEqual(first["mean"], 3.0)
        self.assertAlmostEqual(first["sample_standard_deviation"], 2.0)
        self.assertEqual((first["minimum"], first["maximum"]), (1.0, 5.0))
        self.assertAlmostEqual(second["mean"], 5.0)
        self.assertAlmostEqual(second["sample_standard_deviation"], math.sqrt(20 / 3))
        self.assertEqual((third["mean"], third["sample_standard_deviation"]), (10.0, 0.0))

    def test_local_provenance_is_content_addressed_without_directory_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix_path = root / "downloaded-series.txt.gz"
            matrix_path.write_bytes(_matrix_payload())

            report = build_expression_quality_report(
                "GSE123456",
                scale="normalized_intensity",
                matrix_file=matrix_path,
            )
            repeated_address = build_expression_quality_report(
                "GSE123456",
                scale="normalized_intensity",
                matrix_file=matrix_path,
            )["content_address"]

        self.assertEqual(report["source"]["retrieval"], "local_file")
        self.assertEqual(report["source"]["source_file_name"], matrix_path.name)
        self.assertNotIn(str(root), json.dumps(report))
        self.assertEqual(
            report["content_address"],
            content_hash(
                {key: value for key, value in report.items() if key != "content_address"},
                prefix="geo-expression-quality",
            ),
        )
        self.assertEqual(
            report["content_address"],
            repeated_address,
        )

    def test_unobserved_sample_metrics_are_null_and_no_sample_is_dropped(self) -> None:
        samples = '\t"GSM000001"\t"GSM000002"\t"GSM000003"\t"GSM000004"'
        text = gzip.decompress(_matrix_payload()).decode("utf-8")
        text = text.replace(
            '!Sample_geo_accession\t"GSM000001"\t"GSM000002"\t"GSM000003"',
            f"!Sample_geo_accession{samples}",
        )
        original_characteristics = (
            '!Sample_characteristics_ch1\t"diagnosis: normal"'
            '\t"diagnosis: normal"\t"diagnosis: normal"'
        )
        text = text.replace(
            original_characteristics,
            f'{original_characteristics}\t"diagnosis: normal"',
        )
        text = text.replace(
            'ID_REF\t"GSM000001"\t"GSM000002"\t"GSM000003"\n',
            'ID_REF\t"GSM000001"\t"GSM000002"\t"GSM000003"\t"GSM000004"\n',
        )
        text = text.replace("probe-1\t1\t2\tNA\n", "probe-1\t1\t2\tNA\tNA\n")
        text = text.replace("probe-2\t3\t4\tNA\n", "probe-2\t3\t4\tNA\tNA\n")
        text = text.replace("probe-3\t5\t6\t10\n", "probe-3\t5\t6\t10\tNA\n")
        text = text.replace("probe-4\tNA\t8\t10\n", "probe-4\tNA\t8\t10\tNA\n")

        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "all-missing-sample.txt.gz"
            matrix_path.write_bytes(gzip.compress(text.encode("utf-8"), mtime=0))

            report = build_expression_quality_report(
                "GSE123456",
                scale="normalized_intensity",
                matrix_file=matrix_path,
            )

        unobserved = report["samples"][-1]
        self.assertEqual(report["summary"]["sample_count"], 4)
        self.assertEqual(unobserved["missing_feature_count"], 4)
        self.assertEqual(unobserved["missing_fraction"], 1.0)
        self.assertIsNone(unobserved["mean"])
        self.assertIsNone(unobserved["sample_standard_deviation"])
        self.assertIsNone(unobserved["minimum"])
        self.assertIsNone(unobserved["maximum"])

    def test_rejects_multiple_platforms_invalid_scales_and_timeouts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "matrix.txt.gz"
            matrix_path.write_bytes(_matrix_payload(platform_ids=("GPL123", "GPL456")))
            with self.assertRaisesRegex(ValidationError, "exactly one platform"):
                build_expression_quality_report(
                    "GSE123456",
                    scale="normalized_intensity",
                    matrix_file=matrix_path,
                )
            matrix_path.write_bytes(_matrix_payload())
            with self.assertRaisesRegex(ValidationError, "expression scale"):
                build_expression_quality_report(
                    "GSE123456",
                    scale="unknown_scale",
                    matrix_file=matrix_path,
                )
            with self.assertRaisesRegex(ValidationError, "timeout"):
                build_expression_quality_report(
                    "GSE123456",
                    scale="normalized_intensity",
                    matrix_file=matrix_path,
                    timeout_seconds=math.inf,
                )

    def test_cli_dispatches_geo_qc_and_writes_a_machine_readable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix_path = root / "downloaded.txt.gz"
            report_path = root / "quality.json"
            matrix_path.write_bytes(_matrix_payload())

            exit_code = cli_main(
                [
                    "geo-qc",
                    "GSE123456",
                    "--scale",
                    "normalized_intensity",
                    "--matrix-file",
                    str(matrix_path),
                    "--output",
                    str(report_path),
                ]
            )
            serialized = report_path.read_text(encoding="utf-8")
            report = json.loads(serialized)

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["schema"], "glio-noncode.geo-expression-quality.v1")
        self.assertNotIn(str(root), serialized)

    def test_https_retrieval_records_response_provenance(self) -> None:
        response_url = series_matrix_url("GSE123456")
        response = SimpleNamespace(status=200, url=response_url, body=_matrix_payload())
        with patch(
            "glio_noncode.geo_expression.UrllibTransport.request", return_value=response
        ) as request:
            report = build_expression_quality_report(
                "GSE123456",
                scale="normalized_intensity",
            )

        request.assert_called_once()
        self.assertEqual(report["source"]["retrieval"], "https")
        self.assertEqual(report["source"]["response_url"], response_url)
        self.assertIsNone(report["source"]["source_file_name"])

    def test_static_command_discovery_includes_geo_qc(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = cli_main(["commands", "show", "geo-qc"])

        self.assertEqual(exit_code, 0)
        self.assertIn("summarize sample coverage", output.getvalue())

    def test_unrepresentable_sample_standard_deviation_serializes_as_null(self) -> None:
        text = gzip.decompress(_matrix_payload()).decode("utf-8")
        text = text.replace("probe-1\t1\t2\tNA", "probe-1\t1\t-1.7e308\tNA")
        text = text.replace("probe-2\t3\t4\tNA", "probe-2\t3\t1.7e308\tNA")
        text = text.replace("probe-3\t5\t6\t10", "probe-3\t5\tNA\t10")
        text = text.replace("probe-4\tNA\t8\t10", "probe-4\tNA\tNA\t10")

        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "extreme-values.txt.gz"
            matrix_path.write_bytes(gzip.compress(text.encode("utf-8"), mtime=0))

            report = build_expression_quality_report(
                "GSE123456",
                scale="normalized_intensity",
                matrix_file=matrix_path,
            )

        self.assertAlmostEqual(report["samples"][1]["mean"], 0.0)
        self.assertIsNone(report["samples"][1]["sample_standard_deviation"])
        json.dumps(report, allow_nan=False)


if __name__ == "__main__":
    unittest.main()

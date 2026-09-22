from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.geo_expression import (
    parse_series_matrix_metadata,
    scan_series_matrix_features,
    series_matrix_url,
)
from glio_noncode.geo_metadata import build_geo_sample_metadata_report
from glio_noncode.serialization import content_hash

SAMPLE_IDS = ("GSM000001", "GSM000002", "GSM000003")


def _matrix_payload() -> bytes:
    samples = "\t".join(f'"{sample}"' for sample in SAMPLE_IDS)
    rows = (
        '!Series_geo_accession\t"GSE123456"\n'
        '!Series_title\t"Fixture sample metadata series"\n'
        '!Series_type\t"Expression profiling by array"\n'
        '!Series_platform_id\t"GPL123"\n'
        f"!Sample_geo_accession\t{samples}\n"
        '!Sample_title\t"Sample one"\t"Sample two"\t"Sample three"\n'
        '!Sample_source_name_ch1\t"brain"\t"brain"\t"normal brain"\n'
        '!Sample_characteristics_ch1\t"diagnosis: Normal"\t'
        '"diagnosis: glioblastoma"\t"diagnosis: normal"\n'
        '!Sample_characteristics_ch1\t"diagnosis: recurrent"\t'
        '"subtype: proneural"\t"batch: B"\n'
        '!Sample_characteristics_ch1\t"Diagnosis: NORMAL"\t'
        '"subtype: proneural"\t"batch: B"\n'
        "!series_matrix_table_begin\n"
        f"ID_REF\t{samples}\n"
        "probe-1\t1\t2\t3\n"
        "!series_matrix_table_end\n"
    )
    return gzip.compress(rows.encode("utf-8"), mtime=0)


def _large_category_payload(category_count: int) -> bytes:
    samples = tuple(f"GSM{index + 1:06d}" for index in range(category_count))
    quoted_samples = "\t".join(f'"{sample}"' for sample in samples)
    categories = "\t".join(f'"group: value-{index:03d}"' for index in range(category_count))
    expression_values = "\t".join("1" for _ in samples)
    rows = (
        '!Series_geo_accession\t"GSE123456"\n'
        '!Series_title\t"Fixture category truncation series"\n'
        '!Series_type\t"Expression profiling by array"\n'
        '!Series_platform_id\t"GPL123"\n'
        f"!Sample_geo_accession\t{quoted_samples}\n"
        f"!Sample_characteristics_ch1\t{categories}\n"
        "!series_matrix_table_begin\n"
        f"ID_REF\t{quoted_samples}\n"
        f"probe-1\t{expression_values}\n"
        "!series_matrix_table_end\n"
    )
    return gzip.compress(rows.encode("utf-8"), mtime=0)


class GeoSampleMetadataTests(unittest.TestCase):
    def test_metadata_parser_validates_matrix_without_retaining_feature_values(self) -> None:
        matrix = parse_series_matrix_metadata(
            _matrix_payload(),
            accession="GSE123456",
            source_file_name="matrix.txt.gz",
        )

        self.assertEqual(matrix.accession, "GSE123456")
        self.assertEqual(matrix.feature_count, 1)
        self.assertEqual(matrix.samples[0].characteristics[0], ("diagnosis", "Normal"))
        self.assertFalse(hasattr(matrix, "features"))
        self.assertEqual(matrix.source_file_name, "matrix.txt.gz")

    def test_streaming_scanner_delivers_rows_and_returns_metadata_only(self) -> None:
        observed_features = []
        matrix = scan_series_matrix_features(
            _matrix_payload(),
            accession="GSE123456",
            feature_consumer=observed_features.append,
        )

        self.assertEqual(matrix.feature_count, 1)
        self.assertFalse(hasattr(matrix, "features"))
        self.assertEqual([feature.feature_id for feature in observed_features], ["probe-1"])
        self.assertEqual(observed_features[0].values, (1.0, 2.0, 3.0))

    def test_streaming_scanner_rejects_duplicate_feature_identifiers(self) -> None:
        text = gzip.decompress(_matrix_payload()).decode("utf-8").replace(
            "!series_matrix_table_end\n",
            "probe-1\t4\t5\t6\n!series_matrix_table_end\n",
        )
        payload = gzip.compress(text.encode("utf-8"), mtime=0)

        with self.assertRaisesRegex(ValidationError, "feature IDs are not unique"):
            scan_series_matrix_features(
                payload,
                accession="GSE123456",
                feature_consumer=lambda feature: None,
            )

    def test_report_summarizes_casefolded_categories_missingness_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "matrix.txt.gz"
            matrix_path.write_bytes(_matrix_payload())
            report = build_geo_sample_metadata_report(
                "GSE123456",
                matrix_file=matrix_path,
            )

        self.assertEqual(report["schema"], "glio-noncode.geo-sample-metadata.v1")
        self.assertFalse(report["analysis"]["expression_values_retained"])
        self.assertTrue(report["analysis"]["expression_values_validated"])
        self.assertFalse(report["analysis"]["automatic_group_assignment"])
        self.assertEqual(report["summary"]["sample_count"], 3)
        self.assertEqual(report["summary"]["characteristic_annotation_entry_count"], 9)
        self.assertEqual(report["summary"]["duplicate_characteristic_entry_count"], 3)

        fields = {item["field"].casefold(): item for item in report["characteristics"]}
        diagnosis = fields["diagnosis"]
        self.assertEqual(diagnosis["sample_count"], 3)
        self.assertEqual(diagnosis["multiple_value_sample_count"], 1)
        self.assertEqual(
            {item["value"].casefold(): item["sample_count"] for item in diagnosis["values"]},
            {"normal": 2, "glioblastoma": 1, "recurrent": 1},
        )
        self.assertEqual(fields["subtype"]["missing_sample_count"], 2)
        self.assertEqual(fields["batch"]["coverage_fraction"], 1 / 3)

    def test_report_is_content_addressed_and_does_not_leak_local_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix_path = root / "downloaded.txt.gz"
            matrix_path.write_bytes(_matrix_payload())
            report = build_geo_sample_metadata_report("GSE123456", matrix_file=matrix_path)

        serialized = json.dumps(report)
        self.assertNotIn(str(root), serialized)
        self.assertEqual(report["source"]["source_file_name"], matrix_path.name)
        self.assertEqual(
            report["content_address"],
            content_hash(
                {key: value for key, value in report.items() if key != "content_address"},
                prefix="geo-sample-metadata",
            ),
        )

    def test_category_truncation_is_explicit_and_counts_omitted_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "many-categories.txt.gz"
            matrix_path.write_bytes(_large_category_payload(102))
            report = build_geo_sample_metadata_report("GSE123456", matrix_file=matrix_path)

        group = report["characteristics"][0]
        self.assertEqual(group["distinct_value_count"], 102)
        self.assertEqual(group["reported_value_count"], 100)
        self.assertTrue(group["values_truncated"])
        self.assertEqual(group["omitted_value_count"], 2)
        self.assertEqual(group["omitted_value_sample_memberships"], 2)
        self.assertEqual(report["summary"]["omitted_category_count"], 2)

    def test_metadata_only_parser_still_rejects_invalid_expression_cells(self) -> None:
        malformed = gzip.decompress(_matrix_payload()).decode("utf-8").replace(
            "probe-1\t1\t2\t3", "probe-1\t1\tNaN\t3"
        )
        payload = gzip.compress(malformed.encode("utf-8"), mtime=0)

        with self.assertRaisesRegex(ValidationError, "non-finite"):
            parse_series_matrix_metadata(payload, accession="GSE123456")

    def test_blank_characteristic_cells_are_missing_not_invalid(self) -> None:
        text = gzip.decompress(_matrix_payload()).decode("utf-8").replace(
            '"diagnosis: glioblastoma"', '""'
        )
        payload = gzip.compress(text.encode("utf-8"), mtime=0)
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "partially-annotated.txt.gz"
            matrix_path.write_bytes(payload)
            report = build_geo_sample_metadata_report("GSE123456", matrix_file=matrix_path)

        diagnosis = next(
            field for field in report["characteristics"] if field["field"] == "diagnosis"
        )
        self.assertEqual(diagnosis["sample_count"], 2)
        self.assertEqual(diagnosis["missing_sample_count"], 1)
        self.assertEqual(
            {item["value"].casefold(): item["sample_count"] for item in diagnosis["values"]},
            {"normal": 2, "recurrent": 1},
        )

    def test_rejects_invalid_timeout_and_accession(self) -> None:
        with self.assertRaisesRegex(ValidationError, "timeout"):
            build_geo_sample_metadata_report("GSE123456", timeout_seconds=float("inf"))
        with self.assertRaises(ValidationError):
            build_geo_sample_metadata_report("../../invalid")

    def test_cli_writes_report_from_local_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix_path = root / "matrix.txt.gz"
            report_path = root / "metadata.json"
            matrix_path.write_bytes(_matrix_payload())
            result = cli_main(
                [
                    "geo-metadata",
                    "GSE123456",
                    "--matrix-file",
                    str(matrix_path),
                    "--output",
                    str(report_path),
                ]
            )
            serialized = report_path.read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(serialized)["status"], "completed")
        self.assertNotIn(str(root), serialized)

    def test_https_retrieval_records_response_provenance(self) -> None:
        response_url = series_matrix_url("GSE123456")
        response = SimpleNamespace(status=200, url=response_url, body=_matrix_payload())
        with patch(
            "glio_noncode.geo_expression.UrllibTransport.request", return_value=response
        ) as request:
            report = build_geo_sample_metadata_report("GSE123456")

        request.assert_called_once()
        self.assertEqual(report["source"]["retrieval"], "https")
        self.assertEqual(report["source"]["response_url"], response_url)

    def test_command_is_available_in_the_static_cli_index(self) -> None:
        stdout = []
        with redirect_stdout(_ListWriter(stdout)):
            result = cli_main(["commands", "show", "geo-metadata"])

        self.assertEqual(result, 0)
        self.assertIn("inventory GEO sample characteristics", "".join(stdout))


class _ListWriter:
    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks

    def write(self, value: str) -> int:
        self.chunks.append(value)
        return len(value)


if __name__ == "__main__":
    unittest.main()

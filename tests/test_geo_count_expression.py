from __future__ import annotations

import csv
import gzip
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from glio_noncode._cli_geo import count_main
from glio_noncode.cli import main as cli_main
from glio_noncode.errors import SourceNotFoundError, ValidationError
from glio_noncode.geo_expression import (
    build_geo_count_outlier_report,
    geo_series_supplementary_url,
    parse_geo_supplementary_count_matrix,
)

SAMPLE_IDS = tuple(f"PRIVATE_SAMPLE_{index}" for index in range(6))


def _gzip_csv(rows: list[list[str]]) -> bytes:
    text = io.StringIO(newline="")
    writer = csv.writer(text, lineterminator="\n")
    writer.writerows(rows)
    return gzip.compress(text.getvalue().encode("utf-8"), mtime=0)


def _count_payload(*, target_value: str = "5000") -> bytes:
    rows = [
        ["", *SAMPLE_IDS],
        ["EGFR", "10", "20", "30", "40", "50", target_value],
        ["PTEN", "1000", "1000", "1000", "1000", "1000", "1000"],
    ]
    rows.append(["PTEN", "5", "5", "5", "5", "5", "5"])
    return _gzip_csv(rows)


def _metadata_payload(*, tumor_count: int = 6, extra_sample: str | None = None) -> bytes:
    rows = [["", "Patient", "Timepoint"]]
    for index, sample_id in enumerate(SAMPLE_IDS):
        timepoint = "Tumor" if index < tumor_count else "Control"
        rows.append([sample_id, f"SUBJECT_PRIVATE_{index}", timepoint])
    if extra_sample is not None:
        rows.append([extra_sample, "SUBJECT_PRIVATE_EXTRA", "Tumor"])
    return _gzip_csv(rows)


def _write_files(root: Path, *, tumor_count: int = 6) -> tuple[Path, Path]:
    counts_path = root / "counts.csv.gz"
    metadata_path = root / "metadata.csv.gz"
    counts_path.write_bytes(_count_payload())
    metadata_path.write_bytes(_metadata_payload(tumor_count=tumor_count))
    return counts_path, metadata_path


class GeoCountExpressionTests(unittest.TestCase):
    def test_local_matrix_runs_sample_free_leave_one_out_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts_path, metadata_path = _write_files(root)
            report = build_geo_count_outlier_report(
                "GSE141945",
                feature_id="EGFR",
                sample_key_column="",
                sample_filters=(("Timepoint", "Tumor"),),
                counts_file=counts_path,
                metadata_file=metadata_path,
            )
            serialized = json.dumps(report, sort_keys=True)
            self.assertEqual(report["status"], "completed")
            self.assertEqual(report["matrix"]["feature_count"], 3)
            self.assertEqual(report["matrix"]["sample_count"], 6)
            self.assertEqual(report["matrix"]["duplicate_feature_label_count"], 1)
            self.assertEqual(report["comparison"]["comparison_count"], 6)
            self.assertEqual(report["comparison"]["reference_count_range"], [5, 5])
            self.assertEqual(
                sum(report["result"]["call_counts"].values()),
                6,
            )
            self.assertNotIn(str(root), serialized)
            for sample_id in SAMPLE_IDS:
                self.assertNotIn(sample_id, serialized)
            self.assertNotIn("SUBJECT_PRIVATE_", serialized)
            self.assertTrue(report["content_address"].startswith("geo-count-expression-outlier:"))

    def test_insufficient_reference_count_is_reported_as_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory), tumor_count=4)
            report = build_geo_count_outlier_report(
                "GSE141945",
                feature_id="EGFR",
                sample_key_column="",
                sample_filters=(("Timepoint", "Tumor"),),
                counts_file=counts_path,
                metadata_file=metadata_path,
            )
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["result"]["call_counts"]["unresolved"], 4)
        self.assertEqual(report["result"]["evidence_state_counts"], {"abstained": 4})
        self.assertEqual(
            report["result"]["reason_code_counts"], {"insufficient_reference_count": 4}
        )

    def test_empty_filter_cohort_returns_addressed_unresolved_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory))
            report = build_geo_count_outlier_report(
                "GSE141945",
                feature_id="EGFR",
                sample_key_column="",
                sample_filters=(("Timepoint", "NotPresent"),),
                counts_file=counts_path,
                metadata_file=metadata_path,
            )
        self.assertEqual(report["status"], "unresolved")
        self.assertEqual(report["comparison"]["selected_sample_count"], 0)
        self.assertEqual(
            report["result"]["reason_code_counts"],
            {"no_samples_match_metadata_filters": 1},
        )

    def test_input_validation_rejects_mismatched_samples_and_invalid_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts_path, metadata_path = _write_files(root)
            metadata_path.write_bytes(_metadata_payload(extra_sample="UNMATCHED_SAMPLE"))
            with self.assertRaises(ValidationError):
                build_geo_count_outlier_report(
                    "GSE141945",
                    feature_id="EGFR",
                    sample_key_column="",
                    sample_filters=(("Timepoint", "Tumor"),),
                    counts_file=counts_path,
                    metadata_file=metadata_path,
                )

            metadata_path.write_bytes(_metadata_payload())
            counts_path.write_bytes(_count_payload(target_value="-1"))
            with self.assertRaises(ValidationError):
                build_geo_count_outlier_report(
                    "GSE141945",
                    feature_id="EGFR",
                    sample_key_column="",
                    sample_filters=(("Timepoint", "Tumor"),),
                    counts_file=counts_path,
                    metadata_file=metadata_path,
                )

    def test_duplicate_requested_feature_is_rejected_but_other_duplicates_count(self) -> None:
        duplicate_target = _gzip_csv(
            [
                ["", *SAMPLE_IDS],
                ["EGFR", "1", "2", "3", "4", "5", "6"],
                ["EGFR", "1", "2", "3", "4", "5", "6"],
            ]
        )
        with self.assertRaises(ValidationError):
            parse_geo_supplementary_count_matrix(
                duplicate_target,
                accession="GSE141945",
                feature_id="EGFR",
            )

        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory))
            parsed_report_data = build_geo_count_outlier_report(
                "GSE141945",
                feature_id="EGFR",
                sample_key_column="",
                sample_filters=(("Timepoint", "Tumor"),),
                counts_file=counts_path,
                metadata_file=metadata_path,
            )
        self.assertEqual(parsed_report_data["matrix"]["duplicate_feature_label_count"], 1)

    def test_remote_retrieval_is_confined_to_canonical_geo_series_paths(self) -> None:
        counts_name = "counts.csv.gz"
        metadata_name = "samples.csv.gz"
        counts_url = geo_series_supplementary_url("GSE141945", counts_name)
        metadata_url = geo_series_supplementary_url("GSE141945", metadata_name)
        responses = (
            SimpleNamespace(status=200, url=counts_url, body=_count_payload()),
            SimpleNamespace(status=200, url=metadata_url, body=_metadata_payload()),
        )
        with patch(
            "glio_noncode.geo_expression.UrllibTransport.request", side_effect=responses
        ) as request:
            report = build_geo_count_outlier_report(
                "GSE141945",
                feature_id="EGFR",
                sample_key_column="",
                sample_filters=(("Timepoint", "Tumor"),),
                counts_file_name=counts_name,
                metadata_file_name=metadata_name,
            )
        self.assertEqual(request.call_count, 2)
        self.assertEqual(report["source"]["retrieval"], "https")
        self.assertEqual(report["source"]["count_matrix"]["response_url"], counts_url)
        self.assertEqual(report["source"]["sample_metadata"]["response_url"], metadata_url)

    def test_cli_local_file_path_and_static_command_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts_path, metadata_path = _write_files(root)
            output_path = root / "result.json"
            status = count_main(
                [
                    "GSE141945",
                    "--feature-id",
                    "EGFR",
                    "--sample-key-column",
                    "",
                    "--sample-filter",
                    "Timepoint=Tumor",
                    "--counts-file",
                    str(counts_path),
                    "--metadata-file",
                    str(metadata_path),
                    "--output",
                    str(output_path),
                ]
            )
            serialized = output_path.read_text(encoding="utf-8")
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(serialized)["status"], "completed")
            self.assertNotIn(str(root), serialized)

        output: list[str] = []

        class Writer:
            def write(self, value: str) -> int:
                output.append(value)
                return len(value)

        with patch("sys.stdout", Writer()):
            self.assertEqual(cli_main(["commands", "show", "geo-count-outlier"]), 0)
        self.assertIn("supplementary count matrix", "".join(output))

        with patch("glio_noncode._cli_geo.count_main", return_value=17) as count_dispatch:
            self.assertEqual(cli_main(["geo-count-outlier", "GSE141945"]), 17)
        count_dispatch.assert_called_once_with(["GSE141945"])

    def test_supplementary_url_rejects_path_traversal(self) -> None:
        with self.assertRaises(ValidationError):
            geo_series_supplementary_url("GSE141945", "../private.csv.gz")
        missing_url = geo_series_supplementary_url("GSE141945", "missing.csv.gz")
        with patch(
            "glio_noncode.geo_expression.UrllibTransport.request",
            return_value=SimpleNamespace(status=404, url=missing_url, body=b""),
        ):
            with self.assertRaises(SourceNotFoundError):
                build_geo_count_outlier_report(
                    "GSE141945",
                    feature_id="EGFR",
                    sample_key_column="",
                    sample_filters=(("Timepoint", "Tumor"),),
                    counts_file_name="missing.csv.gz",
                    metadata_file_name="samples.csv.gz",
                )


if __name__ == "__main__":
    unittest.main()

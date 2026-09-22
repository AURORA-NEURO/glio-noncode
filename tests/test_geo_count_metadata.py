from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from glio_noncode._cli_geo_count_metadata import main as count_metadata_main
from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.geo_expression import geo_series_supplementary_url
from glio_noncode.geo_metadata import build_geo_count_metadata_report
from glio_noncode.serialization import content_hash


def _gzip_csv(rows: list[list[str]]) -> bytes:
    text = io.StringIO(newline="")
    writer = csv.writer(text, lineterminator="\n")
    writer.writerows(rows)
    return gzip.compress(text.getvalue().encode("utf-8"), mtime=0)


def _metadata_payload() -> bytes:
    rows = [["", "Patient", "Timepoint", "Cohort", "Patient_ID"]]
    for index in reversed(range(4)):
        case_id = f"PRIVATE_SAMPLE_CASE_{index}"
        reference_id = f"PRIVATE_SAMPLE_REFERENCE_{index}"
        pair_id = f"PRIVATE_SUBJECT_{index}"
        cohort = "StudyA" if index < 2 else "StudyB"
        rows.append([case_id, pair_id, "Tumor", cohort, f"PRIVATE_DONOR_{index}"])
        rows.append([reference_id, pair_id, "1wk", cohort, f"PRIVATE_DONOR_{index}"])
    return _gzip_csv(rows)


def _build_report(payload: bytes | None = None, **options: Any) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "metadata.csv.gz"
        path.write_bytes(_metadata_payload() if payload is None else payload)
        defaults: dict[str, Any] = {
            "sample_key_column": "",
            "pair_key_column": "Patient",
            "metadata_file": path,
        }
        return build_geo_count_metadata_report("GSE141945", **(defaults | options))


class GeoCountMetadataTests(unittest.TestCase):
    def test_local_inventory_reports_categories_and_pair_shape_without_identifiers(self) -> None:
        report = _build_report()
        serialized = json.dumps(report, sort_keys=True)
        columns = {column["field"]: column for column in report["columns"]}

        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["schema"], "glio-noncode.geo-count-metadata.v1")
        self.assertEqual(report["source"]["retrieval"], "local_file")
        self.assertEqual(report["source"]["file_name"], "metadata.csv.gz")
        self.assertEqual(report["analysis"]["metadata_row_count"], 8)
        self.assertTrue(report["analysis"]["sample_key_unique"])
        self.assertFalse(report["analysis"]["sample_key_values_emitted"])
        self.assertEqual(columns[""]["distinct_value_count"], 8)
        self.assertEqual(columns[""]["values_suppression_reason"], "sample_key")
        self.assertFalse(columns[""]["filter_field_round_trippable"])
        self.assertEqual(columns["Patient"]["values_suppression_reason"], "pair_key")
        self.assertFalse(columns["Patient"]["filter_field_round_trippable"])
        self.assertEqual(
            columns["Patient_ID"]["values_suppression_reason"],
            "identifier_like_field_name",
        )
        self.assertEqual(
            {item["value"]: item["sample_count"] for item in columns["Timepoint"]["values"]},
            {"Tumor": 4, "1wk": 4},
        )
        self.assertTrue(columns["Timepoint"]["filter_field_round_trippable"])
        pair = report["summary"]["pair_key"]
        self.assertEqual(pair["distinct_pair_key_count"], 4)
        self.assertEqual(pair["repeated_pair_key_count"], 4)
        self.assertEqual(pair["rows_beyond_first_per_pair_key_count"], 4)
        self.assertEqual(pair["rows_with_repeated_pair_key_count"], 8)
        self.assertEqual(pair["maximum_rows_per_pair_key"], 2)
        self.assertEqual(pair["nonblank_pair_key_coverage_fraction"], 1.0)
        for identifier in ("PRIVATE_SAMPLE", "PRIVATE_SUBJECT", "PRIVATE_DONOR"):
            self.assertNotIn(identifier, serialized)
        self.assertNotIn("TemporaryDirectory", serialized)
        self.assertEqual(
            report["content_address"],
            content_hash(
                {key: value for key, value in report.items() if key != "content_address"},
                prefix="geo-count-metadata",
            ),
        )

    def test_metadata_source_hash_and_pair_missingness_are_recorded(self) -> None:
        payload = _gzip_csv(
            [
                ["sample", "subject", "condition"],
                ["S-1", "P-1", "Tumor"],
                ["S-2", "", "Normal"],
                ["S-3", "   ", "Tumor"],
            ]
        )
        report = _build_report(
            payload,
            sample_key_column="sample",
            pair_key_column="subject",
        )

        self.assertEqual(
            report["source"]["source_sha256"],
            f"sha256:{hashlib.sha256(payload).hexdigest()}",
        )
        self.assertEqual(report["summary"]["pair_key"]["blank_pair_key_row_count"], 2)
        self.assertEqual(
            report["summary"]["pair_key"]["nonblank_pair_key_coverage_fraction"],
            1 / 3,
        )
        self.assertEqual(report["columns"][2]["blank_value_count"], 0)
        self.assertEqual(report["columns"][2]["whitespace_only_value_count"], 0)

    def test_casefolded_categories_and_unroundtrippable_whitespace_are_explicit(self) -> None:
        payload = _gzip_csv(
            [
                ["sample", "condition"],
                ["S-1", "Tumor"],
                ["S-2", "tumor"],
                ["S-3", " Tumor"],
                ["S-4", "Normal "],
            ]
        )
        report = _build_report(payload, sample_key_column="sample", pair_key_column=None)
        values = {item["value"]: item for item in report["columns"][1]["values"]}

        self.assertEqual(values["Tumor"]["sample_count"], 2)
        self.assertTrue(values["Tumor"]["filter_value_round_trippable"])
        self.assertFalse(values[" Tumor"]["filter_value_round_trippable"])
        self.assertFalse(values["Normal "]["filter_value_round_trippable"])
        self.assertIsNone(report["summary"]["pair_key"])

    def test_high_cardinality_category_values_are_suppressed_with_a_lower_bound(self) -> None:
        payload = _gzip_csv(
            [["sample", "group"]]
            + [[f"S-{index}", f"label-{index}"] for index in range(40)]
        )
        report = _build_report(payload, sample_key_column="sample", pair_key_column=None)
        group = report["columns"][1]

        self.assertEqual(group["distinct_value_count"], 26)
        self.assertTrue(group["distinct_value_count_is_lower_bound"])
        self.assertEqual(group["values"], [])
        self.assertEqual(group["values_suppression_reason"], "category_limit_exceeded")

    def test_non_roundtrippable_field_and_long_category_are_flagged(self) -> None:
        long_value = "x" * 1_100
        payload = _gzip_csv(
            [["sample", " condition "], ["S-1", long_value], ["S-2", "Normal"]]
        )
        report = _build_report(payload, sample_key_column="sample", pair_key_column=None)
        condition = report["columns"][1]
        long_category = next(item for item in condition["values"] if item["value"].startswith("x"))

        self.assertFalse(condition["filter_field_round_trippable"])
        self.assertTrue(long_category["value_truncated"])
        self.assertFalse(long_category["filter_value_round_trippable"])
        self.assertEqual(len(long_category["value"]), 1_024)

    def test_duplicate_sample_keys_and_casefold_duplicate_headers_fail_closed(self) -> None:
        duplicate_keys = _gzip_csv(
            [["sample", "condition"], ["S-1", "Tumor"], ["S-1", "Normal"]]
        )
        duplicate_headers = _gzip_csv(
            [["sample", "Condition", "condition"], ["S-1", "Tumor", "Normal"]]
        )

        with self.assertRaisesRegex(ValidationError, "duplicate sample keys"):
            _build_report(duplicate_keys, sample_key_column="sample", pair_key_column=None)
        with self.assertRaisesRegex(ValidationError, "duplicate columns"):
            _build_report(duplicate_headers, sample_key_column="sample", pair_key_column=None)

    def test_pair_column_must_exist_and_local_path_is_not_revealed(self) -> None:
        with self.assertRaisesRegex(ValidationError, "pair-key column is absent"):
            _build_report(pair_key_column="missing")

    def test_remote_metadata_uses_only_the_canonical_geo_supplementary_url(self) -> None:
        file_name = "GSE141945_RNAseq.metadata.csv.gz"
        url = geo_series_supplementary_url("GSE141945", file_name)
        response = SimpleNamespace(status=200, url=url, body=_metadata_payload())

        with patch(
            "glio_noncode.geo_expression.UrllibTransport.request", return_value=response
        ) as request:
            report = build_geo_count_metadata_report(
                "GSE141945",
                sample_key_column="",
                pair_key_column="Patient",
                metadata_file_name=file_name,
            )

        request.assert_called_once()
        self.assertEqual(request.call_args.args[1], url)
        self.assertEqual(report["source"]["retrieval"], "https")
        self.assertEqual(report["source"]["response_url"], url)

    def test_cli_writes_report_and_dispatch_index_exposes_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.csv.gz"
            path.write_bytes(_metadata_payload())
            output = io.StringIO()
            with redirect_stdout(output):
                status = count_metadata_main(
                    [
                        "GSE141945",
                        "--sample-key-column",
                        "",
                        "--pair-key-column",
                        "Patient",
                        "--metadata-file",
                        str(path),
                    ]
                )

        self.assertEqual(status, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["status"], "completed")
        self.assertNotIn(str(Path(directory)), output.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli_main(["commands", "show", "geo-count-metadata"]), 0)
        with patch("glio_noncode._cli_geo_count_metadata.main", return_value=19):
            self.assertEqual(cli_main(["geo-count-metadata", "GSE141945"]), 19)


if __name__ == "__main__":
    unittest.main()

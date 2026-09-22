from __future__ import annotations

import csv
import gzip
import io
import json
import tempfile
import unittest
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from glio_noncode._cli_geo_count_contrast import main as paired_count_main
from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.geo_expression import (
    _paired_sign_test,
    _paired_signed_rank_test,
    build_geo_count_contrast_report,
    geo_series_supplementary_url,
)

PAIR_COUNT = 4
SAMPLE_IDS = tuple(
    sample_id
    for pair_index in range(PAIR_COUNT)
    for sample_id in (f"PRIVATE_TUMOR_{pair_index}", f"PRIVATE_ORGANOID_{pair_index}")
)
PAIR_IDS = tuple(f"PRIVATE_SUBJECT_{index}" for index in range(PAIR_COUNT))
CASE_COUNTS = (800, 900, 700, 1_000)
REFERENCE_COUNTS = (80, 90, 70, 100)


def _gzip_csv(rows: list[list[str]]) -> bytes:
    text = io.StringIO(newline="")
    writer = csv.writer(text, lineterminator="\n")
    writer.writerows(rows)
    return gzip.compress(text.getvalue().encode("utf-8"), mtime=0)


def _count_payload() -> bytes:
    counts_by_sample: dict[str, int] = {}
    background_by_sample: dict[str, int] = {}
    for pair_index in range(PAIR_COUNT):
        case_id, reference_id = SAMPLE_IDS[pair_index * 2 : pair_index * 2 + 2]
        case_count = CASE_COUNTS[pair_index]
        reference_count = REFERENCE_COUNTS[pair_index]
        counts_by_sample[case_id] = case_count
        counts_by_sample[reference_id] = reference_count
        background_by_sample[case_id] = 10_000 - case_count - 120
        background_by_sample[reference_id] = 10_000 - reference_count - 120
    rows = [
        ["", *SAMPLE_IDS],
        ["SIGNAL", *(str(counts_by_sample[key]) for key in SAMPLE_IDS)],
        ["HOUSEKEEPING", *(str(background_by_sample[key]) for key in SAMPLE_IDS)],
        ["STABLE", *(["100"] * len(SAMPLE_IDS))],
        ["DUPLICATE", *(["10"] * len(SAMPLE_IDS))],
        ["DUPLICATE", *(["10"] * len(SAMPLE_IDS))],
    ]
    return _gzip_csv(rows)


def _metadata_payload(
    *,
    unmatched_case: bool = False,
    duplicate_case_pair: bool = False,
) -> bytes:
    rows = [["", "Patient", "Timepoint", "Cohort"]]
    # Reverse row order to prove that the join uses sample keys, not row position.
    for pair_index in reversed(range(PAIR_COUNT)):
        case_id, reference_id = SAMPLE_IDS[pair_index * 2 : pair_index * 2 + 2]
        pair_id = f"PRIVATE_SUBJECT_{pair_index}"
        if unmatched_case and pair_index == 0:
            pair_id = "PRIVATE_UNMATCHED_SUBJECT"
        if duplicate_case_pair and pair_index == 0:
            pair_id = f"PRIVATE_SUBJECT_{PAIR_COUNT - 1}"
        cohort = "StudyA" if pair_index < 3 else "StudyB"
        rows.append([case_id, pair_id, "Tumor", cohort])
        rows.append([reference_id, f"PRIVATE_SUBJECT_{pair_index}", "1wk", cohort])
    return _gzip_csv(rows)


def _write_files(root: Path, **metadata_options: bool) -> tuple[Path, Path]:
    counts_path = root / "counts.csv.gz"
    metadata_path = root / "metadata.csv.gz"
    counts_path.write_bytes(_count_payload())
    metadata_path.write_bytes(_metadata_payload(**metadata_options))
    return counts_path, metadata_path


def _build_report(**options: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "case_filters": (("Timepoint", "Tumor"),),
        "reference_filters": (("Timepoint", "1wk"),),
        "sample_key_column": "",
        "pair_key_column": "Patient",
    }
    return build_geo_count_contrast_report("GSE141945", **(defaults | options))


class GeoCountContrastTests(unittest.TestCase):
    def test_local_paired_contrast_is_keyed_sample_free_and_multiple_tested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts_path, metadata_path = _write_files(root)
            report = _build_report(counts_file=counts_path, metadata_file=metadata_path)

        serialized = json.dumps(report, sort_keys=True)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["matrix"]["feature_row_count"], 5)
        self.assertEqual(report["matrix"]["duplicate_feature_id_count_excluded"], 1)
        self.assertEqual(report["matrix"]["duplicate_feature_row_count_excluded"], 2)
        self.assertEqual(report["matrix"]["uniquely_identified_feature_count_tested"], 3)
        self.assertEqual(report["comparison"]["matched_pair_count"], PAIR_COUNT)
        self.assertEqual(report["comparison"]["case_sample_count_unmatched"], 0)
        self.assertEqual(report["summary"]["tested_feature_count"], 3)
        rows = {row["feature_id"]: row for row in report["results"]}
        self.assertEqual(set(rows), {"SIGNAL", "HOUSEKEEPING", "STABLE"})
        self.assertGreater(rows["SIGNAL"]["mean_paired_difference_log2_cpm"], 0.0)
        self.assertEqual(rows["SIGNAL"]["effect_direction"], "case_higher")
        self.assertEqual(rows["SIGNAL"]["test_method"], "exact_paired_signed_rank")
        self.assertEqual(rows["SIGNAL"]["p_value"], 0.125)
        self.assertEqual(rows["SIGNAL"]["case_higher_pair_count"], PAIR_COUNT)
        self.assertEqual(rows["SIGNAL"]["case_lower_pair_count"], 0)
        self.assertEqual(rows["SIGNAL"]["tied_pair_count"], 0)
        self.assertEqual(rows["SIGNAL"]["sign_test_p_value"], 0.125)
        self.assertEqual(
            rows["SIGNAL"]["case_higher_pair_count"]
            + rows["SIGNAL"]["case_lower_pair_count"]
            + rows["SIGNAL"]["tied_pair_count"],
            rows["SIGNAL"]["paired_sample_count"],
        )
        self.assertGreaterEqual(rows["SIGNAL"]["sign_test_q_value"], 0.0)
        self.assertLessEqual(rows["SIGNAL"]["sign_test_q_value"], 1.0)
        self.assertEqual(rows["STABLE"]["p_value"], 1.0)
        self.assertEqual(rows["STABLE"]["sign_test_p_value"], 1.0)
        self.assertEqual(rows["STABLE"]["tied_pair_count"], PAIR_COUNT)
        self.assertEqual(
            report["summary"]["sign_test_method_counts"], {"exact_paired_sign_test": 3}
        )
        self.assertFalse(rows["SIGNAL"]["fdr_significant"])
        self.assertFalse(rows["SIGNAL"]["sign_test_fdr_significant"])
        for private_key in (*SAMPLE_IDS, *PAIR_IDS, "PRIVATE_UNMATCHED_SUBJECT"):
            self.assertNotIn(private_key, serialized)
        self.assertNotIn(str(root), serialized)
        self.assertTrue(report["content_address"].startswith("geo-paired-count-contrast:"))

    def test_exact_signed_rank_uses_ties_zeros_and_both_tails(self) -> None:
        effect, p_value, method, nonzero_pairs = _paired_signed_rank_test((1, 2, 3, 4))
        self.assertEqual(effect, 1.0)
        self.assertEqual(p_value, 0.125)
        self.assertEqual(method, "exact_paired_signed_rank")
        self.assertEqual(nonzero_pairs, 4)

        tied_effect, tied_p, _, tied_nonzero = _paired_signed_rank_test((1, -1, 1, -1, 0))
        self.assertEqual(tied_effect, 0.0)
        self.assertEqual(tied_p, 1.0)
        self.assertEqual(tied_nonzero, 4)

        zero_effect, zero_p, _, zero_nonzero = _paired_signed_rank_test((0, 0, 0))
        self.assertEqual((zero_effect, zero_p, zero_nonzero), (0.0, 1.0, 0))

        all_positive_17 = _paired_signed_rank_test(tuple(range(1, 18)))
        self.assertEqual(all_positive_17[1], 1 / 65_536)

    def test_paired_sign_test_excludes_ties_and_reports_direction_counts(self) -> None:
        positive, negative, tied, p_value, method = _paired_sign_test((1, 2, 3, 4, 0))
        self.assertEqual((positive, negative, tied), (4, 0, 1))
        self.assertEqual(p_value, 0.125)
        self.assertEqual(method, "exact_paired_sign_test")

        balanced = _paired_sign_test((1, -1, 2, -2, 0))
        self.assertEqual(balanced[:3], (2, 2, 1))
        self.assertEqual(balanced[3], 1.0)

        all_ties = _paired_sign_test((0, 0, 0))
        self.assertEqual(all_ties[:4], (0, 0, 3, 1.0))

    def test_exact_paired_sign_test_matches_exhaustive_sign_assignments(self) -> None:
        for pair_count in range(1, 9):
            assignments = tuple(product((-1.0, 1.0), repeat=pair_count))
            for differences in assignments:
                observed_positive_count = sum(value > 0.0 for value in differences)
                observed_distance = abs(observed_positive_count - pair_count / 2.0)
                expected = sum(
                    abs(sum(value > 0.0 for value in assignment) - pair_count / 2.0)
                    >= observed_distance
                    for assignment in assignments
                ) / (2**pair_count)
                self.assertAlmostEqual(_paired_sign_test(differences)[3], expected)

    def test_paired_sign_test_uses_bounded_normal_approximation(self) -> None:
        result = _paired_sign_test((1.0,) * 129)
        self.assertEqual(result[:3], (129, 0, 0))
        self.assertEqual(result[4], "normal_approximation_paired_sign_test")
        self.assertGreaterEqual(result[3], 0.0)
        self.assertLessEqual(result[3], 1.0)

    def test_paired_sign_test_rejects_non_finite_differences(self) -> None:
        with self.assertRaisesRegex(ValidationError, "must be finite"):
            _paired_sign_test((1.0, float("nan")))

    def test_exact_signed_rank_matches_exhaustive_sign_assignments_with_ties(self) -> None:
        for differences in (
            (1.0, -2.0, 3.0, -4.0),
            (1.0, -1.0, 2.0, -2.0, 0.0),
            (0.5, -2.5, 2.5, -1.5, 1.5),
        ):
            nonzero = tuple(value for value in differences if value != 0.0)
            ordered = sorted(abs(value) for value in nonzero)
            weights = [0] * len(ordered)
            start = 0
            while start < len(ordered):
                end = start + 1
                while end < len(ordered) and ordered[end] == ordered[start]:
                    end += 1
                weights[start:end] = [start + end + 1] * (end - start)
                start = end
            observed = sum(
                weight
                for weight, value in zip(weights, sorted(nonzero, key=abs), strict=True)
                if value > 0
            )
            center = sum(weights) / 2.0
            distance = abs(observed - center)
            extreme = sum(
                abs(
                    sum(weight for weight, positive in zip(weights, signs, strict=True) if positive)
                    - center
                )
                >= distance
                for signs in product((False, True), repeat=len(weights))
            )
            expected_p = extreme / (2 ** len(weights))

            actual = _paired_signed_rank_test(differences)
            self.assertAlmostEqual(actual[1], expected_p)

    def test_large_paired_group_uses_labeled_normal_approximation(self) -> None:
        effect, p_value, method, nonzero_pairs = _paired_signed_rank_test(tuple(range(1, 35)))
        self.assertEqual(effect, 1.0)
        self.assertEqual(method, "normal_approximation_paired_signed_rank")
        self.assertEqual(nonzero_pairs, 34)
        self.assertGreaterEqual(p_value, 0.0)
        self.assertLessEqual(p_value, 1.0)

    def test_filter_order_does_not_change_the_paired_report_address(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory))
            shared = {"counts_file": counts_path, "metadata_file": metadata_path}
            first = _build_report(
                **shared,
                case_filters=(("Timepoint", "Tumor"), ("Cohort", "StudyA")),
                reference_filters=(("Timepoint", "1wk"), ("Cohort", "StudyA")),
            )
            reordered = _build_report(
                **shared,
                case_filters=(("Cohort", "StudyA"), ("Timepoint", "Tumor")),
                reference_filters=(("Cohort", "StudyA"), ("Timepoint", "1wk")),
            )
        self.assertEqual(first["comparison"]["matched_pair_count"], 3)
        self.assertEqual(first["content_address"], reordered["content_address"])

    def test_by_adjustment_is_conservative_relative_to_bh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory))
            shared = {"counts_file": counts_path, "metadata_file": metadata_path, "top": 3}
            bh = _build_report(**shared, fdr_method="bh")
            by = _build_report(**shared, fdr_method="by")
        bh_q = {row["feature_id"]: row["q_value"] for row in bh["results"]}
        by_q = {row["feature_id"]: row["q_value"] for row in by["results"]}
        for feature_id, q_value in bh_q.items():
            self.assertGreaterEqual(by_q[feature_id], q_value)

    def test_unmatched_pairs_are_excluded_and_reported_as_counts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory), unmatched_case=True)
            report = _build_report(counts_file=counts_path, metadata_file=metadata_path)
        self.assertEqual(report["comparison"]["matched_pair_count"], 3)
        self.assertEqual(report["comparison"]["case_sample_count_unmatched"], 1)
        self.assertEqual(report["comparison"]["reference_sample_count_unmatched"], 1)

    def test_duplicate_pair_key_within_one_group_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory), duplicate_case_pair=True)
            with self.assertRaisesRegex(ValidationError, "more than one sample per pair"):
                _build_report(counts_file=counts_path, metadata_file=metadata_path)

    def test_fewer_than_three_matched_pairs_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory), unmatched_case=True)
            with self.assertRaisesRegex(ValidationError, "at least three complete pairs"):
                _build_report(
                    counts_file=counts_path,
                    metadata_file=metadata_path,
                    case_filters=(("Timepoint", "Tumor"), ("Cohort", "StudyB")),
                    reference_filters=(("Timepoint", "1wk"), ("Cohort", "StudyB")),
                )

    def test_overlapping_groups_and_pair_key_as_group_filter_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory))
            common = {"counts_file": counts_path, "metadata_file": metadata_path}
            with self.assertRaisesRegex(ValidationError, "overlapping samples"):
                _build_report(
                    **common,
                    case_filters=(("Timepoint", "Tumor"),),
                    reference_filters=(("Timepoint", "Tumor"),),
                )
            with self.assertRaisesRegex(ValidationError, "cannot also define"):
                _build_report(**common, case_filters=(("Patient", "PRIVATE_SUBJECT_0"),))

    def test_remote_retrieval_uses_canonical_geo_paths(self) -> None:
        count_name = "paired-counts.csv.gz"
        metadata_name = "paired-metadata.csv.gz"
        count_url = geo_series_supplementary_url("GSE141945", count_name)
        metadata_url = geo_series_supplementary_url("GSE141945", metadata_name)
        responses = (
            SimpleNamespace(status=200, url=count_url, body=_count_payload()),
            SimpleNamespace(status=200, url=metadata_url, body=_metadata_payload()),
        )
        with patch(
            "glio_noncode.geo_expression.UrllibTransport.request", side_effect=responses
        ) as request:
            report = _build_report(
                counts_file_name=count_name,
                metadata_file_name=metadata_name,
            )
        self.assertEqual(request.call_count, 2)
        self.assertEqual(report["source"]["retrieval"], "https")
        self.assertEqual(report["source"]["count_matrix"]["response_url"], count_url)
        self.assertEqual(report["source"]["sample_metadata"]["response_url"], metadata_url)

    def test_cli_entrypoint_and_static_discovery_use_the_same_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts_path, metadata_path = _write_files(root)
            output = root / "contrast.json"
            status = paired_count_main(
                [
                    "GSE141945",
                    "--case-filter",
                    "Timepoint=Tumor",
                    "--reference-filter",
                    "Timepoint=1wk",
                    "--sample-key-column",
                    "",
                    "--pair-key-column",
                    "Patient",
                    "--counts-file",
                    str(counts_path),
                    "--metadata-file",
                    str(metadata_path),
                    "--output",
                    str(output),
                ]
            )
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(status, 0)
        self.assertEqual(report["summary"]["tested_feature_count"], 3)

        output_lines: list[str] = []

        class Writer:
            def write(self, value: str) -> int:
                output_lines.append(value)
                return len(value)

        with patch("sys.stdout", Writer()):
            self.assertEqual(cli_main(["commands", "show", "geo-count-contrast"]), 0)
        self.assertIn("paired groups", "".join(output_lines))

        with patch("glio_noncode._cli_geo_count_contrast.main", return_value=19) as dispatch:
            self.assertEqual(cli_main(["geo-count-contrast", "GSE141945"]), 19)
        dispatch.assert_called_once_with(["GSE141945"])


if __name__ == "__main__":
    unittest.main()

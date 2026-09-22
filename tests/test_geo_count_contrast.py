from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import tempfile
import unittest
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from glio_noncode._cli_geo_count_contrast import (
    design_main as count_design_main,
)
from glio_noncode._cli_geo_count_contrast import (
    main as paired_count_main,
)
from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.geo_expression import (
    _paired_leave_one_out_median_sensitivity,
    _paired_median_sign_interval,
    _paired_sign_test,
    _paired_signed_rank_test,
    build_geo_count_contrast_report,
    geo_series_supplementary_url,
)
from glio_noncode.geo_metadata import build_geo_count_contrast_design_report

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


def _count_payload(
    *,
    include_direction_discordance: bool = False,
    include_date_like_feature: bool = False,
) -> bytes:
    counts_by_sample: dict[str, int] = {}
    influential_by_sample: dict[str, int] = {}
    discordant_by_sample: dict[str, int] = {}
    background_by_sample: dict[str, int] = {}
    for pair_index in range(PAIR_COUNT):
        case_id, reference_id = SAMPLE_IDS[pair_index * 2 : pair_index * 2 + 2]
        case_count = CASE_COUNTS[pair_index]
        reference_count = REFERENCE_COUNTS[pair_index]
        influential_case_count = (1, 2, 200, 400)[pair_index]
        influential_reference_count = (512, 512, 100, 100)[pair_index]
        discordant_case_count = (5, 5, 5, 100)[pair_index] if include_direction_discordance else 0
        discordant_reference_count = 10 if include_direction_discordance else 0
        counts_by_sample[case_id] = case_count
        counts_by_sample[reference_id] = reference_count
        influential_by_sample[case_id] = influential_case_count
        influential_by_sample[reference_id] = influential_reference_count
        discordant_by_sample[case_id] = discordant_case_count
        discordant_by_sample[reference_id] = discordant_reference_count
        background_by_sample[case_id] = (
            10_000 - case_count - influential_case_count - discordant_case_count - 120
        )
        background_by_sample[reference_id] = (
            10_000
            - reference_count
            - influential_reference_count
            - discordant_reference_count
            - 120
        )
    rows = [
        ["", *SAMPLE_IDS],
        ["SIGNAL", *(str(counts_by_sample[key]) for key in SAMPLE_IDS)],
        ["INFLUENTIAL", *(str(influential_by_sample[key]) for key in SAMPLE_IDS)],
        *(
            [["SKEWED_DIRECTION", *(str(discordant_by_sample[key]) for key in SAMPLE_IDS)]]
            if include_direction_discordance
            else []
        ),
        ["HOUSEKEEPING", *(str(background_by_sample[key]) for key in SAMPLE_IDS)],
        ["STABLE", *(["100"] * len(SAMPLE_IDS))],
        *(
            [["2-Sep", *(["20"] * len(SAMPLE_IDS))]]
            if include_date_like_feature
            else []
        ),
        ["DUPLICATE", *(["10"] * len(SAMPLE_IDS))],
        ["DUPLICATE", *(["10"] * len(SAMPLE_IDS))],
    ]
    return _gzip_csv(rows)


def _metadata_payload(
    *,
    unmatched_case: bool = False,
    duplicate_case_pair: bool = False,
    blank_case_pair: bool = False,
    mismatch_sample_key: bool = False,
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
        if blank_case_pair and pair_index == 0:
            pair_id = ""
        cohort = "StudyA" if pair_index < 3 else "StudyB"
        metadata_case_id = (
            "PRIVATE_UNKNOWN_SAMPLE" if mismatch_sample_key and pair_index == 0 else case_id
        )
        rows.append([metadata_case_id, pair_id, "Tumor", cohort])
        rows.append([reference_id, f"PRIVATE_SUBJECT_{pair_index}", "1wk", cohort])
    return _gzip_csv(rows)


def _write_files(
    root: Path,
    *,
    include_direction_discordance: bool = False,
    include_date_like_feature: bool = False,
    **metadata_options: bool,
) -> tuple[Path, Path]:
    counts_path = root / "counts.csv.gz"
    metadata_path = root / "metadata.csv.gz"
    counts_path.write_bytes(
        _count_payload(
            include_direction_discordance=include_direction_discordance,
            include_date_like_feature=include_date_like_feature,
        )
    )
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


def _build_design_report(**options: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "case_filters": (("Timepoint", "Tumor"),),
        "reference_filters": (("Timepoint", "1wk"),),
        "sample_key_column": "",
        "pair_key_column": "Patient",
    }
    return build_geo_count_contrast_design_report("GSE141945", **(defaults | options))


class GeoCountContrastTests(unittest.TestCase):
    def test_count_design_preflight_validates_join_without_statistics_or_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory))
            report = _build_design_report(counts_file=counts_path, metadata_file=metadata_path)

        serialized = json.dumps(report, sort_keys=True)
        self.assertEqual(report["status"], "completed")
        self.assertTrue(report["design"]["estimable"])
        self.assertEqual(report["design"]["complete_pair_count"], PAIR_COUNT)
        self.assertEqual(report["matrix"]["sample_count"], len(SAMPLE_IDS))
        self.assertEqual(report["matrix"]["feature_row_count"], 6)
        self.assertEqual(report["matrix"]["uniquely_labeled_feature_count"], 4)
        self.assertEqual(report["comparison"]["case_sample_count_selected"], PAIR_COUNT)
        self.assertEqual(report["comparison"]["reference_sample_count_selected"], PAIR_COUNT)
        self.assertEqual(report["comparison"]["case_sample_count_unmatched"], 0)
        self.assertEqual(report["comparison"]["reference_sample_count_unmatched"], 0)
        self.assertFalse(
            report["matrix"]["feature_label_review"]["manual_annotation_review_recommended"]
        )
        self.assertFalse(report["analysis"]["effect_sizes_calculated"])
        self.assertFalse(report["analysis"]["p_values_calculated"])
        self.assertNotIn("PRIVATE_TUMOR_", serialized)
        self.assertNotIn("PRIVATE_SUBJECT_", serialized)

    def test_date_like_feature_labels_are_flagged_without_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(
                Path(directory), include_date_like_feature=True
            )
            options = {"counts_file": counts_path, "metadata_file": metadata_path}
            design = _build_design_report(**options)
            contrast = _build_report(**options, fdr_threshold=1.0)

        expected_review = {
            "possible_date_like_source_label_count": 1,
            "reported_possible_date_like_source_labels": ["2-Sep"],
            "omitted_possible_date_like_source_label_count": 0,
            "automatic_normalization_performed": False,
            "manual_annotation_review_recommended": True,
        }
        self.assertEqual(design["matrix"]["feature_label_review"], expected_review)
        self.assertEqual(contrast["matrix"]["feature_label_review"], expected_review)
        self.assertEqual(contrast["matrix"]["feature_row_count"], 7)
        date_like_result = next(
            result for result in contrast["results"] if result["feature_id"] == "2-Sep"
        )
        self.assertEqual(date_like_result["feature_label_review"], {
            "possible_date_like_source_label": True,
            "manual_annotation_review_recommended": True,
            "source_label_preserved": True,
            "automatic_normalization_performed": False,
        })
        self.assertEqual(contrast["summary"]["reported_date_like_feature_label_count"], 1)
        ordinary_result = next(
            result for result in contrast["results"] if result["feature_id"] == "SIGNAL"
        )
        self.assertFalse(ordinary_result["feature_label_review"]["possible_date_like_source_label"])
        self.assertEqual(ordinary_result["feature_label_review"]["source_label_preserved"], True)

    def test_tracked_feature_is_retained_outside_ranked_result_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(
                Path(directory), include_date_like_feature=True
            )
            report = _build_report(
                counts_file=counts_path,
                metadata_file=metadata_path,
                top=1,
                track_feature_ids=("2-Sep",),
                fdr_threshold=1.0,
            )

        self.assertEqual(report["summary"]["ranked_feature_count"], 1)
        self.assertEqual(report["summary"]["additional_tracked_feature_count"], 1)
        self.assertEqual(report["summary"]["reported_feature_count"], 2)
        self.assertEqual(report["comparison"]["tracked_feature_ids"], ["2-Sep"])
        self.assertEqual(
            {row["feature_id"] for row in report["results"]},
            {report["results"][0]["feature_id"], "2-Sep"},
        )
        self.assertEqual(
            report["summary"]["reported_date_like_feature_label_count"], 1
        )

    def test_tracked_feature_ids_require_unique_present_source_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(
                Path(directory), include_date_like_feature=True
            )
            options = {"counts_file": counts_path, "metadata_file": metadata_path}
            with self.assertRaisesRegex(ValidationError, "must be unique"):
                _build_report(**options, track_feature_ids=("2-Sep", "2-Sep"))
            with self.assertRaisesRegex(ValidationError, "not present"):
                _build_report(**options, track_feature_ids=("MISSING_FEATURE",))

    def test_explicit_feature_annotation_preserves_statistics_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts_path, metadata_path = _write_files(
                root, include_date_like_feature=True
            )
            annotation_path = root / "annotations.csv"
            annotation_bytes = (
                b"source_feature_id,curated_feature_id\n"
                b"2-Sep,SEPT2\n"
                b"SIGNAL,CURATED_SIGNAL\n"
                b"STABLE,CURATED_SIGNAL\n"
            )
            annotation_path.write_bytes(annotation_bytes)
            options = {
                "counts_file": counts_path,
                "metadata_file": metadata_path,
                "fdr_threshold": 1.0,
            }
            unannotated = _build_report(**options)
            curated = _build_report(**options, feature_annotation_file=annotation_path)

        self.assertEqual(
            curated["source"]["feature_annotation_map"],
            {
                "status": "provided",
                "format": "csv",
                "mapping_entry_count": 3,
                "source_sha256": f"sha256:{hashlib.sha256(annotation_bytes).hexdigest()}",
            },
        )
        self.assertNotEqual(
            curated["comparison"]["source_version"],
            unannotated["comparison"]["source_version"],
        )
        before = {row["feature_id"]: row for row in unannotated["results"]}
        after = {row["feature_id"]: row for row in curated["results"]}
        self.assertEqual(set(before), set(after))
        for feature_id in before:
            for statistic in (
                "p_value",
                "q_value",
                "sign_test_p_value",
                "sign_test_q_value",
                "median_paired_difference_log2_cpm",
            ):
                self.assertEqual(after[feature_id][statistic], before[feature_id][statistic])
        self.assertEqual(after["2-Sep"]["feature_id"], "2-Sep")
        self.assertEqual(
            after["2-Sep"]["feature_annotation"],
            {"status": "mapped", "curated_feature_id": "SEPT2"},
        )
        self.assertTrue(after["2-Sep"]["feature_label_review"]["possible_date_like_source_label"])
        self.assertEqual(
            after["SIGNAL"]["feature_annotation"],
            {"status": "mapped", "curated_feature_id": "CURATED_SIGNAL"},
        )
        self.assertEqual(
            after["STABLE"]["feature_annotation"],
            {"status": "mapped", "curated_feature_id": "CURATED_SIGNAL"},
        )
        self.assertIn("SIGNAL", after)
        self.assertIn("STABLE", after)
        self.assertEqual(curated["summary"]["reported_curated_feature_count"], 3)

    def test_feature_annotation_map_rejects_ambiguous_source_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts_path, metadata_path = _write_files(root)
            annotation_path = root / "annotations.csv"
            invalid_maps = (
                (
                    "duplicate source mapping",
                    "source_feature_id,curated_feature_id\nSIGNAL,A\nSIGNAL,B\n",
                    "repeats a source identifier",
                ),
                (
                    "missing source row",
                    "source_feature_id,curated_feature_id\nNOT_IN_MATRIX,A\n",
                    "missing=1; duplicated=0",
                ),
                (
                    "duplicated matrix row",
                    "source_feature_id,curated_feature_id\nDUPLICATE,A\n",
                    "missing=0; duplicated=1",
                ),
            )
            for label, contents, expected_error in invalid_maps:
                with self.subTest(label=label):
                    annotation_path.write_text(contents, encoding="utf-8")
                    with self.assertRaisesRegex(ValidationError, expected_error):
                        _build_report(
                            counts_file=counts_path,
                            metadata_file=metadata_path,
                            feature_annotation_file=annotation_path,
                        )

    def test_count_design_reports_incomplete_but_estimable_pairs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(
                Path(directory), unmatched_case=True
            )
            report = _build_design_report(counts_file=counts_path, metadata_file=metadata_path)

        self.assertEqual(report["design"]["state"], "estimable")
        self.assertEqual(report["comparison"]["matched_pair_count"], PAIR_COUNT - 1)
        self.assertEqual(report["comparison"]["case_sample_count_unmatched"], 1)
        self.assertEqual(report["comparison"]["reference_sample_count_unmatched"], 1)

    def test_count_design_fails_estimability_for_duplicate_pair_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(
                Path(directory), duplicate_case_pair=True
            )
            report = _build_design_report(counts_file=counts_path, metadata_file=metadata_path)

        self.assertEqual(report["design"]["state"], "not_estimable")
        self.assertIn(
            "a selected group has more than one sample for a pair key",
            report["design"]["reasons"],
        )
        self.assertEqual(report["comparison"]["case_duplicate_pair_key_count"], 1)

    def test_count_design_fails_estimability_for_blank_pair_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(
                Path(directory), blank_case_pair=True
            )
            report = _build_design_report(counts_file=counts_path, metadata_file=metadata_path)

        self.assertEqual(report["design"]["state"], "not_estimable")
        self.assertEqual(report["comparison"]["case_blank_pair_key_sample_count"], 1)
        self.assertIn(
            "one or more selected samples have a blank pair key",
            report["design"]["reasons"],
        )

    def test_count_design_rejects_non_exact_sample_key_join(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(
                Path(directory), mismatch_sample_key=True
            )
            report = _build_design_report(counts_file=counts_path, metadata_file=metadata_path)

        serialized = json.dumps(report, sort_keys=True)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["design"]["state"], "not_estimable")
        self.assertIn(
            "count matrix and metadata sample keys do not match exactly",
            report["design"]["reasons"],
        )
        self.assertEqual(
            report["comparison"]["sample_key_join"],
            {
                "exact_match": False,
                "count_matrix_sample_key_count": len(SAMPLE_IDS),
                "metadata_sample_key_count": len(SAMPLE_IDS),
                "joined_sample_key_count": len(SAMPLE_IDS) - 1,
                "count_matrix_sample_key_without_metadata_count": 1,
                "metadata_sample_key_without_count_matrix_count": 1,
                "sample_key_values_emitted": False,
            },
        )
        self.assertNotIn("PRIVATE_UNKNOWN_SAMPLE", serialized)

    def test_count_design_reports_overlapping_group_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory))
            report = _build_design_report(
                counts_file=counts_path,
                metadata_file=metadata_path,
                case_filters=(("Timepoint", "Tumor"),),
                reference_filters=(("Timepoint", "Tumor"),),
            )

        self.assertEqual(report["design"]["state"], "not_estimable")
        self.assertEqual(report["comparison"]["overlap_sample_count"], PAIR_COUNT)
        self.assertIn(
            "case and reference filters select overlapping samples",
            report["design"]["reasons"],
        )

    def test_count_design_cli_runs_locally_and_dispatches_from_shell(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts_path, metadata_path = _write_files(root)
            output = root / "design.json"
            status = count_design_main(
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
        self.assertEqual(report["schema"], "glio-noncode.geo-count-contrast-design.v1")
        self.assertTrue(report["summary"]["design_estimable"])
        with patch("glio_noncode._cli_geo_count_contrast.design_main", return_value=23) as dispatch:
            self.assertEqual(cli_main(["geo-count-design", "GSE141945"]), 23)
        dispatch.assert_called_once_with(["GSE141945"])

    def test_effect_direction_matches_rank_biserial_and_exposes_mean_median_signs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(
                Path(directory), include_direction_discordance=True
            )
            report = _build_report(
                counts_file=counts_path,
                metadata_file=metadata_path,
                fdr_threshold=1.0,
            )

        row = next(
            result for result in report["results"] if result["feature_id"] == "SKEWED_DIRECTION"
        )
        self.assertGreater(row["mean_paired_difference_log2_cpm"], 0.0)
        self.assertLess(row["median_paired_difference_log2_cpm"], 0.0)
        self.assertLess(row["matched_pairs_rank_biserial_correlation"], 0.0)
        self.assertEqual(row["effect_direction"], "case_higher")
        self.assertEqual(row["mean_effect_direction"], "case_higher")
        self.assertEqual(row["median_effect_direction"], "case_lower")
        self.assertEqual(row["rank_biserial_effect_direction"], "case_lower")
        self.assertEqual(
            report["comparison"]["effect_direction_basis"],
            "sign of mean paired difference (compatibility field)",
        )
        self.assertEqual(
            report["comparison"]["rank_biserial_effect_direction_basis"],
            "sign of matched-pairs rank-biserial correlation",
        )

    def test_tmm_contrast_corrects_a_composition_shift_for_stable_features(self) -> None:
        rows = [["", *SAMPLE_IDS]]
        rows.extend(
            [f"STABLE_{feature_index:02d}", *("100" for _ in SAMPLE_IDS)]
            for feature_index in range(20)
        )
        rows.append(
            [
                "DOMINANT",
                *(
                    "100000" if sample_index % 2 == 0 else "0"
                    for sample_index in range(len(SAMPLE_IDS))
                ),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts_path = root / "counts.csv.gz"
            metadata_path = root / "metadata.csv.gz"
            counts_path.write_bytes(_gzip_csv(rows))
            metadata_path.write_bytes(_metadata_payload())
            options = {"counts_file": counts_path, "metadata_file": metadata_path}
            raw = _build_report(**options, top=100)
            tmm = _build_report(**options, top=100, normalization_method="tmm_log2_cpm")

        self.assertEqual(
            raw["comparison"]["source_version"],
            tmm["comparison"]["source_version"],
        )
        self.assertNotEqual(
            raw["comparison"]["context_key"],
            tmm["comparison"]["context_key"],
        )
        raw_stable = next(row for row in raw["results"] if row["feature_id"] == "STABLE_00")
        tmm_stable = next(row for row in tmm["results"] if row["feature_id"] == "STABLE_00")
        self.assertLess(raw_stable["median_paired_difference_log2_cpm"], -5.0)
        self.assertAlmostEqual(tmm_stable["median_paired_difference_log2_cpm"], 0.0, places=8)
        self.assertEqual(tmm["comparison"]["normalization_details"]["method"], "tmm_log2_cpm")
        self.assertEqual(
            tmm["quality_control"]["case"]["effective_library_size"]["sample_count"],
            PAIR_COUNT,
        )

    def test_local_paired_contrast_is_keyed_sample_free_and_multiple_tested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            counts_path, metadata_path = _write_files(root)
            report = _build_report(counts_file=counts_path, metadata_file=metadata_path)

        serialized = json.dumps(report, sort_keys=True)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["matrix"]["feature_row_count"], 6)
        self.assertEqual(report["matrix"]["duplicate_feature_id_count_excluded"], 1)
        self.assertEqual(report["matrix"]["duplicate_feature_row_count_excluded"], 2)
        self.assertEqual(report["matrix"]["uniquely_identified_feature_count_tested"], 4)
        self.assertEqual(report["comparison"]["matched_pair_count"], PAIR_COUNT)
        self.assertEqual(report["comparison"]["case_sample_count_unmatched"], 0)
        self.assertEqual(report["summary"]["tested_feature_count"], 4)
        quality = report["quality_control"]
        self.assertEqual(quality["case"]["sample_count"], PAIR_COUNT)
        self.assertEqual(
            quality["case"]["library_size"],
            {"sample_count": PAIR_COUNT, "minimum": 10_000, "median": 10_000.0, "maximum": 10_000},
        )
        self.assertEqual(
            quality["case"]["unique_features_detected_by_minimum_count"]["5"],
            {"sample_count": PAIR_COUNT, "minimum": 3, "median": 3.5, "maximum": 4},
        )
        self.assertEqual(
            quality["reference"]["unique_features_detected_by_minimum_count"]["5"]["minimum"],
            4,
        )
        self.assertEqual(quality["paired_library_size_imbalance_fold"]["maximum"], 1.0)
        self.assertFalse(quality["automatic_sample_exclusion"])
        rows = {row["feature_id"]: row for row in report["results"]}
        self.assertEqual(set(rows), {"SIGNAL", "INFLUENTIAL", "HOUSEKEEPING", "STABLE"})
        self.assertGreater(rows["SIGNAL"]["mean_paired_difference_log2_cpm"], 0.0)
        self.assertEqual(rows["SIGNAL"]["effect_direction"], "case_higher")
        self.assertEqual(rows["SIGNAL"]["test_method"], "exact_paired_signed_rank")
        self.assertEqual(rows["SIGNAL"]["p_value"], 0.125)
        self.assertEqual(rows["SIGNAL"]["case_higher_pair_count"], PAIR_COUNT)
        self.assertEqual(rows["SIGNAL"]["case_lower_pair_count"], 0)
        self.assertEqual(rows["SIGNAL"]["tied_pair_count"], 0)
        self.assertEqual(rows["SIGNAL"]["sign_test_p_value"], 0.125)
        interval = rows["SIGNAL"]["median_paired_difference_confidence_interval_log2_cpm"]
        self.assertEqual(interval["status"], "no_finite_interval_at_requested_confidence")
        self.assertIsNone(interval["bounds_log2_cpm"])
        self.assertEqual(interval["maximum_finite_interval_confidence_level"], 0.875)
        self.assertEqual(
            rows["SIGNAL"]["leave_one_pair_out_median_sensitivity"]["direction_counts"],
            {"case_higher": PAIR_COUNT, "case_lower": 0, "tied": 0},
        )
        self.assertTrue(
            rows["SIGNAL"]["leave_one_pair_out_median_sensitivity"]["direction_stable"]
        )
        self.assertFalse(
            rows["INFLUENTIAL"]["leave_one_pair_out_median_sensitivity"]["direction_stable"]
        )
        self.assertEqual(
            rows["INFLUENTIAL"]["leave_one_pair_out_median_sensitivity"]["direction_counts"],
            {"case_higher": 2, "case_lower": 2, "tied": 0},
        )
        self.assertEqual(
            report["summary"]["pair_deletion_sensitivity"]["features_with_direction_change_count"],
            1,
        )
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
            report["summary"]["sign_test_method_counts"], {"exact_paired_sign_test": 4}
        )
        self.assertFalse(rows["SIGNAL"]["fdr_significant"])
        self.assertFalse(rows["SIGNAL"]["sign_test_fdr_significant"])
        for private_key in (*SAMPLE_IDS, *PAIR_IDS, "PRIVATE_UNMATCHED_SUBJECT"):
            self.assertNotIn(private_key, serialized)
        self.assertNotIn(str(root), serialized)
        self.assertTrue(report["content_address"].startswith("geo-paired-count-contrast:"))

    def test_pair_deletion_summary_counts_fdr_significant_sensitivity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            counts_path, metadata_path = _write_files(Path(directory))
            report = _build_report(
                counts_file=counts_path,
                metadata_file=metadata_path,
                fdr_threshold=1.0,
            )
        self.assertEqual(report["summary"]["fdr_significant_feature_count"], 4)
        self.assertEqual(
            report["summary"]["pair_deletion_sensitivity"],
            {
                "feature_count": 4,
                "features_with_direction_change_count": 1,
                "fdr_significant_features_with_direction_change_count": 1,
            },
        )

    def test_median_sign_interval_uses_maximal_exact_order_statistics(self) -> None:
        differences = tuple(float(value) for value in range(-8, 9))
        interval = _paired_median_sign_interval(differences, confidence_level=0.95)
        achieved = 1.0 - 2.0 * sum(math.comb(17, rank) for rank in range(5)) / 2**17
        next_rank_coverage = 1.0 - 2.0 * sum(math.comb(17, rank) for rank in range(6)) / 2**17

        self.assertEqual(interval["status"], "bounded")
        self.assertEqual(interval["bounds_log2_cpm"], [-4.0, 4.0])
        self.assertEqual(interval["lower_order_statistic_rank"], 5)
        self.assertEqual(interval["upper_order_statistic_rank"], 13)
        self.assertAlmostEqual(interval["achieved_confidence_level"], achieved)
        self.assertGreaterEqual(achieved, 0.95)
        self.assertLess(next_rank_coverage, 0.95)

    def test_median_sign_interval_reports_when_requested_coverage_is_unattainable(self) -> None:
        differences = (1.0, 2.0, 3.0, 4.0)
        unavailable = _paired_median_sign_interval(differences, confidence_level=0.95)
        attainable = _paired_median_sign_interval(differences, confidence_level=0.8)

        self.assertEqual(unavailable["status"], "no_finite_interval_at_requested_confidence")
        self.assertIsNone(unavailable["bounds_log2_cpm"])
        self.assertEqual(unavailable["maximum_finite_interval_confidence_level"], 0.875)
        self.assertEqual(attainable["status"], "bounded")
        self.assertEqual(attainable["bounds_log2_cpm"], [1.0, 4.0])
        self.assertEqual(attainable["achieved_confidence_level"], 0.875)

    def test_median_sign_interval_retains_ties_and_rejects_invalid_inputs(self) -> None:
        tied = _paired_median_sign_interval((0.0, 0.0, 1.0, 1.0, 2.0), confidence_level=0.8)
        self.assertEqual(tied["bounds_log2_cpm"], [0.0, 2.0])
        for level in (0.0, 1.0, float("nan"), float("inf"), True):
            with self.subTest(level=level), self.assertRaisesRegex(
                ValidationError, "confidence level"
            ):
                _paired_median_sign_interval((1.0, 2.0, 3.0), confidence_level=level)
        with self.assertRaisesRegex(ValidationError, "finite and non-empty"):
            _paired_median_sign_interval((1.0, float("nan")), confidence_level=0.8)
        with self.assertRaisesRegex(ValidationError, "finite and non-empty"):
            _paired_median_sign_interval((), confidence_level=0.8)

    def test_median_sign_interval_scales_to_large_pair_counts(self) -> None:
        differences = tuple(float(value) for value in range(1_500))
        interval = _paired_median_sign_interval(differences, confidence_level=0.95)

        self.assertEqual(interval["status"], "bounded")
        self.assertIsInstance(interval["lower_order_statistic_rank"], int)
        self.assertIsInstance(interval["upper_order_statistic_rank"], int)
        self.assertGreaterEqual(interval["achieved_confidence_level"], 0.95)
        self.assertEqual(
            interval["bounds_log2_cpm"],
            [
                differences[interval["lower_order_statistic_rank"] - 1],
                differences[interval["upper_order_statistic_rank"] - 1],
            ],
        )

    def test_pair_deletion_sensitivity_detects_a_direction_driven_by_one_pair(self) -> None:
        sensitivity = _paired_leave_one_out_median_sensitivity(
            (1.0, 2.0, 100.0, -1_000.0, -1_000.0)
        )
        self.assertEqual(sensitivity["omitted_pair_count"], 5)
        self.assertEqual(sensitivity["median_difference_range_log2_cpm"], [-499.5, 1.5])
        self.assertEqual(
            sensitivity["direction_counts"],
            {"case_higher": 2, "case_lower": 3, "tied": 0},
        )
        self.assertFalse(sensitivity["direction_stable"])

    def test_pair_deletion_order_statistics_match_brute_force_with_ties(self) -> None:
        for pair_count in range(3, 7):
            for differences in product((-2.0, 0.0, 3.0), repeat=pair_count):
                full_median = sorted(differences)[pair_count // 2]
                if pair_count % 2 == 0:
                    ordered = sorted(differences)
                    full_median = ordered[pair_count // 2 - 1] / 2 + ordered[pair_count // 2] / 2
                full_direction = (
                    "case_higher"
                    if full_median > 0
                    else "case_lower"
                    if full_median < 0
                    else "tied"
                )
                leave_one_out = tuple(
                    sorted(differences[:index] + differences[index + 1 :])
                    for index in range(pair_count)
                )
                medians = []
                for remaining in leave_one_out:
                    middle = len(remaining) // 2
                    medians.append(
                        remaining[middle]
                        if len(remaining) % 2
                        else remaining[middle - 1] / 2 + remaining[middle] / 2
                    )
                sensitivity = _paired_leave_one_out_median_sensitivity(differences)
                self.assertEqual(
                    sensitivity["median_difference_range_log2_cpm"],
                    [min(medians), max(medians)],
                )
                expected_counts = {
                    "case_higher": sum(value > 0 for value in medians),
                    "case_lower": sum(value < 0 for value in medians),
                    "tied": sum(value == 0 for value in medians),
                }
                self.assertEqual(sensitivity["direction_counts"], expected_counts)
                self.assertEqual(
                    sensitivity["direction_stable"],
                    all(
                        ("case_higher" if value > 0 else "case_lower" if value < 0 else "tied")
                        == full_direction
                        for value in medians
                    ),
                )

    def test_pair_deletion_sensitivity_rejects_invalid_input(self) -> None:
        with self.assertRaisesRegex(ValidationError, "at least three pairs"):
            _paired_leave_one_out_median_sensitivity((1.0, 2.0))
        with self.assertRaisesRegex(ValidationError, "must be finite"):
            _paired_leave_one_out_median_sensitivity((1.0, 2.0, float("nan")))

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
        self.assertEqual(report["quality_control"]["case"]["sample_count"], 3)
        self.assertEqual(report["quality_control"]["reference"]["sample_count"], 3)

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
            annotation_path = root / "annotations.csv"
            annotation_path.write_text(
                "source_feature_id,curated_feature_id\nSIGNAL,CURATED_SIGNAL\n",
                encoding="utf-8",
            )
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
                    "--feature-annotation-file",
                    str(annotation_path),
                    "--confidence-level",
                    "0.8",
                    "--normalization-method",
                    "tmm_log2_cpm",
                    "--output",
                    str(output),
                ]
            )
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(status, 0)
        self.assertEqual(report["summary"]["tested_feature_count"], 4)
        self.assertEqual(
            report["comparison"]["normalization_details"]["method"], "tmm_log2_cpm"
        )
        self.assertEqual(report["summary"]["reported_curated_feature_count"], 1)
        signal = next(row for row in report["results"] if row["feature_id"] == "SIGNAL")
        self.assertEqual(
            signal["feature_annotation"],
            {"status": "mapped", "curated_feature_id": "CURATED_SIGNAL"},
        )
        self.assertEqual(report["comparison"]["median_difference_interval_confidence_level"], 0.8)
        self.assertEqual(
            report["results"][0]["median_paired_difference_confidence_interval_log2_cpm"]["status"],
            "bounded",
        )

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

from __future__ import annotations

import gzip
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.geo_expression import (
    _adjust_p_values,
    _benjamini_hochberg,
    _mann_whitney_test,
    build_expression_contrast_report,
    parse_series_matrix_features,
    scan_series_matrix_features,
)

SAMPLE_IDS = tuple(f"GSM0000{index}" for index in range(1, 11))


def _matrix_payload() -> bytes:
    samples = "\t".join(f'"{sample}"' for sample in SAMPLE_IDS)
    diagnoses = "\t".join(['"diagnosis: normal"'] * 5 + ['"diagnosis: glioblastoma"'] * 5)
    rows = [
        '!Series_geo_accession\t"GSE123456"',
        '!Series_title\t"Fixture public expression series"',
        '!Series_type\t"Expression profiling by array"',
        '!Series_platform_id\t"GPL123"',
        f"!Sample_geo_accession\t{samples}",
        f"!Sample_characteristics_ch1\t{diagnoses}",
        "!series_matrix_table_begin",
        f"ID_REF\t{samples}",
    ]
    references = [1, 2, 3, 4, 5]
    cases = [10, 11, 12, 13, 14]
    for index in range(1, 6):
        values = references + cases
        rows.append(f"probe-up-{index}\t" + "\t".join(map(str, values)))
    rows.append("probe-null\t" + "\t".join(map(str, references + references)))
    rows.append("probe-missing\tNA\tNA\tNA\tNA\t1\t2\t3\t4\t5\t6")
    rows.append("!series_matrix_table_end")
    return gzip.compress(("\n".join(rows) + "\n").encode("utf-8"), mtime=0)


def _platform_annotation_payload(*, platform_id: str = "GPL123") -> bytes:
    rows = [
        "^PLATFORM = local-array-design",
        f"!Platform_geo_accession = {platform_id}",
        "!Platform_table_begin",
        "ID\tGene Symbol\tSPOT_ID",
        "probe-up-1\tLINC-A|LINC-B\tfeature-1",
        "probe-up-2\tLINC-C\tfeature-2",
        "!Platform_table_end",
    ]
    return ("\n".join(rows) + "\n").encode("utf-8")


def _covariate_matrix_payload(
    *,
    missing_age_index: int | None = None,
    nonnumeric_age_index: int | None = None,
    confounded_batch: bool = False,
) -> bytes:
    samples = "\t".join(f'"{sample}"' for sample in SAMPLE_IDS)
    diagnoses = ["normal"] * 5 + ["glioblastoma"] * 5
    age_measurements = [30, 40, 50, 60, 70, 40, 50, 60, 70, 80]
    ages: list[int | str] = list(age_measurements)
    if missing_age_index is not None:
        ages[missing_age_index] = "NA"
    if nonnumeric_age_index is not None:
        ages[nonnumeric_age_index] = "old"
    batches = (
        ["A"] * 5 + ["B"] * 5
        if confounded_batch
        else ["A", "B", "A", "B", "A", "A", "B", "A", "B", "A"]
    )
    noises = [-1, 1, 1, -1, 0, 1, -1, -1, 1, 0]
    expression = [
        100 + (5 if index >= 5 else 0) + 2 * (age - 55) + (3 if batch == "B" else 0) + noise
        for index, (age, batch, noise) in enumerate(
            zip(age_measurements, batches, noises, strict=True)
        )
    ]
    rows = [
        '!Series_geo_accession\t"GSE123456"',
        '!Series_title\t"Fixture public expression series"',
        '!Series_type\t"Expression profiling by array"',
        '!Series_platform_id\t"GPL123"',
        f"!Sample_geo_accession\t{samples}",
        "!Sample_characteristics_ch1\t" + "\t".join(f'"diagnosis: {value}"' for value in diagnoses),
        "!Sample_characteristics_ch1\t" + "\t".join(f'"age: {value}"' for value in ages),
        "!Sample_characteristics_ch1\t" + "\t".join(f'"batch: {value}"' for value in batches),
        "!series_matrix_table_begin",
        f"ID_REF\t{samples}",
        "probe-adjusted\t" + "\t".join(map(str, expression)),
        "probe-adjusted-missing\tNA\t" + "\t".join(map(str, expression[1:])),
        "probe-flat\t" + "\t".join("4" for _ in SAMPLE_IDS),
        "!series_matrix_table_end",
    ]
    return gzip.compress(("\n".join(rows) + "\n").encode("utf-8"), mtime=0)


class GeoContrastTests(unittest.TestCase):
    def test_full_matrix_parser_retains_features_and_source_provenance(self) -> None:
        matrix = parse_series_matrix_features(_matrix_payload(), accession="GSE123456")

        self.assertEqual(matrix.feature_count, 7)
        self.assertEqual(len(matrix.features), 7)
        self.assertEqual(matrix.features[0].feature_id, "probe-up-1")
        self.assertEqual(matrix.features[0].values, (1, 2, 3, 4, 5, 10, 11, 12, 13, 14))
        self.assertEqual(matrix.platform_ids, ("GPL123",))
        self.assertEqual(len(matrix.source_sha256), 64)

    def test_contrast_streams_feature_rows_without_retaining_the_full_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "streamed_matrix.txt.gz"
            matrix_path.write_bytes(_matrix_payload())
            with (
                patch(
                    "glio_noncode.geo_expression.parse_series_matrix_features",
                    side_effect=AssertionError("contrast must not retain the complete matrix"),
                ),
                patch(
                    "glio_noncode.geo_expression.scan_series_matrix_features",
                    wraps=scan_series_matrix_features,
                ) as streaming_scan,
            ):
                report = build_expression_contrast_report(
                    "GSE123456",
                    case_filters=(("diagnosis", "glioblastoma"),),
                    reference_filters=(("diagnosis", "normal"),),
                    scale="normalized_intensity",
                    matrix_file=matrix_path,
                    top=20,
                )

        self.assertEqual(streaming_scan.call_count, 1)
        self.assertEqual(report["summary"]["tested_feature_count"], 6)
        self.assertEqual(report["analysis_limits"]["matrix_scan_passes"], 2)
        self.assertFalse(report["analysis_limits"]["retains_feature_vectors"])
        self.assertEqual(report["results"][0]["feature_id"], "probe-up-1")

    def test_platform_feature_identifiers_may_contain_underscores(self) -> None:
        payload = gzip.compress(
            gzip.decompress(_matrix_payload()).replace(b"probe-up-1", b"probe_up_1", 1),
            mtime=0,
        )

        matrix = parse_series_matrix_features(payload, accession="GSE123456")

        self.assertEqual(matrix.features[0].feature_id, "probe_up_1")

    def test_contrast_runs_exact_tests_and_adjusts_the_complete_test_family(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "series_matrix.txt.gz"
            matrix_path.write_bytes(_matrix_payload())
            report = build_expression_contrast_report(
                "GSE123456",
                case_filters=(("diagnosis", "glioblastoma"),),
                reference_filters=(("diagnosis", "normal"),),
                scale="normalized_intensity",
                matrix_file=matrix_path,
                top=2,
            )

        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["source"]["retrieval"], "local_file")
        self.assertEqual(report["comparison"]["case_sample_ids"], list(SAMPLE_IDS[5:]))
        self.assertEqual(report["comparison"]["reference_sample_ids"], list(SAMPLE_IDS[:5]))
        self.assertEqual(report["summary"]["matrix_feature_count"], 7)
        self.assertEqual(report["summary"]["tested_feature_count"], 6)
        self.assertEqual(report["summary"]["fdr_family_size"], 6)
        self.assertEqual(report["summary"]["reported_feature_count"], 2)
        self.assertEqual(report["summary"]["fdr_significant_feature_count"], 5)
        self.assertEqual(report["results"][0]["feature_id"], "probe-up-1")
        self.assertAlmostEqual(report["results"][0]["p_value"], 2 / 252)
        self.assertAlmostEqual(report["results"][0]["q_value"], 2 / 210)
        self.assertEqual(report["results"][0]["test_method"], "exact_label_permutation")
        self.assertEqual(report["results"][0]["rank_biserial_correlation"], 1.0)
        self.assertEqual(report["results"][0]["effect_direction"], "case_higher")
        sensitivity = report["results"][0]["leave_one_sample_out_median_sensitivity"]
        self.assertEqual(sensitivity["status"], "complete")
        self.assertEqual(sensitivity["full_data_median_direction"], "case_higher")
        self.assertEqual(sensitivity["omitted_case_sample_count"], 5)
        self.assertEqual(sensitivity["omitted_reference_sample_count"], 5)
        self.assertEqual(sensitivity["eligible_omission_count"], 10)
        self.assertEqual(
            sensitivity["direction_counts"],
            {"case_higher": 10, "case_lower": 0, "no_median_difference": 0},
        )
        self.assertTrue(sensitivity["direction_stable"])
        self.assertEqual(sensitivity["median_difference_range"], [8.5, 9.5])
        self.assertEqual(
            report["summary"]["median_sensitivity_direction_unstable_feature_count"], 1
        )
        self.assertEqual(report["summary"]["fdr_significant_case_higher_count"], 5)
        self.assertEqual(report["summary"]["fdr_significant_case_lower_count"], 0)
        self.assertEqual(report["comparison"]["fdr_method"], "bh")
        resolution = report["comparison"]["finite_sample_resolution"]
        self.assertEqual(resolution["exact_test_feature_count"], 6)
        self.assertEqual(
            resolution["exact_test_feature_count"],
            report["summary"]["test_method_counts"]["exact_label_permutation"],
        )
        self.assertEqual(
            resolution["label_assignment_count_range"], {"minimum": 252, "maximum": 252}
        )
        self.assertEqual(
            resolution["no_tie_minimum_two_sided_p_range"],
            {"minimum": 2 / 252, "maximum": 2 / 252},
        )
        self.assertAlmostEqual(resolution["smallest_observed_exact_p_value"], 2 / 252)
        self.assertEqual(resolution["feature_count_at_smallest_observed_exact_p_value"], 5)
        self.assertEqual(
            report["comparison"]["multiple_testing_adjustment"],
            "Benjamini-Hochberg over all testable matrix features",
        )
        self.assertEqual(report["analysis_limits"]["max_retained_features"], 100_000)
        self.assertEqual(report["content_address"].split(":", 1)[0], "geo-expression-contrast")
        self.assertIn(
            "covariates and batch effects are not modeled",
            " ".join(report["limitations"]),
        )
        self.assertIn(
            "Exact two-sided permutation p-values are discrete",
            " ".join(report["limitations"]),
        )

    def test_unpaired_median_sensitivity_reports_instability_and_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "sensitivity_matrix.txt.gz"
            matrix_text = gzip.decompress(_matrix_payload()).decode("utf-8")
            sensitivity_rows = [
                "probe-influential\t1\t1\t1\t1\t1\t0\t10\t100\t0\t0",
                "probe-partial\t1\t2\tNA\tNA\tNA\t10\t11\t12\tNA\tNA",
                "probe-two-by-two\t1\t2\tNA\tNA\tNA\t10\t11\tNA\tNA\tNA",
            ]
            matrix_text = matrix_text.replace(
                "!series_matrix_table_end",
                "\n".join(sensitivity_rows) + "\n!series_matrix_table_end",
            )
            matrix_path.write_bytes(gzip.compress(matrix_text.encode("utf-8"), mtime=0))
            report = build_expression_contrast_report(
                "GSE123456",
                case_filters=(("diagnosis", "glioblastoma"),),
                reference_filters=(("diagnosis", "normal"),),
                scale="normalized_intensity",
                matrix_file=matrix_path,
                top=20,
            )

        rows = {row["feature_id"]: row for row in report["results"]}
        null_sensitivity = rows["probe-null"]["leave_one_sample_out_median_sensitivity"]
        self.assertEqual(null_sensitivity["full_data_median_direction"], "no_median_difference")
        self.assertFalse(null_sensitivity["direction_stable"])
        self.assertEqual(
            null_sensitivity["direction_counts"],
            {"case_higher": 4, "case_lower": 4, "no_median_difference": 2},
        )
        influential = rows["probe-influential"]["leave_one_sample_out_median_sensitivity"]
        self.assertEqual(influential["status"], "complete")
        self.assertEqual(influential["full_data_median_direction"], "case_lower")
        self.assertEqual(
            influential["direction_counts"],
            {"case_higher": 3, "case_lower": 7, "no_median_difference": 0},
        )
        self.assertFalse(influential["direction_stable"])
        self.assertEqual(influential["median_difference_range"], [-1.0, 4.0])

        partial = rows["probe-partial"]["leave_one_sample_out_median_sensitivity"]
        self.assertEqual(partial["status"], "partial")
        self.assertEqual(partial["reason"], "a_group_has_only_two_observed_values")
        self.assertEqual(partial["omitted_case_sample_count"], 3)
        self.assertEqual(partial["omitted_reference_sample_count"], 0)
        self.assertEqual(partial["eligible_omission_coverage"], 3 / 5)
        self.assertTrue(partial["direction_stable"])

        two_by_two = rows["probe-two-by-two"]["leave_one_sample_out_median_sensitivity"]
        self.assertEqual(two_by_two["status"], "unavailable")
        self.assertEqual(two_by_two["reason"], "no_eligible_single_sample_deletions")
        self.assertIsNone(two_by_two["direction_stable"])

        missing = rows["probe-missing"]["leave_one_sample_out_median_sensitivity"]
        self.assertEqual(missing["status"], "unavailable")
        self.assertEqual(
            missing["reason"], "fewer_than_two_nonmissing_observations_in_a_group"
        )
        self.assertEqual(
            report["summary"]["median_sensitivity_status_counts"],
            {"complete": 7, "partial": 1, "unavailable": 2, "not_calculated": 0},
        )
        self.assertEqual(
            report["summary"]["median_sensitivity_direction_unstable_feature_count"], 2
        )

    def test_finite_sample_resolution_tracks_per_feature_missingness(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "partial_matrix.txt.gz"
            matrix_text = gzip.decompress(_matrix_payload()).decode("utf-8")
            partial_row = "probe-partial\t1\t2\t3\tNA\t4\t10\t11\t12\tNA\t13"
            matrix_text = matrix_text.replace(
                "!series_matrix_table_end", f"{partial_row}\n!series_matrix_table_end"
            )
            matrix_path.write_bytes(gzip.compress(matrix_text.encode("utf-8"), mtime=0))
            report = build_expression_contrast_report(
                "GSE123456",
                case_filters=(("diagnosis", "glioblastoma"),),
                reference_filters=(("diagnosis", "normal"),),
                scale="normalized_intensity",
                matrix_file=matrix_path,
                top=20,
            )

        resolution = report["comparison"]["finite_sample_resolution"]
        self.assertEqual(resolution["exact_test_feature_count"], 7)
        self.assertEqual(
            resolution["label_assignment_count_range"], {"minimum": 70, "maximum": 252}
        )
        self.assertEqual(
            resolution["no_tie_minimum_two_sided_p_range"],
            {"minimum": 2 / 252, "maximum": 2 / 70},
        )
        self.assertEqual(report["summary"]["tested_feature_count"], 7)

    def test_covariate_adjusted_screen_separates_group_effect_from_age_and_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "covariates.txt.gz"
            matrix_path.write_bytes(_covariate_matrix_payload())
            report = build_expression_contrast_report(
                "GSE123456",
                case_filters=(("diagnosis", "glioblastoma"),),
                reference_filters=(("diagnosis", "normal"),),
                scale="normalized_intensity",
                matrix_file=matrix_path,
                top=3,
                covariates=(("age", "continuous"), ("batch", "categorical")),
            )

        results = {row["feature_id"]: row for row in report["results"]}
        signal = results["probe-adjusted"]
        self.assertAlmostEqual(signal["mean_difference"], 25.0)
        self.assertAlmostEqual(signal["adjusted_mean_difference"], 5.0, places=10)
        self.assertLess(signal["adjusted_mean_difference_ci_low"], 5.0)
        self.assertGreater(signal["adjusted_mean_difference_ci_high"], 5.0)
        self.assertGreater(signal["residual_standard_error"], 0.0)
        self.assertLessEqual(signal["adjusted_r_squared"], 1.0)
        self.assertEqual(report["comparison"]["model"]["confidence_level"], 0.95)
        self.assertEqual(signal["case_n"], 5)
        self.assertEqual(signal["reference_n"], 5)
        self.assertEqual(signal["degrees_of_freedom"], 6)
        self.assertTrue(0.0 <= signal["p_value"] <= 1.0)
        self.assertEqual(signal["test_method"], "covariate_adjusted_ols_t_test")
        self.assertEqual(
            signal["leave_one_sample_out_median_sensitivity"]["status"], "not_calculated"
        )
        self.assertIsNone(signal["rank_biserial_correlation"])
        self.assertEqual(
            results["probe-adjusted-missing"]["reason"],
            "missing_expression_in_covariate_complete_samples",
        )
        self.assertEqual(results["probe-flat"]["reason"], "zero_residual_variance")
        self.assertIsNone(results["probe-flat"]["residual_standard_error"])
        self.assertIsNone(results["probe-flat"]["adjusted_r_squared"])
        self.assertEqual(report["summary"]["tested_feature_count"], 1)
        self.assertEqual(report["summary"]["fdr_family_size"], 1)
        self.assertEqual(
            report["summary"]["median_sensitivity_status_counts"]["not_calculated"], 3
        )
        self.assertAlmostEqual(signal["q_value"], signal["p_value"])
        self.assertEqual(
            report["comparison"]["model"]["parameter_names"],
            [
                "intercept",
                "group_case_minus_reference",
                "covariate_1:age_standardized",
                "covariate_2:batch[B]",
            ],
        )
        self.assertEqual(report["comparison"]["model"]["covariates"][1]["reference_level"], "A")
        resolution = report["comparison"]["finite_sample_resolution"]
        self.assertEqual(resolution["exact_test_feature_count"], 0)
        self.assertIsNone(resolution["label_assignment_count_range"])
        self.assertIsNone(resolution["no_tie_minimum_two_sided_p_range"])
        self.assertIsNone(resolution["smallest_observed_exact_p_value"])
        self.assertEqual(resolution["feature_count_at_smallest_observed_exact_p_value"], 0)
        self.assertEqual(report["summary"]["covariate_complete_sample_count"], 10)
        self.assertIn(
            "covariates[age:continuous,batch:categorical]",
            report["comparison"]["context_key"],
        )
        self.assertIn(
            "approximately normal homoscedastic residuals",
            " ".join(report["limitations"]),
        )

    def test_covariate_missingness_is_listwise_and_reported_by_sample(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "covariates.txt.gz"
            matrix_path.write_bytes(_covariate_matrix_payload(missing_age_index=7))
            report = build_expression_contrast_report(
                "GSE123456",
                case_filters=(("diagnosis", "glioblastoma"),),
                reference_filters=(("diagnosis", "normal"),),
                scale="normalized_intensity",
                matrix_file=matrix_path,
                covariates=(("age", "continuous"), ("batch", "categorical")),
            )

        comparison = report["comparison"]
        self.assertEqual(comparison["case_sample_ids"], list(SAMPLE_IDS[5:]))
        self.assertEqual(
            comparison["analysis_case_sample_ids"],
            [SAMPLE_IDS[5], SAMPLE_IDS[6], SAMPLE_IDS[8], SAMPLE_IDS[9]],
        )
        self.assertEqual(comparison["covariate_excluded_case_sample_ids"], [SAMPLE_IDS[7]])
        self.assertEqual(report["summary"]["covariate_complete_sample_count"], 9)
        self.assertEqual(report["summary"]["covariate_excluded_sample_count"], 1)
        self.assertEqual(report["results"][0]["case_n"], 4)
        self.assertEqual(report["results"][0]["degrees_of_freedom"], 5)

    def test_rank_deficient_or_confounded_covariate_design_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "confounded.txt.gz"
            matrix_path.write_bytes(_covariate_matrix_payload(confounded_batch=True))
            with self.assertRaisesRegex(ValidationError, "rank deficient|collinear"):
                build_expression_contrast_report(
                    "GSE123456",
                    case_filters=(("diagnosis", "glioblastoma"),),
                    reference_filters=(("diagnosis", "normal"),),
                    scale="normalized_intensity",
                    matrix_file=matrix_path,
                    covariates=(("batch", "categorical"),),
                )

    def test_covariates_cannot_reuse_group_fields_or_accept_invalid_continuous_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "covariates.txt.gz"
            matrix_path.write_bytes(_covariate_matrix_payload())
            base = {
                "accession": "GSE123456",
                "case_filters": (("diagnosis", "glioblastoma"),),
                "reference_filters": (("diagnosis", "normal"),),
                "scale": "normalized_intensity",
                "matrix_file": matrix_path,
            }
            with self.assertRaisesRegex(ValidationError, "cannot reuse"):
                build_expression_contrast_report(**base, covariates=(("diagnosis", "categorical"),))

            matrix_path.write_bytes(_covariate_matrix_payload(nonnumeric_age_index=0))
            with self.assertRaisesRegex(ValidationError, "non-numeric"):
                build_expression_contrast_report(
                    **base,
                    covariates=(("age", "continuous"), ("batch", "categorical")),
                )

    def test_cli_accepts_repeated_typed_covariates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix_path = root / "covariates.txt.gz"
            report_path = root / "contrast.json"
            matrix_path.write_bytes(_covariate_matrix_payload())
            exit_code = cli_main(
                [
                    "geo-contrast",
                    "GSE123456",
                    "--case-filter",
                    "diagnosis=glioblastoma",
                    "--reference-filter",
                    "diagnosis=normal",
                    "--scale",
                    "normalized_intensity",
                    "--matrix-file",
                    str(matrix_path),
                    "--covariate",
                    "age=continuous",
                    "--covariate",
                    "batch=categorical",
                    "--output",
                    str(report_path),
                ]
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["results"][0]["test_method"], "covariate_adjusted_ols_t_test")

    def test_unstable_missing_feature_is_reported_but_not_in_fdr_family(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "matrix.txt.gz"
            matrix_path.write_bytes(_matrix_payload())
            report = build_expression_contrast_report(
                "GSE123456",
                case_filters=(("diagnosis", "glioblastoma"),),
                reference_filters=(("diagnosis", "normal"),),
                scale="normalized_intensity",
                matrix_file=matrix_path,
                top=7,
            )

        missing = next(row for row in report["results"] if row["feature_id"] == "probe-missing")
        self.assertEqual(missing["case_n"], 5)
        self.assertEqual(missing["reference_n"], 1)
        self.assertIsNone(missing["p_value"])
        self.assertIsNone(missing["q_value"])
        self.assertEqual(missing["reason"], "fewer_than_two_nonmissing_observations_in_a_group")
        self.assertEqual(report["summary"]["untestable_feature_count"], 1)

    def test_cli_writes_a_machine_readable_report_for_downloaded_local_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix_path = root / "downloaded.txt.gz"
            annotation_path = root / "platform.soft"
            report_path = root / "contrast.json"
            matrix_path.write_bytes(_matrix_payload())
            annotation_path.write_bytes(_platform_annotation_payload())
            exit_code = cli_main(
                [
                    "geo-contrast",
                    "GSE123456",
                    "--case-filter",
                    "diagnosis=glioblastoma",
                    "--reference-filter",
                    "diagnosis=normal",
                    "--scale",
                    "normalized_intensity",
                    "--matrix-file",
                    str(matrix_path),
                    "--platform-annotation-file",
                    str(annotation_path),
                    "--annotation-column",
                    "Gene Symbol",
                    "--annotation-column",
                    "SPOT_ID",
                    "--output",
                    str(report_path),
                ]
            )
            serialized = report_path.read_text(encoding="utf-8")
            report = json.loads(serialized)

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["source"]["source_file_name"], "downloaded.txt.gz")
        self.assertEqual(
            report["source"]["platform_annotation"]["platform_accession"],
            "GPL123",
        )
        self.assertEqual(
            report["source"]["platform_annotation"]["annotation_columns"],
            ["Gene Symbol", "SPOT_ID"],
        )
        self.assertEqual(report["summary"]["platform_annotation_matched_feature_count"], 2)
        self.assertEqual(report["summary"]["platform_annotation_unmatched_feature_count"], 5)
        annotated = next(row for row in report["results"] if row["feature_id"] == "probe-up-1")
        self.assertEqual(annotated["platform_annotation_status"], "matched")
        self.assertEqual(
            annotated["platform_annotation"],
            {"Gene Symbol": "LINC-A|LINC-B", "SPOT_ID": "feature-1"},
        )
        unmatched = next(row for row in report["results"] if row["feature_id"] == "probe-missing")
        self.assertEqual(unmatched["platform_annotation_status"], "not_found")
        self.assertIsNone(unmatched["platform_annotation"])
        self.assertNotIn(str(root), serialized)

    def test_cli_tracks_a_requested_feature_outside_the_ranked_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix_path = root / "downloaded.txt.gz"
            report_path = root / "contrast.json"
            matrix_path.write_bytes(_matrix_payload())
            exit_code = cli_main(
                [
                    "geo-contrast",
                    "GSE123456",
                    "--case-filter",
                    "diagnosis=glioblastoma",
                    "--reference-filter",
                    "diagnosis=normal",
                    "--scale",
                    "normalized_intensity",
                    "--matrix-file",
                    str(matrix_path),
                    "--top",
                    "1",
                    "--track-feature-id",
                    "probe-null",
                    "--output",
                    str(report_path),
                ]
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["comparison"]["tracked_feature_ids"], ["probe-null"])
        self.assertEqual(report["summary"]["additional_feature_result_count"], 1)
        self.assertEqual(
            report["additional_feature_results"][0]["feature_id"], "probe-null"
        )
        self.assertEqual(report["summary"]["reported_feature_count"], 1)

    def test_missing_tracked_feature_is_rejected_instead_of_silently_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "matrix.txt.gz"
            matrix_path.write_bytes(_matrix_payload())
            with self.assertRaisesRegex(ValidationError, "requested tracked GEO feature"):
                build_expression_contrast_report(
                    "GSE123456",
                    case_filters=(("diagnosis", "glioblastoma"),),
                    reference_filters=(("diagnosis", "normal"),),
                    scale="normalized_intensity",
                    matrix_file=matrix_path,
                    track_feature_ids=("not-in-the-matrix",),
                )

    def test_annotation_file_platform_must_match_series_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix_path = root / "matrix.txt.gz"
            annotation_path = root / "wrong-platform.soft"
            matrix_path.write_bytes(_matrix_payload())
            annotation_path.write_bytes(_platform_annotation_payload(platform_id="GPL456"))
            with self.assertRaisesRegex(ValidationError, "differs from the matrix"):
                build_expression_contrast_report(
                    "GSE123456",
                    case_filters=(("diagnosis", "glioblastoma"),),
                    reference_filters=(("diagnosis", "normal"),),
                    scale="normalized_intensity",
                    matrix_file=matrix_path,
                    platform_annotation_file=annotation_path,
                    annotation_columns=("Gene Symbol",),
                )

    def test_overlapping_filters_and_raw_counts_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "matrix.txt.gz"
            matrix_path.write_bytes(_matrix_payload())
            base = {
                "accession": "GSE123456",
                "case_filters": (("diagnosis", "normal"),),
                "reference_filters": (("diagnosis", "normal"),),
                "scale": "normalized_intensity",
                "matrix_file": matrix_path,
            }
            with self.assertRaisesRegex(ValidationError, "overlapping"):
                build_expression_contrast_report(**base)
            with self.assertRaisesRegex(ValidationError, "raw counts"):
                build_expression_contrast_report(**(base | {"scale": "raw_count"}))

    def test_exact_and_approximate_rank_tests_are_labeled(self) -> None:
        effect, p_value, method = _mann_whitney_test(
            (10, 11, 12, 13, 14), (1, 2, 3, 4, 5), assignment_limit=300
        )
        self.assertEqual(effect, 1.0)
        self.assertAlmostEqual(p_value, 2 / 252)
        self.assertEqual(method, "exact_label_permutation")

        _, approximate_p, approximate_method = _mann_whitney_test(
            (10, 11, 12, 13, 14), (1, 2, 3, 4, 5), assignment_limit=1
        )
        self.assertGreaterEqual(approximate_p, 0.0)
        self.assertLessEqual(approximate_p, 1.0)
        self.assertEqual(approximate_method, "tie_corrected_normal_approximation")

    def test_exact_permutation_uses_the_smaller_group_and_handles_ties(self) -> None:
        effect, p_value, method = _mann_whitney_test(
            tuple(range(3, 11)), (1, 2), assignment_limit=50
        )
        self.assertEqual(effect, 1.0)
        self.assertAlmostEqual(p_value, 2 / 45)
        self.assertEqual(method, "exact_label_permutation")

        tied_effect, tied_p, tied_method = _mann_whitney_test(
            (4, 4, 4), (4, 4, 4), assignment_limit=30
        )
        self.assertEqual(tied_effect, 0.0)
        self.assertEqual(tied_p, 1.0)
        self.assertEqual(tied_method, "exact_label_permutation")

    def test_benjamini_hochberg_is_monotone_in_sorted_p_value_order(self) -> None:
        values = _benjamini_hochberg((0.04, 0.01, 0.03, 0.002))

        self.assertEqual(values, [0.04, 0.02, 0.04, 0.008])

    def test_benjamini_yekutieli_adjustment_handles_dependence_conservatively(self) -> None:
        p_values = (0.04, 0.01, 0.03, 0.002)

        bh_values = _adjust_p_values(p_values, method="bh")
        by_values = _adjust_p_values(p_values, method="by")

        expected_by = (
            0.04 * 25 / 12,
            0.01 * 25 / 6,
            0.03 * 25 / 9,
            0.002 * 25 / 3,
        )
        for observed, expected in zip(by_values, expected_by, strict=True):
            self.assertAlmostEqual(observed, expected)
        self.assertTrue(all(by >= bh for by, bh in zip(by_values, bh_values, strict=True)))
        self.assertEqual(_adjust_p_values((), method="by"), [])

    def test_fdr_adjustment_rejects_unknown_methods_and_invalid_probabilities(self) -> None:
        with self.assertRaisesRegex(ValidationError, "FDR method"):
            _adjust_p_values((0.01,), method="holm")
        with self.assertRaisesRegex(ValidationError, "finite p-values"):
            _adjust_p_values((0.01, math.nan), method="by")

    def test_by_adjustment_is_selected_in_report_and_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            matrix_path = root / "matrix.txt.gz"
            report_path = root / "contrast.json"
            matrix_path.write_bytes(_matrix_payload())

            exit_code = cli_main(
                [
                    "geo-contrast",
                    "GSE123456",
                    "--case-filter",
                    "diagnosis=glioblastoma",
                    "--reference-filter",
                    "diagnosis=normal",
                    "--scale",
                    "normalized_intensity",
                    "--matrix-file",
                    str(matrix_path),
                    "--fdr-method",
                    "by",
                    "--output",
                    str(report_path),
                ]
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["comparison"]["fdr_method"], "by")
        self.assertEqual(
            report["comparison"]["multiple_testing_adjustment"],
            "Benjamini-Yekutieli over all testable matrix features",
        )
        self.assertTrue(
            any("arbitrary dependence" in limitation for limitation in report["limitations"])
        )

    def test_unknown_fdr_method_is_rejected_before_matrix_read(self) -> None:
        with self.assertRaisesRegex(ValidationError, "FDR method"):
            build_expression_contrast_report(
                "GSE123456",
                case_filters=(("diagnosis", "glioblastoma"),),
                reference_filters=(("diagnosis", "normal"),),
                scale="normalized_intensity",
                matrix_file="does-not-need-to-exist.txt.gz",
                fdr_method="holm",
            )


if __name__ == "__main__":
    unittest.main()

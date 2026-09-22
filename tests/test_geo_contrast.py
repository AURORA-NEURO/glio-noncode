from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.geo_expression import (
    _benjamini_hochberg,
    _mann_whitney_test,
    build_expression_contrast_report,
    parse_series_matrix_features,
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
        self.assertEqual(report["summary"]["fdr_significant_case_higher_count"], 5)
        self.assertEqual(report["summary"]["fdr_significant_case_lower_count"], 0)
        self.assertEqual(report["analysis_limits"]["max_retained_features"], 100_000)
        self.assertEqual(report["content_address"].split(":", 1)[0], "geo-expression-contrast")
        self.assertIn(
            "covariates and batch effects are not modeled",
            " ".join(report["limitations"]),
        )

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


if __name__ == "__main__":
    unittest.main()

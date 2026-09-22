from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from glio_noncode.cli import main as cli_main
from glio_noncode.geo_design import build_geo_contrast_design_report
from glio_noncode.serialization import content_hash

SAMPLE_IDS = tuple(f"GSM{index:06d}" for index in range(1, 9))


def _matrix_payload(
    *,
    missing_age: int | None = None,
    confounded_batch: bool = False,
    separated_age_ranges: bool = False,
    case_only_batch_level: bool = False,
) -> bytes:
    quoted_samples = "\t".join(f'"{sample}"' for sample in SAMPLE_IDS)
    diagnoses = ("glioblastoma",) * 4 + ("normal",) * 4
    ages = (
        ["70", "80", "90", "100", "30", "40", "50", "60"]
        if separated_age_ranges
        else ["40", "50", "60", "70", "30", "40", "50", "60"]
    )
    if missing_age is not None:
        ages[missing_age] = "NA"
    batches = (
        ("A", "B", "C", "C", "A", "B", "B", "B")
        if case_only_batch_level
        else ("A", "B", "A", "B", "B", "A", "B", "A")
    )
    if confounded_batch:
        batches = ("A",) * 4 + ("B",) * 4
    characteristic_rows = (
        ("diagnosis", diagnoses),
        ("age", tuple(ages)),
        ("batch", batches),
    )
    lines = [
        '!Series_geo_accession\t"GSE123456"',
        '!Series_title\t"Design preflight fixture"',
        '!Series_type\t"Expression profiling by array"',
        '!Series_platform_id\t"GPL123"',
        f"!Sample_geo_accession\t{quoted_samples}",
    ]
    lines.extend(
        "!Sample_characteristics_ch1\t"
        + "\t".join(f'"{field}: {value}"' for value in values)
        for field, values in characteristic_rows
    )
    lines.extend(
        (
            "!series_matrix_table_begin",
            f"ID_REF\t{quoted_samples}",
            "probe-1\t1\t2\t3\t4\t5\t6\t7\t8",
            "!series_matrix_table_end",
        )
    )
    return gzip.compress(("\n".join(lines) + "\n").encode(), mtime=0)


class GeoContrastDesignTests(unittest.TestCase):
    def _report(
        self,
        *,
        payload: bytes | None = None,
        case: str = "glioblastoma",
        reference: str = "normal",
        covariates: tuple[tuple[str, str], ...] = (),
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "matrix.txt.gz"
            matrix_path.write_bytes(payload if payload is not None else _matrix_payload())
            return build_geo_contrast_design_report(
                "GSE123456",
                case_filters=(("diagnosis", case),),
                reference_filters=(("diagnosis", reference),),
                covariates=covariates,
                matrix_file=matrix_path,
            )

    def test_explicit_groups_are_audited_without_expression_testing(self) -> None:
        report = self._report()

        self.assertEqual(report["schema"], "glio-noncode.geo-contrast-design.v1")
        self.assertEqual(report["design"]["state"], "estimable")
        self.assertEqual(report["design"]["method"], "two_group_difference")
        self.assertEqual(report["summary"]["selected_case_count"], 4)
        self.assertEqual(report["summary"]["selected_reference_count"], 4)
        self.assertEqual(report["design"]["residual_degrees_of_freedom"], 6)
        self.assertFalse(report["analysis"]["expression_values_retained"])
        self.assertFalse(report["analysis"]["effect_sizes_calculated"])
        self.assertFalse(report["analysis"]["p_values_calculated"])
        self.assertNotIn("features", report)

    def test_adjusted_design_reports_encoding_and_group_balance(self) -> None:
        report = self._report(covariates=(("age", "continuous"), ("batch", "categorical")))

        design = report["design"]
        self.assertEqual(design["state"], "estimable")
        self.assertEqual(design["residual_degrees_of_freedom"], 4)
        self.assertEqual(design["parameter_count"], 4)
        self.assertEqual([item["field"] for item in design["covariate_balance"]], ["age", "batch"])
        self.assertEqual(
            design["covariate_balance"][1]["levels"],
            [
                {
                    "value": "A",
                    "case_count": 2,
                    "reference_count": 2,
                    "case_fraction": 0.5,
                    "reference_fraction": 0.5,
                    "absolute_fraction_difference": 0.0,
                },
                {
                    "value": "B",
                    "case_count": 2,
                    "reference_count": 2,
                    "case_fraction": 0.5,
                    "reference_fraction": 0.5,
                    "absolute_fraction_difference": 0.0,
                },
            ],
        )
        age = design["covariate_balance"][0]
        self.assertAlmostEqual(
            age["standardized_mean_difference"], 10 / (500 / 3) ** 0.5
        )
        self.assertEqual(age["standardized_mean_difference_status"], "available")
        self.assertTrue(age["range_overlap"]["overlaps"])
        self.assertEqual(age["range_overlap"]["minimum"], 40.0)
        self.assertEqual(age["range_overlap"]["maximum"], 60.0)
        batch = design["covariate_balance"][1]
        self.assertEqual(batch["shared_level_count"], 2)
        self.assertEqual(batch["maximum_absolute_level_fraction_difference"], 0.0)

    def test_disjoint_continuous_covariate_ranges_are_reported(self) -> None:
        report = self._report(
            payload=_matrix_payload(separated_age_ranges=True),
            covariates=(("age", "continuous"),),
        )

        age = report["design"]["covariate_balance"][0]
        self.assertEqual(report["design"]["state"], "estimable")
        self.assertFalse(age["range_overlap"]["overlaps"])
        self.assertIsNone(age["range_overlap"]["minimum"])
        self.assertIsNone(age["range_overlap"]["maximum"])
        self.assertGreater(age["standardized_mean_difference"], 0.0)

    def test_case_only_categorical_level_is_reported_when_design_is_estimable(self) -> None:
        report = self._report(
            payload=_matrix_payload(case_only_batch_level=True),
            covariates=(("batch", "categorical"),),
        )

        balance = report["design"]["covariate_balance"][0]
        self.assertEqual(report["design"]["state"], "estimable")
        self.assertEqual(balance["case_only_levels"], ["C"])
        self.assertEqual(balance["reference_only_levels"], [])
        self.assertEqual(balance["shared_level_count"], 2)
        self.assertEqual(balance["maximum_absolute_level_fraction_difference"], 0.5)

    def test_missing_covariate_is_excluded_and_accounted_for(self) -> None:
        report = self._report(
            payload=_matrix_payload(missing_age=0),
            covariates=(("age", "continuous"),),
        )

        design = report["design"]
        self.assertEqual(design["state"], "estimable")
        self.assertEqual(design["complete_case_group_counts"], {"case": 3, "reference": 4})
        self.assertEqual(
            design["excluded_for_missing_covariates"][0]["sample_accession"], "GSM000001"
        )
        self.assertEqual(design["excluded_for_missing_covariates"][0]["missing_fields"], ["age"])
        self.assertEqual(design["residual_degrees_of_freedom"], 4)

    def test_collinear_covariate_fails_closed_with_reason(self) -> None:
        report = self._report(
            payload=_matrix_payload(confounded_batch=True),
            covariates=(("batch", "categorical"),),
        )

        self.assertEqual(report["design"]["state"], "not_estimable")
        self.assertIn("rank deficient", report["design"]["reason"])
        self.assertFalse(report["summary"]["design_estimable"])

    def test_overlapping_filters_are_reported_not_silently_resolved(self) -> None:
        report = self._report(case="normal", reference="normal")

        self.assertEqual(report["design"]["state"], "not_estimable")
        self.assertEqual(report["summary"]["overlap_count"], 4)
        self.assertEqual(len(report["comparison"]["overlapping_sample_ids"]), 4)

    def test_invalid_numeric_covariate_is_not_silently_coerced(self) -> None:
        invalid_age = gzip.compress(
            gzip.decompress(_matrix_payload()).replace(b"age: 40", b"age: old"),
            mtime=0,
        )
        report = self._report(
            payload=invalid_age,
            covariates=(("age", "continuous"),),
        )

        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["design"]["state"], "not_estimable")
        self.assertIn("non-numeric value", report["design"]["reason"])

    def test_content_address_and_local_path_privacy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "matrix.txt.gz"
            matrix_path.write_bytes(_matrix_payload())
            report = build_geo_contrast_design_report(
                "GSE123456",
                case_filters=(("diagnosis", "glioblastoma"),),
                reference_filters=(("diagnosis", "normal"),),
                matrix_file=matrix_path,
            )

        serialized = json.dumps(report)
        self.assertNotIn(temporary, serialized)
        self.assertEqual(report["source"]["source_file_name"], matrix_path.name)
        self.assertEqual(
            report["content_address"],
            content_hash(
                {key: value for key, value in report.items() if key != "content_address"},
                prefix="geo-contrast-design",
            ),
        )

    def test_cli_reads_local_matrix_and_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            matrix_path = Path(temporary) / "matrix.txt.gz"
            matrix_path.write_bytes(_matrix_payload())
            output = StringIO()
            with redirect_stdout(output):
                exit_code = cli_main(
                    [
                        "geo-design",
                        "GSE123456",
                        "--case-filter",
                        "diagnosis=glioblastoma",
                        "--reference-filter",
                        "diagnosis=normal",
                        "--covariate",
                        "age=continuous",
                        "--matrix-file",
                        str(matrix_path),
                    ]
                )

        self.assertEqual(exit_code, 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["design"]["state"], "estimable")
        self.assertGreater(
            report["design"]["covariate_balance"][0]["standardized_mean_difference"], 0.0
        )


if __name__ == "__main__":
    unittest.main()

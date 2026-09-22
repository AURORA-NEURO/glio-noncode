from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.cli import main as cli_main
from glio_noncode.errors import ValidationError
from glio_noncode.geo_consistency import build_geo_contrast_consistency_report
from glio_noncode.geo_expression import build_expression_contrast_report
from glio_noncode.serialization import content_hash

FEATURE_VALUES = {
    "probe-a-concordant": (1, 2, 3, 10, 11, 12),
    "probe-b-discordant": (1, 2, 3, 10, 11, 12),
    "probe-c-neutral": (5, 5, 5, 5, 5, 5),
    "probe-d-untestable": (1, 2, 3, 10, "NA", "NA"),
}


def _matrix_payload(
    accession: str,
    *,
    reverse_discordant: bool = False,
    reverse_group_roles: bool = False,
    sample_base: int = 1,
) -> bytes:
    sample_ids = tuple(f"GSM{sample_base + index:06d}" for index in range(6))
    quoted_samples = "\t".join(f'"{sample}"' for sample in sample_ids)
    diagnoses = ("normal", "normal", "normal", "glioblastoma", "glioblastoma", "glioblastoma")
    if reverse_group_roles:
        diagnoses = tuple(reversed(diagnoses))
    rows = [
        f'!Series_geo_accession\t"{accession}"',
        '!Series_title\t"Cross-series direction fixture"',
        '!Series_type\t"Expression profiling by array"',
        '!Series_platform_id\t"GPL123"',
        f"!Sample_geo_accession\t{quoted_samples}",
        "!Sample_characteristics_ch1\t"
        + "\t".join(f'"diagnosis: {value}"' for value in diagnoses),
        "!series_matrix_table_begin",
        f"ID_REF\t{quoted_samples}",
    ]
    for feature_id, values in FEATURE_VALUES.items():
        if feature_id == "probe-b-discordant" and reverse_discordant:
            values = (*values[3:], *values[:3])
        rows.append(f"{feature_id}\t" + "\t".join(map(str, values)))
    rows.append("!series_matrix_table_end")
    return gzip.compress(("\n".join(rows) + "\n").encode("utf-8"), mtime=0)


def _contrast_report(
    root: Path,
    accession: str,
    *,
    reverse_discordant: bool = False,
    reverse_group_roles: bool = False,
    sample_base: int = 1,
    top: int = 10,
    fdr_method: str = "bh",
    track_feature_ids: tuple[str, ...] = (),
) -> dict[str, object]:
    matrix_path = root / f"{accession}-matrix.txt.gz"
    matrix_path.write_bytes(
        _matrix_payload(
            accession,
            reverse_discordant=reverse_discordant,
            reverse_group_roles=reverse_group_roles,
            sample_base=sample_base,
        )
    )
    return build_expression_contrast_report(
        accession,
        case_filters=(("diagnosis", "glioblastoma"),),
        reference_filters=(("diagnosis", "normal"),),
        scale="normalized_intensity",
        matrix_file=matrix_path,
        fdr_method=fdr_method,
        fdr_threshold=0.05,
        top=top,
        track_feature_ids=track_feature_ids,
    )


class GeoContrastConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.report_a = _contrast_report(self.root, "GSE123456")
        self.report_b = _contrast_report(
            self.root,
            "GSE123457",
            reverse_discordant=True,
            sample_base=101,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_exact_feature_directions_are_compared_without_pooling(self) -> None:
        report = build_geo_contrast_consistency_report(
            (self.report_a, self.report_b),
            feature_ids=(
                "probe-a-concordant",
                "probe-b-discordant",
                "probe-c-neutral",
                "probe-d-untestable",
                "probe-not-reported",
            ),
        )

        by_feature = {feature["feature_id"]: feature for feature in report["features"]}
        self.assertEqual(report["schema"], "glio-noncode.geo-contrast-consistency.v1")
        self.assertEqual(
            by_feature["probe-a-concordant"]["summary"]["direction_consistency"],
            "concordant_among_reported",
        )
        self.assertEqual(
            by_feature["probe-b-discordant"]["summary"]["direction_consistency"],
            "discordant_among_reported",
        )
        self.assertEqual(
            by_feature["probe-c-neutral"]["summary"]["distinct_directions"], ["neutral"]
        )
        self.assertEqual(by_feature["probe-d-untestable"]["summary"]["untestable_count"], 2)
        missing = by_feature["probe-not-reported"]["studies"]
        self.assertEqual(
            [study["result_state"] for study in missing],
            [
                "not_reported_in_bounded_or_tracked_results",
                "not_reported_in_bounded_or_tracked_results",
            ],
        )
        self.assertFalse(report["analysis"]["p_values_combined"])
        self.assertNotIn("combined_p_value", json.dumps(report))
        self.assertEqual(report["summary"]["shared_sample_id_count_across_series"], 0)

    def test_tracked_features_remain_comparable_beyond_ranked_result_limit(self) -> None:
        first = _contrast_report(
            self.root,
            "GSE123460",
            top=1,
            track_feature_ids=("probe-b-discordant",),
        )
        second = _contrast_report(
            self.root,
            "GSE123461",
            reverse_discordant=True,
            sample_base=301,
            top=1,
            track_feature_ids=("probe-b-discordant",),
        )
        report = build_geo_contrast_consistency_report(
            (first, second),
            feature_ids=("probe-b-discordant",),
        )

        self.assertNotIn(
            "probe-b-discordant", {row["feature_id"] for row in first["results"]}
        )
        self.assertEqual(
            first["additional_feature_results"][0]["feature_id"], "probe-b-discordant"
        )
        self.assertEqual(
            report["features"][0]["summary"]["direction_consistency"],
            "discordant_among_reported",
        )

    def test_tracked_feature_declaration_must_match_additional_rows(self) -> None:
        first = _contrast_report(
            self.root,
            "GSE123462",
            sample_base=401,
            top=1,
            track_feature_ids=("probe-b-discordant",),
        )
        changed = dict(first)
        changed["comparison"] = dict(first["comparison"], tracked_feature_ids=[])
        changed["content_address"] = content_hash(
            {key: value for key, value in changed.items() if key != "content_address"},
            prefix="geo-expression-contrast",
        )

        with self.assertRaisesRegex(ValidationError, "tracked feature IDs do not match"):
            build_geo_contrast_consistency_report(
                (changed, self.report_b),
                feature_ids=("probe-b-discordant",),
            )

    def test_overlapping_gsm_ids_and_conflicting_group_roles_are_reported(self) -> None:
        overlapping = _contrast_report(
            self.root,
            "GSE123463",
            sample_base=1,
            reverse_group_roles=True,
        )
        report = build_geo_contrast_consistency_report(
            (self.report_a, overlapping),
            feature_ids=("probe-a-concordant",),
        )

        self.assertEqual(report["summary"]["shared_sample_id_count_across_series"], 6)
        self.assertEqual(report["summary"]["sample_ids_assigned_to_different_groups"], 6)
        self.assertTrue(report["analysis"]["shared_sample_ids_detected"])
        self.assertTrue(report["analysis"]["cross_series_group_conflict_detected"])

    def test_content_address_is_verified_and_output_is_content_addressed(self) -> None:
        report = build_geo_contrast_consistency_report(
            (self.report_a, self.report_b),
            feature_ids=("probe-a-concordant",),
        )
        self.assertEqual(
            report["content_address"],
            content_hash(
                {key: value for key, value in report.items() if key != "content_address"},
                prefix="geo-contrast-consistency",
            ),
        )

        changed = dict(self.report_a)
        changed["comparison"] = dict(self.report_a["comparison"], scale="transformed_intensity")
        with self.assertRaisesRegex(ValidationError, "content address"):
            build_geo_contrast_consistency_report(
                (changed, self.report_b),
                feature_ids=("probe-a-concordant",),
            )

    def test_incompatible_analysis_settings_are_rejected(self) -> None:
        by_report = _contrast_report(
            self.root,
            "GSE123458",
            sample_base=201,
            fdr_method="by",
        )

        with self.assertRaisesRegex(ValidationError, "same scale, FDR method"):
            build_geo_contrast_consistency_report(
                (self.report_a, by_report),
                feature_ids=("probe-a-concordant",),
            )

    def test_different_case_or_reference_filters_are_rejected(self) -> None:
        for field, replacement in (
            ("case_filters", [{"field": "phenotype", "equals": "TMZ-resistant"}]),
            ("reference_filters", [{"field": "phenotype", "equals": "TMZ-sensitive"}]),
        ):
            with self.subTest(field=field):
                changed = dict(self.report_b)
                changed["comparison"] = dict(
                    self.report_b["comparison"], **{field: replacement}
                )
                changed["content_address"] = content_hash(
                    {key: value for key, value in changed.items() if key != "content_address"},
                    prefix="geo-expression-contrast",
                )

                with self.assertRaisesRegex(ValidationError, "identical case and reference"):
                    build_geo_contrast_consistency_report(
                        (self.report_a, changed),
                        feature_ids=("probe-a-concordant",),
                    )

    def test_filter_signatures_follow_case_insensitive_matcher_semantics(self) -> None:
        case_insensitive = dict(self.report_b)
        case_insensitive["comparison"] = dict(
            self.report_b["comparison"],
            case_filters=[{"field": "Diagnosis", "equals": "GLIOBLASTOMA"}],
            reference_filters=[{"field": "diagnosis", "equals": "NORMAL"}],
        )
        case_insensitive["content_address"] = content_hash(
            {
                key: value
                for key, value in case_insensitive.items()
                if key != "content_address"
            },
            prefix="geo-expression-contrast",
        )

        report = build_geo_contrast_consistency_report(
            (self.report_a, case_insensitive),
            feature_ids=("probe-a-concordant",),
        )

        self.assertEqual(report["summary"]["study_count"], 2)
        self.assertEqual(
            report["comparison"]["case_filters"],
            self.report_a["comparison"]["case_filters"],
        )

    def test_different_platforms_are_not_matched_by_string_id(self) -> None:
        other_platform = dict(self.report_b)
        other_platform["source"] = dict(self.report_b["source"], platform_ids=["GPL999"])
        other_platform["content_address"] = content_hash(
            {key: value for key, value in other_platform.items() if key != "content_address"},
            prefix="geo-expression-contrast",
        )

        with self.assertRaisesRegex(ValidationError, "same platform accession"):
            build_geo_contrast_consistency_report(
                (self.report_a, other_platform),
                feature_ids=("probe-a-concordant",),
            )

    def test_same_matrix_with_different_series_label_is_not_a_replication(self) -> None:
        reused = dict(self.report_a)
        reused["source"] = dict(self.report_a["source"], accession="GSE123459")
        reused["content_address"] = content_hash(
            {key: value for key, value in reused.items() if key != "content_address"},
            prefix="geo-expression-contrast",
        )

        with self.assertRaisesRegex(ValidationError, "distinct matrix source digests"):
            build_geo_contrast_consistency_report(
                (self.report_a, reused),
                feature_ids=("probe-a-concordant",),
            )

    def test_repeated_feature_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "feature IDs must be unique"):
            build_geo_contrast_consistency_report(
                (self.report_a, self.report_b),
                feature_ids=("probe-a-concordant", "probe-a-concordant"),
            )

    def test_cli_reads_two_reports_without_leaking_paths(self) -> None:
        first_path = self.root / "first.json"
        second_path = self.root / "second.json"
        output_path = self.root / "consistency.json"
        first_path.write_text(json.dumps(self.report_a), encoding="utf-8")
        second_path.write_text(json.dumps(self.report_b), encoding="utf-8")

        exit_code = cli_main(
            [
                "geo-consistency",
                str(first_path),
                str(second_path),
                "--feature-id",
                "probe-a-concordant",
                "--feature-id",
                "probe-b-discordant",
                "--output",
                str(output_path),
            ]
        )

        result_text = output_path.read_text(encoding="utf-8")
        result = json.loads(result_text)
        self.assertEqual(exit_code, 0)
        self.assertNotIn(str(self.root), result_text)
        self.assertEqual(result["summary"]["discordant_feature_count"], 1)

    def test_cli_explains_incompatible_contrasts_without_exposing_paths(self) -> None:
        first_path = self.root / "first.json"
        second_path = self.root / "second.json"
        output_path = self.root / "incompatible.json"
        first_path.write_text(json.dumps(self.report_a), encoding="utf-8")
        incompatible = dict(self.report_b)
        incompatible["comparison"] = dict(
            self.report_b["comparison"],
            case_filters=[{"field": "phenotype", "equals": "TMZ-resistant"}],
        )
        incompatible["content_address"] = content_hash(
            {key: value for key, value in incompatible.items() if key != "content_address"},
            prefix="geo-expression-contrast",
        )
        second_path.write_text(json.dumps(incompatible), encoding="utf-8")

        exit_code = cli_main(
            [
                "geo-consistency",
                str(first_path),
                str(second_path),
                "--feature-id",
                "probe-a-concordant",
                "--output",
                str(output_path),
            ]
        )

        result_text = output_path.read_text(encoding="utf-8")
        result = json.loads(result_text)
        self.assertEqual(exit_code, 2)
        self.assertEqual(result["error"]["code"], "incompatible_contrast_reports")
        self.assertIn("case and reference filter definitions", result["error"]["message"])
        self.assertNotIn(str(self.root), result_text)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.variation_fixture_eval import (
    VariationFixtureEvaluator,
    evaluate_variation_fixture,
)
from glio_noncode.variation_public_data import VariationDataState

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "variation-public-aggregate.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"


class VariationFixtureEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.evaluator = VariationFixtureEvaluator()

    def test_public_aggregate_fixture_passes_all_variation_adapters(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE)
        self.assertTrue(report.passed)
        self.assertEqual(report.state, VariationDataState.ACCEPTED)
        self.assertEqual(report.fixture_id, "variation-public-aggregate-001")
        self.assertEqual(report.context_key, CONTEXT)
        self.assertEqual(len(report.checks), 29)
        self.assertEqual(report.failed_check_ids, ())

    def test_positive_reports_cover_every_record_identity(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE)
        self.assertEqual(
            set(report.positive_reports),
            {
                "dbsnp:rs121913502:vrs",
                "categorical:rs121913502",
                "annotation:rs121913502",
                "multiallelic:rs121913502",
                "repeat-window:public-reference-01",
            },
        )

    def test_vrs_report_is_supported_and_preserves_public_identifier(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE)
        output = report.positive_reports["dbsnp:rs121913502:vrs"]
        self.assertEqual(output["state"], "supported")
        self.assertEqual(output["input_id"], "dbsnp:rs121913502")
        self.assertEqual(output["candidates"][0]["vrs_allele"]["type"], "Allele")
        self.assertFalse(output["candidates"][0]["reference_digest_supplied"])

    def test_categorical_report_matches_only_declared_member(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE)
        output = report.positive_reports["categorical:rs121913502"]
        self.assertEqual(output["state"], "supported")
        self.assertEqual(output["selected_category_id"], "CAT-PUBLIC-AGGREGATE-01")
        self.assertEqual(
            output["candidates"][0]["match_basis"],
            ["declared_member_variation_id"],
        )

    def test_annotation_report_is_provenance_complete(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE)
        output = report.positive_reports["annotation:rs121913502"]
        self.assertEqual(output["state"], "supported")
        self.assertEqual(output["context_key"], CONTEXT)
        self.assertEqual(len(output["statements"]), 1)
        self.assertEqual(len(output["evidence_lines"]), 1)

    def test_multiallelic_report_preserves_two_children_and_parent_hash(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE)
        output = report.positive_reports["multiallelic:rs121913502"]
        self.assertEqual(output["state"], "supported")
        self.assertEqual([child["allele_index"] for child in output["children"]], [1, 2])
        self.assertEqual(
            {child["parent_raw_hash"] for child in output["children"]},
            {output["input_hash"]},
        )

    def test_repeat_report_is_ambiguous_without_silent_selection(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE)
        output = report.positive_reports["repeat-window:public-reference-01"]
        self.assertEqual(output["state"], "ambiguous")
        self.assertIsNone(output["selected_placement"])
        self.assertGreater(len(output["placements"]), 1)
        self.assertTrue(
            all(
                placement["equivalence_basis"].startswith("reference substring")
                for placement in output["placements"]
            )
        )

    def test_negative_controls_preserve_all_declared_states(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE)
        self.assertEqual(
            {key: value["state"] for key, value in report.negative_reports.items()},
            {
                "vrs-symbolic-breakend": "abstained",
                "categorical-label-only": "abstained",
                "annotation-context-mismatch": "out_of_domain",
                "multiallelic-symbolic": "abstained",
                "repeat-reference-mismatch": "abstained",
            },
        )

    def test_negative_control_issue_codes_are_retained(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE)
        self.assertEqual(
            report.negative_reports["categorical-label-only"]["issues"][0]["code"],
            "category_not_resolved",
        )
        self.assertEqual(
            report.negative_reports["multiallelic-symbolic"]["issues"][0]["code"],
            "invalid_alternate",
        )
        self.assertEqual(
            report.negative_reports["repeat-reference-mismatch"]["issues"][0]["code"],
            "reference_mismatch",
        )

    def test_report_has_stable_content_address(self) -> None:
        first = evaluate_variation_fixture(FIXTURE).to_dict()
        second = evaluate_variation_fixture(FIXTURE).to_dict()
        self.assertEqual(first, second)
        self.assertRegex(first["content_address"], r"^sha256:[0-9a-f]{64}$")

    def test_every_operation_report_is_content_addressed(self) -> None:
        report = self.evaluator.evaluate_file(FIXTURE)
        for output in (*report.positive_reports.values(), *report.negative_reports.values()):
            self.assertRegex(output["content_address"], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(all(check.content_address.startswith("sha256:") for check in report.checks))

    def test_mutated_positive_vrs_state_fails_evidence(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["records"][0]["payload"]["alternate"] = "<DEL>"
        report = self.evaluator.evaluate(raw)
        self.assertFalse(report.passed)
        self.assertEqual(report.state, VariationDataState.REVIEW)
        self.assertIn("positive:dbsnp:rs121913502:vrs", report.failed_check_ids)

    def test_mutated_positive_annotation_context_fails_evidence(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["records"][2]["payload"]["statements"][0]["context_key"] = CONTEXT.replace(
            "tumor_core", "core_margin"
        )
        report = self.evaluator.evaluate(raw)
        self.assertFalse(report.passed)
        self.assertEqual(
            report.positive_reports["annotation:rs121913502"]["state"],
            "out_of_domain",
        )

    def test_sensitive_fixture_data_fails_data_boundary(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["records"][0]["payload"]["patient_id"] = "restricted"
        report = self.evaluator.evaluate(raw)
        self.assertFalse(report.passed)
        self.assertIn("data-boundary:variation-catalog", report.failed_check_ids)

    def test_missing_record_kind_is_rejected_before_execution(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["records"] = [record for record in raw["records"] if record["kind"] != "repeat"]
        with self.assertRaises(ValidationError):
            self.evaluator.evaluate(raw)

    def test_missing_negative_controls_is_rejected_before_execution(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw.pop("negative_controls")
        with self.assertRaises(ValidationError):
            self.evaluator.evaluate(raw)

    def test_negative_control_requires_structured_payload(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["negative_controls"][0]["payload"] = []
        with self.assertRaises(ValidationError):
            self.evaluator.evaluate(raw)

    def test_negative_control_requires_expected_state(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["negative_controls"][0].pop("expected_state")
        with self.assertRaises(ValidationError):
            self.evaluator.evaluate(raw)

    def test_serialized_report_contains_evidence_boundary(self) -> None:
        payload = self.evaluator.evaluate_file(FIXTURE).to_dict()
        self.assertEqual(
            payload["evidence_boundary"],
            "public aggregate identity and deterministic software receipts only; "
            "no biological or clinical claim",
        )
        self.assertEqual(payload["passed_count"], payload["check_count"])
        self.assertEqual(payload["failed_count"], 0)

    def test_output_does_not_contain_restricted_fixture_values(self) -> None:
        payload = self.evaluator.evaluate_file(FIXTURE).to_dict()
        serialized = json.dumps(payload, sort_keys=True).casefold()
        self.assertNotIn("patient_id", serialized)
        self.assertNotIn("mrn", serialized)
        self.assertNotIn("secret", serialized)


if __name__ == "__main__":
    unittest.main()

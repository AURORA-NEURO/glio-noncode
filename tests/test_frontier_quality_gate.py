from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.frontier_quality_gate import (
    FrontierQualityGate,
    QualityGateCheck,
    QualityGateState,
    evaluate_frontier_quality_gate,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "frontier-glioma-case.json"
CONTEXT = "GRCh38|diffuse_glioma|adult|malignant_oligodendrocyte_like|tumor_core|pre_treatment"
SOURCES = ("glioma-regulatory-reference", "regulatory-assay-contract-reference")


class FrontierQualityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.gate = FrontierQualityGate()

    def test_checked_in_fixture_passes_quality_gate(self) -> None:
        report = self.gate.evaluate_file(FIXTURE)
        self.assertTrue(report.passed)
        self.assertEqual(report.state, QualityGateState.ACCEPTED)
        self.assertEqual(report.fixture_id, "glioma-frontier-public-aggregate-001")
        self.assertEqual(report.fixture_version, "frontier-fixture-v1")
        self.assertEqual(report.context_key, CONTEXT)
        self.assertEqual(report.source_ids, SOURCES)
        self.assertEqual(report.failed_check_ids, ())

    def test_quality_gate_has_twelve_explicit_checks(self) -> None:
        report = self.gate.evaluate_file(FIXTURE)
        self.assertEqual(len(report.checks), 12)
        self.assertEqual(len(report.passed_check_ids), 12)
        self.assertEqual(
            tuple(check.check_id for check in report.checks),
            (
                "fixture-evaluation",
                "fixture-check-floor",
                "public-data-audit",
                "replay-integrity",
                "scenario-matrix",
                "scenario-review-floor",
                "contract-count",
                "capability-count",
                "context-consistency",
                "source-consistency",
                "deterministic-evaluation",
                "secret-output-boundary",
            ),
        )

    def test_component_receipts_expose_diagnostics_without_raw_fixture(self) -> None:
        report = self.gate.evaluate_file(FIXTURE)
        self.assertEqual(
            set(report.component_receipts),
            {"fixture", "data", "replay", "scenarios", "contracts"},
        )
        self.assertEqual(report.component_receipts["fixture"]["check_count"], 49)
        self.assertEqual(report.component_receipts["data"]["record_count"], 10)
        self.assertEqual(report.component_receipts["replay"]["case_count"], 1)
        self.assertEqual(report.component_receipts["scenarios"]["scenario_count"], 8)
        self.assertEqual(report.component_receipts["contracts"]["contract_count"], 79)
        serialized = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn("fixture-signing-secret-v1", serialized)
        self.assertNotIn("subject_id", serialized)

    def test_quality_gate_has_stable_content_address(self) -> None:
        first = self.gate.evaluate_file(FIXTURE)
        second = self.gate.evaluate_file(FIXTURE)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertRegex(first.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_mapping_evaluation_uses_temporary_replay_boundary(self) -> None:
        report = self.gate.evaluate(copy.deepcopy(self.fixture))
        self.assertTrue(report.passed)
        self.assertEqual(report.context_key, CONTEXT)
        self.assertEqual(report.component_receipts["replay"]["case_count"], 1)

    def test_convenience_function_matches_gate_instance(self) -> None:
        expected = self.gate.evaluate_file(FIXTURE).to_dict()
        actual = evaluate_frontier_quality_gate(FIXTURE).to_dict()
        self.assertEqual(actual, expected)

    def test_quality_gate_reviews_failed_fixture_evaluation(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["pipelines"]["workbench"]["accessibility_surface"]["contrast"] = False
        report = self.gate.evaluate(fixture)
        self.assertFalse(report.passed)
        self.assertEqual(report.state, QualityGateState.REVIEW)
        self.assertIn("fixture-evaluation", report.failed_check_ids)
        self.assertIn("scenario-matrix", report.failed_check_ids)
        self.assertIn("fixture-check-floor", report.passed_check_ids)

    def test_quality_gate_reviews_a_public_data_boundary_failure(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["pipelines"]["validation"]["risk_records"][0]["patient_id"] = "blocked"
        report = self.gate.evaluate(fixture)
        self.assertFalse(report.passed)
        self.assertIn("public-data-audit", report.failed_check_ids)
        self.assertEqual(report.component_receipts["data"]["accepted"], False)

    def test_quality_gate_reviews_contract_count_drift(self) -> None:
        class IncompleteGate(FrontierQualityGate):
            expected_contract_count = 80

        report = IncompleteGate().evaluate(self.fixture)
        self.assertFalse(report.passed)
        self.assertIn("contract-count", report.failed_check_ids)
        self.assertEqual(report.component_receipts["contracts"]["contract_count"], 79)

    def test_quality_gate_reviews_capability_count_drift(self) -> None:
        class IncompleteGate(FrontierQualityGate):
            expected_capability_count = 17

        report = IncompleteGate().evaluate(self.fixture)
        self.assertFalse(report.passed)
        self.assertIn("capability-count", report.failed_check_ids)

    def test_quality_gate_reviews_reduced_fixture_check_floor(self) -> None:
        class StrictGate(FrontierQualityGate):
            expected_fixture_checks = 50

        report = StrictGate().evaluate(self.fixture)
        self.assertFalse(report.passed)
        self.assertIn("fixture-check-floor", report.failed_check_ids)

    def test_quality_gate_reviews_review_scenario_floor_drift(self) -> None:
        class StrictGate(FrontierQualityGate):
            expected_review_scenarios = 5

        report = StrictGate().evaluate(self.fixture)
        self.assertFalse(report.passed)
        self.assertIn("scenario-review-floor", report.failed_check_ids)

    def test_quality_gate_metadata_requires_text_identifiers(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["fixture_id"] = None
        with self.assertRaises(ValidationError):
            self.gate.evaluate(fixture)

    def test_quality_gate_metadata_requires_context_object(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["context"] = "wrong"
        with self.assertRaises(ValidationError):
            self.gate.evaluate(fixture)

    def test_quality_gate_preserves_evidence_boundary(self) -> None:
        report = self.gate.evaluate_file(FIXTURE)
        self.assertEqual(
            report.evidence_boundary,
            (
                "deterministic repository contract evaluation; no biological, clinical, "
                "or transport claim"
            ),
        )

    def test_quality_gate_check_serializes_observed_mapping(self) -> None:
        check = QualityGateCheck(
            "example",
            "one requirement",
            {"state": "accepted", "count": 1},
            True,
            "a deterministic test check",
        )
        self.assertEqual(check.to_dict()["check_id"], "example")
        self.assertEqual(check.to_dict()["observed"]["count"], 1)

    def test_quality_gate_check_rejects_blank_fields(self) -> None:
        with self.assertRaises(ValidationError):
            QualityGateCheck(" ", "requirement", True, True, "detail")
        with self.assertRaises(ValidationError):
            QualityGateCheck("check", " ", True, True, "detail")
        with self.assertRaises(ValidationError):
            QualityGateCheck("check", "requirement", True, True, " ")

    def test_quality_gate_report_serializes_counts(self) -> None:
        payload = self.gate.evaluate_file(FIXTURE).to_dict()
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["state"], "accepted")
        self.assertEqual(payload["check_count"], 12)
        self.assertEqual(payload["passed_count"], 12)
        self.assertEqual(payload["failed_count"], 0)

    def test_quality_gate_can_write_report_for_ci_consumers(self) -> None:
        report = self.gate.evaluate_file(FIXTURE)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "quality.json"
            path.write_text(
                json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8"
            )
            loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(loaded["passed"])
        self.assertEqual(loaded["fixture_id"], report.fixture_id)


if __name__ == "__main__":
    unittest.main()

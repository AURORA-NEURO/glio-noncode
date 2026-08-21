from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.identity_public_data import IdentityDataState
from glio_noncode.identity_quality_gate import (
    IdentityQualityGate,
    evaluate_identity_quality_gate,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "examples" / "identity-public-aggregate.json"


class IdentityQualityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_checked_in_quality_gate_passes_twelve_checks(self) -> None:
        report = evaluate_identity_quality_gate(FIXTURE)
        self.assertTrue(report.passed)
        self.assertEqual(report.state, IdentityDataState.ACCEPTED)
        self.assertEqual(len(report.checks), 12)
        self.assertEqual(report.failed_check_ids, ())

    def test_component_receipts_cover_every_gate_input(self) -> None:
        report = evaluate_identity_quality_gate(FIXTURE)
        self.assertEqual(
            set(report.component_receipts),
            {"data", "fixture", "replay", "scenarios", "contracts"},
        )
        self.assertEqual(report.component_receipts["fixture"]["check_count"], 37)
        self.assertEqual(report.component_receipts["scenarios"]["scenario_count"], 12)
        self.assertEqual(report.component_receipts["contracts"]["contract_count"], 4)

    def test_quality_gate_is_deterministic(self) -> None:
        first = evaluate_identity_quality_gate(FIXTURE)
        second = evaluate_identity_quality_gate(FIXTURE)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_quality_gate_exposes_failed_fixture_check(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["records"][0]["payload"]["query"] = "missing-query"
        gate = IdentityQualityGate()
        report = gate.evaluator.evaluate(raw)
        self.assertFalse(report.passed)
        self.assertIn("positive:equivalence:rs121913502", report.failed_check_ids)

    def test_quality_gate_contract_count_is_explicit(self) -> None:
        self.assertEqual(IdentityQualityGate.expected_contract_count, 4)
        self.assertEqual(IdentityQualityGate.expected_fixture_checks, 37)
        self.assertEqual(IdentityQualityGate.expected_scenario_count, 12)

    def test_report_to_dict_contains_pass_counts(self) -> None:
        payload = evaluate_identity_quality_gate(FIXTURE).to_dict()
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["check_count"], 12)
        self.assertEqual(payload["passed_count"], 12)

    def test_quality_gate_context_and_sources_are_exact(self) -> None:
        report = evaluate_identity_quality_gate(FIXTURE)
        self.assertIn("GRCh38|diffuse_glioma|adult", report.context_key)
        self.assertEqual(
            report.source_ids,
            ("ncbi-clinvar-rs121913502", "ncbi-grch38-reference-assembly"),
        )

    def test_quality_gate_rejects_sensitive_fixture_boundary(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["records"][0]["payload"]["secret"] = "restricted"
        report = IdentityQualityGate().evaluator.evaluate(raw)
        self.assertFalse(report.passed)
        self.assertIn("data-boundary:identity-catalog", report.failed_check_ids)

    def test_quality_gate_reports_source_context_mutation(self) -> None:
        raw = copy.deepcopy(self.raw)
        raw["source_receipts"][0]["context_key"] = raw["source_receipts"][0][
            "context_key"
        ].replace("tumor_core", "core_margin")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mutated.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            report = IdentityQualityGate().evaluate_file(path)
        self.assertFalse(report.passed)
        self.assertIn("public-data-audit", report.failed_check_ids)
        self.assertIn("replay-integrity", report.failed_check_ids)

    def test_quality_check_ids_and_addresses_are_unique(self) -> None:
        report = evaluate_identity_quality_gate(FIXTURE)
        check_ids = tuple(check.check_id for check in report.checks)
        addresses = tuple(check.content_address for check in report.checks)
        self.assertEqual(len(check_ids), len(set(check_ids)))
        self.assertEqual(len(addresses), len(set(addresses)))
        self.assertTrue(all(address.startswith("sha256:") for address in addresses))

    def test_contract_component_receipt_is_addressed(self) -> None:
        report = evaluate_identity_quality_gate(FIXTURE)
        contracts = report.component_receipts["contracts"]
        self.assertEqual(contracts["contract_count"], 4)
        self.assertRegex(contracts["content_address"], r"^sha256:[0-9a-f]{64}$")

    def test_quality_state_accepts_expected_partial_positive_entry(self) -> None:
        report = evaluate_identity_quality_gate(FIXTURE)
        reconciliation = report.component_receipts["fixture"]["positive_reports"][
            "reconciliation:rs121913502"
        ]
        self.assertEqual(reconciliation["state"], "partial")
        self.assertTrue(report.passed)


if __name__ == "__main__":
    unittest.main()

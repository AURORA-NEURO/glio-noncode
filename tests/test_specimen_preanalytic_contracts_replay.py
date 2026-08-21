from __future__ import annotations

import unittest
from pathlib import Path

from glio_noncode.specimen_preanalytic_contracts import default_specimen_preanalytic_contracts
from glio_noncode.specimen_preanalytic_public_data import SpecimenPreanalyticFixtureCatalog
from glio_noncode.specimen_preanalytic_replay import (
    SpecimenPreanalyticReplayExpectation,
    replay_specimen_preanalytic_fixture,
)
from glio_noncode.specimen_preanalytic_scenario_matrix import (
    evaluate_specimen_preanalytic_scenarios,
)

FIXTURE = Path("examples/specimen-preanalytic-public-aggregate.json")


class SpecimenPreanalyticContractsReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = SpecimenPreanalyticFixtureCatalog.from_file(FIXTURE)

    def test_contract_registry_covers_exactly_four_operations(self) -> None:
        registry = default_specimen_preanalytic_contracts()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(
            {item.operation.value for item in registry.contracts},
            {"preanalytic_quality", "assay_lineage", "identity_adjudication", "context_envelope"},
        )
        self.assertTrue(registry.content_address.startswith("sha256:"))

    def test_contracts_retain_required_fields_and_safety_boundaries(self) -> None:
        registry = default_specimen_preanalytic_contracts()
        for contract in registry.contracts:
            self.assertTrue(contract.required_input_fields)
            self.assertTrue(contract.output_fields)
            self.assertTrue(contract.safety_boundary)
            self.assertTrue(contract.accepts_result_state("review"))

    def test_replay_passes_declared_floors(self) -> None:
        report = replay_specimen_preanalytic_fixture(self.catalog)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.entries), 1)
        self.assertEqual(report.entries[0].failed_expectations, ())

    def test_replay_detects_context_drift(self) -> None:
        expectation = SpecimenPreanalyticReplayExpectation(
            self.catalog.fixture_id,
            "GRCh38|drift|adult|stem_like|core|untreated",
            12,
            120,
            4,
            8,
        )
        report = replay_specimen_preanalytic_fixture(self.catalog, expectation)
        self.assertFalse(report.passed)
        self.assertIn("context_key", report.entries[0].failed_expectations)

    def test_scenario_matrix_preserves_four_positive_and_eight_controls(self) -> None:
        report = evaluate_specimen_preanalytic_scenarios(self.catalog)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.scenarios), 12)
        self.assertEqual(report.positive_count, 4)
        self.assertEqual(report.control_count, 8)
        self.assertTrue(
            all(item.content_address.startswith("sha256:") for item in report.scenarios)
        )

    def test_scenario_matrix_is_deterministic(self) -> None:
        first = evaluate_specimen_preanalytic_scenarios(self.catalog)
        second = evaluate_specimen_preanalytic_scenarios(self.catalog)
        self.assertEqual(first.content_address, second.content_address)


if __name__ == "__main__":
    unittest.main()

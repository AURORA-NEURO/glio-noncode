from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from glio_noncode.specimen_lineage_contracts import default_specimen_lineage_contracts
from glio_noncode.specimen_lineage_public_data import (
    SpecimenLineageFixtureCatalog,
    SpecimenLineageOperation,
)
from glio_noncode.specimen_lineage_replay import (
    SpecimenLineageReplayExpectation,
    replay_specimen_lineage_fixtures,
)
from glio_noncode.specimen_lineage_scenario_matrix import evaluate_specimen_lineage_scenarios

FIXTURE = Path("examples/specimen-lineage-public-aggregate.json")


class SpecimenLineageContractReplayTests(unittest.TestCase):
    def test_contract_registry_covers_exactly_four_operations(self) -> None:
        registry = default_specimen_lineage_contracts()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(
            {contract.operation for contract in registry.contracts},
            set(SpecimenLineageOperation),
        )
        self.assertTrue(registry.content_address.startswith("sha256:"))

    def test_contract_states_accept_all_fixture_expectations(self) -> None:
        catalog = SpecimenLineageFixtureCatalog.from_file(FIXTURE)
        registry = default_specimen_lineage_contracts()
        for record in catalog.records:
            self.assertTrue(
                registry.get(record.operation).accepts_result_state(record.expected_result_state)
            )

    def test_contract_manifest_contains_safety_notes_and_input_fields(self) -> None:
        manifest = default_specimen_lineage_contracts().to_dict()
        self.assertEqual(manifest["contract_count"], 4)
        for contract in manifest["contracts"]:
            self.assertTrue(contract["input_fields"])
            self.assertTrue(contract["safety_notes"])
            self.assertTrue(contract["content_address"].startswith("sha256:"))

    def test_replay_passes_one_fixture(self) -> None:
        catalog = SpecimenLineageFixtureCatalog.from_file(FIXTURE)
        expectation = SpecimenLineageReplayExpectation(
            catalog.fixture_id,
            catalog.context_key,
            catalog.source_ids,
            minimum_checks=159,
            minimum_positive_records=4,
            minimum_control_records=8,
        )
        report = replay_specimen_lineage_fixtures([FIXTURE], expectation=expectation)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.entries), 1)

    def test_replay_detects_context_drift(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        payload["context_key"] = "GRCh38|drift|adult|drift|drift|drift"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drift.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            catalog = SpecimenLineageFixtureCatalog.from_file(FIXTURE)
            expectation = SpecimenLineageReplayExpectation(
                catalog.fixture_id,
                catalog.context_key,
                catalog.source_ids,
                minimum_checks=159,
                minimum_positive_records=4,
                minimum_control_records=8,
            )
            report = replay_specimen_lineage_fixtures([path], expectation=expectation)
            self.assertFalse(report.passed)
            self.assertIn("context_drift", report.issue_codes)

    def test_replay_is_deterministic(self) -> None:
        catalog = SpecimenLineageFixtureCatalog.from_file(FIXTURE)
        expectation = SpecimenLineageReplayExpectation(
            catalog.fixture_id,
            catalog.context_key,
            catalog.source_ids,
            minimum_checks=159,
            minimum_positive_records=4,
            minimum_control_records=8,
        )
        first = replay_specimen_lineage_fixtures([FIXTURE], expectation=expectation)
        second = replay_specimen_lineage_fixtures([FIXTURE], expectation=expectation)
        self.assertEqual(first.content_address, second.content_address)

    def test_scenario_matrix_passes_all_rows(self) -> None:
        report = evaluate_specimen_lineage_scenarios(FIXTURE)
        self.assertTrue(report.passed)
        self.assertEqual(len(report.scenarios), 12)
        self.assertEqual(report.failed_scenarios, ())

    def test_scenario_matrix_keeps_review_states_visible(self) -> None:
        report = evaluate_specimen_lineage_scenarios(FIXTURE)
        states = {item.scenario_id: item.observed_state for item in report.scenarios}
        self.assertEqual(states["control-region-cycle"], "contradictory")
        self.assertEqual(states["control-treatment-overlap"], "ambiguous")
        self.assertEqual(states["control-longitudinal-missing-predecessor"], "partial")


if __name__ == "__main__":
    unittest.main()

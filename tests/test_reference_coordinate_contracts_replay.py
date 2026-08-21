from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.errors import ValidationError
from glio_noncode.reference_coordinate_contracts import (
    ReferenceCoordinateContract,
    ReferenceCoordinateContractRegistry,
    default_reference_coordinate_contracts,
)
from glio_noncode.reference_coordinate_public_data import ReferenceCoordinateFixtureCatalog
from glio_noncode.reference_coordinate_replay import (
    ReferenceCoordinateReplayExpectation,
    default_reference_coordinate_expectation,
    replay_reference_coordinate_fixture,
)
from glio_noncode.reference_coordinate_scenario_matrix import (
    evaluate_reference_coordinate_scenarios,
)

FIXTURE = Path(__file__).parents[1] / "examples" / "reference-coordinate-public-aggregate.json"


class ReferenceCoordinateContractsReplayTests(unittest.TestCase):
    def load(self) -> ReferenceCoordinateFixtureCatalog:
        return ReferenceCoordinateFixtureCatalog.from_file(FIXTURE)

    def test_contract_registry_covers_exactly_four_capabilities(self) -> None:
        registry = default_reference_coordinate_contracts()
        self.assertEqual(len(registry.all()), 4)
        self.assertEqual(
            tuple(contract.capability_id for contract in registry.all()),
            ("GNC-D04-C01", "GNC-D04-C02", "GNC-D04-C03", "GNC-D04-C04"),
        )
        manifest = registry.manifest()
        self.assertEqual(manifest["operation_count"], 4)
        self.assertTrue(manifest["content_address"].startswith("sha256:"))

    def test_contracts_retain_required_fields_and_boundaries(self) -> None:
        registry = default_reference_coordinate_contracts()
        for contract in registry.all():
            self.assertTrue(contract.required_fields)
            self.assertTrue(contract.output_fields)
            self.assertTrue(contract.safety_boundary)
            self.assertTrue(contract.issue_codes)
            self.assertEqual(
                contract.validate_payload({"unrelated": 1})[0], contract.required_fields[0]
            )

    def test_duplicate_contract_operations_are_rejected(self) -> None:
        contract = default_reference_coordinate_contracts().all()[0]
        with self.assertRaises(ValidationError):
            ReferenceCoordinateContractRegistry((contract, contract))

    def test_empty_contract_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ReferenceCoordinateContract(
                operation=default_reference_coordinate_contracts().all()[0].operation,
                capability_id="GNC-D04-X01",
                title="bad",
                required_fields=(),
                output_fields=("state",),
                safety_boundary="bounded",
                issue_codes=("bad",),
                supported_states=("invalid",),
            )

    def test_replay_passes_declared_identity_and_floors(self) -> None:
        catalog = self.load()
        expectation = default_reference_coordinate_expectation(catalog)
        report = replay_reference_coordinate_fixture(catalog, expectation)
        self.assertEqual(report.state, "accepted")
        self.assertTrue(report.passed)
        self.assertEqual(len(report.checks), 16)
        self.assertEqual(report.failed_check_ids, ())

    def test_replay_detects_context_drift(self) -> None:
        catalog = self.load()
        expectation = ReferenceCoordinateReplayExpectation(
            fixture_id=catalog.fixture_id,
            fixture_version=catalog.fixture_version,
            context_key="GRCh37|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline",
            source_ids=catalog.source_ids,
            record_ids=tuple(catalog.record_ids),
            operation_ids=catalog.operation_ids,
            minimum_check_count=130,
            minimum_positive_count=4,
            minimum_control_count=12,
        )
        report = replay_reference_coordinate_fixture(catalog, expectation)
        self.assertEqual(report.state, "review")
        self.assertIn("context-key", report.failed_check_ids)
        self.assertIn("replay-context", report.failed_check_ids)

    def test_replay_detects_floor_drift(self) -> None:
        catalog = self.load()
        expectation = ReferenceCoordinateReplayExpectation(
            fixture_id=catalog.fixture_id,
            fixture_version=catalog.fixture_version,
            context_key=catalog.context_key,
            source_ids=catalog.source_ids,
            record_ids=tuple(catalog.record_ids),
            operation_ids=catalog.operation_ids,
            minimum_check_count=999,
            minimum_positive_count=4,
            minimum_control_count=12,
        )
        report = replay_reference_coordinate_fixture(catalog, expectation)
        self.assertEqual(report.state, "review")
        self.assertIn("evaluation-check-floor", report.failed_check_ids)

    def test_scenario_matrix_has_four_positive_and_twelve_controls(self) -> None:
        report = evaluate_reference_coordinate_scenarios(self.load())
        self.assertTrue(report.passed)
        self.assertEqual(len(report.results), 16)
        self.assertEqual(sum(result.role.value == "positive" for result in report.results), 4)
        self.assertEqual(sum(result.role.value == "control" for result in report.results), 12)

    def test_scenario_matrix_is_deterministic(self) -> None:
        catalog = self.load()
        first = evaluate_reference_coordinate_scenarios(catalog)
        second = evaluate_reference_coordinate_scenarios(catalog)
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_mutated_expected_issue_is_observable(self) -> None:
        raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
        raw["records"][4]["expected_issue_codes"] = ["chain_unmapped"]
        mutated = ReferenceCoordinateFixtureCatalog.from_mapping(raw)
        report = evaluate_reference_coordinate_scenarios(mutated)
        self.assertEqual(report.state, "review")
        self.assertIn("d04-c02-positive-forward-chain", report.failed_scenario_ids)


if __name__ == "__main__":
    unittest.main()

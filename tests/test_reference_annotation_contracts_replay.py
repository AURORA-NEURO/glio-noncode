from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.reference_annotation_contracts import default_reference_annotation_contracts
from glio_noncode.reference_annotation_fixture_eval import evaluate_reference_annotation_fixture
from glio_noncode.reference_annotation_public_data import ReferenceAnnotationOperation
from glio_noncode.reference_annotation_replay import (
    build_reference_annotation_expectation,
    replay_reference_annotation_evaluation,
)
from glio_noncode.reference_annotation_scenario_matrix import (
    evaluate_reference_annotation_scenarios,
)


class ReferenceAnnotationContractsReplayTests(unittest.TestCase):
    def test_registry_has_exactly_four_ordered_contracts(self) -> None:
        registry = default_reference_annotation_contracts()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(
            tuple(contract.operation for contract in registry.contracts),
            tuple(ReferenceAnnotationOperation),
        )

    def test_contracts_have_unique_fields_and_content_addresses(self) -> None:
        for contract in default_reference_annotation_contracts().contracts:
            self.assertEqual(
                len(contract.required_input_fields), len(set(contract.required_input_fields))
            )
            self.assertEqual(len(contract.output_fields), len(set(contract.output_fields)))
            self.assertTrue(contract.content_address.startswith("sha256:"))

    def test_contract_payload_validation_reports_missing_fields(self) -> None:
        contract = default_reference_annotation_contracts().contracts[0]
        self.assertIn("input_text", contract.validate_payload({}))
        self.assertEqual(
            contract.validate_payload(
                {"input_text": "x", "input_format": "gtf", "query": {}, "assembly": "GRCh38"}
            ),
            (),
        )

    def test_manifest_is_deterministic(self) -> None:
        first = default_reference_annotation_contracts().manifest()
        second = default_reference_annotation_contracts().manifest()
        self.assertEqual(first, second)
        self.assertTrue(first["content_address"].startswith("sha256:"))

    def test_unknown_operation_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            default_reference_annotation_contracts().by_operation("not-an-operation")

    def test_replay_accepts_identity_and_floors(self) -> None:
        evaluation = evaluate_reference_annotation_fixture()
        replay = replay_reference_annotation_evaluation(evaluation)
        self.assertTrue(replay.accepted)
        self.assertEqual(len(replay.checks), 12)

    def test_replay_detects_context_drift(self) -> None:
        evaluation = evaluate_reference_annotation_fixture()
        replay = replay_reference_annotation_evaluation(
            evaluation,
            expected_context_key="GRCh37|diffuse_glioma|adult|bulk_tumor|reference_plane|baseline",
        )
        self.assertFalse(replay.accepted)
        self.assertIn("context-key", replay.failed_check_ids)

    def test_replay_detects_check_floor_drift(self) -> None:
        evaluation = evaluate_reference_annotation_fixture()
        expectation = build_reference_annotation_expectation(evaluation_check_floor=999)
        replay = replay_reference_annotation_evaluation(evaluation, expectation=expectation)
        self.assertFalse(replay.accepted)
        self.assertIn("check-floor", replay.failed_check_ids)

    def test_scenario_matrix_has_sixteen_passed_rows(self) -> None:
        matrix = evaluate_reference_annotation_scenarios()
        self.assertTrue(matrix.accepted)
        self.assertEqual(len(matrix.results), 16)
        self.assertEqual(matrix.positive_count, 4)
        self.assertEqual(matrix.control_count, 12)

    def test_scenario_matrix_is_deterministic(self) -> None:
        first = evaluate_reference_annotation_scenarios()
        second = evaluate_reference_annotation_scenarios()
        self.assertEqual(first.content_address, second.content_address)

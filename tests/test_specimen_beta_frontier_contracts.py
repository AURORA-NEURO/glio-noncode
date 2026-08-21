from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_beta_frontier_contracts import (
    SpecimenBetaFrontierContractRegistry,
    default_specimen_beta_frontier_contracts,
)
from glio_noncode.specimen_beta_frontier_public_data import SpecimenBetaFrontierOperation


class SpecimenBetaFrontierContractTests(unittest.TestCase):
    def test_registry_covers_four_operations(self) -> None:
        registry = default_specimen_beta_frontier_contracts()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(
            {contract.operation for contract in registry.contracts},
            set(SpecimenBetaFrontierOperation),
        )
        self.assertTrue(registry.content_address.startswith("sha256:"))

    def test_contract_capability_ids_are_c05_through_c08(self) -> None:
        registry = default_specimen_beta_frontier_contracts()
        self.assertEqual(
            {contract.capability_id for contract in registry.contracts},
            {"GNC-D03-C05", "GNC-D03-C06", "GNC-D03-C07", "GNC-D03-C08"},
        )

    def test_origin_contract_accepts_supported_and_review_states(self) -> None:
        contract = default_specimen_beta_frontier_contracts().get("origin")
        self.assertTrue(contract.accepts_result_state("supported"))
        self.assertTrue(contract.accepts_result_state("ambiguous"))
        self.assertFalse(contract.accepts_result_state("unrecognized"))

    def test_unknown_operation_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            default_specimen_beta_frontier_contracts().get("missing")

    def test_contract_registry_rejects_duplicate_operations(self) -> None:
        registry = default_specimen_beta_frontier_contracts()
        with self.assertRaises(ValidationError):
            SpecimenBetaFrontierContractRegistry(
                contracts=(registry.contracts[0], registry.contracts[0])
            )

    def test_every_contract_has_safety_notes_and_address(self) -> None:
        for contract in default_specimen_beta_frontier_contracts().contracts:
            self.assertTrue(contract.safety_notes)
            self.assertTrue(contract.content_address.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()

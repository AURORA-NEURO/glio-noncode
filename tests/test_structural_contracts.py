"""Contract registry tests for Domain 02 structural operations."""

from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.structural_contracts import (
    StructuralContractRegistry,
    StructuralOperationContract,
    default_structural_contract_registry,
)
from glio_noncode.structural_public_data import StructuralOperation


class StructuralContractTests(unittest.TestCase):
    def test_default_registry_has_four_unique_contracts(self) -> None:
        registry = default_structural_contract_registry()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(
            {contract.operation for contract in registry.contracts},
            set(StructuralOperation),
        )
        self.assertEqual(
            len({contract.contract_id for contract in registry.contracts}),
            4,
        )

    def test_lookup_accepts_enum_and_string(self) -> None:
        registry = default_structural_contract_registry()
        reconstruction = registry.get(StructuralOperation.RECONSTRUCTION)
        consensus = registry.get("consensus")
        self.assertEqual(reconstruction.capability_id, "GNC-D02-C01")
        self.assertEqual(consensus.capability_id, "GNC-D02-C02")
        self.assertTrue(reconstruction.accepts("eventful"))
        self.assertTrue(reconstruction.reviews("error"))

    def test_manifest_is_addressed_and_versioned(self) -> None:
        manifest = default_structural_contract_registry().manifest()
        self.assertEqual(manifest["schema_version"], "structural-contracts-v1")
        self.assertEqual(manifest["contract_count"], 4)
        self.assertRegex(manifest["content_address"], r"^sha256:[0-9a-f]{64}$")
        for contract in manifest["contracts"]:
            self.assertTrue(contract["input_fields"])
            self.assertTrue(contract["output_fields"])
            self.assertTrue(contract["required_provenance"])

    def test_contract_input_and_output_fields_are_unique(self) -> None:
        for contract in default_structural_contract_registry().contracts:
            self.assertEqual(len(contract.input_fields), len(set(contract.input_fields)))
            self.assertEqual(len(contract.output_fields), len(set(contract.output_fields)))

    def test_contract_requires_both_state_sets(self) -> None:
        with self.assertRaises(ValidationError):
            StructuralOperationContract(
                "contract",
                "GNC-D02-C01",
                StructuralOperation.RECONSTRUCTION,
                ("input",),
                ("output",),
                ("source",),
                (),
                ("review",),
                (),
            )

    def test_registry_rejects_duplicate_contract_ids(self) -> None:
        contract = default_structural_contract_registry().contracts[0]
        with self.assertRaises(ValidationError):
            StructuralContractRegistry((contract, contract))

    def test_contract_addresses_are_stable(self) -> None:
        registry = default_structural_contract_registry()
        first = tuple(contract.content_address for contract in registry.contracts)
        second = tuple(contract.content_address for contract in default_structural_contract_registry().contracts)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

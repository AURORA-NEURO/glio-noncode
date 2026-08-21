"""Contract registry tests for Domain 03 C01-C04."""

from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.specimen_frontier_contracts import (
    SpecimenFrontierContractRegistry,
    default_specimen_frontier_contract_registry,
)
from glio_noncode.specimen_frontier_public_data import SpecimenFrontierOperation


class SpecimenFrontierContractTests(unittest.TestCase):
    def test_default_registry_has_four_unique_capability_contracts(self) -> None:
        registry = default_specimen_frontier_contract_registry()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(
            {contract.capability_id for contract in registry.contracts},
            {"GNC-D03-C01", "GNC-D03-C02", "GNC-D03-C03", "GNC-D03-C04"},
        )
        self.assertEqual(
            {contract.operation for contract in registry.contracts},
            set(SpecimenFrontierOperation),
        )

    def test_contracts_have_unique_addresses_and_review_states(self) -> None:
        registry = default_specimen_frontier_contract_registry()
        addresses = {contract.content_address for contract in registry.contracts}
        self.assertEqual(len(addresses), 4)
        for contract in registry.contracts:
            self.assertTrue(contract.input_fields)
            self.assertTrue(contract.output_fields)
            self.assertTrue(contract.required_provenance)
            self.assertTrue(contract.safety_notes)
            self.assertTrue(contract.review_result_states)

    def test_manifest_is_stable_and_versioned(self) -> None:
        registry = default_specimen_frontier_contract_registry()
        first = registry.manifest()
        second = registry.manifest()
        self.assertEqual(first, second)
        self.assertEqual(first["schema_version"], "specimen-frontier-contracts-v1")
        self.assertEqual(first["contract_count"], 4)
        self.assertTrue(first["content_address"].startswith("sha256:"))

    def test_lookup_accepts_enum_and_string(self) -> None:
        registry = default_specimen_frontier_contract_registry()
        self.assertEqual(
            registry.get(SpecimenFrontierOperation.PURITY_PLOIDY).capability_id,
            "GNC-D03-C03",
        )
        self.assertEqual(
            registry.get("sample_integrity").capability_id,
            "GNC-D03-C04",
        )

    def test_unknown_operation_and_duplicate_contracts_fail(self) -> None:
        registry = default_specimen_frontier_contract_registry()
        with self.assertRaises(ValidationError):
            registry.get("missing")
        with self.assertRaises(ValidationError):
            SpecimenFrontierContractRegistry(
                contracts=(registry.contracts[0], registry.contracts[0])
            )

    def test_contract_state_predicates_are_explicit(self) -> None:
        registry = default_specimen_frontier_contract_registry()
        ontology = registry.get("ontology_mapping")
        self.assertTrue(ontology.accepts("supported"))
        self.assertTrue(ontology.reviews("ambiguous"))
        self.assertFalse(ontology.accepts("ambiguous"))
        purity = registry.get("purity_ploidy")
        self.assertTrue(purity.accepts("accepted"))
        self.assertTrue(purity.reviews("review"))


if __name__ == "__main__":
    unittest.main()

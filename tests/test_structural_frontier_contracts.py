"""Contract registry tests for Domain 02 C13-C16."""

from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.structural_frontier_contracts import (
    StructuralFrontierContractRegistry,
    StructuralFrontierOperationContract,
    default_structural_frontier_contract_registry,
)
from glio_noncode.structural_frontier_public_data import StructuralFrontierOperation


class StructuralFrontierContractTests(unittest.TestCase):
    def test_default_registry_has_four_addressed_contracts(self) -> None:
        registry = default_structural_frontier_contract_registry()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual({contract.operation for contract in registry.contracts}, set(StructuralFrontierOperation))
        self.assertTrue(all(contract.content_address.startswith("sha256:") for contract in registry.contracts))

    def test_manifest_has_stable_schema_and_address(self) -> None:
        registry = default_structural_frontier_contract_registry()
        manifest = registry.manifest()
        self.assertEqual(manifest["schema_version"], "structural-frontier-contracts-v1")
        self.assertEqual(manifest["contract_count"], 4)
        self.assertRegex(manifest["content_address"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(len(manifest["contracts"]), 4)

    def test_lookup_accepts_enum_and_string(self) -> None:
        registry = default_structural_frontier_contract_registry()
        first = registry.get(StructuralFrontierOperation.TANDEM_REPEAT)
        second = registry.get("tandem_repeat")
        self.assertEqual(first, second)
        self.assertEqual(first.capability_id, "GNC-D02-C13")

    def test_contract_fields_are_unique_and_nonempty(self) -> None:
        for contract in default_structural_frontier_contract_registry().contracts:
            self.assertTrue(contract.input_fields)
            self.assertTrue(contract.output_fields)
            self.assertTrue(contract.required_provenance)
            self.assertTrue(contract.safety_notes)
            self.assertEqual(len(contract.input_fields), len(set(contract.input_fields)))
            self.assertEqual(len(contract.output_fields), len(set(contract.output_fields)))
            self.assertEqual(len(contract.required_provenance), len(set(contract.required_provenance)))

    def test_result_state_sets_match_positive_and_review_semantics(self) -> None:
        registry = default_structural_frontier_contract_registry()
        self.assertTrue(registry.get("tandem_repeat").accepts("accepted"))
        self.assertTrue(registry.get("compound_haplotype").reviews("review"))
        self.assertTrue(registry.get("breakpoint_uncertainty").reviews("review"))
        self.assertTrue(registry.get("structural_evidence_export").accepts("published"))
        self.assertTrue(registry.get("structural_evidence_export").reviews("invalid"))

    def test_unknown_operation_is_rejected(self) -> None:
        with self.assertRaises((ValidationError, ValueError)):
            default_structural_frontier_contract_registry().get("unknown")

    def test_empty_registry_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValidationError, "must not be empty"):
            StructuralFrontierContractRegistry(())

    def test_duplicate_contract_ids_are_rejected(self) -> None:
        registry = default_structural_frontier_contract_registry()
        duplicate = registry.contracts[0]
        with self.assertRaisesRegex(ValidationError, "IDs must be unique"):
            StructuralFrontierContractRegistry(registry.contracts + (duplicate,))

    def test_duplicate_operations_are_rejected(self) -> None:
        registry = default_structural_frontier_contract_registry()
        duplicate = registry.contracts[0]
        changed = StructuralFrontierOperationContract(
            contract_id="different-contract",
            capability_id="GNC-D02-C99",
            operation=duplicate.operation,
            input_fields=duplicate.input_fields,
            output_fields=duplicate.output_fields,
            required_provenance=duplicate.required_provenance,
            accepted_result_states=duplicate.accepted_result_states,
            review_result_states=duplicate.review_result_states,
            safety_notes=duplicate.safety_notes,
        )
        with self.assertRaisesRegex(ValidationError, "operations must be unique"):
            StructuralFrontierContractRegistry(registry.contracts + (changed,))

    def test_contract_serialization_contains_no_operation_payload(self) -> None:
        manifest = default_structural_frontier_contract_registry().manifest()
        serialized = str(manifest)
        self.assertNotIn("raw_record", serialized)
        self.assertNotIn("patient_id", serialized)

    def test_contract_addresses_are_deterministic(self) -> None:
        first = default_structural_frontier_contract_registry().manifest()
        second = default_structural_frontier_contract_registry().manifest()
        self.assertEqual(first["content_address"], second["content_address"])
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

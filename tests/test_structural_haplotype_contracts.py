"""Operation contract tests for Domain 02 C09-C12."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from glio_noncode.errors import ValidationError
from glio_noncode.structural_haplotype_contracts import (
    StructuralHaplotypeContractRegistry,
    StructuralHaplotypeOperationContract,
    default_structural_haplotype_contract_registry,
)
from glio_noncode.structural_haplotype_public_data import StructuralHaplotypeOperation


class StructuralHaplotypeContractTests(unittest.TestCase):
    def test_default_registry_contains_four_ordered_contracts(self) -> None:
        registry = default_structural_haplotype_contract_registry()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(
            tuple(contract.capability_id for contract in registry.contracts),
            ("GNC-D02-C09", "GNC-D02-C10", "GNC-D02-C11", "GNC-D02-C12"),
        )
        self.assertEqual({contract.operation for contract in registry.contracts}, set(StructuralHaplotypeOperation))

    def test_manifest_is_addressed_and_serializable(self) -> None:
        manifest = default_structural_haplotype_contract_registry().manifest()
        self.assertEqual(manifest["schema_version"], "structural-haplotype-contracts-v1")
        self.assertEqual(manifest["contract_count"], 4)
        self.assertRegex(manifest["content_address"], r"^sha256:[0-9a-f]{64}$")
        serialized = json.dumps(manifest, sort_keys=True)
        self.assertIn("GNC-D02-C09-contract", serialized)
        self.assertIn("sequence homology", serialized)

    def test_lookup_accepts_enum_and_string(self) -> None:
        registry = default_structural_haplotype_contract_registry()
        self.assertEqual(registry.get(StructuralHaplotypeOperation.PHASED_HAPLOTYPE), registry.get("phased_haplotype"))
        self.assertEqual(registry.get("repeat_mobile_annotation").capability_id, "GNC-D02-C12")

    def test_contract_state_sets_and_sections_are_explicit(self) -> None:
        registry = default_structural_haplotype_contract_registry()
        for contract in registry.contracts:
            self.assertTrue(contract.input_fields)
            self.assertTrue(contract.output_fields)
            self.assertTrue(contract.required_provenance)
            self.assertTrue(contract.accepted_result_states)
            self.assertTrue(contract.review_result_states)
            self.assertTrue(contract.safety_notes)
            self.assertTrue(contract.accepts("supported"))
            self.assertTrue(contract.reviews("partial"))
            self.assertRegex(contract.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_field_declarations_are_unique(self) -> None:
        for contract in default_structural_haplotype_contract_registry().contracts:
            for field_name in ("input_fields", "output_fields", "required_provenance"):
                values = getattr(contract, field_name)
                self.assertEqual(len(values), len(set(values)), contract.contract_id)

    def test_unknown_operation_lookup_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            default_structural_haplotype_contract_registry().get("not-an-operation")

    def test_registry_rejects_duplicate_contract_ids(self) -> None:
        registry = default_structural_haplotype_contract_registry()
        with self.assertRaisesRegex(ValidationError, "IDs must be unique"):
            StructuralHaplotypeContractRegistry(registry.contracts[:2] + (registry.contracts[0],))

    def test_registry_rejects_duplicate_operations(self) -> None:
        registry = default_structural_haplotype_contract_registry()
        duplicate = replace(registry.contracts[0], contract_id="unique-duplicate-operation")
        with self.assertRaisesRegex(ValidationError, "operations must be unique"):
            StructuralHaplotypeContractRegistry(registry.contracts[:2] + (duplicate,))

    def test_contract_rejects_empty_sections(self) -> None:
        source = default_structural_haplotype_contract_registry().contracts[0]
        with self.assertRaisesRegex(ValidationError, "input_fields"):
            StructuralHaplotypeOperationContract(
                contract_id="empty-input",
                capability_id=source.capability_id,
                operation=source.operation,
                input_fields=(),
                output_fields=source.output_fields,
                required_provenance=source.required_provenance,
                accepted_result_states=source.accepted_result_states,
                review_result_states=source.review_result_states,
                safety_notes=source.safety_notes,
            )

    def test_contract_rejects_duplicate_fields(self) -> None:
        source = default_structural_haplotype_contract_registry().contracts[0]
        with self.assertRaisesRegex(ValidationError, "input_fields must be unique"):
            StructuralHaplotypeOperationContract(
                contract_id="duplicate-field",
                capability_id=source.capability_id,
                operation=source.operation,
                input_fields=("records", "records"),
                output_fields=source.output_fields,
                required_provenance=source.required_provenance,
                accepted_result_states=source.accepted_result_states,
                review_result_states=source.review_result_states,
                safety_notes=source.safety_notes,
            )

    def test_repeat_contract_preserves_annotation_boundary(self) -> None:
        contract = default_structural_haplotype_contract_registry().get("repeat_mobile_annotation")
        payload = contract.to_dict()
        self.assertEqual(payload["capability_id"], "GNC-D02-C12")
        self.assertIn("annotation_ids", payload["required_provenance"])
        self.assertIn("transposition", " ".join(payload["safety_notes"]))
        self.assertNotIn("raw_record", json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    unittest.main()

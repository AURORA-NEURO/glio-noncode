"""Operation contract tests for Domain 02 C05-C08."""

from __future__ import annotations

import json
import unittest
from dataclasses import replace

from glio_noncode.errors import ValidationError
from glio_noncode.structural_beta_contracts import (
    StructuralBetaContractRegistry,
    StructuralBetaOperationContract,
    default_structural_beta_contract_registry,
)
from glio_noncode.structural_beta_public_data import StructuralBetaOperation


class StructuralBetaContractTests(unittest.TestCase):
    def test_default_registry_contains_four_ordered_capability_contracts(self) -> None:
        registry = default_structural_beta_contract_registry()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(
            tuple(contract.capability_id for contract in registry.contracts),
            ("GNC-D02-C05", "GNC-D02-C06", "GNC-D02-C07", "GNC-D02-C08"),
        )
        self.assertEqual(
            {contract.operation for contract in registry.contracts},
            set(StructuralBetaOperation),
        )

    def test_manifest_is_content_addressed_and_serializable(self) -> None:
        manifest = default_structural_beta_contract_registry().manifest()
        self.assertEqual(manifest["schema_version"], "structural-beta-contracts-v1")
        self.assertEqual(manifest["contract_count"], 4)
        self.assertRegex(manifest["content_address"], r"^sha256:[0-9a-f]{64}$")
        serialized = json.dumps(manifest, sort_keys=True)
        self.assertIn("GNC-D02-C05-contract", serialized)
        self.assertIn("nearest-gene proximity", serialized)

    def test_lookup_accepts_enum_and_string_operation_names(self) -> None:
        registry = default_structural_beta_contract_registry()
        enum_contract = registry.get(StructuralBetaOperation.ECDNA)
        string_contract = registry.get("ecdna")
        self.assertEqual(enum_contract, string_contract)
        self.assertEqual(enum_contract.capability_id, "GNC-D02-C07")

    def test_contract_state_sets_are_explicit(self) -> None:
        registry = default_structural_beta_contract_registry()
        for contract in registry.contracts:
            self.assertTrue(contract.accepted_result_states)
            self.assertTrue(contract.review_result_states)
            self.assertTrue(contract.accepts("supported"))
            self.assertTrue(contract.reviews("abstained"))
            self.assertTrue(contract.input_fields)
            self.assertTrue(contract.output_fields)
            self.assertTrue(contract.required_provenance)
            self.assertTrue(contract.safety_notes)
            self.assertRegex(contract.content_address, r"^sha256:[0-9a-f]{64}$")

    def test_each_contract_has_unique_field_declarations(self) -> None:
        registry = default_structural_beta_contract_registry()
        for contract in registry.contracts:
            for field_name in ("input_fields", "output_fields", "required_provenance"):
                values = getattr(contract, field_name)
                self.assertEqual(len(values), len(set(values)), contract.contract_id)

    def test_unknown_operation_lookup_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "'not-an-operation'"):
            default_structural_beta_contract_registry().get("not-an-operation")

    def test_registry_rejects_duplicate_contract_ids(self) -> None:
        registry = default_structural_beta_contract_registry()
        duplicate = tuple(registry.contracts[:2]) + (registry.contracts[0],)
        with self.assertRaisesRegex(ValidationError, "IDs must be unique"):
            StructuralBetaContractRegistry(duplicate)

    def test_registry_rejects_duplicate_operations(self) -> None:
        registry = default_structural_beta_contract_registry()
        duplicate = tuple(registry.contracts[:2]) + (
            replace(registry.contracts[0], contract_id="unique-duplicate-operation"),
        )
        with self.assertRaisesRegex(ValidationError, "operations must be unique"):
            StructuralBetaContractRegistry(duplicate)

    def test_contract_rejects_empty_required_sections(self) -> None:
        registry = default_structural_beta_contract_registry()
        source = registry.contracts[0]
        with self.assertRaisesRegex(ValidationError, "input_fields"):
            StructuralBetaOperationContract(
                contract_id=source.contract_id,
                capability_id=source.capability_id,
                operation=source.operation,
                input_fields=(),
                output_fields=source.output_fields,
                required_provenance=source.required_provenance,
                accepted_result_states=source.accepted_result_states,
                review_result_states=source.review_result_states,
                safety_notes=source.safety_notes,
            )

    def test_contract_rejects_duplicate_input_fields(self) -> None:
        registry = default_structural_beta_contract_registry()
        source = registry.contracts[0]
        with self.assertRaisesRegex(ValidationError, "input_fields must be unique"):
            StructuralBetaOperationContract(
                contract_id="duplicate-input-contract",
                capability_id=source.capability_id,
                operation=source.operation,
                input_fields=("records", "records"),
                output_fields=source.output_fields,
                required_provenance=source.required_provenance,
                accepted_result_states=source.accepted_result_states,
                review_result_states=source.review_result_states,
                safety_notes=source.safety_notes,
            )

    def test_contract_serialization_preserves_operation_and_safety_boundary(self) -> None:
        contract = default_structural_beta_contract_registry().get("enhancer_hijacking")
        payload = contract.to_dict()
        self.assertEqual(payload["operation"], "enhancer_hijacking")
        self.assertEqual(payload["capability_id"], "GNC-D02-C08")
        self.assertIn("event_id", payload["required_provenance"])
        self.assertIn("structural bridge", " ".join(payload["safety_notes"]))
        self.assertNotIn("raw_record", json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    unittest.main()

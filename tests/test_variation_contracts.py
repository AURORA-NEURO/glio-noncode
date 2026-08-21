from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.variation_contracts import (
    VariationContractFamily,
    VariationContractRegistry,
    VariationOperationContract,
    default_variation_contract_registry,
)
from glio_noncode.variation_public_data import VariationRecordKind


class VariationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = default_variation_contract_registry()

    def test_default_registry_has_five_unique_contracts(self) -> None:
        manifest = self.registry.manifest()
        self.assertEqual(manifest["contract_count"], 5)
        self.assertEqual(
            manifest["family_counts"],
            {
                "normalization": 1,
                "categorical": 1,
                "annotation": 1,
                "decomposition": 1,
                "repeat": 1,
            },
        )
        self.assertEqual(len(set(manifest["capability_ids"])), 5)
        self.assertEqual(len(set(manifest["record_kinds"])), 5)

    def test_registry_manifest_is_deterministic_and_addressed(self) -> None:
        first = self.registry.manifest()
        second = default_variation_contract_registry().manifest()
        self.assertEqual(first, second)
        self.assertRegex(first["manifest_address"], r"^sha256:[0-9a-f]{64}$")

    def test_each_contract_can_be_resolved_by_operation_and_kind(self) -> None:
        for contract in self.registry.contracts:
            self.assertIs(
                self.registry.contract_for_operation(contract.operation),
                contract,
            )
            self.assertIs(self.registry.contract_for_kind(contract.record_kind), contract)
            self.assertTrue(contract.accepts_state(contract.accepted_states[0]))
            self.assertTrue(contract.accepts_state(contract.review_states[0]))

    def test_expected_operation_names_and_capability_ids_are_stable(self) -> None:
        self.assertEqual(
            tuple(contract.operation for contract in self.registry.contracts),
            (
                "vrs-normalization",
                "categorical-normalization",
                "annotation-envelope",
                "multiallelic-decomposition",
                "repeat-aware-normalization",
            ),
        )
        self.assertEqual(
            tuple(contract.capability_id for contract in self.registry.contracts),
            (
                "GNC-D01-C04",
                "GNC-D01-C05",
                "GNC-D01-C06",
                "GNC-D01-C07",
                "GNC-D01-C08",
            ),
        )

    def test_payload_validation_reports_missing_fields_without_running_code(self) -> None:
        missing = self.registry.validate_payload(
            "vrs-normalization",
            {"variant_id": "vrs:1"},
        )
        self.assertEqual(missing, ("chromosome", "start", "reference", "alternate"))
        self.assertEqual(
            self.registry.validate_payload(
                "repeat-aware-normalization",
                {"variant": {}, "reference_sequence": "CC", "reference_start": 1},
            ),
            (),
        )

    def test_payload_validation_rejects_non_mapping(self) -> None:
        with self.assertRaises(ValidationError):
            self.registry.validate_payload("vrs-normalization", [])

    def test_unknown_operation_and_kind_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.registry.contract_for_operation("missing-operation")
        with self.assertRaises(ValidationError):
            self.registry.contract_for_kind("missing-kind")  # type: ignore[arg-type]

    def test_duplicate_operation_is_rejected(self) -> None:
        contract = self.registry.contracts[0]
        with self.assertRaises(ValidationError):
            VariationContractRegistry((contract, contract))

    def test_duplicate_capability_id_is_rejected(self) -> None:
        first = self.registry.contracts[0]
        second = VariationOperationContract(
            "other-operation",
            VariationContractFamily.REPEAT,
            VariationRecordKind.REPEAT,
            first.capability_id,
            ("input",),
            ("output",),
            ("supported",),
            ("abstained",),
            "duplicate capability test",
        )
        with self.assertRaises(ValidationError):
            VariationContractRegistry((first, second))

    def test_duplicate_record_kind_is_rejected(self) -> None:
        first = self.registry.contracts[0]
        second = VariationOperationContract(
            "other-operation",
            VariationContractFamily.NORMALIZATION,
            first.record_kind,
            "GNC-D01-C99",
            ("input",),
            ("output",),
            ("supported",),
            ("abstained",),
            "duplicate kind test",
        )
        with self.assertRaises(ValidationError):
            VariationContractRegistry((first, second))

    def test_contract_rejects_overlapping_state_classes(self) -> None:
        with self.assertRaises(ValidationError):
            VariationOperationContract(
                "bad",
                VariationContractFamily.NORMALIZATION,
                VariationRecordKind.VRS,
                "GNC-D01-C99",
                ("input",),
                ("output",),
                ("supported",),
                ("supported",),
                "bad state classes",
            )

    def test_contract_requires_input_output_and_state_declarations(self) -> None:
        base = dict(
            operation="bad",
            family=VariationContractFamily.NORMALIZATION,
            record_kind=VariationRecordKind.VRS,
            capability_id="GNC-D01-C99",
            required_fields=(),
            output_fields=("output",),
            accepted_states=("supported",),
            review_states=("abstained",),
            evidence_role="test",
        )
        with self.assertRaises(ValidationError):
            VariationOperationContract(**base)
        base["required_fields"] = ("input",)
        base["output_fields"] = ()
        with self.assertRaises(ValidationError):
            VariationOperationContract(**base)
        base["output_fields"] = ("output",)
        base["accepted_states"] = ()
        with self.assertRaises(ValidationError):
            VariationOperationContract(**base)

    def test_contract_serialization_contains_evidence_role(self) -> None:
        payload = self.registry.contracts[0].to_dict()
        self.assertEqual(payload["operation"], "vrs-normalization")
        self.assertIn("evidence_role", payload)
        self.assertIn("required_fields", payload)
        self.assertIn("output_fields", payload)


if __name__ == "__main__":
    unittest.main()

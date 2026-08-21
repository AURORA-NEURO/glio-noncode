from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.identity_contracts import (
    IdentityContractFamily,
    IdentityContractRegistry,
    IdentityOperationContract,
    default_identity_contract_registry,
)
from glio_noncode.identity_public_data import IdentityRecordKind


class IdentityContractTests(unittest.TestCase):
    def test_default_registry_has_one_contract_per_identity_kind(self) -> None:
        registry = default_identity_contract_registry()
        self.assertEqual(len(registry.contracts), 4)
        self.assertEqual(
            {contract.kind for contract in registry.contracts},
            set(IdentityRecordKind),
        )
        self.assertEqual(
            {contract.family for contract in registry.contracts},
            set(IdentityContractFamily),
        )

    def test_manifest_is_versioned_and_addressed(self) -> None:
        manifest = default_identity_contract_registry().manifest()
        self.assertEqual(manifest["contract_version"], "identity-contracts-v1")
        self.assertEqual(manifest["contract_count"], 4)
        self.assertRegex(manifest["content_address"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(len(manifest["contracts"]), 4)

    def test_contract_lookup_supports_kind_and_operation(self) -> None:
        registry = default_identity_contract_registry()
        equivalence = registry.contract_for_kind(IdentityRecordKind.EQUIVALENCE)
        self.assertEqual(equivalence.capability_id, "GNC-D01-C09")
        custody = registry.contract_for_operation("capture-chain-of-custody")
        self.assertEqual(custody.kind, IdentityRecordKind.CUSTODY)
        self.assertTrue(custody.accepts_state("supported"))
        self.assertTrue(custody.accepts_state("contradictory"))
        self.assertFalse(custody.accepts_state("absent"))

    def test_validate_record_reports_missing_required_fields(self) -> None:
        registry = default_identity_contract_registry()
        self.assertEqual(
            registry.validate_record(IdentityRecordKind.EQUIVALENCE, {"query": "x"}),
            ("records",),
        )
        self.assertEqual(
            registry.validate_record(IdentityRecordKind.SAMPLE, {"observations": []}),
            (),
        )

    def test_unknown_kind_and_operation_are_rejected(self) -> None:
        registry = default_identity_contract_registry()
        with self.assertRaises((ValidationError, ValueError)):
            registry.contract_for_kind("missing")
        with self.assertRaises(ValidationError):
            registry.contract_for_operation("missing")

    def test_duplicate_capability_ids_are_rejected(self) -> None:
        contract = IdentityOperationContract(
            "GNC-D01-C09",
            IdentityContractFamily.EQUIVALENCE,
            IdentityRecordKind.EQUIVALENCE,
            "resolve-variant-equivalence",
            ("records", "query"),
            ("state",),
            ("supported",),
            ("absent",),
            "identity resolution",
            "external truth remains",
        )
        with self.assertRaises(ValidationError):
            IdentityContractRegistry((contract, contract))

    def test_duplicate_kinds_are_rejected(self) -> None:
        first = IdentityOperationContract(
            "GNC-D01-C09",
            IdentityContractFamily.EQUIVALENCE,
            IdentityRecordKind.EQUIVALENCE,
            "resolve-variant-equivalence",
            ("records", "query"),
            ("state",),
            ("supported",),
            ("absent",),
            "identity resolution",
            "external truth remains",
        )
        second = IdentityOperationContract(
            "GNC-D01-C99",
            IdentityContractFamily.EQUIVALENCE,
            IdentityRecordKind.EQUIVALENCE,
            "another-operation",
            ("records",),
            ("state",),
            ("supported",),
            ("absent",),
            "identity resolution",
            "external truth remains",
        )
        with self.assertRaises(ValidationError):
            IdentityContractRegistry((first, second))

    def test_contract_rejects_duplicate_field_declarations(self) -> None:
        with self.assertRaises(ValidationError):
            IdentityOperationContract(
                "GNC-D01-C99",
                IdentityContractFamily.EQUIVALENCE,
                IdentityRecordKind.EQUIVALENCE,
                "resolve-variant-equivalence",
                ("records", "records"),
                ("state",),
                ("supported",),
                ("absent",),
                "identity resolution",
                "external truth remains",
            )

    def test_contract_requires_states(self) -> None:
        with self.assertRaises(ValidationError):
            IdentityOperationContract(
                "GNC-D01-C99",
                IdentityContractFamily.EQUIVALENCE,
                IdentityRecordKind.EQUIVALENCE,
                "resolve-variant-equivalence",
                ("records",),
                ("state",),
                (),
                ("absent",),
                "identity resolution",
                "external truth remains",
            )


if __name__ == "__main__":
    unittest.main()

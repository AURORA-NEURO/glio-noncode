"""Declarative contract tests for Domain 01 intake capabilities."""

from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.intake_contracts import (
    IntakeContractFamily,
    IntakeContractRegistry,
    IntakeOperationContract,
    default_intake_contract_registry,
)
from glio_noncode.intake_public_data import IntakeRecordKind


class IntakeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = default_intake_contract_registry()

    def test_registry_contains_exactly_four_unique_capability_contracts(self) -> None:
        self.assertEqual(len(self.registry.contracts), 4)
        self.assertEqual(
            {contract.capability_id for contract in self.registry.contracts},
            {"GNC-D01-C13", "GNC-D01-C14", "GNC-D01-C15", "GNC-D01-C16"},
        )
        self.assertEqual({contract.kind for contract in self.registry.contracts}, set(IntakeRecordKind))
        self.assertEqual(
            {contract.family for contract in self.registry.contracts},
            set(IntakeContractFamily),
        )

    def test_contract_lookup_works_by_kind_and_operation(self) -> None:
        consent = self.registry.contract_for_kind(IntakeRecordKind.CONSENT)
        self.assertEqual(consent.operation, "attach-consent-policy")
        self.assertEqual(
            self.registry.contract_for_operation("export-intake-bundle").kind,
            IntakeRecordKind.BUNDLE,
        )
        self.assertTrue(consent.accepts_state("accepted"))
        self.assertTrue(consent.accepts_state("blocked"))
        self.assertFalse(consent.accepts_state("published"))

    def test_positive_fixture_payloads_have_all_required_fields(self) -> None:
        payloads = {
            "consent": {
                "records": [],
                "policy_id": "p",
                "policy_version": "v",
                "purpose": "research",
                "permitted_uses": ["research"],
            },
            "anomaly": {"records": [], "allowed_bases": "ACGTN"},
            "completeness": {
                "records": [],
                "required_fields": ["record_id"],
                "weights": {"record_id": 1.0},
                "minimum_score": 0.8,
            },
            "bundle": {
                "records": [],
                "bundle_id": "bundle",
                "source_ids": ["source"],
                "require_accepted": True,
            },
        }
        for kind, payload in payloads.items():
            self.assertEqual(self.registry.validate_record(kind, payload), (), kind)

    def test_missing_fields_are_returned_in_contract_order(self) -> None:
        missing = self.registry.validate_record(
            IntakeRecordKind.COMPLETENESS,
            {"records": [], "required_fields": []},
        )
        self.assertEqual(missing, ("weights", "minimum_score"))

    def test_manifest_is_content_addressed_and_serializable(self) -> None:
        manifest = self.registry.manifest()
        self.assertEqual(manifest["contract_version"], "intake-contracts-v1")
        self.assertEqual(manifest["contract_count"], 4)
        self.assertRegex(manifest["content_address"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(len(manifest["contracts"]), 4)
        self.assertEqual(
            {contract["kind"] for contract in manifest["contracts"]},
            {item.value for item in IntakeRecordKind},
        )

    def test_contracts_reject_duplicate_capability_kind_and_operation(self) -> None:
        base = self.registry.contracts[0]
        with self.assertRaises(ValidationError):
            IntakeContractRegistry((base, base))
        duplicate_kind = IntakeOperationContract(
            "GNC-D01-C99",
            IntakeContractFamily.EXPORT,
            IntakeRecordKind.CONSENT,
            "new-operation",
            (),
            ("state",),
            ("accepted",),
            ("review",),
            "role",
            "boundary",
        )
        with self.assertRaises(ValidationError):
            IntakeContractRegistry((base, duplicate_kind))
        duplicate_operation = IntakeOperationContract(
            "GNC-D01-C99",
            IntakeContractFamily.EXPORT,
            IntakeRecordKind.BUNDLE,
            base.operation,
            (),
            ("state",),
            ("accepted",),
            ("review",),
            "role",
            "boundary",
        )
        with self.assertRaises(ValidationError):
            IntakeContractRegistry((base, duplicate_operation))

    def test_contract_rejects_overlapping_states_and_duplicate_fields(self) -> None:
        with self.assertRaises(ValidationError):
            IntakeOperationContract(
                "GNC-D01-C99",
                IntakeContractFamily.EXPORT,
                IntakeRecordKind.BUNDLE,
                "operation",
                ("records", "records"),
                ("state",),
                ("accepted",),
                ("accepted",),
                "role",
                "boundary",
            )
        with self.assertRaises(ValidationError):
            IntakeOperationContract(
                "GNC-D01-C99",
                IntakeContractFamily.EXPORT,
                IntakeRecordKind.BUNDLE,
                "operation",
                (),
                ("state", "state"),
                ("accepted",),
                ("review",),
                "role",
                "boundary",
            )

    def test_unknown_lookups_raise(self) -> None:
        with self.assertRaises(ValueError):
            self.registry.contract_for_kind("unknown")
        with self.assertRaises(ValidationError):
            self.registry.contract_for_operation("unknown")


if __name__ == "__main__":
    unittest.main()

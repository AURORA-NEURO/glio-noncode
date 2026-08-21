from __future__ import annotations

import unittest

from glio_noncode.errors import ValidationError
from glio_noncode.frontier_contracts import (
    FrontierContractRegistry,
    OperationContract,
    OperationFamily,
    default_frontier_contract_registry,
)
from glio_noncode.frontier_end_to_end import END_TO_END_OPERATIONS
from glio_noncode.frontier_release_hardening import HARDENING_OPERATIONS


class FrontierContractRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = default_frontier_contract_registry()

    def test_registry_covers_all_frontier_operation_families(self) -> None:
        manifest = self.registry.manifest()
        self.assertEqual(manifest["contract_count"], 79)
        self.assertEqual(
            manifest["family_counts"],
            {
                "data": 16,
                "context": 16,
                "inference": 16,
                "release": 17,
                "hardening": 10,
                "end_to_end": 4,
            },
        )

    def test_registry_has_sixteen_catalog_capabilities(self) -> None:
        capability_ids = self.registry.capability_ids()
        self.assertEqual(len(capability_ids), 16)
        self.assertEqual(capability_ids[0], "GNC-D13-C13")
        self.assertEqual(capability_ids[-1], "GNC-D16-C16")
        for capability_id in capability_ids:
            contracts = self.registry.by_capability(capability_id)
            self.assertTrue(contracts, capability_id)
            self.assertTrue(
                all(contract.family == OperationFamily.RELEASE for contract in contracts)
            )

    def test_each_release_capability_has_stage_mapping(self) -> None:
        for contract in self.registry.by_family(OperationFamily.RELEASE):
            with self.subTest(operation=contract.operation):
                self.assertTrue(contract.capability_ids)
                self.assertIsNotNone(contract.stage_id)

    def test_release_dossier_has_two_distinct_contracts(self) -> None:
        contracts = self.registry.by_capability("GNC-D14-C16")
        self.assertEqual(
            {contract.operation for contract in contracts},
            {"publish-signed-dossier", "verify-signed-dossier"},
        )

    def test_get_returns_same_contract_object(self) -> None:
        contract = self.registry.get("audit-off-target-alignments")
        self.assertIs(contract, self.registry.get("audit-off-target-alignments"))
        self.assertEqual(contract.family, OperationFamily.HARDENING)

    def test_unknown_operation_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.registry.get("not-a-frontier-operation")

    def test_empty_operation_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.registry.get(" ")

    def test_validate_payload_accepts_outer_shape(self) -> None:
        self.registry.validate_payload(
            "optimize-validation-voi",
            {"records": [], "plan_id": "plan", "budget": 1.0, "context_key": "context"},
        )

    def test_validate_payload_rejects_missing_field(self) -> None:
        with self.assertRaises(ValidationError):
            self.registry.validate_payload(
                "optimize-validation-voi",
                {"records": [], "plan_id": "plan", "context_key": "context"},
            )

    def test_validate_payload_rejects_non_mapping(self) -> None:
        with self.assertRaises(ValidationError):
            self.registry.validate_payload("optimize-validation-voi", [])  # type: ignore[arg-type]

    def test_contract_constructor_rejects_empty_required_fields(self) -> None:
        with self.assertRaises(ValidationError):
            OperationContract("bad", OperationFamily.DATA, (), ("state",))

    def test_contract_constructor_rejects_empty_output_fields(self) -> None:
        with self.assertRaises(ValidationError):
            OperationContract("bad", OperationFamily.DATA, ("records",), ())

    def test_contract_constructor_rejects_duplicate_required_fields(self) -> None:
        with self.assertRaises(ValidationError):
            OperationContract("bad", OperationFamily.DATA, ("records", "records"), ("state",))

    def test_contract_constructor_rejects_duplicate_capability_ids(self) -> None:
        with self.assertRaises(ValidationError):
            OperationContract(
                "bad",
                OperationFamily.RELEASE,
                ("records",),
                ("state",),
                ("GNC-D13-C13", "GNC-D13-C13"),
            )

    def test_registry_constructor_rejects_duplicate_operation_names(self) -> None:
        contract = OperationContract("same", OperationFamily.DATA, ("records",), ("state",))
        with self.assertRaises(ValidationError):
            FrontierContractRegistry((contract, contract))

    def test_manifest_is_content_addressed(self) -> None:
        manifest = self.registry.manifest()
        self.assertRegex(manifest["manifest_address"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(len(manifest["contracts"]), manifest["contract_count"])

    def test_manifest_is_deterministic(self) -> None:
        self.assertEqual(self.registry.manifest(), default_frontier_contract_registry().manifest())

    def test_data_family_has_sixteen_operations(self) -> None:
        self.assertEqual(len(self.registry.by_family(OperationFamily.DATA)), 16)

    def test_context_family_has_sixteen_operations(self) -> None:
        self.assertEqual(len(self.registry.by_family(OperationFamily.CONTEXT)), 16)

    def test_inference_family_has_sixteen_operations(self) -> None:
        self.assertEqual(len(self.registry.by_family(OperationFamily.INFERENCE)), 16)

    def test_hardening_family_matches_exported_operations(self) -> None:
        self.assertEqual(
            {contract.operation for contract in self.registry.by_family(OperationFamily.HARDENING)},
            set(HARDENING_OPERATIONS),
        )

    def test_end_to_end_family_matches_exported_operations(self) -> None:
        self.assertEqual(
            {
                contract.operation
                for contract in self.registry.by_family(OperationFamily.END_TO_END)
            },
            set(END_TO_END_OPERATIONS),
        )

    def test_release_required_fields_are_nonempty(self) -> None:
        for contract in self.registry.by_family(OperationFamily.RELEASE):
            with self.subTest(operation=contract.operation):
                self.assertTrue(all(field.strip() for field in contract.required_fields))
                self.assertTrue(all(field.strip() for field in contract.output_fields))

    def test_contract_serialization_retains_boundary(self) -> None:
        contract = self.registry.get("publish-signed-dossier")
        payload = contract.to_dict()
        self.assertEqual(payload["operation"], "publish-signed-dossier")
        self.assertIn("signing_secret", payload["required_fields"])
        self.assertIn("external validity", payload["research_boundary"])


if __name__ == "__main__":
    unittest.main()

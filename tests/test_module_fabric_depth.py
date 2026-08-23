"""Depth and integrity regression checks for the module fabric."""

from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.capability_registry import default_capability_registry
from glio_noncode.module_fabric_contracts import FabricState
from glio_noncode.module_fabric_depth import audit_module_fabric_depth
from glio_noncode.module_fabric_fixture_eval import evaluate_module_fabric_fixture
from glio_noncode.module_fabric_public_data import default_module_fabric_fixture
from glio_noncode.module_fabric_quality_gate import run_module_fabric_quality_gate


class ModuleFabricDepthTests(unittest.TestCase):
    def test_all_catalog_records_have_evidence(self) -> None:
        registry = default_capability_registry()
        self.assertEqual(len(registry.records()), 256)
        self.assertTrue(all(item.state.value == "verified" for item in registry.records()))
        self.assertTrue(all(item.implementation_modules and item.test_modules for item in registry.records()))

    def test_depth_is_deterministic(self) -> None:
        fixture = default_module_fabric_fixture()
        first = audit_module_fabric_depth(fixture)
        second = audit_module_fabric_depth(fixture)
        self.assertTrue(first.accepted)
        self.assertEqual(first.content_address, second.content_address)

    def test_positive_expectation_drift_fails_evaluation(self) -> None:
        fixture = default_module_fabric_fixture()
        record = fixture.positive_records[0]
        mutated = replace(record, payload={**record.payload, "required_capability_order": 99})
        records = tuple(mutated if item.record_id == record.record_id else item for item in fixture.records)
        changed = replace(fixture, records=records)
        evaluation = evaluate_module_fabric_fixture(changed)
        self.assertFalse(evaluation.accepted)
        self.assertTrue(any(not item.passed for item in evaluation.checks))

    def test_quality_gate_rejects_unresolved_reference(self) -> None:
        fixture = default_module_fabric_fixture()
        record = fixture.positive_records[0]
        registry = default_capability_registry()
        from glio_noncode.capability_registry import CapabilityState

        evidence = {
            item.spec.capability_id: {
                "state": item.state.value,
                "implementation_modules": item.implementation_modules,
                "test_modules": item.test_modules,
                "evidence_note": item.evidence_note,
            }
            for item in registry.records()
        }
        evidence[record.capability_id]["implementation_modules"] = ("glio_noncode.module_fabric_missing_surface",)
        broken = registry.with_evidence(evidence)
        report = run_module_fabric_quality_gate(fixture, broken)
        self.assertFalse(report.accepted)
        self.assertTrue(any(item.check_id == "reference-closure" and not item.passed for item in report.checks))


if __name__ == "__main__":
    unittest.main()

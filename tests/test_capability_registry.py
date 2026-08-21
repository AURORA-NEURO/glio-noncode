from __future__ import annotations

import unittest

from glio_noncode.capability_registry import (
    CapabilityRegistry,
    CapabilityState,
    default_capability_registry,
)


class CapabilityRegistryTests(unittest.TestCase):
    def test_blueprint_catalog_has_256_rows_and_64_mvp_rows(self) -> None:
        registry = default_capability_registry()
        coverage = registry.coverage()
        self.assertEqual(coverage.total_capabilities, 256)
        self.assertEqual(coverage.mvp_capabilities, 64)
        self.assertEqual(coverage.verified, 3)
        self.assertEqual(coverage.partial, 85)
        self.assertEqual(coverage.planned, 168)
        self.assertAlmostEqual(coverage.implementation_percent, 1.17)
        self.assertAlmostEqual(coverage.mvp_implementation_percent, 4.69)
        self.assertEqual(coverage.started, 88)
        self.assertAlmostEqual(coverage.started_percent, 34.38)
        self.assertEqual(coverage.mvp_started, 64)
        self.assertAlmostEqual(coverage.to_dict()["mvp_started_percent"], 100.0)
        self.assertEqual(len(registry.by_domain("D01")), 16)
        self.assertEqual(registry.record("GNC-D01-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D01-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D02-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D02-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D03-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D03-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D04-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D04-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D05-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D05-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D06-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D06-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D16-C04").spec.capability, "Agent execution sandbox")

    def test_evidence_updates_only_declared_capabilities(self) -> None:
        registry = CapabilityRegistry.from_csv().with_evidence(
            {
                "GNC-D01-C01": {
                    "state": CapabilityState.VERIFIED.value,
                    "implementation_modules": ["intake.VariantIntake"],
                    "test_modules": ["tests.test_intake"],
                    "evidence_note": "lossless fixture and quarantine tests",
                },
                "GNC-D01-C02": {
                    "state": CapabilityState.PARTIAL.value,
                    "implementation_modules": ["intake.VariantIntake"],
                    "test_modules": ["tests.test_intake"],
                },
            }
        )
        coverage = registry.coverage()
        self.assertEqual(coverage.verified, 1)
        self.assertEqual(coverage.partial, 1)
        self.assertEqual(coverage.planned, 254)
        self.assertAlmostEqual(coverage.implementation_percent, 0.39)
        self.assertAlmostEqual(coverage.verified_percent, 0.39)
        self.assertAlmostEqual(coverage.mvp_implementation_percent, 1.56)


if __name__ == "__main__":
    unittest.main()

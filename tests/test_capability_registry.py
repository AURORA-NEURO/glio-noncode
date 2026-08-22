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
        self.assertEqual(coverage.verified, 188)
        self.assertEqual(coverage.partial, 68)
        self.assertEqual(coverage.planned, 0)
        self.assertAlmostEqual(coverage.implementation_percent, 73.44)
        self.assertAlmostEqual(coverage.mvp_implementation_percent, 75.0)
        self.assertEqual(coverage.started, 256)
        self.assertAlmostEqual(coverage.started_percent, 100.0)
        self.assertEqual(coverage.mvp_started, 64)
        self.assertAlmostEqual(coverage.to_dict()["mvp_started_percent"], 100.0)
        self.assertEqual(len(registry.by_domain("D01")), 16)
        self.assertEqual(registry.record("GNC-D01-C04").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C05").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C06").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C07").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C08").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C09").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C10").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C11").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C12").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C13").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C14").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C15").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D01-C16").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C01").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C02").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C03").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C04").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C05").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C06").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C07").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C08").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C09").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C10").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C11").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C12").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C13").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C14").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C15").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D02-C16").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C01").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C02").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C03").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C04").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C05").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C06").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C07").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C08").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C09").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C10").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C11").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D03-C12").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C01").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C02").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C03").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C04").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C05").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C06").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C07").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C08").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C09").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C10").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C11").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D04-C12").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C01").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C02").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C03").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C04").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C05").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C06").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C07").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C08").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C09").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C10").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C11").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D05-C12").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C01").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C02").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C03").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C04").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C09").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C10").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C11").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C12").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C09").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C01").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C02").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C03").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C04").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C10").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C11").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C12").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C05").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C06").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C07").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D07-C08").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D08-C09").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D08-C10").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D08-C11").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D08-C01").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D08-C02").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D08-C03").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D08-C04").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D08-C12").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C05").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C06").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C07").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D06-C08").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D08-C05").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D08-C08").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D09-C01").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D09-C02").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D09-C03").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D09-C04").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D09-C05").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D09-C08").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D09-C09").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D09-C12").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D10-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D10-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D10-C09").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D10-C12").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D10-C13").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D10-C16").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D11-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D11-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D11-C09").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D11-C12").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D12-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D12-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D12-C09").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D12-C12").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D13-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D13-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D13-C09").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D13-C12").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D14-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D14-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D14-C09").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D14-C12").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D15-C05").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D15-C01").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D15-C02").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D15-C03").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D15-C04").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D15-C06").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D15-C07").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D15-C08").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D15-C09").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D15-C10").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D15-C11").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D15-C12").state, CapabilityState.VERIFIED)
        self.assertEqual(registry.record("GNC-D16-C05").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D16-C08").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D16-C09").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D16-C12").state, CapabilityState.PARTIAL)
        self.assertEqual(registry.record("GNC-D16-C04").spec.capability, "Agent execution sandbox")
        for capability_id in (
            "GNC-D01-C13",
            "GNC-D01-C16",
            "GNC-D02-C13",
            "GNC-D02-C16",
            "GNC-D03-C13",
            "GNC-D03-C16",
            "GNC-D04-C13",
            "GNC-D04-C16",
            "GNC-D05-C13",
            "GNC-D05-C16",
            "GNC-D06-C13",
            "GNC-D06-C16",
            "GNC-D07-C13",
            "GNC-D07-C16",
            "GNC-D08-C13",
            "GNC-D08-C16",
            "GNC-D09-C13",
            "GNC-D09-C16",
            "GNC-D10-C13",
            "GNC-D10-C16",
            "GNC-D11-C13",
            "GNC-D11-C16",
            "GNC-D12-C13",
            "GNC-D12-C16",
            "GNC-D13-C13",
            "GNC-D13-C16",
            "GNC-D14-C13",
            "GNC-D14-C16",
            "GNC-D15-C13",
            "GNC-D15-C16",
            "GNC-D16-C13",
            "GNC-D16-C16",
        ):
            expected_state = (
                CapabilityState.VERIFIED
                if capability_id.split("-")[1]
                in {
                    "D01",
                    "D02",
                    "D03",
                    "D04",
                    "D05",
                    "D06",
                    "D07",
                    "D08",
                    "D09",
                    "D10",
                    "D11",
                    "D12",
                    "D13",
                    "D14",
                    "D15",
                    "D16",
                }
                else CapabilityState.PARTIAL
            )
            self.assertEqual(registry.record(capability_id).state, expected_state)

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

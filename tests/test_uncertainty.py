from __future__ import annotations

import unittest
from math import nan

from glio_noncode.models import EvidenceClaim, EvidenceState, EvidenceTier, ReferenceContext
from glio_noncode.uncertainty import (
    CalibrationDatum,
    CalibrationEvaluator,
    DomainProfile,
    OODStatus,
    OutOfDomainDetector,
    UncertaintyBand,
    UncertaintyPropagator,
    UncertaintyComponent,
)
from glio_noncode.errors import ValidationError


class UncertaintyTests(unittest.TestCase):
    def test_ood_detector_distinguishes_in_domain_watch_and_missing(self) -> None:
        profile = DomainProfile(
            "profile-1",
            "GRCh38|glioma|adult|stem_like|unknown|unknown",
            ("accessibility", "motif_score"),
            {"accessibility": (0.0, 1.0), "motif_score": (0.0, 1.0)},
            "profile-source-1",
        )
        detector = OutOfDomainDetector()
        self.assertEqual(
            detector.assess({"accessibility": 0.7, "motif_score": 0.4}, profile).status,
            OODStatus.IN_DOMAIN,
        )
        self.assertEqual(
            detector.assess({"accessibility": 1.05, "motif_score": 0.4}, profile).status,
            OODStatus.WATCH,
        )
        self.assertEqual(
            detector.assess({"accessibility": 0.7}, profile).status, OODStatus.ABSTAINED
        )

    def test_uncertainty_propagator_keeps_missing_and_contradiction_components(self) -> None:
        context = ReferenceContext("GRCh38", "glioma", "adult", "stem_like")
        claims = (
            EvidenceClaim(
                "e1",
                "edge",
                "source-a",
                "sequence_model",
                EvidenceState.SUPPORTED,
                EvidenceTier.COMPUTED,
                0.8,
                0.9,
                context,
                "supported",
                {},
            ),
            EvidenceClaim(
                "e2",
                "edge",
                "source-b",
                "functional",
                EvidenceState.CONTRADICTORY,
                EvidenceTier.EXPERIMENTAL,
                0.2,
                0.6,
                context,
                "contradictory",
                {},
            ),
            EvidenceClaim(
                "e3",
                "edge",
                "source-b",
                "atlas",
                EvidenceState.ABSTAINED,
                EvidenceTier.REFERENCE,
                None,
                0.0,
                context,
                "abstained",
                {},
            ),
        )
        report = UncertaintyPropagator().summarize(claims)
        self.assertIn(
            report.band, {UncertaintyBand.LOW, UncertaintyBand.MODERATE, UncertaintyBand.HIGH}
        )
        self.assertEqual(
            {component.name for component in report.components},
            {
                "missingness",
                "contradiction",
                "context_transport",
                "source_dependence",
            },
        )

    def test_ood_abstention_sets_aggregate_band_to_abstain(self) -> None:
        profile = DomainProfile("p", "ctx", ("x",), {"x": (0.0, 1.0)}, "source")
        ood = OutOfDomainDetector().assess({}, profile)
        report = UncertaintyPropagator().summarize((), ood=ood)
        self.assertEqual(report.band, UncertaintyBand.ABSTAIN)

    def test_calibration_report_is_grouped_and_content_addressed(self) -> None:
        report = CalibrationEvaluator().evaluate(
            (
                CalibrationDatum(0.9, 1.0, "glioma"),
                CalibrationDatum(0.2, 0.0, "glioma"),
                CalibrationDatum(0.8, 1.0, "control"),
            ),
            bins=5,
        )
        self.assertEqual(report.sample_count, 3)
        self.assertIn("glioma", report.group_metrics)
        self.assertGreaterEqual(report.expected_calibration_error, 0.0)
        self.assertTrue(report.content_address.startswith("sha256:"))

    def test_uncertainty_contracts_reject_coercion_and_non_finite_values(self) -> None:
        with self.assertRaises(ValidationError):
            DomainProfile(
                "p",
                "ctx",
                ["x"],  # type: ignore[arg-type]
                {"x": (0.0, 1.0)},
                "source",
            )
        with self.assertRaises(ValidationError):
            DomainProfile("p", "ctx", ("x", "x"), {"x": (0.0, 1.0)}, "source")
        profile = DomainProfile("p", "ctx", ("x",), {"x": (0.0, 1.0)}, "source")
        with self.assertRaises(ValidationError):
            OutOfDomainDetector().assess({"x": "0.5"}, profile)  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            OutOfDomainDetector().assess({"x": nan}, profile)
        with self.assertRaises(ValidationError):
            UncertaintyComponent("x", nan, "bad")

    def test_calibration_contracts_reject_invalid_rows_and_bins(self) -> None:
        with self.assertRaises(ValidationError):
            CalibrationDatum(1, 0.0)  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            CalibrationDatum(0.5, 0.5, "")
        with self.assertRaises(ValidationError):
            CalibrationEvaluator().evaluate((CalibrationDatum(0.5, 0.5),), bins=True)  # type: ignore[arg-type]
        with self.assertRaises(ValidationError):
            CalibrationEvaluator().evaluate((object(),))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()

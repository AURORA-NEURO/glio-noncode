from __future__ import annotations

import tempfile
import unittest

from glio_noncode.quality import QualityBand, QualityEvaluator
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class QualityTests(unittest.TestCase):
    def test_quality_report_exposes_multiple_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            report = QualityEvaluator().evaluate(dossier)
            self.assertGreaterEqual(len(report.metrics), 4)
            self.assertTrue(all(metric.value is not None for metric in report.metrics))
            self.assertIn(report.metrics[0].band, {QualityBand.PASS, QualityBand.WATCH, QualityBand.FAIL})

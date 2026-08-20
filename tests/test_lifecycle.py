from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace

from glio_noncode.lifecycle import (
    DriftMonitor,
    DriftStatus,
    LifecycleReclassifier,
    ReviewPacketBuilder,
    ReviewPriority,
)
from glio_noncode.models import EvidenceState
from glio_noncode.runtime import CaseRuntime

from .helpers import fixture_manifest


class LifecycleTests(unittest.TestCase):
    def test_review_packet_exposes_claim_states_and_expertise(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
        packet = ReviewPacketBuilder().build(dossier)
        self.assertEqual(packet.dossier_id, dossier.dossier_id)
        self.assertIn(
            packet.priority,
            {ReviewPriority.ELEVATED, ReviewPriority.BLOCKING, ReviewPriority.ROUTINE},
        )
        self.assertGreater(sum(packet.claim_state_counts.values()), 0)
        self.assertTrue(packet.required_expertise)
        self.assertTrue(packet.content_address.startswith("sha256:"))

    def test_reclassification_marks_source_version_change_for_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = CaseRuntime(directory).evaluate(fixture_manifest())
        changed_claim = replace(previous.evidence[0], state=EvidenceState.CONTRADICTORY, score=0.0)
        current = replace(
            previous,
            dossier_id=previous.dossier_id + "-next",
            evidence=(changed_claim,) + previous.evidence[1:],
        )
        plan = LifecycleReclassifier().plan(
            previous,
            current,
            source_version_before="source-1",
            source_version_after="source-2",
            reason="public reference source release changed",
        )
        self.assertTrue(plan.requires_review)
        self.assertGreaterEqual(len(plan.deltas), 1)

    def test_drift_monitor_escalates_operational_alert(self) -> None:
        report = DriftMonitor().compare(
            {"unsupported_claim_fraction": 0.1, "abstention_fraction": 0.1},
            {"unsupported_claim_fraction": 0.8, "abstention_fraction": 0.4},
            case_id="case-1",
        )
        self.assertEqual(report.status, DriftStatus.ALERT)
        self.assertTrue(any(signal.status == DriftStatus.ALERT for signal in report.signals))
        self.assertTrue(report.content_address.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()

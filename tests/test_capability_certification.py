"""Deep verification for live certification of the complete capability catalog."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from glio_noncode.capability_certification import (
    CHECKS_PER_CAPABILITY,
    GLOBAL_CHECK_COUNT,
    capability_certification_domain_matrix,
    capability_certification_percent,
    certify_capability_catalog,
    diff_capability_certifications,
    query_capability_certification,
)
from glio_noncode.capability_certification_contracts import CapabilityCertificationState
from glio_noncode.capability_certification_exports import (
    export_capability_certification_checks_csv,
    export_capability_certification_csv,
    export_capability_certification_domains_csv,
    export_capability_certification_json,
    export_capability_certification_summary_json,
    render_capability_certification_markdown,
)
from glio_noncode.capability_certification_quality import (
    QUALITY_CHECK_COUNT,
    run_capability_certification_quality_gate,
)
from glio_noncode.capability_certification_replay import (
    replay_capability_certification,
    replay_is_deterministic,
    run_capability_certification_failure_injections,
)
from glio_noncode.capability_certification_runtime import run_capability_certification


class CapabilityCertificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = certify_capability_catalog()
        cls.runtime = run_capability_certification()

    def test_complete_catalog_is_live_certified(self) -> None:
        self.assertTrue(self.report.accepted)
        self.assertEqual(self.report.capability_count, 256)
        self.assertEqual(self.report.total_checks, 256 * CHECKS_PER_CAPABILITY + GLOBAL_CHECK_COUNT)
        self.assertEqual(self.report.passed_checks, self.report.total_checks)
        self.assertEqual(self.report.failed_checks, 0)
        self.assertEqual(capability_certification_percent(self.report), 100.0)

    def test_domain_and_mvp_denominators_are_conserved(self) -> None:
        matrix = capability_certification_domain_matrix(self.report)
        self.assertEqual(len(matrix), 16)
        self.assertEqual(sum(item["capability_count"] for item in matrix), 256)
        self.assertEqual(sum(item["mvp_count"] for item in matrix), 64)
        self.assertTrue(all(item["accepted_count"] == 16 for item in matrix))
        self.assertTrue(all(item["readiness_percent"] == 100.0 for item in matrix))

    def test_all_receipts_and_checks_are_addressed(self) -> None:
        self.assertTrue(all(item.content_address.startswith("capability-certificate:") for item in self.report.certificates))
        self.assertTrue(all(item.content_address.startswith("capability-domain-summary:") for item in self.report.domain_summaries))
        self.assertTrue(all(check.content_address.startswith("capability-certification-check:") for check in self.report.checks))
        self.assertTrue(all(receipt.content_address for item in self.report.certificates for receipt in (*item.implementation_receipts, *item.test_receipts)))

    def test_query_supports_domain_mvp_state_and_text(self) -> None:
        self.assertEqual(len(query_capability_certification(self.report, domain_id="D01")), 16)
        self.assertEqual(len(query_capability_certification(self.report, mvp_only=True)), 64)
        self.assertEqual(len(query_capability_certification(self.report, state=CapabilityCertificationState.ACCEPTED)), 256)
        rows = query_capability_certification(self.report, text="variant identity")
        self.assertTrue(rows)
        self.assertTrue(all("variant identity" in f"{row.domain} {row.capability}".lower() for row in rows))

    def test_report_and_projection_serialization(self) -> None:
        payload = json.loads(export_capability_certification_json(self.report))
        summary = json.loads(export_capability_certification_summary_json(self.report))
        self.assertEqual(payload["capability_count"], 256)
        self.assertEqual(summary["certification_percent"], 100.0)
        self.assertEqual(len(export_capability_certification_csv(self.report).splitlines()), 257)
        self.assertEqual(len(export_capability_certification_domains_csv(self.report).splitlines()), 17)
        self.assertEqual(len(export_capability_certification_checks_csv(self.report).splitlines()), 2573)
        markdown = render_capability_certification_markdown(self.report)
        self.assertIn("# Capability certification", markdown)
        self.assertIn("## Domain readiness", markdown)

    def test_quality_gate_closes_fixed_denominators(self) -> None:
        quality = run_capability_certification_quality_gate(self.report)
        self.assertTrue(quality.accepted)
        self.assertEqual(len(quality.checks), QUALITY_CHECK_COUNT)
        self.assertEqual(quality.passed_checks, QUALITY_CHECK_COUNT)
        self.assertEqual(quality.failed_checks, 0)

    def test_runtime_closes_ordered_stages(self) -> None:
        self.assertTrue(self.runtime.accepted)
        self.assertEqual(self.runtime.state, CapabilityCertificationState.ACCEPTED)
        self.assertEqual(len(self.runtime.stages), 12)
        self.assertEqual([item.ordinal for item in self.runtime.stages], list(range(1, 13)))
        self.assertTrue(all(item.content_address.startswith("capability-certification-stage:") for item in self.runtime.stages))
        self.assertTrue(self.runtime.quality.accepted)

    def test_replay_is_deterministic(self) -> None:
        replay = replay_capability_certification()
        self.assertTrue(replay.accepted)
        self.assertTrue(replay_is_deterministic(replay))
        self.assertEqual(replay.first_address, replay.second_address)

    def test_failure_injections_hold_missing_evidence(self) -> None:
        failures = run_capability_certification_failure_injections()
        self.assertTrue(failures.accepted)
        self.assertEqual(len(failures.probes), 2)
        self.assertTrue(all(item.passed for item in failures.probes))
        self.assertTrue(all(item.observed_state is CapabilityCertificationState.REVIEW for item in failures.probes))
        self.assertTrue(all(item.failed_check_ids for item in failures.probes))

    def test_report_diff_is_empty_for_identical_replay(self) -> None:
        replayed = certify_capability_catalog()
        diff = diff_capability_certifications(self.report, replayed)
        self.assertEqual(diff["added"], [])
        self.assertEqual(diff["removed"], [])
        self.assertEqual(diff["changed"], [])
        self.assertEqual(diff["changed_count"], 0)

    def test_checked_in_closure_matches_runtime_denominators(self) -> None:
        path = Path(__file__).parents[1] / "data" / "capability-certification-runtime-closure.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["runtime"]["state"], "accepted")
        self.assertEqual(payload["runtime"]["stage_count"], 12)
        self.assertEqual(payload["report"]["capability_count"], 256)
        self.assertEqual(payload["report"]["total_checks"], 2572)
        self.assertEqual(payload["quality"]["passed_checks"], 18)
        self.assertTrue(payload["failure_controls"]["accepted"])


if __name__ == "__main__":
    unittest.main()

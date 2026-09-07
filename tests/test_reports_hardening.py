from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from types import MappingProxyType
from typing import Any, ClassVar, cast

from glio_noncode.errors import ValidationError
from glio_noncode.models import Dossier, EvidenceState
from glio_noncode.reports import (
    DEFAULT_REPORT_LIMITS,
    RENDERED_REPORT_ADDRESS_PREFIX,
    REPORT_ADDRESS_PREFIX,
    REPORT_PAYLOAD_ADDRESS_PREFIX,
    SUMMARY_ADDRESS_PREFIX,
    DossierReport,
    DossierSummary,
    RenderedReport,
    ReportAudience,
    ReportFormat,
    ReportLimits,
    build_report,
    render_json,
    render_markdown,
    render_report,
    render_report_json,
    render_report_markdown,
    summarize,
)
from glio_noncode.runtime import CaseRuntime
from glio_noncode.serialization import content_hash

from .helpers import fixture_manifest


def _rehydrate(raw: dict[str, Any]) -> Dossier:
    raw["content_address"] = content_hash(
        {key: value for key, value in raw.items() if key != "content_address"}
    )
    return Dossier.from_dict(raw)


class ReportsHardeningTests(unittest.TestCase):
    _directory: ClassVar[tempfile.TemporaryDirectory[str]]
    dossier: ClassVar[Dossier]

    @classmethod
    def setUpClass(cls) -> None:
        cls._directory = tempfile.TemporaryDirectory()
        cls.dossier = CaseRuntime(cls._directory.name).evaluate(fixture_manifest())

    @classmethod
    def tearDownClass(cls) -> None:
        cls._directory.cleanup()

    def test_reporting_requires_an_exact_valid_addressed_dossier(self) -> None:
        with self.assertRaises(ValidationError):
            summarize(cast(Any, object()))
        with self.assertRaises(ValidationError):
            render_markdown(cast(Any, object()))

        forged = replace(self.dossier, content_address="sha256:" + "0" * 64)
        with self.assertRaises(ValidationError):
            summarize(forged)
        with self.assertRaises(ValidationError):
            render_json(forged)

    def test_summary_is_strict_addressed_and_replay_verifiable(self) -> None:
        summary = summarize(self.dossier)
        self.assertTrue(summary.content_address.startswith(SUMMARY_ADDRESS_PREFIX + ":"))
        self.assertEqual(DossierSummary.from_dict(summary.to_dict()), summary)
        self.assertTrue(summary.verify(self.dossier))
        self.assertFalse(summary.verify(replace(self.dossier, case_id="different-case")))

        unknown = summary.to_dict()
        unknown["unexpected"] = True
        with self.assertRaises(ValidationError):
            DossierSummary.from_dict(unknown)
        with self.assertRaises(ValidationError):
            DossierSummary.from_dict(cast(Any, MappingProxyType(summary.to_dict())))

        changed = summary.to_dict()
        changed["warning_count"] = cast(int, changed["warning_count"]) + 1
        with self.assertRaises(ValidationError):
            DossierSummary.from_dict(changed)

    def test_summary_conserves_all_evidence_and_lifecycle_states(self) -> None:
        raw = self.dossier.to_dict()
        old_claim = dict(raw["evidence"][0])
        old_claim.update(
            {
                "evidence_id": "report-orphan-old",
                "edge_id": "report-orphan-edge",
                "state": "absent",
                "score": None,
                "depends_on": [],
                "supersedes": None,
                "summary": "explicit absent orphan claim",
            }
        )
        current_claim = dict(raw["evidence"][0])
        current_claim.update(
            {
                "evidence_id": "report-orphan-current",
                "edge_id": "report-orphan-edge",
                "depends_on": [],
                "supersedes": "report-orphan-old",
                "summary": "current orphan claim",
            }
        )
        raw["evidence"].extend([old_claim, current_claim])
        dossier = _rehydrate(raw)

        summary = summarize(dossier)
        state_counts = dict(summary.evidence_state_counts)
        self.assertEqual(
            tuple(state_counts),
            tuple(state.value for state in EvidenceState),
        )
        self.assertEqual(sum(state_counts.values()), summary.evidence_count)
        self.assertEqual(
            summary.supported_claim_count
            + summary.negative_claim_count
            + summary.missing_claim_count,
            summary.evidence_count,
        )
        self.assertEqual(
            summary.active_claim_count
            + summary.superseded_claim_count
            + summary.orphan_claim_count,
            summary.evidence_count,
        )
        self.assertEqual(state_counts["absent"], 1)
        self.assertGreaterEqual(summary.superseded_claim_count, 1)
        self.assertGreaterEqual(summary.orphan_claim_count, 1)

    def test_ranking_is_deterministic_and_independent_of_storage_order(self) -> None:
        raw = self.dossier.to_dict()
        duplicate = dict(raw["hypotheses"][0])
        duplicate["hypothesis_id"] = "000-report-ranking-tie"
        raw["hypotheses"].append(duplicate)
        raw["hypotheses"].reverse()
        raw["experiments"].reverse()
        dossier = _rehydrate(raw)

        expected_hypothesis = min(
            raw["hypotheses"],
            key=lambda item: (-item["support"], item["uncertainty"], item["hypothesis_id"]),
        )["hypothesis_id"]
        expected_experiment = min(
            dossier.experiments,
            key=lambda item: (-item.priority, item.option_id),
        ).option_id
        first = summarize(dossier)
        second = summarize(dossier)
        self.assertEqual(first, second)
        self.assertEqual(first.top_hypothesis_id, expected_hypothesis)
        self.assertEqual(first.recommended_experiment_id, expected_experiment)

    def test_limits_are_downward_only_and_revalidated_at_use(self) -> None:
        with self.assertRaises(ValidationError):
            ReportLimits(
                max_hypotheses=DEFAULT_REPORT_LIMITS.max_hypotheses + 1,
            )

        tampered = ReportLimits()
        object.__setattr__(
            tampered,
            "max_hypotheses",
            DEFAULT_REPORT_LIMITS.max_hypotheses + 1,
        )
        with self.assertRaises(ValidationError):
            summarize(self.dossier, limits=tampered)
        with self.assertRaises(ValidationError):
            render_markdown(self.dossier, limits=ReportLimits(max_markdown_bytes=1))

        raw = self.dossier.to_dict()
        duplicate = dict(raw["hypotheses"][0])
        duplicate["hypothesis_id"] = "report-limit-hypothesis"
        raw["hypotheses"].append(duplicate)
        with self.assertRaises(ValidationError):
            summarize(_rehydrate(raw), limits=ReportLimits(max_hypotheses=1))

    def test_issue_code_cap_does_not_truncate_authoritative_gate_evaluation(self) -> None:
        raw = self.dossier.to_dict()
        raw["evidence"][0]["summary"] = "This asserts a diagnosis."
        dossier = _rehydrate(raw)
        ordinary = summarize(dossier)
        self.assertIn("policy_violation", ordinary.release_gate_issue_codes)
        self.assertIn("release_status_required", ordinary.release_gate_issue_codes)
        with self.assertRaisesRegex(ValidationError, "issue codes exceed"):
            summarize(dossier, limits=ReportLimits(max_issue_codes=1))

    def test_markdown_escapes_untrusted_text_and_rejects_invalid_utf8(self) -> None:
        raw = self.dossier.to_dict()
        raw["evidence"][0]["summary"] = (
            "claim\n# injected <script>alert(1)</script> [click](javascript:bad) `code`"
        )
        dossier = _rehydrate(raw)
        markdown = render_markdown(dossier)
        self.assertNotIn("\n# injected", markdown)
        self.assertNotIn("<script>", markdown)
        self.assertNotIn("[click](javascript:bad)", markdown)
        self.assertIn("&lt;script&gt;", markdown)
        self.assertEqual(markdown.encode("utf-8").decode("utf-8"), markdown)

        hostile_claim = replace(self.dossier.evidence[0], summary="invalid \ud800 text")
        hostile = replace(
            self.dossier,
            evidence=(hostile_claim, *self.dossier.evidence[1:]),
        )
        with self.assertRaises(ValidationError):
            render_markdown(hostile)

    def test_legacy_json_remains_the_full_canonical_dossier_export(self) -> None:
        self.assertEqual(json.loads(render_json(self.dossier)), self.dossier.to_dict())

    def test_public_projection_is_allowlisted_and_redacts_free_text_and_ids(self) -> None:
        canary = "PRIVATE-CANARY-CASE-AND-FREE-TEXT"
        raw = self.dossier.to_dict()
        raw["case_id"] = canary
        raw["policy_version"] = canary
        raw["warnings"].append(canary)
        raw["evidence"][0]["summary"] = canary
        dossier = _rehydrate(raw)

        public = build_report(dossier, audience=ReportAudience.PUBLIC)
        review = build_report(dossier, audience=ReportAudience.REVIEW)
        public_json = render_report_json(public)
        self.assertNotIn(canary, public_json)
        self.assertIn(canary, render_report_json(review))
        self.assertNotIn("case_id", public.projection)
        self.assertNotIn("run_id", public.projection)
        self.assertNotIn("top_hypothesis_id", public.projection)
        self.assertNotIn("recommended_experiment_id", public.projection)
        self.assertNotIn("input_address", public.projection)
        self.assertNotIn("event_head", public.projection)
        self.assertNotIn("policy_version", public.projection)
        self.assertTrue(public.projection["public_safe"])
        self.assertNotEqual(public.content_address, review.content_address)
        self.assertTrue(public.verify(dossier))
        self.assertTrue(review.verify(dossier))
        self.assertEqual(DossierReport.from_dict(public.to_dict()), public)

        public_markdown = render_report_markdown(public)
        self.assertNotIn(canary, public_markdown)
        self.assertNotIn("Top hypothesis", public_markdown)

    def test_report_and_rendered_envelopes_are_strict_and_content_addressed(self) -> None:
        report = build_report(self.dossier)
        self.assertTrue(report.content_address.startswith(REPORT_ADDRESS_PREFIX + ":"))
        for report_format in ReportFormat:
            rendered = render_report(report, format=report_format)
            self.assertTrue(
                rendered.content_address.startswith(RENDERED_REPORT_ADDRESS_PREFIX + ":")
            )
            self.assertTrue(
                rendered.payload_address.startswith(REPORT_PAYLOAD_ADDRESS_PREFIX + ":")
            )
            self.assertEqual(rendered.byte_count, len(rendered.payload.encode("utf-8")))
            self.assertEqual(RenderedReport.from_dict(rendered.to_dict()), rendered)
            self.assertTrue(rendered.verify(report))
            self.assertEqual(rendered, render_report(report, format=report_format))

            changed = rendered.to_dict()
            changed["payload"] = cast(str, changed["payload"]) + "tampered"
            with self.assertRaises(ValidationError):
                RenderedReport.from_dict(changed)

        with self.assertRaises(ValidationError):
            render_report(report, limits=ReportLimits(max_rendered_report_bytes=1))

    def test_public_report_rejects_extra_projection_fields_even_if_readdressed(self) -> None:
        report = build_report(self.dossier, audience="public")
        raw = report.to_dict()
        projection = cast(dict[str, Any], raw["projection"])
        projection["case_id"] = self.dossier.case_id
        body = {key: value for key, value in raw.items() if key != "content_address"}
        raw["content_address"] = content_hash(body, prefix=REPORT_ADDRESS_PREFIX)
        with self.assertRaises(ValidationError):
            DossierReport.from_dict(raw)


if __name__ == "__main__":
    unittest.main()

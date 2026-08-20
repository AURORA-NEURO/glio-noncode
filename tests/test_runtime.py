from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode.models import ReviewDecision, ReviewState
from glio_noncode.data_sources import EnrichmentResult, ReferenceBundle
from glio_noncode.replay import ReplayVerifier
from glio_noncode.reports import render_markdown, summarize
from glio_noncode.runtime import CaseRuntime
from glio_noncode.validation import ContractValidator, ReleaseGate

from .helpers import fixture_manifest


class RuntimeTests(unittest.TestCase):
    def test_evaluate_persists_replayable_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            self.assertTrue(dossier.research_use_only)
            self.assertGreater(len(dossier.hypotheses), 0)
            self.assertGreater(len(dossier.evidence), 0)
            self.assertTrue(runtime.store.store.exists(dossier.content_address))
            run = runtime.get_run(dossier.run_id)
            stored = runtime.get_dossier(dossier.content_address)
            self.assertEqual(stored["content_address"], dossier.content_address)
            self.assertEqual(run["dossier_address"], dossier.content_address)

    def test_review_changes_status_and_creates_new_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            review = ReviewDecision(
                review_id="review-1",
                case_id=dossier.case_id,
                reviewer="scientific-reviewer",
                state=ReviewState.ACCEPTED,
                reviewed_hypothesis_ids=(dossier.hypotheses[0].hypothesis_id,),
                rationale="Checked the displayed edge claims and retained alternatives.",
                checked_claim_ids=tuple(claim.evidence_id for claim in dossier.evidence),
            )
            released = runtime.review(dossier, review)
            self.assertEqual(released.status.value, "released_research")
            self.assertNotEqual(released.content_address, dossier.content_address)
            self.assertTrue(released.is_releasable)
            self.assertTrue(ReleaseGate().check(released).valid)

    def test_replay_verifier_detects_valid_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            runtime = CaseRuntime(directory)
            dossier = runtime.evaluate(fixture_manifest())
            run = runtime.get_run(dossier.run_id)
            events = runtime.store.store.get(run["event_address"])
            stored_dossier = runtime.get_dossier(run["dossier_address"])
            report = ReplayVerifier().verify(run, events, stored_dossier)
            self.assertTrue(report.event_chain_valid)
            self.assertTrue(report.stored_dossier_matches_address)
            self.assertFalse(report.warnings)

    def test_summary_and_markdown_preserve_edge_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory).evaluate(fixture_manifest())
            summary = summarize(dossier)
            markdown = render_markdown(dossier)
            self.assertEqual(summary.case_id, dossier.case_id)
            self.assertIn("Evidence ledger", markdown)
            self.assertIn(dossier.hypotheses[0].element_id, markdown)

    def test_manifest_contract_reports_missing_versions_as_warning(self) -> None:
        report = ContractValidator().validate_manifest(fixture_manifest())
        self.assertTrue(report.valid)
        self.assertFalse(any(issue.code == "missing_input_versions" for issue in report.issues))

    def test_live_reference_enrichment_is_persisted_with_dossier_provenance(self) -> None:
        manifest = fixture_manifest()

        class StubRetriever:
            def enrich_manifest(self, value):
                bundle = ReferenceBundle(
                    variant_id=value.variants[0].variant_id,
                    context_key=value.context.key,
                    sequence=None,
                    elements=value.candidate_elements,
                    raw_features=(),
                    receipts=(),
                    warnings=(),
                    content_address="sha256:" + "1" * 64,
                )
                return EnrichmentResult(value, (bundle,), ())

        with tempfile.TemporaryDirectory() as directory:
            dossier = CaseRuntime(directory, reference_retriever=StubRetriever()).evaluate(
                manifest,
                live_reference=True,
            )
            self.assertEqual(len(dossier.source_bundle_addresses), 1)
            self.assertTrue(dossier.source_bundle_addresses[0].startswith("sha256:"))
            self.assertEqual(len(dossier.source_receipts), 0)
            self.assertTrue(CaseRuntime(directory).store.store.exists(dossier.source_bundle_addresses[0]))

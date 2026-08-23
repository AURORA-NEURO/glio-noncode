from __future__ import annotations

import unittest

from glio_noncode.evidence_release_frontier_attestation import attestations_are_independent, build_evidence_release_attestation
from glio_noncode.evidence_release_frontier_context_boundary import evaluate_evidence_release_context_boundary
from glio_noncode.evidence_release_frontier_citation_graph import build_evidence_release_citation_graph
from glio_noncode.evidence_release_frontier_decision_ledger import build_evidence_release_decision_ledger, ledger_is_append_only
from glio_noncode.evidence_release_frontier_diff import diff_evidence_release_evaluations
from glio_noncode.evidence_release_frontier_fixture_eval import evaluate_evidence_release_fixture
from glio_noncode.evidence_release_frontier_operator_console import build_evidence_release_operator_console
from glio_noncode.evidence_release_frontier_publication_policy import evaluate_evidence_release_publication_policy
from glio_noncode.evidence_release_frontier_public_data import default_evidence_release_frontier_fixture
from glio_noncode.evidence_release_frontier_review_ledger import build_evidence_release_review_ledger, close_review_assignment
from glio_noncode.evidence_release_frontier_schema_diagnostics import diagnose_evidence_release_schema


class EvidenceReleaseExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_evidence_release_frontier_fixture()
        cls.evaluation = evaluate_evidence_release_fixture(cls.fixture)

    def test_attestation_and_decision_ledger(self) -> None:
        first = self.evaluation.executions[0]
        attestations = (build_evidence_release_attestation(first.record_id, "reviewer-a", "accept", "receipt complete", first.output), build_evidence_release_attestation(first.record_id, "reviewer-b", "accept", "independent receipt complete", first.output))
        self.assertTrue(attestations_are_independent(attestations))
        ledger = build_evidence_release_decision_ledger(self.evaluation.executions)
        self.assertTrue(ledger_is_append_only(ledger))
        self.assertEqual(len(ledger.entries), 16)

    def test_graph_and_context_boundary(self) -> None:
        graph = build_evidence_release_citation_graph(self.fixture)
        self.assertTrue(graph.closed)
        boundary = evaluate_evidence_release_context_boundary(self.fixture.records)
        self.assertEqual(len(boundary.foreign_record_ids), 4)

    def test_review_ledger_closes_one_row(self) -> None:
        queue = __import__("glio_noncode.evidence_release_frontier_review_queue", fromlist=["build_evidence_release_review_queue"]).build_evidence_release_review_queue(self.evaluation)
        ledger = build_evidence_release_review_ledger(queue.rows)
        self.assertGreater(ledger.open_count, 0)
        closed = close_review_assignment(ledger, ledger.assignments[0]["record_id"])
        self.assertEqual(closed.open_count, ledger.open_count - 1)

    def test_publication_policy_requires_verification(self) -> None:
        dossier = self.fixture.records[12].payload
        denied = evaluate_evidence_release_publication_policy(dossier, verified=False, release_accepted=True)
        allowed = evaluate_evidence_release_publication_policy(dossier, verified=True, release_accepted=True)
        self.assertFalse(denied.allowed)
        self.assertTrue(allowed.allowed)

    def test_schema_diagnostics_and_console_are_addressed(self) -> None:
        diagnostics = diagnose_evidence_release_schema(("missing:payload", "context_key:not_text"))
        self.assertEqual(diagnostics.fields, ("not_text", "payload"))
        console = build_evidence_release_operator_console(type("Runtime", (), {"evaluation": self.evaluation, "accepted": True})())
        self.assertTrue(console.content_address.startswith("sha256:"))

    def test_evaluation_diff_is_deterministic(self) -> None:
        self.assertEqual(diff_evidence_release_evaluations(self.evaluation, self.evaluation).changed_states, ())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from glio_noncode.evidence_release_frontier_acceptance import acceptance_reason, build_evidence_release_acceptance
from glio_noncode.evidence_release_frontier_benchmark import benchmark_evidence_release, benchmark_is_closed
from glio_noncode.evidence_release_frontier_fixture_eval import evaluate_evidence_release_fixture
from glio_noncode.evidence_release_frontier_invariants import evaluate_evidence_release_invariants
from glio_noncode.evidence_release_frontier_public_data import default_evidence_release_frontier_fixture
from glio_noncode.evidence_release_frontier_resilience import evaluate_evidence_release_resilience
from glio_noncode.evidence_release_frontier_source_policy import evaluate_evidence_release_sources
from glio_noncode.evidence_release_frontier_state_machine import build_evidence_release_state_machine, transition_is_allowed


class EvidenceReleaseAssuranceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_evidence_release_frontier_fixture()
        cls.evaluation = evaluate_evidence_release_fixture(cls.fixture)

    def test_benchmark_and_invariants_close(self) -> None:
        benchmark = benchmark_evidence_release(self.evaluation, self.fixture)
        self.assertTrue(benchmark_is_closed(benchmark))
        self.assertTrue(evaluate_evidence_release_invariants(self.fixture, self.evaluation).accepted)

    def test_state_machine_preserves_safe_transitions(self) -> None:
        machine = build_evidence_release_state_machine()
        self.assertTrue(machine.accepted)
        self.assertTrue(transition_is_allowed(machine, "signed", "verified"))
        self.assertFalse(transition_is_allowed(machine, "blocked", "signed"))

    def test_source_policy_and_resilience(self) -> None:
        self.assertTrue(evaluate_evidence_release_sources(self.fixture))
        resilience = evaluate_evidence_release_resilience(self.fixture)
        self.assertTrue(resilience.stable)

    def test_acceptance_preserves_failed_gate_reasons(self) -> None:
        accepted = build_evidence_release_acceptance(data=True, quality=True, signature=True)
        held = build_evidence_release_acceptance(data=True, quality=False, signature=True)
        self.assertTrue(accepted.accepted)
        self.assertEqual(acceptance_reason(held), ("quality",))


if __name__ == "__main__":
    unittest.main()

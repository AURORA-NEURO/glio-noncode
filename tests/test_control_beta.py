from __future__ import annotations

import unittest

from glio_noncode.control_beta import (
    BudgetResourceScheduler,
    BudgetWorkItem,
    ControlBetaState,
    DeterministicFallbackRouter,
    FallbackCandidate,
    FallbackRequest,
    HumanReviewQueueRouter,
    PolicyClaimAuditor,
)
from glio_noncode.control_plane import (
    ClaimCeiling,
    InvocationRequest,
    MissionContext,
    ProvenanceContext,
    default_control_plane_registry,
)
from glio_noncode.errors import ValidationError
from glio_noncode.workflow import ResourceEnvelope


class ControlBetaTests(unittest.TestCase):
    def _request(self, payload: dict[str, object]) -> InvocationRequest:
        return InvocationRequest(
            request_id="policy-request",
            mission=MissionContext(
                mission_id="mission-beta",
                project_id="glio-noncode",
                intended_use="research-only policy audit",
                requested_question="Which declared workflow is bounded?",
                claim_ceiling=ClaimCeiling.HYPOTHESIS,
            ),
            agent_id="A08",
            tool_id="A08.publish",
            input_payload=payload,
            provenance=ProvenanceContext(("sha256:input",), reference_build="GRCh38"),
            idempotency_key="policy-idempotency",
        )

    def test_policy_auditor_exposes_allowance_and_sensitive_paths(self) -> None:
        registry = default_control_plane_registry()
        request = self._request({"case_hash": "sha256:case", "question": "bounded"})
        audit = PolicyClaimAuditor().audit(
            request,
            registry.agent("A08"),
            registry.tool("A08.publish"),
        )
        self.assertEqual(audit.state, ControlBetaState.SUPPORTED)
        self.assertTrue(audit.allowed)
        self.assertTrue(audit.releaseable)

        blocked = PolicyClaimAuditor().audit(
            self._request({"case_hash": "sha256:case", "email": "redacted@example.test"}),
            registry.agent("A08"),
            registry.tool("A08.publish"),
        )
        self.assertEqual(blocked.state, ControlBetaState.BLOCKED)
        self.assertFalse(blocked.allowed)
        self.assertIn("payload.email", blocked.sensitive_paths)

    def test_budget_scheduler_respects_dependencies_capacity_and_limits(self) -> None:
        items = (
            BudgetWorkItem(
                "root", priority=1, cost_units=2, resource=ResourceEnvelope(max_seconds=10)
            ),
            BudgetWorkItem(
                "child",
                priority=10,
                depends_on=("root",),
                cost_units=2,
                resource=ResourceEnvelope(max_seconds=20),
            ),
            BudgetWorkItem(
                "network",
                priority=5,
                network_egress=True,
                cost_units=1,
                resource=ResourceEnvelope(network_egress=True, max_seconds=5),
            ),
            BudgetWorkItem(
                "too-large",
                priority=20,
                resource=ResourceEnvelope(cpu=5, max_seconds=5),
            ),
        )
        result = BudgetResourceScheduler().schedule(
            items,
            max_invocations=3,
            max_network_requests=0,
            max_seconds=40,
            max_cost_units=5,
            capacity=ResourceEnvelope(cpu=2, max_seconds=100, network_egress=True),
            schedule_id="schedule-1",
        )
        self.assertEqual(result.state, ControlBetaState.PARTIAL)
        self.assertEqual(result.admitted_item_ids, ("root", "child"))
        self.assertIn("network", result.deferred_item_ids)
        self.assertIn("too-large", result.rejected_item_ids)
        self.assertEqual(result.total_seconds, 30)
        self.assertEqual(result.remaining_invocations, 1)

    def test_budget_scheduler_rejects_dependency_cycles(self) -> None:
        with self.assertRaises(ValidationError):
            BudgetResourceScheduler().schedule(
                (
                    BudgetWorkItem("a", depends_on=("b",)),
                    BudgetWorkItem("b", depends_on=("a",)),
                ),
                max_invocations=2,
                max_network_requests=0,
                max_seconds=100,
                max_cost_units=10,
                capacity=ResourceEnvelope(),
            )

    def test_fallback_router_selects_only_eligible_declared_alternate(self) -> None:
        request = FallbackRequest(
            request_id="fallback-1",
            failed_operation_id="primary",
            failure_code="source_unavailable",
            retryable=True,
            available_inputs=("case", "context"),
            requested_output_contract="evidence",
            remaining_cost_units=5,
        )
        route = DeterministicFallbackRouter().route(
            request,
            (
                FallbackCandidate(
                    "missing",
                    "alternate-a",
                    priority=10,
                    required_inputs=("missing-input",),
                    output_contract="evidence",
                ),
                FallbackCandidate(
                    "eligible",
                    "alternate-b",
                    priority=5,
                    required_inputs=("case",),
                    output_contract="evidence",
                ),
                FallbackCandidate("primary-repeat", "primary", priority=100),
            ),
        )
        self.assertEqual(route.state, ControlBetaState.SELECTED)
        self.assertEqual(route.selected_candidate_id, "eligible")
        self.assertIn("missing", route.rejected_candidates)
        self.assertIn("primary-repeat", route.rejected_candidates)

        blocked = DeterministicFallbackRouter().route(
            FallbackRequest("fallback-2", "primary", "handler_failure", False),
            (FallbackCandidate("eligible", "alternate"),),
        )
        self.assertEqual(blocked.state, ControlBetaState.BLOCKED)
        self.assertTrue(blocked.requires_review)

    def test_review_queue_prioritizes_blockers_and_bounds_output(self) -> None:
        result = HumanReviewQueueRouter().route(
            (
                {
                    "item_id": "low",
                    "request_id": "low",
                    "execution_role_id": "role-low",
                    "tool_id": "tool-low",
                    "state": "rejected",
                    "reasons": ["resource_denied"],
                    "priority": 10,
                    "requires_review": True,
                },
                {
                    "item_id": "blocked",
                    "request_id": "blocked",
                    "execution_role_id": "role-blocked",
                    "tool_id": "tool-blocked",
                    "state": "abstained",
                    "reasons": ["source_unavailable"],
                    "blockers": ["abstention"],
                    "priority": 90,
                    "requires_review": True,
                },
                {
                    "item_id": "omitted",
                    "request_id": "omitted",
                    "execution_role_id": "role-omitted",
                    "tool_id": "tool-omitted",
                    "state": "failed",
                    "reasons": ["handler_failure"],
                    "priority": 50,
                    "requires_review": True,
                },
            ),
            required_roles=("statistical_review",),
            max_review_candidates=2,
        )
        self.assertEqual(result.state, ControlBetaState.BLOCKED)
        self.assertEqual([item.item_id for item in result.assignments], ["blocked", "omitted"])
        self.assertEqual(result.omitted_item_ids, ("low",))
        self.assertIn("statistical_review", result.assignments[0].reviewer_roles)
        self.assertTrue(result.assignments[0].blocked)


if __name__ == "__main__":
    unittest.main()

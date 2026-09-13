from __future__ import annotations

import unittest
from dataclasses import replace

from glio_noncode.control_plane import (
    AgentSpec,
    Abstention,
    ClaimCeiling,
    ControlPlaneExecutor,
    EvidenceArbiter,
    EvidenceEnvelope,
    InvocationRequest,
    InvocationState,
    MissionContext,
    MissionPlanner,
    Plane,
    ProvenanceContext,
    ResourceScheduler,
    WorkflowBudget,
    WorkflowDecision,
    default_control_plane_registry,
)
from glio_noncode.errors import SourceError
from glio_noncode.models import EvidenceState, EvidenceTier
from glio_noncode.serialization import content_hash
from glio_noncode.workflow import ResourceEnvelope


def _mission(*, network: bool = False, release: bool = False) -> MissionContext:
    return MissionContext(
        mission_id="mission-control-test",
        project_id="project-test",
        intended_use="research-only regulatory hypothesis evaluation",
        requested_question="Which declared evidence paths merit review?",
        claim_ceiling=ClaimCeiling.RESEARCH_RELEASE if release else ClaimCeiling.HYPOTHESIS,
        allowed_source_ids=(
            "SRC-ENSEMBL-REST",
            "SRC-UCSC-REST",
            "SRC-ENCODE-REST",
        )
        if network
        else (),
        allow_network=network,
    )


def _request(
    agent_id: str, tool_id: str, *, network: bool = False, request_id: str = "request-1"
) -> InvocationRequest:
    return InvocationRequest(
        request_id=request_id,
        mission=_mission(network=network),
        agent_id=agent_id,
        tool_id=tool_id,
        input_payload={"case_hash": "sha256:case", "question": "bounded research question"},
        provenance=ProvenanceContext(
            input_hashes=("sha256:case",),
            reference_build="GRCh38",
        ),
        idempotency_key=f"idem-{request_id}",
    )


class ControlPlaneTests(unittest.TestCase):
    def test_default_registry_contains_all_bounded_roles_and_tools(self) -> None:
        registry = default_control_plane_registry()
        self.assertEqual(len(registry.agents()), 48)
        self.assertEqual(len(registry.tools()), 96)
        self.assertEqual({agent.plane for agent in registry.agents()}, set(Plane))
        manifest = registry.manifest()
        self.assertEqual(manifest["agent_count"], 48)
        self.assertEqual(manifest["tool_count"], 96)

    def test_planner_expands_dependencies_and_marks_review(self) -> None:
        planner = MissionPlanner()
        plan = planner.plan(_mission(release=True), ("A35", "A45"))
        self.assertIsInstance(plan, WorkflowDecision)
        self.assertEqual(plan.decision, "planned")
        self.assertIn("A34", plan.selected_agent_ids)
        self.assertIn("A45", plan.selected_agent_ids)
        self.assertTrue(plan.requires_human_review)
        self.assertEqual(len(plan.selected_tool_ids), len(plan.selected_agent_ids) * 2)

    def test_executor_returns_typed_evidence_and_replays_idempotently(self) -> None:
        executor = ControlPlaneExecutor()
        executor.register(
            "A08.publish",
            lambda request: EvidenceEnvelope(
                evidence_id="evidence-identity-1",
                agent_id=request.agent_id,
                tool_id=request.tool_id,
                state=EvidenceState.SUPPORTED,
                tier=EvidenceTier.COMPUTED,
                claim_summary="canonical identity was derived from declared input",
                payload_hash=content_hash({"canonical": "GRCh38:7:55249071:A:T"}),
                provenance_digest=request.provenance.digest,
                confidence=0.99,
            ),
        )
        request = _request("A08", "A08.publish")
        first = executor.execute(request)
        second = executor.execute(request)
        self.assertEqual(first.state, InvocationState.COMPLETED)
        self.assertIsInstance(first.response, EvidenceEnvelope)
        self.assertTrue(second.cached)
        self.assertTrue(executor.event_log.verify())

    def test_idempotency_keys_are_bound_to_the_original_invocation(self) -> None:
        executor = ControlPlaneExecutor()
        calls = {"count": 0}

        def handler(request: InvocationRequest) -> EvidenceEnvelope:
            calls["count"] += 1
            return EvidenceEnvelope(
                evidence_id="evidence-identity-1",
                agent_id=request.agent_id,
                tool_id=request.tool_id,
                state=EvidenceState.SUPPORTED,
                tier=EvidenceTier.COMPUTED,
                claim_summary="canonical identity was derived from declared input",
                payload_hash=content_hash({"canonical": "GRCh38:7:55249071:A:T"}),
                provenance_digest=request.provenance.digest,
            )

        executor.register("A08.publish", handler)
        request = _request("A08", "A08.publish", request_id="bound")
        first = executor.execute(request)
        replay = executor.execute(request)
        conflicting = executor.execute(
            replace(request, input_payload={"case_hash": "sha256:other", "question": "different"})
        )
        self.assertEqual(first.state, InvocationState.COMPLETED)
        self.assertTrue(replay.cached)
        self.assertEqual(conflicting.state, InvocationState.REJECTED)
        self.assertIsNotNone(conflicting.error)
        self.assertEqual(conflicting.error.code, "idempotency_conflict")
        self.assertEqual(calls["count"], 1)

    def test_workflow_budget_and_deadline_require_finite_integer_limits(self) -> None:
        with self.assertRaises(Exception):
            WorkflowBudget(max_invocations=1.0)  # type: ignore[arg-type]
        with self.assertRaises(Exception):
            WorkflowBudget(max_cost_units=float("nan"))
        with self.assertRaises(Exception):
            _ = replace(_request("A08", "A08.publish"), deadline_seconds=1.5)  # type: ignore[arg-type]

    def test_executor_rejects_non_callable_handlers_at_registration(self) -> None:
        with self.assertRaises(Exception):
            ControlPlaneExecutor().register("A08.publish", object())  # type: ignore[arg-type]

    def test_control_envelopes_reject_malformed_typed_metadata(self) -> None:
        with self.assertRaises(Exception):
            MissionContext(
                mission_id="m",
                project_id="p",
                intended_use="research",
                requested_question="bounded",
                claim_ceiling="hypothesis",  # type: ignore[arg-type]
            )
        with self.assertRaises(Exception):
            ProvenanceContext(("sha256:input", "sha256:input"))
        with self.assertRaises(Exception):
            ProvenanceContext(("sha256:input",), source_versions={"source": 1})  # type: ignore[dict-item]
        with self.assertRaises(Exception):
            AgentSpec(
                agent_id="A99",
                name="Malformed",
                plane="control",  # type: ignore[arg-type]
                purpose="test",
                input_contracts=("input",),
                output_contracts=("output",),
                allowed_tool_ids=("A99.inspect",),
                review_required="false",  # type: ignore[arg-type]
            )

    def test_scheduler_scopes_budgets_to_missions_and_retains_consumed_seconds(self) -> None:
        scheduler = ResourceScheduler(
            capacity=ResourceEnvelope(cpu=1, memory_gb=2, storage_gb=2, max_seconds=100)
        )
        tool = default_control_plane_registry().tool("A08.publish")
        budget = WorkflowBudget(max_invocations=1, max_network_requests=0, max_seconds=5)
        first = _request("A08", "A08.publish", request_id="scheduler-first")
        first = replace(
            first,
            resource=ResourceEnvelope(cpu=1, memory_gb=1, storage_gb=1, max_seconds=4),
            budget=budget,
        )
        self.assertTrue(scheduler.admit(first, tool).admitted)
        same_mission = replace(
            first,
            request_id="scheduler-same-mission",
            idempotency_key="idem-scheduler-same-mission",
        )
        denied = scheduler.admit(same_mission, tool)
        self.assertFalse(denied.admitted)
        self.assertIn("invocation budget", denied.reason)
        scheduler.release(first.request_id)
        still_denied = scheduler.admit(same_mission, tool)
        self.assertFalse(still_denied.admitted)
        other_mission = replace(
            same_mission,
            request_id="scheduler-other-mission",
            idempotency_key="idem-scheduler-other-mission",
            mission=replace(first.mission, mission_id="another-mission"),
        )
        self.assertTrue(scheduler.admit(other_mission, tool).admitted)

    def test_scheduler_rejects_aggregate_live_resource_overcommit(self) -> None:
        scheduler = ResourceScheduler(
            capacity=ResourceEnvelope(cpu=1, memory_gb=2, storage_gb=2, max_seconds=100)
        )
        tool = default_control_plane_registry().tool("A08.publish")
        first = replace(
            _request("A08", "A08.publish", request_id="capacity-first"),
            resource=ResourceEnvelope(cpu=1, memory_gb=1, storage_gb=1, max_seconds=4),
        )
        second = replace(
            first,
            request_id="capacity-second",
            idempotency_key="idem-capacity-second",
            mission=replace(first.mission, mission_id="capacity-other"),
        )
        self.assertTrue(scheduler.admit(first, tool).admitted)
        denied = scheduler.admit(second, tool)
        self.assertFalse(denied.admitted)
        self.assertIn("active resource capacity", denied.reason)
        scheduler.release(first.request_id)
        self.assertTrue(scheduler.admit(second, tool).admitted)

    def test_network_policy_and_source_failure_are_explicit(self) -> None:
        executor = ControlPlaneExecutor()
        executor.register(
            "A15.inspect", lambda request: (_ for _ in ()).throw(SourceError("source timed out"))
        )
        denied = executor.execute(
            _request("A15", "A15.inspect", network=False, request_id="denied")
        )
        self.assertEqual(denied.state, InvocationState.REJECTED)
        allowed = executor.execute(
            _request("A15", "A15.inspect", network=True, request_id="allowed")
        )
        self.assertEqual(allowed.state, InvocationState.ABSTAINED)
        self.assertIsInstance(allowed.response, Abstention)
        self.assertEqual(allowed.response.reason_code, "source_unavailable")

    def test_arbiter_preserves_conflicts_instead_of_choosing_silently(self) -> None:
        base = dict(
            evidence_id="shared-evidence",
            agent_id="A18",
            tool_id="A18.publish",
            state=EvidenceState.SUPPORTED,
            tier=EvidenceTier.EXPERIMENTAL,
            claim_summary="independent measurement",
            provenance_digest="sha256:provenance",
        )
        result = EvidenceArbiter().arbitrate(
            (
                EvidenceEnvelope(**base, payload_hash="sha256:one"),
                EvidenceEnvelope(**base, payload_hash="sha256:two"),
            )
        )
        self.assertEqual(result.accepted, ())
        self.assertEqual(result.conflicts, ("shared-evidence",))
        self.assertEqual(result.abstentions[0].reason_code, "conflicting_evidence_payloads")


if __name__ == "__main__":
    unittest.main()

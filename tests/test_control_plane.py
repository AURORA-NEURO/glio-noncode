from __future__ import annotations

import unittest

from glio_noncode.control_plane import (
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
    WorkflowDecision,
    default_control_plane_registry,
)
from glio_noncode.errors import SourceError
from glio_noncode.models import EvidenceState, EvidenceTier
from glio_noncode.serialization import content_hash


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

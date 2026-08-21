import unittest

from glio_noncode.control_plane import (
    InvocationRequest,
    MissionContext,
    ProvenanceContext,
    WorkflowDecision,
)
from glio_noncode.errors import ValidationError
from glio_noncode.mission_runtime import (
    ExecutionSandbox,
    MissionPlanBuilder,
    MissionPlanState,
    MissionRequest,
    SandboxIsolation,
    TypedToolRegistry,
)


class MissionRuntimeTests(unittest.TestCase):
    def _mission(self) -> MissionContext:
        return MissionContext(
            mission_id="mission-1",
            project_id="glio-noncode",
            intended_use="research hypothesis exploration",
            requested_question="Which observations require review?",
            allowed_data_scopes=("synthetic", "public_reference"),
        )

    def _request(
        self, *, request_id: str = "request-1", payload: dict[str, object] | None = None
    ) -> InvocationRequest:
        return InvocationRequest(
            request_id=request_id,
            mission=self._mission(),
            agent_id="A01",
            tool_id="A01.inspect",
            input_payload=payload or {"data_scope": "synthetic", "question": "bounded"},
            provenance=ProvenanceContext(("sha256:input",), reference_build="GRCh38"),
            idempotency_key=f"idem-{request_id}",
        )

    def test_mission_plan_expands_dependencies_and_compiles_dag(self) -> None:
        request = MissionRequest(
            mission=self._mission(),
            requested_agent_ids=("A02",),
            workflow_id="workflow-1",
        )
        plan = MissionPlanBuilder().plan(request)
        self.assertIn("A01", plan.selected_agent_ids)
        self.assertIn("A01", plan.selected_agent_ids)
        self.assertIn("A02", plan.selected_agent_ids)
        self.assertEqual(plan.workflow.steps[0].step_id, "ingest")
        self.assertEqual(plan.workflow.steps[-1].step_id, "export")
        self.assertEqual(plan.state, MissionPlanState.PLANNED)
        self.assertTrue(plan.registry_address.startswith("sha256:"))

    def test_empty_mission_abstains_without_compiling_hidden_work(self) -> None:
        request = MissionRequest(mission=self._mission(), requested_agent_ids=())
        plan = MissionPlanBuilder().plan(request)
        self.assertEqual(plan.state, MissionPlanState.ABSTAINED)
        self.assertIsNone(plan.workflow)
        self.assertEqual(plan.selected_agent_ids, ())

    def test_typed_registry_exposes_owner_checked_contracts(self) -> None:
        registry = TypedToolRegistry()
        descriptor = registry.resolve("A01.inspect", owner_agent_id="A01")
        self.assertEqual(descriptor.input_contract, "mission_context")
        self.assertEqual(len(registry.list()), 96)
        self.assertEqual(len(registry.tools_for_agent("A01")), 2)
        with self.assertRaises(ValidationError):
            registry.resolve("A01.inspect", owner_agent_id="A02")

    def test_local_sandbox_requires_registration_and_replays_idempotently(self) -> None:
        sandbox = ExecutionSandbox(isolation=SandboxIsolation(workspace_root=".glio/test-sandbox"))
        request = self._request()
        denied = sandbox.execute(request)
        self.assertFalse(denied.admission.admitted)
        self.assertEqual(denied.state.value, "rejected")

        sandbox.register(
            "A01.inspect",
            lambda _request: WorkflowDecision("inspection_complete"),
        )
        first = sandbox.execute(request)
        second = sandbox.execute(request)
        self.assertEqual(first.state.value, "completed")
        self.assertTrue(first.event_ids)
        self.assertTrue(second.cached)
        self.assertEqual(second.content_address, sandbox.execute(request).content_address)

    def test_sandbox_and_policy_retain_boundary_failures(self) -> None:
        sandbox = ExecutionSandbox(isolation=SandboxIsolation(workspace_root=".glio/test-sandbox"))
        with self.assertRaises(ValidationError):
            sandbox.register("A09.inspect", lambda _request: WorkflowDecision("network"))
        sandbox.register("A01.inspect", lambda _request: WorkflowDecision("ok"))
        sensitive = sandbox.execute(
            self._request(request_id="request-sensitive", payload={"name": "hidden"})
        )
        self.assertEqual(sensitive.state.value, "rejected")
        self.assertTrue(sensitive.result.error)
        self.assertIn("direct identifiers", sensitive.result.error.message)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from glio_noncode.control_plane import InvocationRequest, MissionContext, ProvenanceContext
from glio_noncode.mission_runtime import ExecutionSandbox, MissionPlanBuilder, MissionRequest, SandboxIsolation
from glio_noncode.platform_frontier_contract_migrations import migrate_platform_frontier_payload
from glio_noncode.platform_frontier_capacity import build_platform_frontier_capacity_report
from glio_noncode.platform_frontier_contracts import PLATFORM_FRONTIER_VERSION
from glio_noncode.platform_frontier_execution_plan import build_platform_frontier_execution_plan, validate_platform_frontier_execution_plan
from glio_noncode.platform_frontier_freshness import evaluate_platform_frontier_freshness
from glio_noncode.platform_frontier_locking import acquire_platform_frontier_lock
from glio_noncode.platform_frontier_operations import run_platform_frontier_operation
from glio_noncode.platform_frontier_policy import default_platform_frontier_policy
from glio_noncode.platform_frontier_provenance import build_platform_frontier_provenance
from glio_noncode.platform_frontier_public_data import default_platform_frontier_fixture
from glio_noncode.platform_frontier_resource_accounting import account_platform_frontier_resources
from glio_noncode.platform_frontier_rollback import build_platform_frontier_rollback_plan
from glio_noncode.platform_frontier_run_manifest import build_platform_frontier_run_manifest
from glio_noncode.platform_frontier_runtime import run_platform_frontier_runtime
from glio_noncode.platform_frontier_sandbox_policy import audit_platform_frontier_sandbox_policy
from glio_noncode.platform_frontier_schema import default_platform_frontier_schema
from glio_noncode.platform_frontier_schema_diff import diff_platform_frontier_schema
from glio_noncode.platform_frontier_versioning import inspect_platform_frontier_version
from glio_noncode.serialization import jsonable


class PlatformFrontierExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        mission = MissionContext(
            mission_id="extension-mission",
            project_id="glio-noncode",
            intended_use="research hypothesis exploration",
            requested_question="Which declared observations warrant review?",
        )
        cls.plan = MissionPlanBuilder().plan(MissionRequest(mission, ("A02",), "extension-workflow"))
        cls.policy = default_platform_frontier_policy()
        cls.fixture = default_platform_frontier_fixture()
        cls.runtime = run_platform_frontier_runtime(cls.fixture, run_id="extension-runtime")

    def test_execution_plan_and_resource_accounting(self) -> None:
        plan = build_platform_frontier_execution_plan(self.plan)
        self.assertTrue(plan.accepted)
        self.assertEqual(validate_platform_frontier_execution_plan(plan), ())
        accounting = account_platform_frontier_resources(self.plan)
        self.assertTrue(accounting.fits)
        self.assertGreater(accounting.max_seconds, 0)
        capacity = build_platform_frontier_capacity_report(accounting)
        self.assertTrue(capacity.accepted)
        self.assertEqual(capacity.constrained_lanes, ())
        self.assertEqual(len(capacity.lanes), 5)

    def test_capacity_projection_rejects_overloaded_lane(self) -> None:
        accounting = account_platform_frontier_resources(self.plan, capacity={"cpu": 1.0, "memory_gb": 32.0, "storage_gb": 100.0, "gpu_count": 4.0, "max_seconds": 3_600.0})
        capacity = build_platform_frontier_capacity_report(accounting)
        self.assertFalse(capacity.accepted)
        self.assertEqual(capacity.constrained_lanes, ("cpu",))

    def test_provenance_lock_and_run_manifest(self) -> None:
        provenance = build_platform_frontier_provenance("extension-runtime", self.plan, self.policy)
        self.assertTrue(provenance.complete)
        lock = acquire_platform_frontier_lock("extension-runtime", "idem-1")
        replay_lock = acquire_platform_frontier_lock("extension-runtime", "idem-1", existing_keys=("idem-1",))
        self.assertTrue(lock.acquired)
        self.assertTrue(replay_lock.reused)
        manifest = build_platform_frontier_run_manifest("extension-runtime", provenance, self.runtime.stage_ids)
        self.assertTrue(manifest.accepted)
        self.assertEqual(len(manifest.stage_ids), 24)

    def test_schema_diff_and_migration_are_explicit(self) -> None:
        schema = default_platform_frontier_schema()
        diff = diff_platform_frontier_schema(schema, schema)
        self.assertTrue(diff.compatible)
        self.assertEqual(diff.added_fields, ())
        migration = migrate_platform_frontier_payload({"fixture_id": self.fixture.fixture_id, "fixture_version": "old.v0"})
        self.assertTrue(migration.accepted)
        self.assertEqual(migration.migrated_payload["fixture_version"], PLATFORM_FRONTIER_VERSION)
        self.assertTrue(inspect_platform_frontier_version(jsonable(self.fixture)).compatible)

    def test_sandbox_policy_and_freshness(self) -> None:
        sandbox = ExecutionSandbox(isolation=SandboxIsolation(workspace_root=".glio/extension-sandbox"))
        mission = MissionContext(
            mission_id="sandbox-extension",
            project_id="glio-noncode",
            intended_use="research hypothesis exploration",
            requested_question="bounded",
            allowed_mutations=("none", "event_log", "content_addressed_store"),
        )
        request = InvocationRequest(
            "extension-request",
            mission,
            "A01",
            "A01.publish",
            {"data_scope": "synthetic"},
            ProvenanceContext(("sha256:extension",), reference_build="platform-v1"),
            "extension-idem",
        )
        admission = sandbox.admit(request)
        report = audit_platform_frontier_sandbox_policy(admission, sandbox.isolation)
        self.assertTrue(report.accepted)
        self.assertTrue(evaluate_platform_frontier_freshness(self.fixture, observed_date="2026-08-23").accepted)

    def test_rollback_and_positive_operation_remain_bounded(self) -> None:
        release = self.runtime.release
        rollback = build_platform_frontier_rollback_plan(release, prior_release_id="prior-platform-release")
        self.assertTrue(rollback.accepted)
        positive = self.fixture.records[0]
        result = run_platform_frontier_operation(positive.operation, positive.payload)
        self.assertTrue(result.state.value in {"ready", "compatible", "admitted"})


if __name__ == "__main__":
    unittest.main()

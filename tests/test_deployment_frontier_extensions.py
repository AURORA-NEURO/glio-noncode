from __future__ import annotations

import unittest

from glio_noncode.deployment_frontier_audit_log import append_deployment_frontier_audit_event, build_deployment_frontier_audit_log, verify_deployment_frontier_audit_log
from glio_noncode.deployment_frontier_delta import compare_deployment_frontier_evaluations
from glio_noncode.deployment_frontier_exports import export_deployment_frontier_json, export_deployment_frontier_review_csv
from glio_noncode.deployment_frontier_locking import acquire_deployment_frontier_lock
from glio_noncode.deployment_frontier_public_data import deployment_frontier_fixture_json, default_deployment_frontier_fixture, load_deployment_frontier_fixture
from glio_noncode.deployment_frontier_query import query_deployment_frontier
from glio_noncode.deployment_frontier_replay import replay_deployment_frontier_evaluation
from glio_noncode.deployment_frontier_schema import default_deployment_frontier_schema, validate_deployment_frontier_schema
from glio_noncode.deployment_frontier_support import bounded_ratio
from glio_noncode.deployment_frontier_versioning import inspect_deployment_frontier_version, migrate_deployment_frontier_metadata
from glio_noncode.deployment_frontier_fixture_eval import evaluate_deployment_frontier_fixture


class DeploymentFrontierExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_deployment_frontier_fixture()
        cls.evaluation = evaluate_deployment_frontier_fixture(cls.fixture)

    def test_replay_delta_and_exports(self) -> None:
        replay = replay_deployment_frontier_evaluation(self.fixture, self.evaluation)
        self.assertTrue(replay.deterministic)
        delta = compare_deployment_frontier_evaluations(self.evaluation, self.evaluation)
        self.assertTrue(delta.identical)
        self.assertEqual(len(export_deployment_frontier_review_csv(self.evaluation).splitlines()), 17)
        self.assertIn('"fixture_id"', export_deployment_frontier_json(self.evaluation))

    def test_schema_lock_and_version_receipts(self) -> None:
        schema = default_deployment_frontier_schema()
        self.assertEqual(validate_deployment_frontier_schema(self.fixture.records[0].payload, self.fixture.records[0].operation, schema), ())
        first = acquire_deployment_frontier_lock("run-1", "key-1")
        reused = acquire_deployment_frontier_lock("run-1", "key-1", existing_keys=("key-1",))
        self.assertTrue(first.acquired)
        self.assertTrue(reused.reused)
        self.assertTrue(inspect_deployment_frontier_version("2026.08.d16-c13-c16.v1").compatible)
        self.assertEqual(migrate_deployment_frontier_metadata({})["deployment_frontier_version"], "2026.08.d16-c13-c16.v1")
        self.assertEqual(bounded_ratio(2, 4), 0.5)

    def test_fixture_round_trip_validates_identity_and_address(self) -> None:
        import tempfile
        from pathlib import Path

        example = Path(__file__).resolve().parents[1] / "examples" / "deployment-frontier-public-aggregate.json"
        self.assertEqual(load_deployment_frontier_fixture(example).content_address, self.fixture.content_address)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(deployment_frontier_fixture_json(self.fixture), encoding="utf-8")
            loaded = load_deployment_frontier_fixture(path)
            self.assertEqual(loaded.content_address, self.fixture.content_address)

    def test_append_only_audit_log(self) -> None:
        log = build_deployment_frontier_audit_log(("data-audit", "release"))
        extended = append_deployment_frontier_audit_event(log, "bundle")
        self.assertEqual(verify_deployment_frontier_audit_log(extended), ())
        self.assertEqual(len(extended.events), 3)
        self.assertEqual(tuple(item.sequence for item in extended.events), (1, 2, 3))
        self.assertEqual(len(query_deployment_frontier(self.evaluation, "hold").hits), 6)


if __name__ == "__main__":
    unittest.main()

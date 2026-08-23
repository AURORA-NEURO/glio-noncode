from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from glio_noncode.validation_release_frontier_audit_log import append_validation_release_audit_event, build_validation_release_audit_log, verify_validation_release_audit_log
from glio_noncode.validation_release_frontier_benchmark import benchmark_validation_release
from glio_noncode.validation_release_frontier_claim_boundary import evaluate_validation_release_claim_boundary
from glio_noncode.validation_release_frontier_contract_migrations import build_validation_release_contract_migrations
from glio_noncode.validation_release_frontier_delta import compare_validation_release_evaluations
from glio_noncode.validation_release_frontier_exports import export_validation_release_json, export_validation_release_review_csv
from glio_noncode.validation_release_frontier_fixture_eval import evaluate_validation_release_fixture
from glio_noncode.validation_release_frontier_locking import acquire_validation_release_lock
from glio_noncode.validation_release_frontier_public_data import default_validation_release_frontier_fixture, load_validation_release_frontier_fixture, validation_release_frontier_fixture_json
from glio_noncode.validation_release_frontier_query import query_validation_release
from glio_noncode.validation_release_frontier_replay import replay_validation_release_evaluation
from glio_noncode.validation_release_frontier_schema import default_validation_release_frontier_schema, validate_validation_release_schema
from glio_noncode.validation_release_frontier_thresholds import build_validation_release_threshold_report
from glio_noncode.validation_release_frontier_versioning import inspect_validation_release_version, migrate_validation_release_metadata


class ValidationReleaseFrontierExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = default_validation_release_frontier_fixture()
        cls.evaluation = evaluate_validation_release_fixture(cls.fixture)

    def test_replay_delta_exports_and_fixture_round_trip(self) -> None:
        self.assertTrue(replay_validation_release_evaluation(self.fixture, self.evaluation).deterministic)
        self.assertTrue(compare_validation_release_evaluations(self.evaluation, self.evaluation).identical)
        self.assertEqual(len(export_validation_release_review_csv(self.evaluation).splitlines()), 17)
        self.assertIn('"fixture_id"', export_validation_release_json(self.evaluation))
        example = Path(__file__).resolve().parents[1] / "examples" / "validation-release-public-aggregate.json"
        self.assertEqual(load_validation_release_frontier_fixture(example).content_address, self.fixture.content_address)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(validation_release_frontier_fixture_json(self.fixture), encoding="utf-8")
            self.assertEqual(load_validation_release_frontier_fixture(path).content_address, self.fixture.content_address)

    def test_schema_lock_and_version(self) -> None:
        schema = default_validation_release_frontier_schema()
        self.assertEqual(validate_validation_release_schema(self.fixture.records[0].payload, self.fixture.records[0].operation, schema), ())
        first = acquire_validation_release_lock("run-1", "key-1")
        reused = acquire_validation_release_lock("run-1", "key-1", existing_keys=("key-1",))
        self.assertTrue(first.acquired)
        self.assertTrue(reused.reused)
        self.assertTrue(inspect_validation_release_version("2026.08.d13-c13-c16.v1").compatible)
        self.assertEqual(migrate_validation_release_metadata({})["validation_release_version"], "2026.08.d13-c13-c16.v1")

    def test_append_only_log_and_query(self) -> None:
        log = build_validation_release_audit_log(("data-audit", "release"))
        extended = append_validation_release_audit_event(log, "bundle")
        self.assertEqual(verify_validation_release_audit_log(extended), ())
        self.assertEqual(tuple(item.sequence for item in extended.events), (1, 2, 3))
        self.assertTrue(query_validation_release(self.evaluation, "blocked").hits)

    def test_benchmark_and_contract_migration_receipts(self) -> None:
        benchmark = benchmark_validation_release(self.fixture, iterations=2)
        self.assertTrue(benchmark.accepted)
        self.assertEqual(benchmark.check_count, 80)
        self.assertTrue(build_validation_release_contract_migrations().accepted)
        self.assertEqual(build_validation_release_threshold_report().probe_count, 4)
        boundary = evaluate_validation_release_claim_boundary(self.evaluation)
        self.assertTrue(boundary.accepted)
        self.assertIn("clinical efficacy", boundary.prohibited_claims)
        self.assertIn("treatment recommendation", boundary.prohibited_claims)
        self.assertEqual(tuple(sorted(boundary.observed_operations)), ("claim_update", "experiment_package", "off_target_risk", "value_of_information"))
        self.assertTrue(benchmark.deterministic_address.startswith("sha256:"))
        self.assertGreater(benchmark.elapsed_ms, 0.0)
        self.assertEqual(benchmark.iterations, 2)
        self.assertEqual(benchmark.record_count, 16)
        self.assertTrue(benchmark.content_address.startswith("sha256:"))
        self.assertTrue(build_validation_release_contract_migrations().migrations[0].reversible)
        self.assertEqual(build_validation_release_contract_migrations().migrations[0].to_version, "2026.08.d13-c13-c16.v1")
        self.assertTrue(build_validation_release_contract_migrations().content_address.startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()

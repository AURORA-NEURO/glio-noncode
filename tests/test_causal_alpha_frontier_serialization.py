from __future__ import annotations

import json
import unittest

from glio_noncode.causal_alpha_frontier_artifacts import CausalAlphaFrontierArtifactKind
from glio_noncode.causal_alpha_frontier_fixture_eval import evaluate_causal_alpha_frontier_fixture_deep
from glio_noncode.causal_alpha_frontier_public_data import default_causal_alpha_frontier_fixture
from glio_noncode.causal_alpha_frontier_query import query_causal_alpha_frontier
from glio_noncode.causal_alpha_frontier_replay import replay_causal_alpha_frontier
from glio_noncode.causal_alpha_frontier_runtime import run_causal_alpha_frontier_runtime
from glio_noncode.serialization import content_hash, jsonable


class CausalAlphaFrontierSerializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = default_causal_alpha_frontier_fixture()

    def test_fixture_jsonable_round_trip_is_serializable(self) -> None:
        payload = jsonable(self.fixture)
        encoded = json.dumps(payload, sort_keys=True)
        decoded = json.loads(encoded)
        self.assertEqual(decoded["fixture_id"], self.fixture.fixture_id)
        self.assertEqual(len(decoded["sources"]), 5)
        self.assertEqual(len(decoded["records"]), 16)

    def test_content_addresses_are_deterministic_for_same_fixture(self) -> None:
        first = default_causal_alpha_frontier_fixture()
        second = default_causal_alpha_frontier_fixture()
        self.assertEqual(first.content_address, second.content_address)
        self.assertEqual(tuple(item.content_address for item in first.records), tuple(item.content_address for item in second.records))
        self.assertEqual(content_hash(first.to_dict(False)), first.content_address)

    def test_evaluation_serializes_nested_operation_outputs(self) -> None:
        evaluation = evaluate_causal_alpha_frontier_fixture_deep(self.fixture)
        payload = evaluation.to_dict()
        encoded = json.dumps(jsonable(payload), sort_keys=True)
        self.assertGreater(len(encoded), 10000)
        decoded = json.loads(encoded)
        self.assertTrue(decoded["accepted"])
        self.assertEqual(len(decoded["evaluation"]["results"]), 16)
        self.assertTrue(all(item["content_address"].startswith("sha256:") for item in decoded["evaluation"]["results"]))

    def test_runtime_nested_release_surface_serializes(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-serialization")
        payload = jsonable(runtime.to_dict())
        decoded = json.loads(json.dumps(payload, sort_keys=True))
        self.assertTrue(decoded["accepted"])
        self.assertEqual(decoded["stage_count"], 31)
        self.assertEqual(len(decoded["stages"]), 31)
        self.assertEqual(len(decoded["artifacts"]["artifacts"]), 19)
        self.assertEqual(len(decoded["exports"]["envelopes"]), 10)

    def test_runtime_addresses_have_stable_subplane_outputs(self) -> None:
        first = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-stable")
        second = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-stable")
        self.assertEqual(first.fixture.content_address, second.fixture.content_address)
        self.assertEqual(first.evaluation.content_address, second.evaluation.content_address)
        self.assertEqual(first.metrics.content_address, second.metrics.content_address)
        self.assertEqual(first.integrity.content_address, second.integrity.content_address)
        self.assertEqual(first.release.state, second.release.state)
        self.assertEqual(first.release.accepted, second.release.accepted)
        self.assertTrue(first.replay.deterministic and second.replay.deterministic)

    def test_replay_receipt_serializes_all_result_addresses(self) -> None:
        receipt = replay_causal_alpha_frontier(self.fixture, replay_id="alpha-serialization-replay")
        payload = jsonable(receipt)
        self.assertTrue(payload["deterministic"])
        self.assertEqual(len(payload["result_addresses"]), 16)
        self.assertEqual(payload["first_address"], payload["second_address"])

    def test_query_result_contains_typed_filters_and_rows(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-serialization-query")
        result = query_causal_alpha_frontier(runtime.bundle, state="out_of_domain")
        payload = jsonable(result)
        self.assertEqual(payload["filters"], {"state": "out_of_domain"})
        self.assertEqual(len(payload["rows"]), 4)
        self.assertEqual(payload["record_ids"], ["D11-C09-C3", "D11-C10-C3", "D11-C11-C3", "D11-C12-C3"])

    def test_artifact_kind_values_are_json_safe(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-serialization-artifacts")
        kinds = [item.kind.value for item in runtime.artifacts.artifacts]
        self.assertEqual(len(kinds), 19)
        self.assertEqual(kinds[0], CausalAlphaFrontierArtifactKind.FIXTURE.value)
        self.assertEqual(kinds[-1], CausalAlphaFrontierArtifactKind.RELEASE.value)
        self.assertEqual(len(set(kinds)), 19)

    def test_markdown_runbook_contains_every_step(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-serialization-runbook")
        text = runtime.runbook.to_markdown()
        for step in runtime.runbook.steps:
            self.assertIn(step.command, text)
        self.assertEqual(text.count("|"), 5 * (len(runtime.runbook.steps) + 2))

    def test_review_view_rows_are_json_safe(self) -> None:
        runtime = run_causal_alpha_frontier_runtime(self.fixture, run_id="alpha-serialization-view")
        payload = jsonable(runtime.review_view)
        self.assertTrue(payload["accepted"])
        self.assertEqual(len(payload["rows"]), 16)
        self.assertEqual(payload["rows"][0]["record_id"], "D11-C09-P")


if __name__ == "__main__":
    unittest.main()

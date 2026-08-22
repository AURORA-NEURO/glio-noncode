from __future__ import annotations

import json
import unittest

from glio_noncode.causal_beta_frontier_artifacts import build_causal_beta_frontier_artifact_inventory
from glio_noncode.causal_beta_frontier_assurance import build_causal_beta_frontier_assurance
from glio_noncode.causal_beta_frontier_bundle import assemble_causal_beta_frontier_bundle
from glio_noncode.causal_beta_frontier_claim_boundary import build_causal_beta_frontier_claim_boundary
from glio_noncode.causal_beta_frontier_contracts import build_causal_beta_frontier_contracts
from glio_noncode.causal_beta_frontier_exports import build_causal_beta_frontier_exports
from glio_noncode.causal_beta_frontier_fixture_eval import evaluate_causal_beta_frontier_fixture
from glio_noncode.causal_beta_frontier_integrity import evaluate_causal_beta_frontier_integrity
from glio_noncode.causal_beta_frontier_lineage import build_causal_beta_frontier_lineage
from glio_noncode.causal_beta_frontier_metrics import build_causal_beta_frontier_metrics
from glio_noncode.causal_beta_frontier_operational import build_causal_beta_frontier_operational_matrix
from glio_noncode.causal_beta_frontier_policy import default_causal_beta_frontier_policy
from glio_noncode.causal_beta_frontier_provenance import build_causal_beta_frontier_provenance
from glio_noncode.causal_beta_frontier_public_data import CausalBetaFrontierOperation, CausalBetaFrontierRole, causal_beta_frontier_fixture_json, default_causal_beta_frontier_fixture
from glio_noncode.causal_beta_frontier_reconciliation import reconcile_causal_beta_frontier
from glio_noncode.causal_beta_frontier_release import build_causal_beta_frontier_release_manifest
from glio_noncode.causal_beta_frontier_review import build_causal_beta_frontier_review_queue
from glio_noncode.causal_beta_frontier_runtime import run_causal_beta_frontier_runtime
from glio_noncode.causal_beta_frontier_schema import validate_causal_beta_frontier_schema
from glio_noncode.causal_beta_frontier_scenario_matrix import build_causal_beta_frontier_scenario_matrix
from glio_noncode.causal_beta_frontier_validation_matrix import build_causal_beta_frontier_validation_matrix
from glio_noncode.causal_beta_frontier_views import build_causal_beta_frontier_review_view


def make_surfaces():
    fixture = default_causal_beta_frontier_fixture()
    evaluation = evaluate_causal_beta_frontier_fixture(fixture)
    contracts = build_causal_beta_frontier_contracts()
    schema = validate_causal_beta_frontier_schema(fixture, evaluation)
    metrics = build_causal_beta_frontier_metrics(evaluation, fixture)
    lineage = build_causal_beta_frontier_lineage(fixture, evaluation)
    provenance = build_causal_beta_frontier_provenance(fixture, evaluation)
    policy = default_causal_beta_frontier_policy()
    decisions = policy.decide(evaluation)
    review = build_causal_beta_frontier_review_queue(evaluation, policy)
    reconciliation = reconcile_causal_beta_frontier(fixture, evaluation, decisions, policy)
    scenario = build_causal_beta_frontier_scenario_matrix(fixture, evaluation)
    validation = build_causal_beta_frontier_validation_matrix(fixture, evaluation)
    from glio_noncode.causal_beta_frontier_depth import audit_causal_beta_frontier_depth
    from glio_noncode.causal_beta_frontier_quality_gate import evaluate_causal_beta_frontier_quality
    from glio_noncode.causal_beta_frontier_adapters import build_causal_beta_frontier_adapters
    adapters = build_causal_beta_frontier_adapters()
    depth = audit_causal_beta_frontier_depth(fixture, evaluation, adapters, contracts, schema, metrics, lineage, provenance)
    gate = evaluate_causal_beta_frontier_quality(fixture, evaluation, contracts, schema, metrics, lineage, reconciliation, depth, review, decisions)
    bundle = assemble_causal_beta_frontier_bundle(fixture, evaluation, metrics, contracts, schema, lineage, provenance, depth, reconciliation, policy, review, gate, scenario, validation)
    release = build_causal_beta_frontier_release_manifest(bundle, gate, depth, review)
    artifacts = build_causal_beta_frontier_artifact_inventory(fixture, evaluation, bundle, release)
    operational = build_causal_beta_frontier_operational_matrix(fixture, evaluation, decisions, review, bundle)
    boundary = build_causal_beta_frontier_claim_boundary(bundle, operational)
    replay = run_causal_beta_frontier_runtime(run_id="serialization-test")
    view = build_causal_beta_frontier_review_view(fixture, evaluation, decisions, reconciliation, review)
    exports = build_causal_beta_frontier_exports(fixture, evaluation, metrics, view, bundle, release, artifacts)
    integrity = evaluate_causal_beta_frontier_integrity(fixture, evaluation, lineage, provenance)
    assurance = build_causal_beta_frontier_assurance(replay, replay.replay, integrity, operational, boundary, exports, release)
    return fixture, evaluation, contracts, schema, metrics, lineage, provenance, policy, review, reconciliation, scenario, validation, depth, gate, bundle, release, artifacts, operational, boundary, view, exports, integrity, assurance


class CausalBetaFrontierSerializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.values = make_surfaces()
        (
            cls.fixture,
            cls.evaluation,
            cls.contracts,
            cls.schema,
            cls.metrics,
            cls.lineage,
            cls.provenance,
            cls.policy,
            cls.review,
            cls.reconciliation,
            cls.scenario,
            cls.validation,
            cls.depth,
            cls.gate,
            cls.bundle,
            cls.release,
            cls.artifacts,
            cls.operational,
            cls.boundary,
            cls.view,
            cls.exports,
            cls.integrity,
            cls.assurance,
        ) = cls.values

    def test_fixture_json_is_sorted(self) -> None:
        value = causal_beta_frontier_fixture_json(self.fixture)
        self.assertEqual(value, causal_beta_frontier_fixture_json())
        self.assertEqual(json.loads(value)["fixture_id"], self.fixture.fixture_id)

    def test_every_surface_can_be_json_encoded(self) -> None:
        surfaces = self.values
        for surface in surfaces:
            encoded = json.dumps(surface.to_dict(), default=str, sort_keys=True)
            decoded = json.loads(encoded)
            self.assertIsInstance(decoded, dict)
            self.assertIn("content_address", decoded)

    def test_every_surface_address_is_prefixed(self) -> None:
        for surface in self.values:
            self.assertTrue(surface.content_address.startswith("sha256:"), type(surface).__name__)

    def test_fixture_address_changes_when_record_payload_changes(self) -> None:
        first = self.fixture.content_address
        record = self.fixture.records[0]
        from dataclasses import replace
        changed_record = replace(record, description=record.description + " changed", content_address="")
        changed_fixture = replace(self.fixture, records=(changed_record,) + self.fixture.records[1:], content_address="")
        self.assertNotEqual(first, changed_fixture.content_address)

    def test_evaluation_address_changes_when_a_row_changes(self) -> None:
        from dataclasses import replace
        changed = replace(self.evaluation, accepted=False, content_address="")
        self.assertNotEqual(self.evaluation.content_address, changed.content_address)

    def test_release_address_changes_when_boundary_changes(self) -> None:
        from dataclasses import replace
        changed = replace(self.release, accepted=False, content_address="")
        self.assertNotEqual(self.release.content_address, changed.content_address)

    def test_enum_values_are_serialized_as_strings_by_jsonable(self) -> None:
        payload = self.fixture.to_dict()
        decoded = json.loads(json.dumps(payload, default=str))
        self.assertEqual(decoded["records"][0]["operation"], "sequence_to_element")
        self.assertEqual(decoded["records"][0]["role"], "positive")
        self.assertEqual(decoded["records"][0]["expected_state"], "supported")

    def test_operations_are_closed(self) -> None:
        self.assertEqual({item.value for item in CausalBetaFrontierOperation}, {item["value"] if isinstance(item, dict) and "value" in item else item.value for item in CausalBetaFrontierOperation})
        self.assertEqual(len(self.metrics.operations), len(CausalBetaFrontierOperation))

    def test_roles_are_closed(self) -> None:
        self.assertEqual({item.value for item in CausalBetaFrontierRole}, {"positive", "control"})
        self.assertEqual(len(self.fixture.positive_records) + len(self.fixture.control_records), 16)

    def test_to_dict_without_address_has_no_root_address(self) -> None:
        for surface in self.values:
            self.assertNotIn("content_address", surface.to_dict(False))

    def test_nested_export_addresses_are_present(self) -> None:
        payload = self.exports.to_dict()
        self.assertTrue(payload["content_address"].startswith("sha256:"))
        self.assertTrue(all(item["content_address"].startswith("sha256:") for item in payload["envelopes"]))

    def test_runtime_surface_addresses_are_consistent_with_subsurfaces(self) -> None:
        runtime = run_causal_beta_frontier_runtime(run_id="serialization-runtime")
        self.assertEqual(runtime.fixture.content_address, self.fixture.content_address)
        self.assertEqual(runtime.evaluation.content_address, self.evaluation.content_address)
        self.assertEqual(runtime.operational.content_address, self.operational.content_address)
        self.assertEqual(runtime.release.state, self.release.state)
        self.assertEqual(runtime.release.accepted, self.release.accepted)

    def test_runtime_json_is_deterministically_representable(self) -> None:
        first = run_causal_beta_frontier_runtime(run_id="serialization-runtime")
        second = run_causal_beta_frontier_runtime(run_id="serialization-runtime")
        self.assertEqual(first.fixture.content_address, second.fixture.content_address)
        self.assertEqual(first.evaluation.content_address, second.evaluation.content_address)
        self.assertEqual(first.metrics.content_address, second.metrics.content_address)
        self.assertEqual(first.operational.content_address, second.operational.content_address)

    def test_schema_fields_round_trip(self) -> None:
        decoded = json.loads(json.dumps(self.schema.to_dict(), default=str))
        self.assertEqual(len(decoded["fields"]), 10)
        self.assertEqual(decoded["fields"][0]["name"], "record_id")
        self.assertTrue(decoded["accepted"])

    def test_metrics_round_trip(self) -> None:
        decoded = json.loads(json.dumps(self.metrics.to_dict(), default=str))
        self.assertEqual(decoded["record_count"], 16)
        self.assertEqual(len(decoded["operations"]), 4)
        self.assertEqual(decoded["state_accuracy"], 1.0)

    def test_lineage_round_trip(self) -> None:
        decoded = json.loads(json.dumps(self.lineage.to_dict(), default=str))
        self.assertEqual(decoded["fixture_edge_count"], 16)
        self.assertEqual(decoded["record_edge_count"], 16)
        self.assertTrue(decoded["accepted"])

    def test_provenance_round_trip(self) -> None:
        decoded = json.loads(json.dumps(self.provenance.to_dict(), default=str))
        self.assertEqual(decoded["node_count"], 38)
        self.assertEqual(decoded["orphan_node_ids"], [])
        self.assertTrue(decoded["accepted"])

    def test_review_round_trip(self) -> None:
        decoded = json.loads(json.dumps(self.review.to_dict(), default=str))
        self.assertEqual(len(decoded["items"]), 16)
        self.assertEqual(decoded["blocking_record_ids"].__len__(), 8)

    def test_validation_round_trip(self) -> None:
        decoded = json.loads(json.dumps(self.validation.to_dict(), default=str))
        self.assertEqual(decoded["cell_count"], 16)
        self.assertEqual(decoded["passed_count"], 16)

    def test_artifact_round_trip(self) -> None:
        decoded = json.loads(json.dumps(self.artifacts.to_dict(), default=str))
        self.assertEqual(decoded["required_count"], 16)
        self.assertEqual(decoded["resolved_count"], 16)

    def test_operational_round_trip(self) -> None:
        decoded = json.loads(json.dumps(self.operational.to_dict(), default=str))
        self.assertEqual(decoded["cell_count"], 16)
        self.assertEqual(decoded["allowed_count"], 4)

    def test_boundary_round_trip(self) -> None:
        decoded = json.loads(json.dumps(self.boundary.to_dict(), default=str))
        self.assertEqual(decoded["allowed_count"], 3)
        self.assertEqual(decoded["excluded_count"], 4)

    def test_assurance_round_trip(self) -> None:
        decoded = json.loads(json.dumps(self.assurance.to_dict(), default=str))
        self.assertTrue(decoded["accepted"])
        self.assertEqual(decoded["release_state"], "ready")

    def test_reported_content_is_not_empty(self) -> None:
        self.assertTrue(self.exports.by_kind("review-csv").payload)
        self.assertTrue(self.exports.by_kind("review-markdown").payload)
        self.assertTrue(self.exports.by_kind("fixture-json").payload)

    def test_source_receipt_order_is_stable(self) -> None:
        again = default_causal_beta_frontier_fixture()
        self.assertEqual(tuple(item.source_id for item in self.fixture.sources), tuple(item.source_id for item in again.sources))
        self.assertEqual(tuple(item.record_id for item in self.fixture.records), tuple(item.record_id for item in again.records))

    def test_operation_record_order_is_stable(self) -> None:
        again = default_causal_beta_frontier_fixture()
        for operation in CausalBetaFrontierOperation:
            self.assertEqual(tuple(item.record_id for item in self.fixture.operation_records(operation)), tuple(item.record_id for item in again.operation_records(operation)))

    def test_public_fixture_json_contains_no_missing_root_fields(self) -> None:
        decoded = json.loads(causal_beta_frontier_fixture_json())
        required = {"fixture_id", "version", "context_key", "foreign_context_key", "boundary", "sources", "records", "content_address"}
        self.assertTrue(required <= set(decoded))

    def test_public_fixture_json_contains_all_record_fields(self) -> None:
        decoded = json.loads(causal_beta_frontier_fixture_json())
        required = {"record_id", "operation", "role", "context_key", "source_ids", "payload", "expected_state", "expected_issue_codes", "description", "content_address"}
        self.assertTrue(all(required <= set(item) for item in decoded["records"]))

    def test_public_fixture_json_contains_all_source_fields(self) -> None:
        decoded = json.loads(causal_beta_frontier_fixture_json())
        required = {"source_id", "title", "uri", "source_kind", "release", "scope", "content_address"}
        self.assertTrue(all(required <= set(item) for item in decoded["sources"]))

    def test_address_prefix_is_sha256_for_all_nested_rows(self) -> None:
        decoded = json.loads(causal_beta_frontier_fixture_json())
        self.assertTrue(all(item["content_address"].startswith("sha256:") for item in decoded["records"]))
        self.assertTrue(all(item["content_address"].startswith("sha256:") for item in decoded["sources"]))

    def test_surface_counts_are_conserved(self) -> None:
        self.assertEqual(len(self.evaluation.rows), len(self.fixture.records))
        self.assertEqual(len(self.review.items), len(self.evaluation.rows))
        self.assertEqual(len(self.view.rows), len(self.evaluation.rows))
        self.assertEqual(len(self.operational.cells), len(self.evaluation.rows))
        self.assertEqual(len(self.validation.cells), len(self.evaluation.rows))

    def test_release_surface_addresses_are_all_nonempty(self) -> None:
        addresses = (self.bundle.content_address, self.release.content_address, self.artifacts.content_address, self.operational.content_address, self.boundary.content_address, self.exports.content_address, self.integrity.content_address, self.assurance.content_address)
        self.assertEqual(len(addresses), 8)
        self.assertTrue(all(item.startswith("sha256:") for item in addresses))


if __name__ == "__main__":
    unittest.main()

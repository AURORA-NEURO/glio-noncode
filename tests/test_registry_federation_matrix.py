"""Contract tests for multi-peer federation agreement matrices."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from glio_noncode import registry_federation_matrix, registry_federation_matrix_audit
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class RegistryFederationMatrixTests(DurableCatalogPromotionPackageFixture):
    """Exercise pairwise comparison, audit, serialization, and adapters."""

    def _directories(self, root: Path):
        package = self.package_for(root / "package-input", package_id="matrix-package")
        held = self.package_for(root / "held-input", package_id="matrix-package", held=True)
        first = registry_model.build_registry((package,), registry_id="matrix-first")
        second = registry_model.build_registry((package,), registry_id="matrix-second")
        third = registry_model.build_registry((held,), registry_id="matrix-third")
        paths = (root / "first", root / "second", root / "third")
        for value, path in zip((first, second, third), paths, strict=True):
            registry_model.write_registry(value, path)
        return paths

    def _matrix(self, root: Path):
        first, second, third = self._directories(root)
        federation = federation_model.build_federation_from_directories((
            ("alpha", first),
            ("beta", second),
            ("gamma", third),
        ), federation_id="matrix-federation")
        return registry_federation_matrix.build_matrix(federation, matrix_id="matrix-contract")

    def test_three_peer_matrix_has_three_canonical_pairs(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            self.assertEqual(value.peer_ids, ("alpha", "beta", "gamma"))
            self.assertEqual((value.pair_count, value.matching_pair_count, value.divergent_pair_count), (3, 1, 2))
            self.assertEqual(value.state, "conflicted")
            self.assertEqual([item.state for item in value.observations], ["consistent", "conflicted", "conflicted"])
            self.assertEqual([(item.left_peer_id, item.right_peer_id) for item in value.observations], [("alpha", "beta"), ("alpha", "gamma"), ("beta", "gamma")])
            self.assertEqual(value.observations[0].agreement_ratio, 1.0)
            self.assertEqual(value.observations[1].divergent_package_count, 1)
            self.assertEqual(value.observations[2].divergent_package_count, 1)

    def test_matrix_content_and_mapping_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            self.assertEqual(registry_federation_matrix.address_matrix(value), value.content_address)
            self.assertEqual(registry_federation_matrix.matrix_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(registry_federation_matrix.matrix_json(value), registry_federation_matrix.matrix_json(registry_federation_matrix.matrix_from_mapping(json.loads(registry_federation_matrix.matrix_json(value)))))
            self.assertIn("left-only", registry_federation_matrix.render_matrix_markdown(value))
            self.assertTrue(registry_federation_matrix.matrix_csv(value).startswith("ordinal,left_peer_id,right_peer_id"))

    def test_independent_matrix_audit_covers_all_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            audit = registry_federation_matrix_audit.audit_matrix(value)
            self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (16, 16, 0, True))
            self.assertEqual(tuple(item.check_id for item in audit.checks), registry_federation_matrix.CHECK_IDS)
            self.assertEqual(registry_federation_matrix_audit.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertIn("content-address", registry_federation_matrix_audit.render_audit_markdown(audit))
            self.assertIn("check_id", registry_federation_matrix_audit.audit_csv(audit).splitlines()[0])

    def test_single_peer_and_empty_comparison_are_consistent(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, _, _ = self._directories(Path(temporary))
            federation = federation_model.build_federation_from_directories((("solo", first),), federation_id="solo-federation")
            value = registry_federation_matrix.build_matrix(federation, matrix_id="solo-matrix")
            self.assertEqual((value.pair_count, value.matching_pair_count, value.divergent_pair_count, value.agreement_ratio, value.state), (0, 0, 0, 1.0, "consistent"))
            self.assertTrue(registry_federation_matrix_audit.audit_matrix(value).accepted)

    def test_matrix_validation_rejects_pair_and_address_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            corrupted = value.to_dict()
            corrupted["pair_count"] = 2
            with self.assertRaises(ValidationError):
                registry_federation_matrix.matrix_from_mapping(corrupted)

    def test_matrix_query_filters_pairs_and_replays_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            query = registry_federation_matrix.query_matrix(value, peer_id="gamma", state="conflicted", offset=0, limit=1)
            self.assertEqual((query.total_count, query.matched_count, query.returned_count, query.truncated), (3, 2, 1, True))
            self.assertEqual(query.next_offset, 1)
            self.assertEqual(query.rows[0].left_peer_id, "alpha")
            replayed = registry_federation_matrix.query_from_mapping(query.to_dict())
            self.assertEqual(replayed.to_dict(), query.to_dict())
            self.assertIn("pair", registry_federation_matrix.render_query_markdown(query))
            self.assertTrue(registry_federation_matrix.query_csv(query).startswith("ordinal,row_id,left_peer_id"))
            matrix_path = Path(temporary) / "matrix.json"
            matrix_path.write_text(registry_federation_matrix.matrix_json(value), encoding="utf-8")
            self.assertEqual(main(["registry-federation-matrix-query", "--input", str(matrix_path), "--state", "conflicted", "--format", "summary"]), 0)

    def test_matrix_query_rejects_wrong_matrix_and_bad_pagination(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            query = registry_federation_matrix.build_query(value, limit=1)
            other = registry_federation_matrix.build_matrix(federation_model.build_federation_from_directories((("solo", self._directories(Path(temporary) / "other")[0]),), federation_id="other-matrix-federation"), matrix_id="other-matrix")
            with self.assertRaises(ValidationError):
                registry_federation_matrix.query_matrix(other, query=query)
            with self.assertRaises(ValidationError):
                registry_federation_matrix.build_query(value, offset=registry_federation_matrix.MAX_OBSERVATIONS + 1)
            with self.assertRaises(ValidationError):
                registry_federation_matrix.build_query(value, limit=0)

    def test_query_default_page_is_bounded_and_state_filter_is_optional(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            result = registry_federation_matrix.query_matrix(value)
            self.assertEqual((result.total_count, result.matched_count, result.returned_count, result.next_offset, result.truncated), (3, 3, 3, 0, False))
            self.assertEqual([row.ordinal for row in result.rows], [1, 2, 3])
            self.assertEqual(registry_federation_matrix.query_matrix(value, state="consistent").matched_count, 1)
            self.assertEqual(registry_federation_matrix.query_matrix(value, state="conflicted").matched_count, 2)
            self.assertEqual(registry_federation_matrix.query_matrix(value, peer_id="missing").matched_count, 0)

    def test_query_result_rejects_counter_and_nested_query_corruption(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            result = registry_federation_matrix.query_matrix(value, limit=1)
            corrupted = result.to_dict()
            corrupted["next_offset"] = 0
            with self.assertRaises(ValidationError):
                registry_federation_matrix.query_from_mapping(corrupted)
            corrupted = result.to_dict()
            corrupted["query"] = dict(corrupted["query"])
            corrupted["query"]["matrix_address"] = value.content_address + "-changed"
            with self.assertRaises(ValidationError):
                registry_federation_matrix.query_from_mapping(corrupted)
            corrupted = result.to_dict()
            corrupted["rows"] = list(corrupted["rows"])
            corrupted["rows"][0] = dict(corrupted["rows"][0])
            corrupted["rows"][0]["agreement_ratio"] = 0.5
            with self.assertRaises(ValidationError):
                registry_federation_matrix.query_from_mapping(corrupted)

    def test_schema_and_capabilities_describe_every_matrix_projection(self):
        capabilities = registry_federation_matrix.capabilities()
        self.assertEqual(set(capabilities["schemas"]), {"observation", "matrix", "query", "row", "result"})
        self.assertEqual(capabilities["limits"]["max_observations"], registry_federation_matrix.MAX_OBSERVATIONS)
        self.assertEqual(registry_federation_matrix.matrix_schema()["required"], list(registry_federation_matrix.RegistryFederationMatrix.FIELDS))
        self.assertEqual(registry_federation_matrix.observation_schema()["required"], list(registry_federation_matrix.RegistryFederationMatrixObservation.FIELDS))
        self.assertEqual(registry_federation_matrix.query_schema()["required"], list(registry_federation_matrix.RegistryFederationMatrixQuery.FIELDS))
        self.assertEqual(registry_federation_matrix.query_row_schema()["required"], list(registry_federation_matrix.RegistryFederationMatrixQueryRow.FIELDS))
        self.assertEqual(registry_federation_matrix.query_result_schema()["required"], list(registry_federation_matrix.RegistryFederationMatrixQueryResult.FIELDS))

    def test_each_pair_keeps_sorted_path_free_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            for observation in value.observations:
                self.assertEqual(observation.evidence_addresses, tuple(sorted(observation.evidence_addresses)))
                self.assertEqual(len(observation.evidence_addresses), len(set(observation.evidence_addresses)))
                self.assertTrue(all("/" not in address and "\\" not in address for address in observation.evidence_addresses))
                self.assertEqual(registry_federation_matrix.address_observation(observation), observation.content_address)
            self.assertEqual(value.observations[0].package_ids, value.observations[1].package_ids)
            self.assertEqual(value.observations[0].common_package_count, 1)
            self.assertEqual(value.observations[1].common_package_count, 1)

    def test_matrix_audit_rejects_unknown_check_and_counter_mutations(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            audit = registry_federation_matrix_audit.audit_matrix(value)
            corrupted = audit.to_dict()
            corrupted["checks"] = list(corrupted["checks"])
            corrupted["checks"][0] = dict(corrupted["checks"][0])
            corrupted["checks"][0]["check_id"] = "unknown-check"
            with self.assertRaises(ValidationError):
                registry_federation_matrix_audit.audit_from_mapping(corrupted)
            corrupted = audit.to_dict()
            corrupted["passed_count"] = 15
            with self.assertRaises(ValidationError):
                registry_federation_matrix_audit.audit_from_mapping(corrupted)
            corrupted = audit.to_dict()
            corrupted["accepted"] = False
            with self.assertRaises(ValidationError):
                registry_federation_matrix_audit.audit_from_mapping(corrupted)

    def test_query_page_two_has_rebased_ordinals_and_stable_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            first = registry_federation_matrix.query_matrix(value, offset=0, limit=1)
            second = registry_federation_matrix.query_matrix(value, offset=1, limit=1)
            self.assertTrue(first.truncated)
            self.assertTrue(second.truncated)
            self.assertEqual(first.next_offset, 1)
            self.assertEqual(second.next_offset, 2)
            self.assertEqual(first.rows[0].ordinal, 1)
            self.assertEqual(second.rows[0].ordinal, 1)
            self.assertNotEqual(first.content_address, second.content_address)
            self.assertEqual(registry_federation_matrix.address_query_result(first), first.content_address)
            self.assertEqual(registry_federation_matrix.address_query_result(second), second.content_address)

    def test_empty_filtered_page_has_conserved_zero_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            result = registry_federation_matrix.query_matrix(value, peer_id="not-present", limit=1)
            self.assertEqual((result.total_count, result.matched_count, result.returned_count, result.next_offset, result.truncated, result.rows), (3, 0, 0, 0, False, ()))
            self.assertEqual(registry_federation_matrix.query_from_mapping(result.to_dict()).to_dict(), result.to_dict())

    def test_query_filter_rejects_unsupported_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._matrix(Path(temporary))
            with self.assertRaises(ValidationError):
                registry_federation_matrix.build_query(value, state="unknown")
            corrupted = value.to_dict()
            corrupted["observations"] = list(corrupted["observations"])
            corrupted["observations"][0] = dict(corrupted["observations"][0])
            corrupted["observations"][0]["content_address"] = "glio-noncode-assurance-history-observatory-archive-registry-history-release-gate-package-audit-release-certificate-pipeline-observability-bundle-catalog-diff-promotion-gate-release-packet-package-registry-federation-matrix-observation:broken"
            with self.assertRaises(ValidationError):
                registry_federation_matrix.matrix_from_mapping(corrupted)

    def test_cli_matrix_build_and_schema_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second, third = self._directories(Path(temporary))
            result = main(["registry-federation-matrix", "--peer", f"alpha={first}", "--peer", f"beta={second}", "--peer", f"gamma={third}", "--federation-id", "cli-matrix", "--format", "summary"])
            self.assertEqual(result, 2)
            self.assertEqual(main(["registry-federation-matrix-schema"]), 0)
            self.assertEqual(main(["registry-federation-matrix-audit-capabilities"]), 0)

    def test_http_matrix_routes_build_and_schema(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second, _ = self._directories(Path(temporary))
            server = create_server("127.0.0.1", 0)
            import threading
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}/v1/registry/federation"
            try:
                query = urlencode([("peer", f"alpha={first}"), ("peer", f"beta={second}"), ("federation_id", "http-matrix"), ("format", "summary")])
                with urlopen(base + "/matrix?" + query, timeout=10) as response:
                    payload = json.loads(response.read().decode())
                self.assertEqual((payload["pair_count"], payload["state"], payload["agreement_ratio"]), (1, "consistent", 1.0))
                with urlopen(base + "/matrix/schema", timeout=10) as response:
                    schema = json.loads(response.read().decode())
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertIn("observations", schema["properties"])
                federation = federation_model.build_federation_from_directories((("alpha", first), ("beta", second)), federation_id="http-query-federation")
                matrix = registry_federation_matrix.build_matrix(federation, matrix_id="http-query-matrix")
                matrix_path = Path(temporary) / "http-matrix.json"
                matrix_path.write_text(registry_federation_matrix.matrix_json(matrix), encoding="utf-8")
                with urlopen(base + "/matrix/query?" + urlencode({"input": str(matrix_path), "state": "consistent", "format": "summary"}), timeout=10) as response:
                    query_payload = json.loads(response.read().decode())
                self.assertEqual((query_payload["matched_count"], query_payload["returned_count"]), (1, 1))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)


if __name__ == "__main__":
    unittest.main()

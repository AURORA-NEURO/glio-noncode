"""Deep contract tests for federated package-registry reconciliation."""

# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from glio_noncode import registry_federation_audit, registry_federation_diff, registry_federation_diff_audit, registry_federation_gate, registry_federation_history, registry_federation_observatory, registry_federation_query, registry_federation_runtime
from glio_noncode.cli import build_parser, main
from glio_noncode.api import create_server
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class RegistryFederationTests(DurableCatalogPromotionPackageFixture):
    """Exercise the federation family as a deterministic public contract."""

    def _registries(self, root: Path):
        ready = self.package_for(root / "ready-input", package_id="package-ready")
        held_same = self.package_for(root / "held-input", held=True, package_id="package-ready")
        ready_registry = registry_model.build_registry((ready,), registry_id="registry-ready")
        replica_registry = registry_model.build_registry((ready,), registry_id="registry-replica")
        divergent_registry = registry_model.build_registry((held_same,), registry_id="registry-divergent")
        ready_directory = root / "ready-registry"
        replica_directory = root / "replica-registry"
        divergent_directory = root / "divergent-registry"
        registry_model.write_registry(ready_registry, ready_directory)
        registry_model.write_registry(replica_registry, replica_directory)
        registry_model.write_registry(divergent_registry, divergent_directory)
        return ready_directory, replica_directory, divergent_directory

    def _federations(self, root: Path):
        ready, replica, divergent = self._registries(root)
        consistent = federation_model.build_federation_from_directories((("primary", ready), ("replica", replica)), federation_id="federation-consistent")
        conflicted = federation_model.build_federation_from_directories((("primary", ready), ("replica", divergent)), federation_id="federation-conflicted")
        return consistent, conflicted, (ready, replica, divergent)

    def _assert_no_private_fields(self, value) -> None:
        forbidden = {"agent", "agent_id", "assistant", "language", "model", "author"}

        def walk(node):
            if isinstance(node, dict):
                for key, child in node.items():
                    self.assertNotIn(key, forbidden)
                    walk(child)
            elif isinstance(node, (list, tuple)):
                for child in node:
                    walk(child)

        walk(value)

    def test_consistent_replicas_accept_and_persist_five_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            value, _, _ = self._federations(Path(temporary))
            self.assertEqual((value.state, value.decision, value.accepted), ("consistent", "accept", True))
            self.assertEqual((value.peer_count, value.healthy_peer_count, value.package_count, value.conflict_count, value.action_count), (2, 2, 1, 0, 0))
            self.assertEqual(tuple(value.manifest["files"]), federation_model.ARTIFACT_FILES)
            self.assertEqual(federation_model.address_federation(value), value.content_address)
            self.assertEqual(set(federation_model.package_bytes(value)), set(federation_model.FILES))
            self._assert_no_private_fields(value.to_dict())

    def test_divergent_replica_is_rejected_with_blocking_action(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, value, _ = self._federations(Path(temporary))
            self.assertEqual((value.state, value.decision, value.accepted), ("conflicted", "reject", False))
            self.assertEqual((value.conflict_count, value.action_count), (1, 1))
            self.assertEqual(value.reconciliation.conflicts[0].kind, "divergent")
            self.assertEqual(value.reconciliation.conflicts[0].severity, "blocking")
            self.assertEqual(value.actions[0].kind, "conflict")
            self.assertFalse(value.actions[0].severity == "review")

    def test_mapping_and_disk_replay_are_byte_stable(self):
        with tempfile.TemporaryDirectory() as temporary:
            value, _, _ = self._federations(Path(temporary))
            self.assertEqual(federation_model.federation_from_mapping(value.to_dict()).content_address, value.content_address)
            destination = Path(temporary) / "federation"
            federation_model.write_federation(value, destination)
            loaded = federation_model.load_federation(destination)
            self.assertEqual(loaded.content_address, value.content_address)
            self.assertEqual({path.name for path in destination.iterdir()}, set(federation_model.FILES))
            self.assertEqual(federation_model.package_bytes(loaded), federation_model.package_bytes(value))
            with self.assertRaises(ValidationError):
                federation_model.write_federation(value, destination)

    def test_query_covers_resources_filters_and_pagination(self):
        with tempfile.TemporaryDirectory() as temporary:
            value, conflicted, _ = self._federations(Path(temporary))
            result = registry_federation_query.query_federation(value, resources=("summary", "peers", "packages"), limit=2)
            self.assertEqual((result.matched_count, result.returned_count, result.truncated, result.next_offset), (5, 2, True, 2))
            self.assertTrue(all(row.resource in {"summary", "peers", "packages"} for row in result.rows))
            page = registry_federation_query.query_federation(value, resources=("summary", "peers", "packages"), offset=2, limit=10)
            self.assertEqual(page.returned_count, 3)
            self.assertFalse(page.truncated)
            conflict_rows = registry_federation_query.query_federation(conflicted, resources=("conflicts",), kind="divergent", severity="blocking", limit=10)
            self.assertEqual((conflict_rows.matched_count, conflict_rows.rows[0].package_id, conflict_rows.rows[0].kind), (1, "package-ready", "divergent"))
            self.assertEqual(registry_federation_query.query_result_from_mapping(result.to_dict()).content_address, result.content_address)
            self.assertTrue(registry_federation_query.query_csv(result).startswith("ordinal,resource,row_id"))
            self.assertIn("# Package Registry Federation Query", registry_federation_query.render_query_markdown(result))

    def test_query_rejects_wrong_federation_and_bad_pagination(self):
        with tempfile.TemporaryDirectory() as temporary:
            value, _, _ = self._federations(Path(temporary))
            query = registry_federation_query.build_query(value, resources=("summary",), limit=1)
            other_ready, other_replica, _ = self._registries(Path(temporary) / "other")
            other = federation_model.build_federation_from_directories((("primary", other_ready), ("replica", other_replica)), federation_id="other-federation")
            with self.assertRaises(ValidationError):
                registry_federation_query.query_federation(other, query=query)
            with self.assertRaises(ValidationError):
                registry_federation_query.build_query(value, resources=("summary",), offset=-1)
            with self.assertRaises(ValidationError):
                registry_federation_query.build_query(value, resources=("all", "summary"))

    def test_independent_federation_audit_passes_every_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            value, conflicted, _ = self._federations(Path(temporary))
            for federation in (value, conflicted):
                audit = registry_federation_audit.audit_federation(federation)
                self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count, audit.accepted), (14, 14, 0, True))
                self.assertEqual(registry_federation_audit.audit_from_mapping(audit.to_dict()).content_address, audit.content_address)
                self.assertTrue(registry_federation_audit.audit_csv(audit).startswith("ordinal,check_id,passed"))
                self.assertIn("# Package Registry Federation Audit", registry_federation_audit.render_audit_markdown(audit))

    def test_diff_and_diff_audit_explain_transition(self):
        with tempfile.TemporaryDirectory() as temporary:
            consistent, conflicted, _ = self._federations(Path(temporary))
            value = registry_federation_diff.build_diff(consistent, conflicted, diff_id="federation-transition")
            self.assertEqual((value.left_state, value.right_state), ("consistent", "conflicted"))
            self.assertEqual((value.changed_peer_count, value.changed_package_count, value.changed_conflict_count, value.changed_action_count), (1, 1, 1, 1))
            self.assertEqual(value.item_count, 4)
            self.assertEqual(registry_federation_diff.diff_from_mapping(value.to_dict()).content_address, value.content_address)
            audit = registry_federation_diff_audit.audit_diff(value)
            self.assertEqual((audit.check_count, audit.passed_count, audit.failed_count), (12, 12, 0))
            self.assertEqual(registry_federation_diff_audit.audit_from_mapping(audit.to_dict()).content_address, audit.content_address)
            self.assertTrue(registry_federation_diff.diff_csv(value).startswith("ordinal,item_id,category"))

    def test_runtime_composes_audit_query_and_optional_persistence(self):
        with tempfile.TemporaryDirectory() as temporary:
            ready, replica, _ = self._registries(Path(temporary))
            destination = Path(temporary) / "runtime-federation"
            value = registry_federation_runtime.run_federation_runtime((("primary", ready), ("replica", replica)), runtime_id="runtime-demo", federation_id="runtime-fed", destination=destination, resources=("summary", "packages"), limit=3)
            self.assertTrue(value.persisted)
            self.assertTrue(destination.is_dir())
            self.assertEqual((value.federation.accepted, value.audit.accepted, value.query.returned_count), (True, True, 3))
            self.assertEqual(registry_federation_runtime.runtime_from_mapping(value.to_dict()).content_address, value.content_address)

    def test_schemas_and_capabilities_are_public(self):
        schemas = (federation_model.manifest_schema(), federation_model.peer_schema(), federation_model.conflict_schema(), federation_model.action_schema(), federation_model.reconciliation_schema(), federation_model.federation_schema(), registry_federation_query.query_schema(), registry_federation_query.row_schema(), registry_federation_query.result_schema(), registry_federation_audit.audit_schema(), registry_federation_audit.check_schema(), registry_federation_diff.diff_schema(), registry_federation_diff.item_schema(), registry_federation_diff_audit.audit_schema(), registry_federation_diff_audit.check_schema(), registry_federation_runtime.runtime_schema())
        for schema in schemas:
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self._assert_no_private_fields(schema)
        for capabilities in (federation_model.capabilities(), registry_federation_query.capabilities(), registry_federation_audit.capabilities(), registry_federation_diff.capabilities(), registry_federation_diff_audit.capabilities(), registry_federation_runtime.capabilities()):
            self.assertIn("features", capabilities)
            self._assert_no_private_fields(capabilities)

    def test_cli_parser_and_runtime_command_are_available(self):
        parser = build_parser()
        self.assertIn("registry-federation", parser._subparsers._group_actions[0].choices)
        self.assertIn("registry-federation-query", parser._subparsers._group_actions[0].choices)
        with tempfile.TemporaryDirectory() as temporary:
            ready, replica, _ = self._registries(Path(temporary))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(["registry-federation", "--peer", f"primary={ready}", "--peer", f"replica={replica}", "--federation-id", "cli-fed", "--format", "summary"])
            self.assertEqual(result, 0)
            summary = json.loads(output.getvalue())
            self.assertEqual((summary["state"], summary["decision"], summary["accepted"]), ("consistent", "accept", True))

    def test_release_gate_applies_default_policy_to_clean_and_conflicted_receipts(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean, conflict, _ = self._federations(Path(temporary))
            clean_gate = registry_federation_gate.evaluate_gate(clean)
            conflict_gate = registry_federation_gate.evaluate_gate(conflict)
            self.assertEqual((clean_gate.passed_count, clean_gate.failed_count, clean_gate.accepted), (12, 0, True))
            self.assertEqual((conflict_gate.passed_count, conflict_gate.failed_count, conflict_gate.accepted), (7, 5, False))
            self.assertEqual(registry_federation_gate.gate_from_mapping(clean_gate.to_dict()).content_address, clean_gate.content_address)
            self.assertTrue(registry_federation_gate.gate_csv(clean_gate).startswith("ordinal,check_id,passed"))

    def test_history_is_append_only_and_observatory_aggregates_dispositions(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean, conflict, _ = self._federations(Path(temporary))
            history = registry_federation_history.build_history((clean, conflict), history_id="federation-history")
            self.assertEqual((history.entry_count, history.accepted_count, history.rejected_count, history.review_count), (2, 1, 1, 0))
            destination = Path(temporary) / "history"
            registry_federation_history.write_history(history, destination)
            loaded = registry_federation_history.load_history(destination)
            self.assertEqual(loaded.content_address, history.content_address)
            observatory = registry_federation_observatory.build_observatory((loaded,), observatory_id="federation-observatory")
            self.assertEqual((observatory.history_count, observatory.observation_count, observatory.accepted_count, observatory.rejected_count), (1, 2, 1, 1))
            self.assertEqual(len(registry_federation_observatory.query_observatory(observatory, decision="reject")), 1)
            self.assertEqual(registry_federation_observatory.build_observatory((loaded,)).content_address, observatory.content_address)

    def test_missing_package_and_quorum_deficiency_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self.package_for(root / "first-input", package_id="package-first")
            second = self.package_for(root / "second-input", package_id="package-second")
            first_registry = registry_model.build_registry((first,), registry_id="missing-first")
            second_registry = registry_model.build_registry((second,), registry_id="missing-second")
            first_directory = root / "first-registry"
            second_directory = root / "second-registry"
            registry_model.write_registry(first_registry, first_directory)
            registry_model.write_registry(second_registry, second_directory)
            with self.assertRaises(ValidationError):
                federation_model.build_federation_from_directories((("first", first_directory), ("second", second_directory)), federation_id="invalid-quorum", quorum=3)
            value = federation_model.build_federation_from_directories((("first", first_directory), ("second", second_directory)), federation_id="missing-federation", quorum=2)
            self.assertEqual((value.state, value.decision, value.conflict_count, value.action_count), ("degraded", "review", 2, 2))
            self.assertEqual({conflict.kind for conflict in value.reconciliation.conflicts}, {"missing"})
            self.assertTrue(all(action.kind == "conflict" for action in value.actions))

    def test_corrupted_public_mappings_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            value, _, _ = self._federations(Path(temporary))
            corrupted = value.to_dict()
            corrupted["accepted"] = False
            with self.assertRaises(ValidationError):
                federation_model.federation_from_mapping(corrupted)
            query = registry_federation_query.query_federation(value, resources=("summary",), limit=1)
            corrupted_query = query.to_dict()
            corrupted_query["returned_count"] = 0
            with self.assertRaises(ValidationError):
                registry_federation_query.query_result_from_mapping(corrupted_query)

    def test_http_api_exposes_build_query_audit_gate_and_schema_routes(self):
        with tempfile.TemporaryDirectory() as temporary:
            ready, replica, _ = self._registries(Path(temporary))
            persisted = Path(temporary) / "persisted-federation"
            federation = federation_model.build_federation_from_directories((("primary", ready), ("replica", replica)), federation_id="http-federation")
            federation_model.write_federation(federation, persisted)
            server = create_server("127.0.0.1", 0)
            server_thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}/v1/registry/federation"
            try:
                build_query = urlencode([("peer", f"primary={ready}"), ("peer", f"replica={replica}"), ("federation_id", "http-build"), ("format", "summary")])
                with urlopen(base + "?" + build_query, timeout=10) as response:
                    built = json.loads(response.read().decode())
                self.assertEqual((built["state"], built["decision"], built["accepted"]), ("consistent", "accept", True))
                with urlopen(base + "/query?" + urlencode({"input": str(persisted), "resource": "packages"}), timeout=10) as response:
                    queried = json.loads(response.read().decode())
                self.assertEqual(queried["returned_count"], 2)
                with urlopen(base + "/audit?" + urlencode({"input": str(persisted)}), timeout=10) as response:
                    audited = json.loads(response.read().decode())
                self.assertEqual((audited["passed_count"], audited["failed_count"]), (14, 0))
                with urlopen(base + "/gate?" + urlencode({"input": str(persisted), "format": "summary"}), timeout=10) as response:
                    gated = json.loads(response.read().decode())
                self.assertTrue(gated["accepted"])
                with urlopen(base + "/history/schema", timeout=10) as response:
                    schema = json.loads(response.read().decode())
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            finally:
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=10)


if __name__ == "__main__":
    unittest.main()

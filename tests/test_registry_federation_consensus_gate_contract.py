"""Public contract inventory and safety tests for the release-control plane."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import registry_federation_consensus_gate as gate_model
from glio_noncode import registry_federation_consensus_gate_audit as gate_audit_model
from glio_noncode import registry_federation_consensus_gate_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_gate_history as history_model
from glio_noncode import registry_federation_consensus_gate_history_audit as history_audit_model
from glio_noncode import registry_federation_consensus_gate_observatory as observatory_model
from glio_noncode import registry_federation_consensus_gate_observatory_audit as observatory_audit_model
from glio_noncode import registry_federation_consensus_gate_package as package_model
from glio_noncode import registry_federation_consensus_gate_package_audit as package_audit_model
from glio_noncode import registry_federation_consensus_gate_query as query_model
from glio_noncode import registry_federation_consensus_gate_runtime as runtime_model
from glio_noncode.api import create_server
from glio_noncode.cli import build_parser, main
from glio_noncode.errors import ValidationError
from glio_noncode.public_surface_audit import build_default_public_surface_audit
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class RegistryFederationConsensusGateContractTests(DurableCatalogPromotionPackageFixture):
    """Prevent adapter drift as the gate surface grows."""

    COMMANDS = (
        "registry-federation-consensus-gate",
        "registry-federation-consensus-gate-runtime",
        "registry-federation-consensus-gate-audit",
        "registry-federation-consensus-gate-query",
        "registry-federation-consensus-gate-package",
        "registry-federation-consensus-gate-package-audit",
        "registry-federation-consensus-gate-diff",
        "registry-federation-consensus-gate-diff-audit",
        "registry-federation-consensus-gate-history",
        "registry-federation-consensus-gate-history-audit",
        "registry-federation-consensus-gate-observatory",
        "registry-federation-consensus-gate-observatory-audit",
        "registry-federation-consensus-gate-policy-schema",
        "registry-federation-consensus-gate-check-schema",
        "registry-federation-consensus-gate-schema",
        "registry-federation-consensus-gate-capabilities",
        "registry-federation-consensus-gate-audit-schema",
        "registry-federation-consensus-gate-audit-check-schema",
        "registry-federation-consensus-gate-audit-capabilities",
        "registry-federation-consensus-gate-query-schema",
        "registry-federation-consensus-gate-query-row-schema",
        "registry-federation-consensus-gate-query-result-schema",
        "registry-federation-consensus-gate-query-capabilities",
        "registry-federation-consensus-gate-package-manifest-schema",
        "registry-federation-consensus-gate-package-schema",
        "registry-federation-consensus-gate-package-capabilities",
        "registry-federation-consensus-gate-package-audit-schema",
        "registry-federation-consensus-gate-package-audit-check-schema",
        "registry-federation-consensus-gate-package-audit-capabilities",
        "registry-federation-consensus-gate-runtime-schema",
        "registry-federation-consensus-gate-runtime-capabilities",
        "registry-federation-consensus-gate-diff-schema",
        "registry-federation-consensus-gate-diff-item-schema",
        "registry-federation-consensus-gate-diff-capabilities",
        "registry-federation-consensus-gate-diff-audit-schema",
        "registry-federation-consensus-gate-diff-audit-check-schema",
        "registry-federation-consensus-gate-diff-audit-capabilities",
        "registry-federation-consensus-gate-history-manifest-schema",
        "registry-federation-consensus-gate-history-entry-schema",
        "registry-federation-consensus-gate-history-schema",
        "registry-federation-consensus-gate-history-capabilities",
        "registry-federation-consensus-gate-history-audit-schema",
        "registry-federation-consensus-gate-history-audit-check-schema",
        "registry-federation-consensus-gate-history-audit-capabilities",
        "registry-federation-consensus-gate-observatory-observation-schema",
        "registry-federation-consensus-gate-observatory-schema",
        "registry-federation-consensus-gate-observatory-query-schema",
        "registry-federation-consensus-gate-observatory-query-row-schema",
        "registry-federation-consensus-gate-observatory-query-result-schema",
        "registry-federation-consensus-gate-observatory-capabilities",
        "registry-federation-consensus-gate-observatory-audit-schema",
        "registry-federation-consensus-gate-observatory-audit-check-schema",
        "registry-federation-consensus-gate-observatory-audit-capabilities",
    )

    ROUTES = (
        "/consensus/gate",
        "/consensus/gate/runtime",
        "/consensus/gate/audit",
        "/consensus/gate/query",
        "/consensus/gate/package",
        "/consensus/gate/package/audit",
        "/consensus/gate/diff",
        "/consensus/gate/diff/audit",
        "/consensus/gate/history",
        "/consensus/gate/history/audit",
        "/consensus/gate/observatory",
        "/consensus/gate/observatory/audit",
        "/consensus/gate/policy-schema",
        "/consensus/gate/check-schema",
        "/consensus/gate/schema",
        "/consensus/gate/capabilities",
        "/consensus/gate/audit/schema",
        "/consensus/gate/audit/check-schema",
        "/consensus/gate/audit/capabilities",
        "/consensus/gate/query/schema",
        "/consensus/gate/query/row-schema",
        "/consensus/gate/query/result-schema",
        "/consensus/gate/query/capabilities",
        "/consensus/gate/package/manifest-schema",
        "/consensus/gate/package/schema",
        "/consensus/gate/package/capabilities",
        "/consensus/gate/package/audit/schema",
        "/consensus/gate/package/audit/check-schema",
        "/consensus/gate/package/audit/capabilities",
        "/consensus/gate/runtime/schema",
        "/consensus/gate/runtime/capabilities",
        "/consensus/gate/diff/schema",
        "/consensus/gate/diff/item-schema",
        "/consensus/gate/diff/capabilities",
        "/consensus/gate/diff/audit/schema",
        "/consensus/gate/diff/audit/check-schema",
        "/consensus/gate/diff/audit/capabilities",
        "/consensus/gate/history/manifest-schema",
        "/consensus/gate/history/entry-schema",
        "/consensus/gate/history/schema",
        "/consensus/gate/history/capabilities",
        "/consensus/gate/history/audit/schema",
        "/consensus/gate/history/audit/check-schema",
        "/consensus/gate/history/audit/capabilities",
        "/consensus/gate/observatory/observation-schema",
        "/consensus/gate/observatory/schema",
        "/consensus/gate/observatory/query-schema",
        "/consensus/gate/observatory/query-row-schema",
        "/consensus/gate/observatory/query-result-schema",
        "/consensus/gate/observatory/capabilities",
        "/consensus/gate/observatory/audit/schema",
        "/consensus/gate/observatory/audit/check-schema",
        "/consensus/gate/observatory/audit/capabilities",
    )

    def _registries(self, root: Path) -> tuple[Path, Path, Path]:
        from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model

        ready_package = self.package_for(root / "ready-input", package_id="contract-package")
        held_package = self.package_for(root / "held-input", package_id="contract-package", held=True)
        values = (
            registry_model.build_registry((ready_package,), registry_id="contract-ready"),
            registry_model.build_registry((ready_package,), registry_id="contract-copy"),
            registry_model.build_registry((held_package,), registry_id="contract-held"),
        )
        paths = (root / "ready", root / "copy", root / "held")
        for value, path in zip(values, paths, strict=True):
            registry_model.write_registry(value, path)
        return paths

    def _runtime(self, root: Path, *, divergent: bool = False):
        ready, copy, held = self._registries(root / "registries")
        return runtime_model.run_gate_runtime((("primary", ready), ("archive" if divergent else "replica", held if divergent else copy)), runtime_id="contract-runtime-divergent" if divergent else "contract-runtime", federation_id="contract-federation", consensus_id="contract-consensus-divergent" if divergent else "contract-consensus", gate_id="contract-gate", resources=("summary", "checks", "failures", "evidence"), limit=100)

    def test_parser_registers_every_gate_command(self):
        parser = build_parser()
        choices = parser._subparsers._group_actions[0].choices
        for command in self.COMMANDS:
            self.assertIn(command, choices)
        self.assertEqual(len(set(self.COMMANDS)), len(self.COMMANDS))

    def test_all_capability_payloads_are_json_safe_and_public(self):
        modules = (gate_model, gate_audit_model, query_model, package_model, package_audit_model, runtime_model, diff_model, diff_audit_model, history_model, history_audit_model, observatory_model, observatory_audit_model)
        for module in modules:
            payload = module.capabilities()
            encoded = json.dumps(payload, sort_keys=True)
            decoded = json.loads(encoded)
            self.assertEqual(decoded["version"], payload["version"])
            self.assertEqual(decoded["boundary"], payload["boundary"])
            self.assertEqual(tuple(decoded["features"]), payload["features"])
            self.assertEqual(tuple(decoded["schemas"]), payload["schemas"])
            self.assertNotIn("agent", encoded.lower())
            self.assertNotIn("/", encoded)
            self.assertNotIn("\\", encoded)
            self.assertTrue(payload["version"])
            self.assertTrue(payload["boundary"])
            self.assertTrue(payload["features"])
            self.assertTrue(payload["schemas"])

    def test_public_surface_inventory_contains_gate_schemas_and_capabilities(self):
        value = build_default_public_surface_audit()
        self.assertTrue(value.accepted)
        self.assertEqual(value.surface_count, 881)
        self.assertEqual(value.passed_surface_count, 881)
        self.assertEqual(value.failed_surface_count, 0)
        names = {item.surface_id for item in value.checks}
        self.assertIn("registry-federation-consensus-gate-schema", names)
        self.assertIn("registry-federation-consensus-gate-package-audit-schema", names)
        self.assertIn("registry-federation-consensus-gate-observatory-audit-capabilities", names)

    def test_gate_schema_helpers_are_closed_objects(self):
        schemas = (
            gate_model.policy_schema(),
            gate_model.check_schema(),
            gate_model.gate_schema(),
            gate_audit_model.check_schema(),
            gate_audit_model.audit_schema(),
            query_model.query_schema(),
            query_model.row_schema(),
            query_model.result_schema(),
            package_model.manifest_schema(),
            package_model.package_schema(),
            package_audit_model.check_schema(),
            package_audit_model.audit_schema(),
            runtime_model.runtime_schema(),
            diff_model.item_schema(),
            diff_model.diff_schema(),
            diff_audit_model.check_schema(),
            diff_audit_model.audit_schema(),
            history_model.manifest_schema(),
            history_model.entry_schema(),
            history_model.history_schema(),
            history_audit_model.check_schema(),
            history_audit_model.audit_schema(),
            observatory_model.observation_schema(),
            observatory_model.observatory_schema(),
            observatory_model.query_schema(),
            observatory_model.row_schema(),
            observatory_model.result_schema(),
            observatory_audit_model.check_schema(),
            observatory_audit_model.audit_schema(),
        )
        for schema in schemas:
            self.assertEqual(schema["type"], "object")
            self.assertFalse(schema["additionalProperties"])
            self.assertTrue(schema["required"])
            self.assertEqual(json.loads(json.dumps(schema)), schema)

    def test_gate_schema_enumerations_match_runtime_vocabulary(self):
        gate_schema = gate_model.gate_schema()
        self.assertEqual(tuple(gate_schema["properties"]["state"]["enum"]), gate_model.GATE_STATES)
        self.assertEqual(tuple(gate_schema["properties"]["decision"]["enum"]), gate_model.GATE_DECISIONS)
        policy_schema = gate_model.policy_schema()
        self.assertEqual(policy_schema["properties"]["allowed_states"]["items"]["type"], "string")
        self.assertEqual(policy_schema["properties"]["minimum_quorum"]["minimum"], 1)
        query_schema = query_model.query_schema()
        self.assertEqual(query_schema["properties"]["offset"]["minimum"], 0)
        self.assertEqual(query_schema["properties"]["limit"]["minimum"], 1)
        runtime_schema = runtime_model.runtime_schema()
        self.assertIn("consensus_runtime", runtime_schema["properties"])
        self.assertIn("package_address", runtime_schema["properties"])

    def test_gate_runtime_command_supports_quorum_and_all_query_resources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, copy, _ = self._registries(root / "registries")
            output = root / "runtime.json"
            result = main(["registry-federation-consensus-gate-runtime", "--peer", f"primary={ready}", "--peer", f"replica={copy}", "--quorum", "2", "--resource", "summary", "--resource", "checks", "--resource", "failures", "--resource", "evidence", "--limit", "100", "--format", "json", "--output", str(output)])
            self.assertEqual(result, 0)
            value = runtime_model.runtime_from_mapping(json.loads(output.read_text(encoding="utf-8")))
            self.assertTrue(value.gate.accepted)
            self.assertEqual(value.consensus_runtime.consensus.quorum, 2)
            self.assertEqual(value.query.query.resources, query_model.DEFAULT_RESOURCES)
            self.assertFalse(value.query.truncated)

    def test_gate_runtime_command_rejects_malformed_peer_specification(self):
        result = main(["registry-federation-consensus-gate-runtime", "--peer", "missing-separator", "--format", "summary"])
        self.assertEqual(result, 2)

    def test_invalid_filters_are_rejected_at_cli_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self._runtime(root)
            gate_path = root / "gate.json"
            gate_path.write_text(gate_model.gate_json(runtime.gate), encoding="utf-8")
            with self.assertRaises(SystemExit):
                build_parser().parse_args(["registry-federation-consensus-gate-query", "--input", str(gate_path), "--passed", "not-bool"])
            with self.assertRaises(ValidationError):
                query_model.query_gate(runtime.gate, resources=("checks",), offset=-1)
            with self.assertRaises(ValidationError):
                query_model.query_gate(runtime.gate, resources=("checks",), limit=query_model.MAX_LIMIT + 1)

    def test_rejected_gate_exit_code_does_not_delete_explanation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, _, held = self._registries(root / "registries")
            output = root / "blocked.json"
            result = main(["registry-federation-consensus-gate-runtime", "--peer", f"primary={ready}", "--peer", f"archive={held}", "--format", "json", "--output", str(output)])
            self.assertEqual(result, 2)
            self.assertTrue(output.is_file())
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertFalse(document["gate"]["accepted"])
            self.assertEqual(document["gate"]["decision"], "hold")
            self.assertTrue(document["audit"]["accepted"])
            self.assertTrue(document["query"]["returned_count"] > 0)

    def test_http_schema_inventory_is_available_for_every_route(self):
        server = create_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation"
        try:
            for route in self.ROUTES[12:]:
                with urlopen(base + route, timeout=20) as response:
                    document = json.loads(response.read().decode("utf-8"))
                if route.endswith("capabilities"):
                    self.assertIn("features", document, route)
                else:
                    self.assertIn("type", document, route)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)

    def test_http_bad_input_returns_json_error_instead_of_a_partial_gate(self):
        server = create_server(port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            handle.write("{bad-json")
            input_path = Path(handle.name)
        try:
            request = base + "/consensus/gate?" + urlencode({"input": str(input_path)})
            with self.assertRaises(Exception) as context:
                urlopen(request, timeout=20)
            self.assertIn("HTTP Error 400", str(context.exception))
        finally:
            input_path.unlink(missing_ok=True)
            server.shutdown()
            server.server_close()
            thread.join(timeout=10)

    def test_module_export_lists_include_only_public_contract_names(self):
        expected = {
            gate_model: ("RegistryFederationConsensusGate", "RegistryFederationConsensusGateCheck", "RegistryFederationConsensusGatePolicy", "evaluate_gate", "gate_json", "capabilities"),
            gate_audit_model: ("RegistryFederationConsensusGateAudit", "RegistryFederationConsensusGateAuditFinding", "audit_gate", "audit_json", "capabilities"),
            query_model: ("RegistryFederationConsensusGateQuery", "RegistryFederationConsensusGateQueryResult", "RegistryFederationConsensusGateQueryRow", "query_gate", "query_json", "capabilities"),
            package_model: ("RegistryFederationConsensusGatePackage", "build_package", "load_package", "package_json", "capabilities"),
            runtime_model: ("RegistryFederationConsensusGateRuntime", "run_gate_runtime", "runtime_json", "capabilities"),
            diff_model: ("RegistryFederationConsensusGateDiff", "RegistryFederationConsensusGateDiffItem", "build_diff", "diff_json", "capabilities"),
            history_model: ("RegistryFederationConsensusGateHistory", "RegistryFederationConsensusGateHistoryEntry", "build_history", "history_json", "capabilities"),
            observatory_model: ("RegistryFederationConsensusGateObservatory", "build_observatory", "query_observatory", "observatory_json", "capabilities"),
        }
        for module, names in expected.items():
            exported = set(module.__all__)
            for name in names:
                self.assertIn(name, exported, module.__name__)
                self.assertTrue(hasattr(module, name), (module.__name__, name))
            self.assertTrue(all(isinstance(name, str) for name in exported))

    def test_full_real_gate_graph_can_be_rebuilt_from_each_serialized_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self._runtime(root)
            gate = gate_model.gate_from_mapping(json.loads(gate_model.gate_json(runtime.gate)))
            audit = gate_audit_model.audit_from_mapping(json.loads(gate_audit_model.audit_json(runtime.audit)))
            query = query_model.query_from_mapping(json.loads(query_model.query_json(runtime.query)))
            package = package_model.build_package(runtime.consensus_runtime, gate, audit=audit, query=query)
            package_replay = package_model.package_from_mapping(json.loads(package_model.package_json(package)))
            diff = diff_model.build_diff(gate, gate)
            diff_replay = diff_model.diff_from_mapping(json.loads(diff_model.diff_json(diff)))
            history = history_model.build_history(((gate, audit),), history_id="projection-history")
            history_replay = history_model.history_from_mapping(json.loads(history_model.history_json(history)))
            observatory = observatory_model.build_observatory((history,), observatory_id="projection-observatory")
            observatory_replay = observatory_model.observatory_from_mapping(json.loads(observatory_model.observatory_json(observatory)))
            self.assertEqual(gate.to_dict(), runtime.gate.to_dict())
            self.assertEqual(audit.to_dict(), runtime.audit.to_dict())
            self.assertEqual(query.to_dict(), runtime.query.to_dict())
            self.assertEqual(package_replay.to_dict(), package.to_dict())
            self.assertEqual(diff_replay.to_dict(), diff.to_dict())
            self.assertEqual(history_replay.to_dict(), history.to_dict())
            self.assertEqual(observatory_replay.to_dict(), observatory.to_dict())
            self.assertTrue(package_audit_model.audit_package(package).accepted)
            self.assertTrue(diff_audit_model.audit_diff(diff).accepted)
            self.assertTrue(history_audit_model.audit_history(history).accepted)
            self.assertTrue(observatory_audit_model.audit_observatory(observatory).accepted)


if __name__ == "__main__":
    unittest.main()

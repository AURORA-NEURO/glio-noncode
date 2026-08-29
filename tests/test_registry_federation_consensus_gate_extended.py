"""CLI and HTTP integration tests for release-gate artifacts."""

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
from glio_noncode import registry_federation_consensus_gate_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_history as history_model
from glio_noncode import registry_federation_consensus_gate_observatory as observatory_model
from glio_noncode import registry_federation_consensus_gate_package as package_model
from glio_noncode import registry_federation_consensus_gate_runtime as runtime_model
from glio_noncode import registry_federation_consensus_runtime as consensus_runtime_model
from glio_noncode import registry_federation_consensus as consensus_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class RegistryFederationConsensusGateExtendedTests(DurableCatalogPromotionPackageFixture):
    """Verify all public adapters use the same typed release-control graph."""

    def _registries(self, root: Path) -> tuple[Path, Path, Path]:
        from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model

        ready_package = self.package_for(root / "ready-input", package_id="extended-gate-package")
        held_package = self.package_for(root / "held-input", package_id="extended-gate-package", held=True)
        ready = registry_model.build_registry((ready_package,), registry_id="extended-gate-ready")
        copy = registry_model.build_registry((ready_package,), registry_id="extended-gate-copy")
        held = registry_model.build_registry((held_package,), registry_id="extended-gate-held")
        paths = (root / "ready", root / "copy", root / "held")
        for value, path in zip((ready, copy, held), paths, strict=True):
            registry_model.write_registry(value, path)
        return paths

    def _write_runtime(self, root: Path, *, divergent: bool = False) -> tuple[Path, Path, Path, runtime_model.RegistryFederationConsensusGateRuntime]:
        ready, copy, held = self._registries(root / "registries")
        second = held if divergent else copy
        value = runtime_model.run_gate_runtime((("primary", ready), ("replica", second)), runtime_id="extended-gate-runtime-divergent" if divergent else "extended-gate-runtime", federation_id="extended-gate-federation", consensus_id="extended-gate-consensus-divergent" if divergent else "extended-gate-consensus", gate_id="extended-gate", resources=("summary", "checks", "failures", "evidence"), limit=100)
        runtime_path = root / ("divergent-runtime.json" if divergent else "runtime.json")
        runtime_path.write_text(runtime_model.runtime_json(value), encoding="utf-8")
        return ready, copy, held, value

    def test_cli_runtime_evaluation_and_audit_round_trip(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, copy, held = self._registries(root / "registries")
            runtime_json = root / "runtime.json"
            self.assertEqual(main(["registry-federation-consensus-gate-runtime", "--peer", f"primary={ready}", "--peer", f"replica={copy}", "--federation-id", "cli-gate-federation", "--consensus-id", "cli-gate-consensus", "--runtime-id", "cli-gate-runtime", "--format", "json", "--output", str(runtime_json)]), 0)
            runtime_document = json.loads(runtime_json.read_text(encoding="utf-8"))
            self.assertTrue(runtime_document["gate"]["accepted"])
            self.assertEqual(runtime_document["gate"]["decision"], "promote")
            gate_json = root / "gate.json"
            self.assertEqual(main(["registry-federation-consensus-gate", "--input", str(runtime_json), "--format", "json", "--output", str(gate_json)]), 0)
            gate_document = json.loads(gate_json.read_text(encoding="utf-8"))
            self.assertEqual(gate_document["runtime_id"], "cli-gate-runtime-consensus")
            audit_json = root / "audit.json"
            self.assertEqual(main(["registry-federation-consensus-gate-audit", "--input", str(gate_json), "--format", "json", "--output", str(audit_json)]), 0)
            self.assertTrue(json.loads(audit_json.read_text(encoding="utf-8"))["accepted"])
            query_json = root / "query.json"
            self.assertEqual(main(["registry-federation-consensus-gate-query", "--input", str(gate_json), "--resource", "failures", "--format", "json", "--output", str(query_json)]), 0)
            query_document = json.loads(query_json.read_text(encoding="utf-8"))
            self.assertEqual(query_document["matched_count"], 0)
            self.assertEqual(main(["registry-federation-consensus-gate-capabilities"]), 0)
            self.assertEqual(main(["registry-federation-consensus-gate-query-result-schema"]), 0)

    def test_cli_divergence_returns_nonzero_but_still_writes_explainable_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, _, held = self._registries(root / "registries")
            runtime_json = root / "divergent-runtime.json"
            result = main(["registry-federation-consensus-gate-runtime", "--peer", f"primary={ready}", "--peer", f"archive={held}", "--format", "json", "--output", str(runtime_json)])
            self.assertEqual(result, 2)
            value = json.loads(runtime_json.read_text(encoding="utf-8"))
            self.assertFalse(value["gate"]["accepted"])
            self.assertEqual(value["gate"]["state"], "blocked")
            self.assertEqual(value["gate"]["decision"], "hold")
            self.assertGreater(value["gate"]["failed_count"], 0)
            gate_json = root / "divergent-gate.json"
            self.assertEqual(main(["registry-federation-consensus-gate", "--input", str(runtime_json), "--format", "json", "--output", str(gate_json)]), 2)
            audit_json = root / "divergent-audit.json"
            self.assertEqual(main(["registry-federation-consensus-gate-audit", "--input", str(gate_json), "--format", "json", "--output", str(audit_json)]), 0)
            self.assertTrue(json.loads(audit_json.read_text(encoding="utf-8"))["accepted"])

    def test_cli_package_history_and_observatory_chain(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, copy, held = self._registries(root / "registries")
            clean_runtime = root / "clean-runtime.json"
            divergent_runtime = root / "divergent-runtime.json"
            self.assertEqual(main(["registry-federation-consensus-gate-runtime", "--peer", f"primary={ready}", "--peer", f"replica={copy}", "--format", "json", "--output", str(clean_runtime)]), 0)
            self.assertEqual(main(["registry-federation-consensus-gate-runtime", "--peer", f"primary={ready}", "--peer", f"archive={held}", "--format", "json", "--output", str(divergent_runtime)]), 2)
            clean_package = root / "clean-package"
            divergent_package = root / "divergent-package"
            self.assertEqual(main(["registry-federation-consensus-gate-package", "--input", str(clean_runtime), "--destination", str(clean_package), "--format", "summary"]), 0)
            self.assertEqual(main(["registry-federation-consensus-gate-package", "--input", str(divergent_runtime), "--destination", str(divergent_package), "--format", "summary"]), 0)
            self.assertEqual(tuple(sorted(item.name for item in clean_package.iterdir())), tuple(sorted(package_model.FILES)))
            clean_audit = root / "clean-package-audit.json"
            self.assertEqual(main(["registry-federation-consensus-gate-package-audit", "--input", str(clean_package), "--format", "json", "--output", str(clean_audit)]), 0)
            self.assertTrue(json.loads(clean_audit.read_text(encoding="utf-8"))["accepted"])
            clean_gate = root / "clean-gate.json"
            divergent_gate = root / "divergent-gate.json"
            clean_gate.write_text(json.dumps(json.loads(clean_runtime.read_text(encoding="utf-8"))["gate"]), encoding="utf-8")
            divergent_gate.write_text(json.dumps(json.loads(divergent_runtime.read_text(encoding="utf-8"))["gate"]), encoding="utf-8")
            diff_json = root / "gate-diff.json"
            self.assertEqual(main(["registry-federation-consensus-gate-diff", "--left", str(clean_gate), "--right", str(divergent_gate), "--format", "json", "--output", str(diff_json)]), 0)
            self.assertGreater(json.loads(diff_json.read_text(encoding="utf-8"))["item_count"], 0)
            self.assertEqual(main(["registry-federation-consensus-gate-diff-audit", "--input", str(diff_json), "--format", "summary"]), 0)
            history_dir = root / "history"
            self.assertEqual(main(["registry-federation-consensus-gate-history", "--input", str(clean_package), "--input", str(divergent_package), "--destination", str(history_dir), "--format", "summary"]), 0)
            history_json = root / "history.json"
            history_json.write_text(history_model.history_json(history_model.load_history(history_dir)), encoding="utf-8")
            self.assertEqual(main(["registry-federation-consensus-gate-history-audit", "--input", str(history_json), "--format", "summary"]), 0)
            observatory_json = root / "observatory.json"
            self.assertEqual(main(["registry-federation-consensus-gate-observatory", "--input", str(history_dir), "--format", "json", "--output", str(observatory_json)]), 0)
            self.assertEqual(main(["registry-federation-consensus-gate-observatory-audit", "--input", str(observatory_json), "--format", "summary"]), 0)

    def test_cli_serializers_cover_csv_and_markdown_for_every_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _, _, _, runtime = self._write_runtime(root)
            gate_path = root / "gate.json"
            gate_path.write_text(gate_model.gate_json(runtime.gate), encoding="utf-8")
            self.assertEqual(main(["registry-federation-consensus-gate", "--input", str(root / "runtime.json"), "--format", "markdown"]), 0)
            self.assertEqual(main(["registry-federation-consensus-gate-audit", "--input", str(gate_path), "--format", "csv"]), 0)
            self.assertEqual(main(["registry-federation-consensus-gate-query", "--input", str(gate_path), "--format", "markdown"]), 0)
            package = package_model.build_package(runtime.consensus_runtime, runtime.gate, audit=runtime.audit, query=runtime.query)
            package_path = root / "package"
            package_model.write_package(package, package_path)
            package_json = root / "package.json"
            package_json.write_text(package_model.package_json(package), encoding="utf-8")
            self.assertEqual(main(["registry-federation-consensus-gate-package-audit", "--input", str(package_path), "--format", "markdown"]), 0)
            self.assertEqual(main(["registry-federation-consensus-gate-diff", "--left", str(gate_path), "--right", str(gate_path), "--format", "csv"]), 0)
            history = history_model.build_history(((runtime.gate, runtime.audit),), history_id="cli-history")
            history_path = root / "history"
            history_model.write_history(history, history_path)
            history_json = root / "history.json"
            history_json.write_text(history_model.history_json(history), encoding="utf-8")
            self.assertEqual(main(["registry-federation-consensus-gate-history-audit", "--input", str(history_path), "--format", "markdown"]), 0)
            observatory = observatory_model.build_observatory((history,), observatory_id="cli-observatory")
            observatory_json = root / "observatory.json"
            observatory_json.write_text(observatory_model.observatory_json(observatory), encoding="utf-8")
            self.assertEqual(main(["registry-federation-consensus-gate-observatory-audit", "--input", str(observatory_json), "--format", "csv"]), 0)

    def test_http_runtime_gate_and_query_endpoints_use_downloaded_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, copy, _ = self._registries(root / "registries")
            runtime_json = root / "runtime.json"
            gate_json = root / "gate.json"
            server = create_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation"
            try:
                def get(path: str, values: list[tuple[str, str]]):
                    with urlopen(f"{base}{path}?{urlencode(values, doseq=True)}", timeout=20) as response:
                        return response.status, json.loads(response.read().decode("utf-8"))

                status, runtime = get("/consensus/gate/runtime", [("peer", f"primary={ready}"), ("peer", f"replica={copy}"), ("federation_id", "http-gate-federation"), ("runtime_id", "http-gate-runtime"), ("format", "json")])
                self.assertEqual(status, 200)
                self.assertTrue(runtime["gate"]["accepted"])
                runtime_json.write_text(json.dumps(runtime), encoding="utf-8")
                gate_value = runtime_model.runtime_from_mapping(runtime)
                gate_json.write_text(gate_model.gate_json(gate_value.gate), encoding="utf-8")
                status, gate = get("/consensus/gate", [("input", str(runtime_json)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertEqual((gate["state"], gate["decision"], gate["accepted"]), ("eligible", "promote", True))
                status, query = get("/consensus/gate/query", [("input", str(gate_json)), ("resource", "checks"), ("limit", "2"), ("format", "json")])
                self.assertEqual(status, 200)
                self.assertEqual((query["returned_count"], query["truncated"]), (2, True))
                status, audit = get("/consensus/gate/audit", [("input", str(gate_json)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertTrue(audit["accepted"])
                status, schema = get("/consensus/gate/runtime/schema", [])
                self.assertEqual(status, 200)
                self.assertIn("required", schema)
                status, capabilities = get("/consensus/gate/capabilities", [])
                self.assertEqual(status, 200)
                self.assertIn("features", capabilities)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)

    def test_http_package_diff_history_observatory_and_audits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, copy, held = self._registries(root / "registries")
            clean = runtime_model.run_gate_runtime((("primary", ready), ("replica", copy)), runtime_id="http-clean-runtime", federation_id="http-gate-federation", consensus_id="http-clean-consensus", resources=("summary", "checks", "failures", "evidence"), limit=100)
            divergent = runtime_model.run_gate_runtime((("primary", ready), ("archive", held)), runtime_id="http-divergent-runtime", federation_id="http-gate-federation", consensus_id="http-divergent-consensus", resources=("summary", "checks", "failures", "evidence"), limit=100)
            clean_runtime = root / "clean-runtime.json"
            clean_runtime.write_text(runtime_model.runtime_json(clean), encoding="utf-8")
            divergent_runtime = root / "divergent-runtime.json"
            divergent_runtime.write_text(runtime_model.runtime_json(divergent), encoding="utf-8")
            clean_gate = root / "clean-gate.json"
            clean_gate.write_text(gate_model.gate_json(clean.gate), encoding="utf-8")
            divergent_gate = root / "divergent-gate.json"
            divergent_gate.write_text(gate_model.gate_json(divergent.gate), encoding="utf-8")
            clean_package = package_model.build_package(clean.consensus_runtime, clean.gate, audit=clean.audit, query=clean.query)
            divergent_package = package_model.build_package(divergent.consensus_runtime, divergent.gate, audit=divergent.audit, query=divergent.query)
            clean_package_path, divergent_package_path = root / "clean-package", root / "divergent-package"
            package_model.write_package(clean_package, clean_package_path)
            package_model.write_package(divergent_package, divergent_package_path)
            history = history_model.build_history(((clean.gate, clean.audit), (divergent.gate, divergent.audit)), history_id="http-gate-history")
            history_path = root / "history"
            history_model.write_history(history, history_path)
            observatory = observatory_model.build_observatory((history,), observatory_id="http-gate-observatory")
            observatory_path = root / "observatory.json"
            observatory_path.write_text(observatory_model.observatory_json(observatory), encoding="utf-8")
            diff = diff_model.build_diff(clean.gate, divergent.gate, diff_id="http-gate-diff")
            diff_path = root / "diff.json"
            diff_path.write_text(diff_model.diff_json(diff), encoding="utf-8")
            history_json = root / "history.json"
            history_json.write_text(history_model.history_json(history), encoding="utf-8")
            package_json = root / "package.json"
            package_json.write_text(package_model.package_json(clean_package), encoding="utf-8")
            server = create_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation"
            try:
                def get(path: str, values: list[tuple[str, str]]):
                    with urlopen(f"{base}{path}?{urlencode(values, doseq=True)}", timeout=20) as response:
                        return response.status, json.loads(response.read().decode("utf-8"))

                status, package = get("/consensus/gate/package", [("input", str(clean_runtime)), ("format", "json")])
                self.assertEqual(status, 200)
                self.assertEqual(package["gate"]["content_address"], clean.gate.content_address)
                status, package_audit = get("/consensus/gate/package/audit", [("input", str(package_json)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertTrue(package_audit["accepted"])
                status, diff_value = get("/consensus/gate/diff", [("left", str(clean_gate)), ("right", str(divergent_gate)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertGreater(diff_value["item_count"], 0)
                status, diff_audit = get("/consensus/gate/diff/audit", [("input", str(diff_path)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertTrue(diff_audit["accepted"])
                status, history_value = get("/consensus/gate/history", [("input", str(clean_package_path)), ("input", str(divergent_package_path)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertEqual(history_value["entry_count"], 2)
                status, history_audit = get("/consensus/gate/history/audit", [("input", str(history_json)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertTrue(history_audit["accepted"])
                status, observatory_value = get("/consensus/gate/observatory", [("input", str(history_path)), ("accepted", "false"), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertEqual(observatory_value["returned_count"], 1)
                status, observatory_audit = get("/consensus/gate/observatory/audit", [("input", str(observatory_path)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertTrue(observatory_audit["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)

    def test_consensus_runtime_input_remains_distinct_from_gate_runtime_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, copy, _ = self._registries(root / "registries")
            consensus_runtime = consensus_runtime_model.run_consensus_runtime((("primary", ready), ("replica", copy)), runtime_id="ordinary-consensus-runtime", federation_id="ordinary-federation", consensus_id="ordinary-consensus", resources=("summary",), limit=10)
            self.assertTrue(consensus_runtime.consensus.accepted)
            gate = gate_model.evaluate_gate(consensus_runtime)
            self.assertTrue(gate.accepted)
            self.assertEqual(gate.runtime_address, consensus_runtime.content_address)
            with self.assertRaises(ValidationError):
                runtime_model.runtime_from_mapping(consensus_runtime.to_dict())
            self.assertEqual(consensus_model.consensus_from_mapping(consensus_runtime.consensus.to_dict()).to_dict(), consensus_runtime.consensus.to_dict())


if __name__ == "__main__":
    unittest.main()

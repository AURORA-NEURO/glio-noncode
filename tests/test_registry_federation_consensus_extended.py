"""Integration contracts for the consensus execution family."""

# ruff: noqa: E501, I001

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode import registry_federation_consensus as consensus_model
from glio_noncode import registry_federation_consensus_audit as consensus_audit_model
from glio_noncode import registry_federation_consensus_diff as diff_model
from glio_noncode import registry_federation_consensus_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_history as history_model
from glio_noncode import registry_federation_consensus_observatory as observatory_model
from glio_noncode import registry_federation_consensus_remediation as remediation_model
from glio_noncode import registry_federation_consensus_runtime as runtime_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry as registry_model
from glio_noncode import assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package_registry_federation as federation_model
from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode.errors import ValidationError
from tests.test_assurance_history_series_release_registry_federation_gate_review_decision_ledger_assurance_history_observatory_archive_registry_history_release_evidence_pipeline_observability_bundle_catalog_promotion_gate_release_packet_package import DurableCatalogPromotionPackageFixture


class RegistryFederationConsensusExtendedTests(DurableCatalogPromotionPackageFixture):
    """Exercise composition, persistence, adapters, and corruption behavior."""

    def _registries(self, root: Path):
        ready_package = self.package_for(root / "ready-input", package_id="extended-package")
        held_package = self.package_for(root / "held-input", package_id="extended-package", held=True)
        ready = registry_model.build_registry((ready_package,), registry_id="extended-ready")
        ready_copy = registry_model.build_registry((ready_package,), registry_id="extended-copy")
        held = registry_model.build_registry((held_package,), registry_id="extended-held")
        paths = (root / "ready", root / "copy", root / "held")
        for value, path in zip((ready, ready_copy, held), paths, strict=True):
            registry_model.write_registry(value, path)
        return paths

    def _receipt(self, root: Path, *names: str):
        ready, copy, held = self._registries(root)
        paths = {"primary": ready, "replica": copy, "archive": held}
        peers = tuple((name, paths[name]) for name in names)
        federation = federation_model.build_federation_from_directories(peers, federation_id="extended-federation")
        return consensus_model.build_consensus(federation, consensus_id="extended-consensus")

    def _persist(self, root: Path, value: consensus_model.RegistryFederationConsensus, name: str) -> Path:
        destination = root / name
        consensus_model.write_consensus(value, destination)
        self.assertEqual(consensus_model.load_consensus(destination).to_dict(), value.to_dict())
        return destination

    def test_runtime_composes_all_child_receipts_and_replays(self):
        with tempfile.TemporaryDirectory() as temporary:
            ready, copy, _ = self._registries(Path(temporary))
            value = runtime_model.run_consensus_runtime((("primary", ready), ("replica", copy)), runtime_id="extended-runtime", federation_id="extended-runtime-federation", consensus_id="extended-runtime-consensus", resources=("summary", "packages", "selected"), limit=20)
            self.assertTrue(value.consensus.accepted)
            self.assertTrue(value.audit.accepted)
            self.assertEqual(value.query.query.consensus_address, value.consensus.content_address)
            self.assertEqual(runtime_model.runtime_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertEqual(json.loads(runtime_model.runtime_json(value))["runtime_id"], "extended-runtime")

    def test_runtime_persists_only_the_derived_consensus_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            ready, copy, _ = self._registries(Path(temporary))
            destination = Path(temporary) / "derived-consensus"
            value = runtime_model.run_consensus_runtime((('primary', ready), ('replica', copy)), destination=destination, overwrite=False)
            self.assertTrue(value.persisted)
            self.assertEqual(tuple(sorted(path.name for path in destination.iterdir())), tuple(sorted(consensus_model.FILES)))
            self.assertEqual(consensus_model.load_consensus(destination).content_address, value.consensus.content_address)

    def test_runtime_retains_rejection_without_treating_audit_success_as_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            ready, _, held = self._registries(Path(temporary))
            value = runtime_model.run_consensus_runtime((('primary', ready), ('archive', held)))
            self.assertEqual((value.consensus.state, value.consensus.decision, value.consensus.accepted), ("conflicted", "reject", False))
            self.assertTrue(value.audit.accepted)
            self.assertEqual(value.summary()["audit_failed_count"], 0)

    def test_diff_identifies_package_candidate_and_receipt_transitions(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean = self._receipt(Path(temporary) / "clean", "primary", "replica")
            divergent = self._receipt(Path(temporary) / "divergent", "primary", "archive")
            value = diff_model.build_diff(clean, divergent, diff_id="extended-transition")
            categories = {item.category for item in value.items}
            self.assertEqual((value.changed_package_count, value.changed_candidate_count, value.changed_action_count), (1, 1, 0))
            self.assertIn("receipt", categories)
            self.assertIn("candidate", categories)
            self.assertEqual(diff_model.diff_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertIn("Consensus Receipt Diff", diff_model.render_diff_markdown(value))
            self.assertTrue(diff_model.diff_csv(value).startswith("ordinal,item_id,category"))

    def test_diff_audit_recomputes_every_counter_independently(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean = self._receipt(Path(temporary) / "clean", "primary", "replica")
            divergent = self._receipt(Path(temporary) / "divergent", "primary", "archive")
            value = diff_model.build_diff(clean, divergent)
            audit = diff_audit_model.audit_diff(value)
            self.assertEqual((audit.passed_count, audit.check_count, audit.failed_count, audit.accepted), (12, 12, 0, True))
            self.assertEqual(diff_audit_model.audit_from_mapping(audit.to_dict()).to_dict(), audit.to_dict())
            self.assertTrue(any("field-level" in feature for feature in diff_audit_model.capabilities()["features"]))

    def test_diff_audit_rejects_tampered_counter_and_content_address(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean = self._receipt(Path(temporary) / "clean", "primary", "replica")
            divergent = self._receipt(Path(temporary) / "divergent", "primary", "archive")
            value = diff_model.build_diff(clean, divergent)
            corrupted = value.to_dict()
            corrupted["changed_package_count"] = 0
            with self.assertRaises(ValidationError):
                diff_model.diff_from_mapping(corrupted)
            corrupted = value.to_dict()
            corrupted["content_address"] = value.content_address + "-tampered"
            with self.assertRaises(ValidationError):
                diff_model.diff_from_mapping(corrupted)

    def test_history_is_append_only_ordered_and_atomically_replayable(self):
        with tempfile.TemporaryDirectory() as temporary:
            clean = self._receipt(Path(temporary) / "clean", "primary", "replica")
            divergent = self._receipt(Path(temporary) / "divergent", "primary", "archive")
            clean_audit = consensus_audit_model.audit_consensus(clean)
            divergent_audit = consensus_audit_model.audit_consensus(divergent)
            value = history_model.build_history(((clean, clean_audit), (divergent, divergent_audit)), history_id="extended-history")
            destination = Path(temporary) / "history"
            history_model.write_history(value, destination)
            replayed = history_model.load_history(destination)
            self.assertEqual(replayed.to_dict(), value.to_dict())
            self.assertEqual((value.entry_count, value.accepted_count, value.rejected_count, value.latest_consensus_address), (2, 1, 1, divergent.content_address))
            self.assertEqual(len(history_model.query_history(value, decision="reject")), 1)
            self.assertIn("Consensus History", history_model.render_history_markdown(value))
            self.assertTrue(history_model.history_csv(value).startswith("ordinal,consensus_id"))

    def test_history_manifest_and_projection_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            value = self._receipt(Path(temporary), "primary", "replica")
            audit = consensus_audit_model.audit_consensus(value)
            destination = Path(temporary) / "history"
            history_model.write_history(history_model.build_history(((value, audit),)), destination)
            manifest = destination / history_model.MANIFEST_NAME
            raw = json.loads(manifest.read_text(encoding="utf-8"))
            raw["entry_count"] = 2
            manifest.write_text(json.dumps(raw, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(ValidationError):
                history_model.load_history(destination)

    def test_observatory_aggregates_multiple_histories_and_filters(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clean = self._receipt(root / "clean", "primary", "replica")
            divergent = self._receipt(root / "divergent", "primary", "archive")
            clean_audit = consensus_audit_model.audit_consensus(clean)
            divergent_audit = consensus_audit_model.audit_consensus(divergent)
            first = history_model.build_history(((clean, clean_audit),), history_id="first-history")
            second = history_model.build_history(((divergent, divergent_audit),), history_id="second-history")
            value = observatory_model.build_observatory((first, second), observatory_id="extended-observatory")
            self.assertEqual((value.history_count, value.observation_count, value.accepted_count, value.rejected_count), (2, 2, 1, 1))
            self.assertEqual(len(observatory_model.query_observatory(value, accepted=False)), 1)
            self.assertEqual(observatory_model.observatory_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertIn("Consensus Observatory", observatory_model.render_observatory_markdown(value))

    def test_cli_builds_runtime_diff_history_and_observatory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, copy, held = self._registries(root / "registries")
            clean_dir, divergent_dir = root / "clean-consensus", root / "divergent-consensus"
            clean_json, divergent_json = root / "clean.json", root / "divergent.json"
            self.assertEqual(main(["registry-federation-consensus", "--peer", f"primary={ready}", "--peer", f"replica={copy}", "--destination", str(clean_dir), "--format", "json", "--output", str(clean_json)]), 0)
            self.assertEqual(main(["registry-federation-consensus", "--peer", f"primary={ready}", "--peer", f"archive={held}", "--destination", str(divergent_dir), "--format", "json", "--output", str(divergent_json)]), 2)
            runtime_json = root / "runtime.json"
            self.assertEqual(main(["registry-federation-consensus-runtime", "--peer", f"primary={ready}", "--peer", f"replica={copy}", "--format", "json", "--output", str(runtime_json)]), 0)
            diff_json = root / "diff.json"
            self.assertEqual(main(["registry-federation-consensus-diff", "--left", str(clean_dir), "--right", str(divergent_dir), "--format", "json", "--output", str(diff_json)]), 0)
            self.assertEqual(main(["registry-federation-consensus-diff-audit", "--input", str(diff_json), "--format", "summary"]), 0)
            history_dir = root / "history"
            self.assertEqual(main(["registry-federation-consensus-history", "--input", str(clean_dir), "--input", str(divergent_dir), "--destination", str(history_dir), "--format", "json", "--output", str(root / "history.json")]), 0)
            self.assertEqual(main(["registry-federation-consensus-observatory", "--input", str(history_dir), "--format", "summary"]), 0)
            self.assertEqual(main(["registry-federation-consensus-runtime-capabilities"]), 0)
            self.assertEqual(main(["registry-federation-consensus-observatory-schema"]), 0)
            self.assertTrue(json.loads(runtime_json.read_text(encoding="utf-8"))["consensus"]["accepted"])

    def test_http_exposes_runtime_diff_history_observatory_and_schemas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, copy, held = self._registries(root / "registries")
            clean = consensus_model.build_consensus(federation_model.build_federation_from_directories((("primary", ready), ("replica", copy)), federation_id="http-federation"), consensus_id="http-clean")
            divergent = consensus_model.build_consensus(federation_model.build_federation_from_directories((("primary", ready), ("archive", held)), federation_id="http-federation"), consensus_id="http-divergent")
            clean_dir = self._persist(root, clean, "clean")
            divergent_dir = self._persist(root, divergent, "divergent")
            diff_path = root / "diff.json"
            diff_path.write_text(diff_model.diff_json(diff_model.build_diff(clean, divergent)), encoding="utf-8")
            remediation_path = root / "remediation.json"
            remediation_path.write_text(remediation_model.remediation_json(remediation_model.build_remediation(divergent)), encoding="utf-8")
            history_dir = root / "history"
            history_model.write_history(history_model.build_history(((clean, consensus_audit_model.audit_consensus(clean)), (divergent, consensus_audit_model.audit_consensus(divergent)))), history_dir)
            server = create_server(port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}/v1/registry/federation"
            try:
                def get(path: str, values):
                    with urlopen(f"{base}{path}?{urlencode(values, doseq=True)}", timeout=10) as response:
                        return response.status, json.loads(response.read().decode("utf-8"))

                status, runtime = get("/consensus/runtime", [("peer", f"primary={ready}"), ("peer", f"replica={copy}"), ("federation_id", "http-federation"), ("consensus_id", "http-runtime")])
                self.assertEqual(status, 200)
                self.assertTrue(runtime["accepted"])
                status, diff = get("/consensus/diff", [("left", str(clean_dir)), ("right", str(divergent_dir)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertEqual(diff["changed_package_count"], 1)
                status, audit = get("/consensus/diff/audit", [("input", str(diff_path)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertTrue(audit["accepted"])
                status, history = get("/consensus/history", [("input", str(clean_dir)), ("input", str(divergent_dir)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertEqual(history["entry_count"], 2)
                status, observatory = get("/consensus/observatory", [("input", str(history_dir)), ("decision", "reject"), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertEqual(observatory["returned_count"], 1)
                status, schema = get("/consensus/runtime/schema", [])
                self.assertEqual(status, 200)
                self.assertEqual(schema["required"], list(runtime_model.RegistryFederationConsensusRuntime.FIELDS))
                status, remediation = get("/consensus/remediation", [("input", str(clean_dir)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertTrue(remediation["ready"])
                status, remediation_schema = get("/consensus/remediation/query/result-schema", [])
                self.assertEqual(status, 200)
                self.assertIn("returned_count", remediation_schema["properties"])
                status, package = get("/consensus/remediation/package", [("input", str(remediation_path)), ("format", "summary")])
                self.assertEqual(status, 200)
                self.assertEqual(package["blocking_count"], 2)
            finally:
                server.shutdown()
                thread.join(timeout=10)
                server.server_close()


if __name__ == "__main__":
    unittest.main()

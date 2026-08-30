"""Integration tests for certificate projections, CLI, HTTP, and package replay."""

# ruff: noqa: E501, I001

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from glio_noncode.api import create_server
from glio_noncode.cli import main
from glio_noncode import registry_federation_consensus_gate_certificate as certificate_model
from glio_noncode import registry_federation_consensus_gate_certificate_audit as certificate_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_diff as diff_model
from glio_noncode import registry_federation_consensus_gate_certificate_diff_audit as diff_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_history as history_model
from glio_noncode import registry_federation_consensus_gate_certificate_history_audit as history_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_package as package_model
from glio_noncode import registry_federation_consensus_gate_certificate_package_audit as package_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_query as query_model
from glio_noncode import registry_federation_consensus_gate_certificate_query_audit as query_audit_model
from glio_noncode import registry_federation_consensus_gate_certificate_runtime as runtime_model
from glio_noncode.errors import ValidationError
from tests.test_registry_federation_consensus_gate_certificate import CertificateFixture


class CertificateExtendedTests(CertificateFixture):
    def test_query_exposes_complete_projection_set_and_conserves_page_offsets(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            all_rows = query_model.query_certificate(certificate, resources=query_model.DEFAULT_RESOURCES, limit=100)
            self.assertEqual(all_rows.total_count, 26)
            self.assertEqual(all_rows.matched_count, 26)
            self.assertEqual(all_rows.returned_count, 26)
            self.assertFalse(all_rows.truncated)
            self.assertEqual(tuple(row.ordinal for row in all_rows.rows), tuple(range(1, 27)))
            self.assertEqual(query_model.query_from_mapping(all_rows.to_dict()).to_dict(), all_rows.to_dict())
            first = query_model.query_certificate(certificate, resources=("checks",), offset=0, limit=4)
            second = query_model.query_certificate(certificate, resources=("checks",), offset=4, limit=4)
            self.assertEqual(first.returned_count, 4)
            self.assertTrue(first.truncated)
            self.assertEqual(first.next_offset, 4)
            self.assertEqual(tuple(row.ordinal for row in first.rows), (1, 2, 3, 4))
            self.assertEqual(tuple(row.ordinal for row in second.rows), (5, 6, 7, 8))

    def test_query_filters_checks_failures_state_decision_and_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            checks = query_model.query_certificate(certificate, resources=("checks",), check_id="gate-accepted")
            self.assertEqual(checks.matched_count, 1)
            self.assertEqual(checks.rows[0].check_id, "gate-accepted")
            passed = query_model.query_certificate(certificate, resources=("checks",), passed=True)
            self.assertEqual(passed.matched_count, 19)
            failures = query_model.query_certificate(certificate, resources=("failures",), passed=False)
            self.assertEqual(failures.matched_count, 0)
            selected = query_model.query_certificate(certificate, resources=("summary",), state="issued", decision="promote")
            self.assertEqual(selected.matched_count, 1)
            policy = query_model.query_certificate(certificate, resources=("policy",))
            self.assertEqual(policy.matched_count, 1)
            self.assertEqual(policy.rows[0].row_id, certificate.policy.policy_id)

    def test_query_rejects_invalid_resources_filters_and_pages(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            with self.assertRaises(ValidationError):
                query_model.query_certificate(certificate, resources=("not-a-resource",))
            with self.assertRaises(ValidationError):
                query_model.query_certificate(certificate, check_id="not-a-check")
            with self.assertRaises(ValidationError):
                query_model.query_certificate(certificate, state="not-a-state")
            with self.assertRaises(ValidationError):
                query_model.query_certificate(certificate, offset=-1)
            with self.assertRaises(ValidationError):
                query_model.query_certificate(certificate, limit=0)

    def test_query_audit_accepts_full_and_paginated_certificate_views(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            full = query_model.query_certificate(certificate, resources=query_model.DEFAULT_RESOURCES, limit=100)
            paged = query_model.query_certificate(certificate, resources=("checks",), check_id="gate-accepted", limit=1)
            for result in (full, paged):
                value = query_audit_model.audit_query(result)
                self.assertTrue(value.accepted)
                self.assertEqual((value.check_count, value.passed_count, value.failed_count), (11, 11, 0))
                self.assertEqual(value.result_address, result.content_address)
                self.assertEqual(query_audit_model.audit_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            self.assertIn("pagination verification", query_audit_model.capabilities()["features"])

    def test_query_audit_rejects_modified_counters_and_finding_addresses(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            result = query_model.query_certificate(certificate, resources=("checks",), limit=3)
            audit = query_audit_model.audit_query(result)
            document = audit.to_dict()
            document["failed_count"] = 1
            with self.assertRaises(ValidationError):
                query_audit_model.audit_from_mapping(document)
            finding = dict(audit.checks[0].to_dict())
            finding["content_address"] = query_audit_model.CHECK_PREFIX + ":tampered"
            with self.assertRaises(ValidationError):
                query_audit_model.RegistryFederationConsensusGateCertificateQueryAuditFinding.from_mapping(finding)

    def test_cli_query_audit_round_trips_serialized_view(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            certificate = self.certificate_runtime(root, "primary", "replica").certificate
            query = query_model.query_certificate(certificate, resources=("checks",), limit=3)
            query_path = root / "query.json"
            audit_path = root / "audit.json"
            query_path.write_text(query_model.query_json(query), encoding="utf-8")
            self.assertEqual(main(["registry-federation-consensus-gate-certificate-query-audit", "--input", str(query_path), "--format", "json", "--output", str(audit_path)]), 0)
            self.assertTrue(json.loads(audit_path.read_text(encoding="utf-8"))["accepted"])

    def test_package_contains_nine_exact_members_and_replays_nested_certificate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.certificate_runtime(root, "primary", "replica")
            package = package_model.build_package(runtime.gate_runtime, runtime.certificate, gate_audit=runtime.gate_runtime.audit, gate_query=runtime.gate_runtime.query, certificate_audit=runtime.certificate_audit, certificate_query=runtime.certificate_query, package_id="certificate-handoff")
            destination = root / "package"
            package_model.write_package(package, destination)
            self.assertEqual(tuple(sorted(item.name for item in destination.iterdir())), tuple(sorted(package_model.FILES)))
            self.assertEqual(len(package_model.FILES), 9)
            replayed = package_model.load_package(destination)
            self.assertEqual(replayed.to_dict(), package.to_dict())
            self.assertEqual(replayed.certificate.content_address, runtime.certificate.content_address)
            self.assertEqual(replayed.runtime.content_address, runtime.gate_runtime.content_address)
            self.assertEqual(replayed.certificate_audit.content_address, runtime.certificate_audit.content_address)
            self.assertEqual(replayed.certificate_query.content_address, runtime.certificate_query.content_address)
            self.assertEqual(package_model.package_from_mapping(package.to_dict()).to_dict(), package.to_dict())
            self.assertEqual(json.loads(package_model.package_json(package))["package_id"], "certificate-handoff")

    def test_package_manifest_and_member_bytes_are_canonical(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self.certificate_runtime(Path(temporary), "primary", "replica")
            package = package_model.build_package(runtime.gate_runtime, runtime.certificate, gate_audit=runtime.gate_runtime.audit, gate_query=runtime.gate_runtime.query, certificate_audit=runtime.certificate_audit, certificate_query=runtime.certificate_query)
            members = package_model.package_bytes(package)
            manifest = json.loads(members[package_model.MANIFEST_NAME])
            self.assertEqual(tuple(manifest["files"]), package_model.FILES)
            self.assertEqual(manifest["package_address"], package.content_address)
            self.assertEqual(members[package_model.PACKAGE_NAME], package_model.package_json(package).encode())
            self.assertEqual(set(members), set(package_model.FILES))
            self.assertEqual(set(package_model.manifest_schema()["properties"]), {"version", "boundary", "package_id", "files", "package_address", "certificate_address", "runtime_address", "gate_address", "gate_audit_address", "gate_query_address", "certificate_audit_address", "certificate_query_address", "manifest_address"})
            self.assertIn("nine-file certificate handoff", package_model.capabilities()["features"])

    def test_package_audit_recomputes_all_eighteen_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self.certificate_runtime(Path(temporary), "primary", "replica")
            package = package_model.build_package(runtime.gate_runtime, runtime.certificate, gate_audit=runtime.gate_runtime.audit, gate_query=runtime.gate_runtime.query, certificate_audit=runtime.certificate_audit, certificate_query=runtime.certificate_query)
            value = package_audit_model.audit_package(package)
            self.assertTrue(value.accepted)
            self.assertEqual((value.check_count, value.passed_count, value.failed_count), (18, 18, 0))
            self.assertEqual(value.package_address, package.content_address)
            self.assertEqual(package_audit_model.audit_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            corrupted = value.to_dict()
            corrupted["passed_count"] = 1
            with self.assertRaises(ValidationError):
                package_audit_model.audit_from_mapping(corrupted)

    def test_package_loader_rejects_projection_tamper_and_unknown_members(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.certificate_runtime(root, "primary", "replica")
            package = package_model.build_package(runtime.gate_runtime, runtime.certificate, gate_audit=runtime.gate_runtime.audit, gate_query=runtime.gate_runtime.query, certificate_audit=runtime.certificate_audit, certificate_query=runtime.certificate_query)
            destination = root / "package"
            package_model.write_package(package, destination)
            path = destination / package_model.CERTIFICATE_NAME
            document = json.loads(path.read_text(encoding="utf-8"))
            document["accepted"] = False
            path.write_text(json.dumps(document, separators=(",", ":")), encoding="utf-8")
            with self.assertRaises(ValidationError):
                package_model.load_package(destination)
            package_model.write_package(package, destination, overwrite=True)
            (destination / "unexpected.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ValidationError):
                package_model.load_package(destination)

    def test_diff_reports_policy_transition_and_independent_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = self.gate_runtime(Path(temporary), "primary", "replica")
            clean = certificate_model.evaluate_certificate(runtime)
            strict_pending = certificate_model.RegistryFederationConsensusGateCertificatePolicy("strict-transition", ("eligible",), ("promote",), 1, runtime.gate.check_count + 1, True, True, True, False, certificate_model.POLICY_PREFIX + ":pending")
            strict_policy = certificate_model.RegistryFederationConsensusGateCertificatePolicy(strict_pending.policy_id, strict_pending.allowed_gate_states, strict_pending.allowed_gate_decisions, strict_pending.minimum_check_count, strict_pending.minimum_passed_count, strict_pending.require_gate_acceptance, strict_pending.require_gate_audit, strict_pending.require_query_complete, strict_pending.require_package, certificate_model.address_policy(strict_pending))
            held = certificate_model.evaluate_certificate(runtime, policy=strict_policy, certificate_id="strict-transition-certificate")
            value = diff_model.build_diff(clean, held, diff_id="certificate-transition")
            self.assertEqual((value.left_accepted, value.right_accepted), (True, False))
            self.assertEqual(value.direction, "regressed")
            self.assertGreater(value.changed_count, 0)
            self.assertEqual(value.changed_count + value.unchanged_count, value.item_count)
            self.assertEqual(diff_model.diff_from_mapping(value.to_dict()).to_dict(), value.to_dict())
            audit = diff_audit_model.audit_diff(value)
            self.assertTrue(audit.accepted)
            self.assertEqual((audit.check_count, audit.passed_count), (14, 14))
            self.assertEqual(audit.diff_address, value.content_address)

    def test_diff_identical_certificates_are_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            certificate = self.certificate_runtime(Path(temporary), "primary", "replica").certificate
            value = diff_model.build_diff(certificate, certificate, diff_id="same-certificate")
            self.assertEqual(value.direction, "unchanged")
            self.assertEqual(value.changed_count, 0)
            self.assertEqual(value.unchanged_count, value.item_count)
            self.assertTrue(diff_audit_model.audit_diff(value).accepted)

    def test_cli_certificate_schema_and_runtime_exports(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.gate_runtime(root, "primary", "replica")
            runtime_path = root / "gate-runtime.json"
            runtime_path.write_text(json.dumps(runtime.to_dict()), encoding="utf-8")
            schema_path = root / "certificate-schema.json"
            self.assertEqual(main(["registry-federation-consensus-gate-certificate-schema", "--output", str(schema_path)]), 0)
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self.assertFalse(schema["additionalProperties"])
            output_path = root / "certificate.json"
            self.assertEqual(main(["registry-federation-consensus-gate-certificate", "--input", str(runtime_path), "--format", "json", "--output", str(output_path)]), 0)
            certificate = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(certificate["certificate_state"], "issued")
            self.assertEqual(certificate["certificate_decision"], "promote")
            summary_path = root / "summary.json"
            self.assertEqual(main(["registry-federation-consensus-gate-certificate-query", "--input", str(output_path), "--resource", "failures", "--output", str(summary_path)]), 0)
            self.assertEqual(json.loads(summary_path.read_text(encoding="utf-8"))["matched_count"], 0)

    def test_api_certificate_routes_return_schemas_and_audits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.gate_runtime(root, "primary", "replica")
            runtime_path = root / "gate-runtime.json"
            runtime_path.write_text(json.dumps(runtime.to_dict()), encoding="utf-8")
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                base = f"http://{host}:{port}/v1/registry/federation/consensus/gate"
                schema = json.loads(urlopen(base + "/certificate/schema", timeout=10).read().decode())
                self.assertFalse(schema["additionalProperties"])
                capabilities = json.loads(urlopen(base + "/certificate/capabilities", timeout=10).read().decode())
                self.assertIn("issued", capabilities["certificate_states"])
                query = urlencode({"input": str(runtime_path), "resource": "checks", "limit": "3", "format": "json"})
                certificate_query = json.loads(urlopen(base + "/certificate/query?" + query, timeout=10).read().decode())
                self.assertEqual(certificate_query["returned_count"], 3)
                audit = json.loads(urlopen(base + "/certificate/audit?input=" + str(runtime_path), timeout=10).read().decode())
                self.assertTrue(audit["accepted"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)

    def test_api_runtime_route_can_build_and_persist_certificate_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ready, copy, _ = self.registries(root / "registries")
            destination = root / "api-package"
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                base = f"http://{host}:{port}/v1/registry/federation/consensus/gate/certificate/runtime"
                query = urlencode({"peer": ["primary=" + str(ready), "replica=" + str(copy)], "destination": str(destination), "format": "json", "limit": "100"}, doseq=True)
                body = json.loads(urlopen(base + "?" + query, timeout=30).read().decode())
                self.assertTrue(body["certificate"]["accepted"])
                self.assertTrue(body["persisted"])
                self.assertTrue(destination.is_dir())
                loaded = package_model.load_package(destination)
                self.assertEqual(loaded.content_address, body["package_address"])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)

    def test_api_returns_422_for_a_policy_withheld_certificate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = self.gate_runtime(root, "primary", "held")
            runtime_path = root / "held-runtime.json"
            runtime_path.write_text(json.dumps(runtime.to_dict()), encoding="utf-8")
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                query = urlencode({"input": str(runtime_path), "format": "summary"})
                with self.assertRaises(HTTPError) as context:
                    urlopen(f"http://{host}:{port}/v1/registry/federation/consensus/gate/certificate?{query}", timeout=10)
                self.assertEqual(context.exception.code, 422)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)

    def test_api_history_route_persists_and_audits_issued_and_withheld_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            issued = self.certificate_runtime(root / "issued", "primary", "replica")
            withheld = self.certificate_runtime(root / "withheld", "primary", "held")
            issued_package = package_model.build_package(issued.gate_runtime, issued.certificate, gate_audit=issued.gate_runtime.audit, gate_query=issued.gate_runtime.query, certificate_audit=issued.certificate_audit, certificate_query=issued.certificate_query)
            withheld_package = package_model.build_package(withheld.gate_runtime, withheld.certificate, gate_audit=withheld.gate_runtime.audit, gate_query=withheld.gate_runtime.query, certificate_audit=withheld.certificate_audit, certificate_query=withheld.certificate_query)
            issued_dir = root / "issued-package"
            withheld_dir = root / "withheld-package"
            package_model.write_package(issued_package, issued_dir)
            package_model.write_package(withheld_package, withheld_dir)
            history_dir = root / "history"
            server = create_server("127.0.0.1", 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                base = f"http://{host}:{port}/v1/registry/federation/consensus/gate/certificate"
                query = urlencode({"input": [str(issued_dir), str(withheld_dir)], "destination": str(history_dir), "history_id": "api-history", "format": "json"}, doseq=True)
                response = json.loads(urlopen(base + "/history?" + query, timeout=30).read().decode())
                self.assertEqual(response["entry_count"], 2)
                self.assertEqual((response["issued_count"], response["withheld_count"]), (1, 1))
                self.assertTrue(history_dir.is_dir())
                schema = json.loads(urlopen(base + "/history/schema", timeout=10).read().decode())
                self.assertFalse(schema["additionalProperties"])
                audit = json.loads(urlopen(base + "/history/audit?" + urlencode({"input": str(history_dir), "format": "json"}), timeout=10).read().decode())
                self.assertTrue(audit["accepted"])
                self.assertEqual(audit["passed_count"], len(history_audit_model.CHECK_IDS))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=10)


if __name__ == "__main__":
    unittest.main()
